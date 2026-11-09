# Schema: `read` module — `mangas`, `manga_sections`, `manga_pages`, `manga_page_versions`, `library_assets` + `manga` storage bucket

> Per-module schema doc — the database half of the manga-reader feature (the
> `read` module; **"Lector"** is the user-facing display name only). Mirrors how the
> chat module documents its schema. Read `../supabase_guidelines.md` first for the
> migration workflow, and its *Storage Buckets* section for how buckets are managed.
> The backend service/repository that read/write these tables are documented in
> `backend/docs/modules/read.md`; the frontend in `frontend/docs/modules/read.md`.

## Status

**Migrations generated, not yet pushed.** Source fragments live at
`supabase/schema/read/{mangas,manga_sections,manga_pages,library_assets,storage_manga}.sql`.
The generator has stamped them into flat migrations, applied in file order:
`add_mangas` → `add_manga_sections` → `add_manga_pages` → `add_manga_storage` →
`add_library_assets` (the first three FK into the previous, storage third; `library_assets`
FKs only `auth.users`, so it has no ordering dependency on the others — it was simply
generated last) → `add_library_assets_position` (adds `position`, hand-written ALTER +
backfill) → `alter_library_assets_storage_path` (loosens `storage_path` to nullable, for
the streaming-collect reservation described below) → `add_manga_page_versions`
(stamped with `gen_migration.py`, applied to the local database). Next step: `supabase db push`.

## Why these are SQL migrations (not SQLAlchemy)

Every table foreign-keys into Supabase's internal `auth.users` (directly or via a
parent) and uses Row Level Security; the storage bucket and its policies live in
Supabase's internal `storage` schema. None of this is expressible by SQLAlchemy
`create_all`. So tables + FKs + RLS + the bucket live in migrations, and the backend
keeps only an ORM read/write view in `backend/app/modules/read/models.py`.

## Data shape

```
mangas            one manga series, owned by a user
  └─ manga_sections   a volume OR a chapter (kind discriminator)
       └─ manga_pages     one image per section, ordered by `position`
            └─ manga_page_versions   accepted upscaled / translated ('en') image of a page

library_assets    a user's *unassigned* image pool — scraped or uploaded,
                  not yet organized into any manga (no manga link)
```

A manga is organized by **either** volumes **or** chapters — the frontend's two tabs
are just `manga_sections` filtered by `kind`. (Not nested: a section is a volume or a
chapter, never a volume *containing* chapters. If true hierarchy is wanted later, add
a nullable `parent_id` to `manga_sections` in a new migration.)

`library_assets` sits **beside** that tree, not inside it: it's a per-user staging
**pool** for images the user has scraped (possibly across many sessions) or uploaded
but not yet placed into a series. Organizing a pool image into a manga creates a
`manga_pages` row from it and removes the pool row (see *`library_assets`* below) — so
an asset lives in exactly one place at a time: the pool, or a section.

## `mangas`

One row per series. The library grid lists these newest-first.

```sql
create table if not exists public.mangas (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        not null references auth.users (id) on delete cascade,
  title       text        not null,
  description text,
  cover_path  text,                 -- object path of the cover in the `manga` bucket (nullable)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Library query: a user's series, newest activity first.
create index if not exists mangas_user_updated_idx
  on public.mangas (user_id, updated_at desc);

alter table public.mangas enable row level security;

create policy "Mangas are readable by the owner"
  on public.mangas for select using (auth.uid() = user_id);
create policy "Owner can insert mangas"
  on public.mangas for insert with check (auth.uid() = user_id);
create policy "Owner can update their mangas"
  on public.mangas for update using (auth.uid() = user_id);
create policy "Owner can delete their mangas"
  on public.mangas for delete using (auth.uid() = user_id);
```

## `manga_sections`

One row per volume or chapter. The **Volumes** tab is `where kind='volume'`, the
**Chapters** tab is `where kind='chapter'`.

