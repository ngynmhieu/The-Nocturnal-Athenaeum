# Module: `auth`

> Per-module architecture doc. Mirrors `chat.md`.
> Read `../backend_guidelines.md` first for the rules that govern every module.

## Responsibility

The `auth` module answers one question for the rest of the app: **"who is the user making this request?"**

We use **Supabase Auth** (the "Path A" decision). Supabase runs the Google OAuth flow on the frontend and issues a signed JWT. The backend does **not** handle login, passwords, OAuth redirects, or sessions.

Instead of manually decoding JWTs with a shared secret, the backend delegates verification back to Supabase via the **`supabase-py`** client (`supabase.auth.get_user(token)`). Supabase validates the token against its own records and returns the full user object. This keeps verification logic off the backend and in the authority that issued the token.

It owns:
- Calling `supabase.auth.get_user(token)` to validate the JWT and fetch the user.
- Turning the Supabase user object into a `CurrentUser` domain object.
- Syncing the `profiles` table row on first login via `POST /me`.
- Exposing `get_current_user` as the dependency every protected route uses.

It does **not** own:
- The OAuth flow or login UI → Supabase + the frontend.
- The `auth.users` table → managed by Supabase.
- JWT signing or secret management → Supabase handles this internally.
- Configuration / secrets → `core/config.py`.

---

## Request Flow

```
Frontend (supabase-js)
   └─ "Sign in with Google" → Supabase issues a JWT
   └─ calls POST /me immediately after login  (creates/syncs the profile)
   └─ sends every subsequent API request with:  Authorization: Bearer <jwt>
         │
         ▼
FastAPI protected route:  Depends(get_current_user)
   └─→ dependencies.get_current_user        # extract Bearer token from header
         └─→ AuthService.verify(token)       # calls supabase.auth.get_user(token)
               └─→ Supabase validates JWT    # Supabase checks signature, expiry, etc.
                     └─→ CurrentUser(id, email)  # handed to the route
```

### Profile sync flow (first login only)

```
Frontend calls POST /me with JWT
   └─→ get_current_user verifies token → CurrentUser
         └─→ AuthService.sync_profile(user, session)
               └─→ upserts a profiles row (insert if new, update if exists)
               └─→ returns the profile
```

---

## Target Structure

```
backend/app/modules/auth/
├── __init__.py
├── dependencies.py    # get_current_user — the module's PUBLIC surface
├── service.py         # AuthService — verify(token) + sync_profile()
├── schemas.py         # CurrentUser, ProfileResponse
├── models.py          # Profile ORM model (app-owned profiles table)
└── router.py          # POST /me (sync profile), GET /me (read profile)
```

