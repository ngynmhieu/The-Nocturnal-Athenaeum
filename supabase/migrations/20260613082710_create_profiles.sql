-- create_profiles
-- Applied to the remote database with:  supabase db push
--
-- Why SQL and not SQLAlchemy create_all:
--   This table foreign-keys into Supabase's internal `auth.users` table and
--   uses Row Level Security — neither of which SQLAlchemy can express. So the
--   table and its RLS policies are created directly in Supabase.
--
-- What it does:
--   1. Creates a public.profiles table owned by your app, linked 1-to-1 to
--      each Supabase auth user by sharing the same UUID.
--   2. Enables RLS so a user can only read/update their own profile.
--
-- Note: profile ROWS are created/updated by the backend (POST /me ->
--   AuthService.sync_profile), not by a database trigger — business logic
--   lives in the service layer. See backend/docs/modules/auth.md.

-- 1. The table -------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid        primary key references auth.users (id) on delete cascade,
  email       text,
  full_name   text,
  avatar_url  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- 2. Row Level Security (defense-in-depth for the auto-exposed REST API) ----
alter table public.profiles enable row level security;

create policy "Profiles are viewable by the owner"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on public.profiles for update
  using (auth.uid() = id);