```sql
create table if not exists public.manga_sections (
  id         uuid        primary key default gen_random_uuid(),
  manga_id   uuid        not null references public.mangas (id) on delete cascade,
  kind       text        not null check (kind in ('volume', 'chapter')),
  number     numeric,              -- reading-order key within a kind (1, 1.5, 2 …); nullable for one-offs
  title      text,                 -- optional label ("Vol. 1: The Beginning")
  cover_path text,                 -- optional section cover in the `manga` bucket
  created_at timestamptz not null default now()
);

-- Tab query: a manga's sections of one kind, in reading order.
create index if not exists manga_sections_manga_kind_number_idx
  on public.manga_sections (manga_id, kind, number);

-- RLS: a section is visible/editable only through an owned manga.
alter table public.manga_sections enable row level security;

create policy "Sections readable through an owned manga"
  on public.manga_sections for select using (
    exists (select 1 from public.mangas m
            where m.id = manga_sections.manga_id and m.user_id = auth.uid())
  );
create policy "Insert sections into an owned manga"
  on public.manga_sections for insert with check (
    exists (select 1 from public.mangas m
            where m.id = manga_sections.manga_id and m.user_id = auth.uid())
  );
create policy "Update sections through an owned manga"
  on public.manga_sections for update using (
    exists (select 1 from public.mangas m
            where m.id = manga_sections.manga_id and m.user_id = auth.uid())
  );
create policy "Delete sections through an owned manga"
  on public.manga_sections for delete using (
    exists (select 1 from public.mangas m
            where m.id = manga_sections.manga_id and m.user_id = auth.uid())
  );
```

## `manga_pages`

One row per image, in `position` order within its section. `width`/`height` are the
intrinsic pixel dimensions so the reader can reserve an aspect-ratio box (no layout
shift while the image loads).

```sql
create table if not exists public.manga_pages (
  id           uuid        primary key default gen_random_uuid(),
  section_id   uuid        not null references public.manga_sections (id) on delete cascade,
  storage_path text        not null,   -- object path in the `manga` bucket
  position     integer     not null,   -- 0-based order within the section
  width        integer,                -- intrinsic px (nullable until known)
  height       integer,
  created_at   timestamptz not null default now()
);

-- Loading a section: its pages in order. Unique so a (section, position) pair can't dup.
create unique index if not exists manga_pages_section_position_idx
  on public.manga_pages (section_id, position);

-- RLS: a page is visible/editable only through an owned manga (join up via the section).
alter table public.manga_pages enable row level security;

create policy "Pages readable through an owned manga"
  on public.manga_pages for select using (
    exists (
      select 1 from public.manga_sections s
      join public.mangas m on m.id = s.manga_id
      where s.id = manga_pages.section_id and m.user_id = auth.uid()
    )
  );
create policy "Insert pages through an owned manga"
  on public.manga_pages for insert with check (
    exists (
      select 1 from public.manga_sections s
      join public.mangas m on m.id = s.manga_id
      where s.id = manga_pages.section_id and m.user_id = auth.uid()
    )
  );
create policy "Delete pages through an owned manga"
  on public.manga_pages for delete using (
    exists (
      select 1 from public.manga_sections s
      join public.mangas m on m.id = s.manga_id
      where s.id = manga_pages.section_id and m.user_id = auth.uid()
    )
  );
```

> Reorder = rewrite `position` for the affected rows (the backend does this in one
> transaction). No update policy on pages beyond that is needed yet.

## `manga_page_versions`

An accepted derived version of a page: its **upscaled** image and/or its **translated**
(`language = 'en'`) image. At most one row per `(page_id, kind, language)`. `language` is
null for `upscaled` and required for `translated` (enforced by a check). `reference_page_id`
is the page used as the translation reference; it is set null if that page is deleted.