Supabase owns the `auth.users` table — the backend never creates or writes it.
The `public.profiles` table is app-owned (1-to-1 with `auth.users` by UUID).
It is created via `supabase/migrations/20260613082710_create_profiles.sql`,
applied with `supabase db push` (not by SQLAlchemy `create_all`, because it
foreign-keys into Supabase's internal `auth.users`). `models.py` is the backend ORM view.
Profile rows are created/updated by the backend on `POST /me` — not by a
database trigger. Business logic belongs in the service layer.

---

## File-by-File

### `schemas.py` — domain shapes

```
CurrentUser:
    id: str        # Supabase user UUID
    email: str

ProfileResponse:
    id: str
    email: str | None
    full_name: str | None
    avatar_url: str | None
```

`CurrentUser` is what `get_current_user` returns — a lightweight token-derived
object, not a DB row. `ProfileResponse` is what `GET /me` returns — the stored
profile from the database.

### `service.py` — `AuthService`

Two methods:

**`verify(token) → CurrentUser`**
- Calls `self._supabase.auth.get_user(token)`.
- Supabase validates the signature, expiry, and audience internally.
- Maps `response.user` → `CurrentUser(id, email)`.
- Raises 401 on any failure (invalid token, expired, Supabase unreachable).

No manual JWT decoding. No shared secret in config. No `pyjwt`.

**`sync_profile(user, session) → Profile`**
- Upserts a `profiles` row for the given user.
- On insert: copies `email`, `full_name`, `avatar_url` from the Supabase user metadata.
- On conflict (profile already exists): updates `email` and `updated_at`.
- Returns the profile.

### `dependencies.py` — the public surface

`get_current_user(request) -> CurrentUser`:
- Reads the `Authorization` header, extracts the Bearer token.
- Delegates to `AuthService.verify(token)`.
- Returns the `CurrentUser`, or raises 401 if the header is missing/malformed.

**This is the only thing other modules import from `auth`.** Example consumer:
```python
# modules/chat/router.py
from backend.app.modules.auth.dependencies import get_current_user

@router.post("/chat")
async def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user), ...):
    ...  # use user.id
```

### `router.py` — profile endpoints

**`POST /me`** — sync profile (frontend calls this once after login):
- Verifies token via `get_current_user`.
- Calls `AuthService.sync_profile()` to upsert the profile row.
- Returns `ProfileResponse`.

**`GET /me`** — read profile:
- Verifies token via `get_current_user`.
- Fetches and returns the stored `profiles` row.
- Useful as a "is my token accepted?" check and to load the user's display name / avatar.

---

## Dependencies (flow downward only)

```
modules/auth/router.py
    └─→ modules/auth/dependencies.py   (get_current_user)
    └─→ modules/auth/service.py        (AuthService.verify + sync_profile)
    └─→ modules/auth/schemas.py        (CurrentUser, ProfileResponse)
    └─→ modules/auth/models.py         (Profile ORM model)
            └─→ core/config.py         (SUPABASE_URL, SUPABASE_ANON_KEY)
            └─→ core/database.py       (AsyncSession for profile queries)

modules/chat/*  ──imports──>  modules/auth/dependencies.get_current_user   (public surface only)
```

`auth` imports from `core/` only. Other modules reach `auth` exclusively
through `dependencies.py`.

---

## Configuration & Dependencies

**`core/config.py`** gains:
- `SUPABASE_URL` — your project URL (e.g. `https://xyz.supabase.co`)
- `SUPABASE_ANON_KEY` — the public anon key (safe to use server-side for `auth.get_user`)

**`requirements.txt`** gains:
- `supabase` — the official Python client (`supabase-py`)

No `pyjwt`, no JWT secret, no JWKS URL. Supabase handles all of that
internally when `auth.get_user(token)` is called.

---

## Implementation Plan

1. **Supabase project setup**: enable the Google provider in the Supabase
   dashboard (Authentication → Providers → Google). Paste Google OAuth
   client ID/secret from Google Cloud Console. Both free.

2. **Config + deps**: add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to
   `core/config.py` and `.env.backend`. Add `supabase` to `requirements.txt`.

3. **Run the migration**: `supabase db push` — applies
   `supabase/migrations/20260613082710_create_profiles.sql` to the remote
   database. Verify the `profiles` table appears in the Supabase dashboard.

4. **Build `modules/auth/`** in order:
   `schemas.py` → `models.py` → `service.py` → `dependencies.py` → `router.py`

5. **Wire into `main.py`**: include the auth router; initialise `AuthService`
   in lifespan and attach to `app.state`.

6. **Protect chat**: add `user = Depends(get_current_user)` to the chat route.

7. **Frontend**: install `supabase-js`, add the "Sign in with Google" button,
   call `POST /me` immediately after login, attach the JWT to all API requests.

8. **Smoke test**:
   - Request without a token → 401
   - `POST /me` with a valid Supabase token → 200, profile row in Supabase
   - `POST /chat` with a valid token → streams a response

---

## Future

- **Roles / authorization**: a `require_role(...)` dependency layered on top
  of `get_current_user`.
- **GitHub / Facebook providers**: clone the Google setup in the Supabase
  dashboard — no backend changes needed.
