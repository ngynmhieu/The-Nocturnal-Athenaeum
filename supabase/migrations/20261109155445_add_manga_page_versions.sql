-- add_manga_page_versions
-- Generated 2026-11-09T15:54:45+00:00 by scripts/gen_migration.py
-- Seeded from: schema/read/manga_page_versions.sql
-- Desired shape stays authoritative in schema/read/.

-- Desired shape of public.manga_page_versions (read module).
-- An accepted derived version of a page: its upscaled image and/or its translated
-- ('en') image. At most one per (page, kind, language). `language` is null for
-- upscaled and set for translated. `reference_page_id` records which page was used
-- as the translation reference (set null if that page is deleted). Files live in the
-- `manga` bucket. See supabase/docs/modules/read.md.

create table if not exists public.manga_page_versions (
  id                uuid        primary key default gen_random_uuid(),
  page_id           uuid        not null references public.manga_pages (id) on delete cascade,
  kind              text        not null check (kind in ('upscaled', 'translated')),
  language          text,                  -- null for upscaled; e.g. 'en' for translated
  storage_path      text        not null,  -- object path in the `manga` bucket
  width             integer,               -- intrinsic px (nullable until known)
  height            integer,
  reference_page_id uuid        references public.manga_pages (id) on delete set null,
  created_at        timestamptz not null default now(),
  check ((kind = 'upscaled') = (language is null))
);

-- One accepted version per (page, kind, language); coalesce so null language is comparable.
create unique index if not exists manga_page_versions_page_kind_lang_idx
  on public.manga_page_versions (page_id, kind, coalesce(language, ''));

-- Loading a page's versions.
create index if not exists manga_page_versions_page_idx
  on public.manga_page_versions (page_id);

-- RLS: a version is visible/editable only through an owned manga (join up via page → section).
alter table public.manga_page_versions enable row level security;

create policy "Page versions readable through an owned manga"
  on public.manga_page_versions for select using (
    exists (
      select 1 from public.manga_pages p
      join public.manga_sections s on s.id = p.section_id
      join public.mangas m on m.id = s.manga_id
      where p.id = manga_page_versions.page_id and m.user_id = auth.uid()
    )
  );

create policy "Insert page versions through an owned manga"
  on public.manga_page_versions for insert with check (
    exists (
      select 1 from public.manga_pages p
      join public.manga_sections s on s.id = p.section_id
      join public.mangas m on m.id = s.manga_id
      where p.id = manga_page_versions.page_id and m.user_id = auth.uid()
    )
  );

create policy "Update page versions through an owned manga"
  on public.manga_page_versions for update using (
    exists (
      select 1 from public.manga_pages p
      join public.manga_sections s on s.id = p.section_id
      join public.mangas m on m.id = s.manga_id
      where p.id = manga_page_versions.page_id and m.user_id = auth.uid()
    )
  );

create policy "Delete page versions through an owned manga"
  on public.manga_page_versions for delete using (
    exists (
      select 1 from public.manga_pages p
      join public.manga_sections s on s.id = p.section_id
      join public.mangas m on m.id = s.manga_id
      where p.id = manga_page_versions.page_id and m.user_id = auth.uid()
    )
  );