```sql
create table if not exists public.manga_page_versions (
  id                uuid        primary key default gen_random_uuid(),
  page_id           uuid        not null references public.manga_pages (id) on delete cascade,
  kind              text        not null check (kind in ('upscaled', 'translated')),
  language          text,                  -- null for upscaled; 'en' for translated
  storage_path      text        not null,  -- object path in the `manga` bucket
  width             integer,
  height            integer,
  reference_page_id uuid        references public.manga_pages (id) on delete set null,
  created_at        timestamptz not null default now(),
  check ((kind = 'upscaled') = (language is null))
);

create unique index if not exists manga_page_versions_page_kind_lang_idx
  on public.manga_page_versions (page_id, kind, coalesce(language, ''));
create index if not exists manga_page_versions_page_idx
  on public.manga_page_versions (page_id);
```

RLS is enabled with select/insert/update/delete policies that join
`manga_pages -> manga_sections -> mangas` on `auth.uid()` (same shape as `manga_pages`).

## `library_assets`

One row per **unassigned** image in a user's pool — an image that has been scraped or
uploaded but not yet organized into a manga. This is the "loose images with no manga"
you browse in the library pool; when you add one to a series it becomes a `manga_page`
and leaves the pool (see *Notes → The pool lifecycle*).

Unlike `manga_sections`/`manga_pages`, a pool asset has **no parent manga to derive
ownership through**, so it carries `user_id` directly and its RLS is keyed on that
(the same shape as `mangas`).

```sql
create table if not exists public.library_assets (
  id           uuid        primary key default gen_random_uuid(),
  user_id      uuid        not null references auth.users (id) on delete cascade,
  storage_path text,                   -- object path in the `manga` bucket; NULL while a
                                        -- reserved slot's download/upload is still in flight
  source_url   text,                   -- where it was scraped from; NULL for direct uploads
  position     integer     not null,   -- 0-based collect order (assigned per user, not per-request-completion order)
  width        integer,                -- intrinsic px (nullable until known)
  height       integer,
  created_at   timestamptz not null default now()
);

-- Pool view: a user's unassigned images, in collect order (a collection queue —
-- freshly collected images land at the bottom). `position` (not `created_at`) is
-- authoritative: a batch's images can finish downloading/uploading out of order,
-- but `position` is assigned from the batch's original order, not completion time.
create unique index if not exists library_assets_user_position_idx
  on public.library_assets (user_id, position);

-- RLS: owner-keyed directly on user_id (no manga to join through).
alter table public.library_assets enable row level security;

create policy "Library assets are readable by the owner"
  on public.library_assets for select using (auth.uid() = user_id);
create policy "Owner can insert library assets"
  on public.library_assets for insert with check (auth.uid() = user_id);
create policy "Owner can delete their library assets"
  on public.library_assets for delete using (auth.uid() = user_id);
```

> No update policy for regular (user-scoped) access — the backend connects via a
> privileged role that bypasses RLS regardless (ownership is enforced in Python, not
> SQL, per this module's stated pattern), and it's the only thing that ever writes
> to this table. It *does* update rows in place now: a streaming collect reserves a
> placeholder row (`storage_path = NULL`, `position` fixed) before that item's
> download/upload starts, then fills it in via `UPDATE` once the work finishes — see
> `backend/docs/modules/read.md` → `services/library_stream.py`.

## `manga` storage bucket

A **private** bucket holds every page image and cover. Object paths are prefixed by
owner so one RLS rule on `storage.objects` enforces ownership:

```
manga/{user_id}/{manga_id}/{section_id}/{position}-{uuid}.{ext}   ← a page in a series
manga/{user_id}/_pool/{uuid}.{ext}                               ← an unassigned pool asset
manga/{user_id}/_preview/{uuid}.{ext}                            ← a not-yet-accepted upscale/translate preview
        ▲ first path segment = owner (the only segment RLS checks)
```

Because the storage policy keys **only** on the first segment (`{user_id}`), a pool
object at `{user_id}/_pool/…` is already owner-scoped, and — importantly — a
`manga_page` may reference that same `_pool/` path unchanged. So organizing a pool
asset into a series needs **no byte move**: only the metadata row changes (pool → page).
Moving the object to a `{manga_id}/{section_id}/…` path is optional tidiness (a Storage
copy + delete), not a correctness requirement.

```sql
-- Private bucket (public = false → no open URLs; reads go through signed URLs).
insert into storage.buckets (id, name, public)
values ('manga', 'manga', false)
on conflict (id) do nothing;

-- A user may only touch files under their own {user_id}/ prefix.
-- storage.foldername(name) returns text[]; auth.uid() is uuid → cast to text.
create policy "Read own manga files"
  on storage.objects for select
  using (bucket_id = 'manga' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "Upload own manga files"
  on storage.objects for insert
  with check (bucket_id = 'manga' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "Delete own manga files"
  on storage.objects for delete
  using (bucket_id = 'manga' and (storage.foldername(name))[1] = auth.uid()::text);
```

## Notes

- **Two RLS roles, and one of them is load-bearing.**
  - *Table* RLS (`mangas`/`manga_sections`/`manga_pages`) is **defense-in-depth only**,
    exactly as for chat: the backend connects via `asyncpg` as a privileged role where
    `auth.uid()` is not populated, so these policies don't filter backend queries —
    ownership for backend reads/writes is enforced in the service/repository
    (`WHERE user_id = <current user>`).
  - *Storage* RLS (`storage.objects`) is **actively enforced**, because the **frontend
    accesses Storage directly** with the user's session token (upload local files,
    fetch signed URLs) — it never goes through the backend for bytes. That policy is
    the real ownership gate on the files, not just defense-in-depth.
- **Service-role bypass.** The backend's scrape-import uploads use the Supabase
  **service-role key**, which bypasses Storage RLS (trusted server), writing under the
  user's `{user_id}/` prefix on their behalf. That key is server-only — never shipped
  to the frontend.
- **Cascade deletes.** Deleting a user drops their mangas → sections → pages **and**
  their `library_assets` (table rows) via `on delete cascade`. **Storage objects are
  NOT cascaded** by the DB — the backend deletes the files from the bucket when a
  manga/section/page row, or a *discarded* pool asset, is removed.
- **Page versions: cascade and file clean-up.** Deleting a `manga_pages` row cascades to
  its `manga_page_versions` rows (table rows only); deleting a page that was another
  version's translation reference just nulls `reference_page_id`. Storage objects are not
  cascaded, so the backend must delete each version's file when removing a version, page,
  section or manga. `_preview/` objects are transient: they are deleted when a preview is
  rejected or replaced, and promoted to a version (row + kept file) only on accept.
- **The pool lifecycle.** A `library_assets` row has exactly two exits, and they treat
  the underlying Storage object differently:
  - **Organized into a manga** — the backend creates a `manga_pages` row pointing at the
    asset's `storage_path`, then deletes the `library_assets` row. The **file is kept**:
    ownership simply transfers from the pool row to the new page row (which now
    references it). This is your "gets a manga link, leaves the pool."
  - **Discarded** — the user drops the asset without using it: delete the
    `library_assets` row **and** the Storage object.
  One asset → one page: an asset is *consumed* on organize (not referenced by many
  mangas). If shared/reused-across-mangas is ever wanted, keep the pool row and add a
  join table instead of deleting — a later change.
- **Reading order** is `manga_pages.position`; section order within a tab is
  `manga_sections.number`. The pool is browsed by its own `library_assets.position`
  (a collection queue, freshly collected images at the bottom) — assigned by the
  backend from each collect batch's original request order, not `created_at`,
  since a batch's images can finish downloading/uploading out of order. A page's
  actual reading `position` is chosen at organize time, from the order the pool
  items were picked in, not from this browse order.
