-- OpenHome Supabase schema
-- Run this in Supabase Dashboard -> SQL Editor.

-- ============================================================
-- HELPER: set updated_at
-- ============================================================
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================
-- TRIGGER: auto-create profile on signup
-- ============================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, username, plan)
  values (new.id, new.raw_user_meta_data ->> 'name', 'free');
  return new;
end;
$$;

-- ============================================================
-- PROFILES
-- ============================================================
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text,
  plan text not null default 'free' check (plan in ('free', 'plus')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row
  execute function public.set_updated_at();

alter table public.profiles enable row level security;

revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (username) on public.profiles to authenticated;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
  on public.profiles
  for select
  to authenticated
  using (auth.uid() = id);

drop policy if exists "Users can update own username" on public.profiles;
create policy "Users can update own username"
  on public.profiles
  for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- ============================================================
-- SERVERS
-- ============================================================
create table if not exists public.servers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,

  name text not null,
  description text,
  minecraft_version text not null default 'Paper latest',
  loader text not null default 'paper',
  plan text not null default 'free' check (plan in ('free', 'plus')),
  plan_at_creation text not null default 'free',
  status text not null default 'created',
  ram_mb integer not null default 1024 check (ram_mb > 0 and ram_mb <= 4096),
  max_players integer not null default 10 check (max_players > 0),
  storage_limit_gb integer not null default 2,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_servers_updated_at on public.servers;
create trigger trg_servers_updated_at
  before update on public.servers
  for each row
  execute function public.set_updated_at();

alter table public.servers enable row level security;

revoke all on public.servers from anon, authenticated;
grant select on public.servers to authenticated;

drop policy if exists "Users can read their own servers" on public.servers;
create policy "Users can read their own servers"
  on public.servers
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "Users can create their own servers" on public.servers;
drop policy if exists "Users can update their own servers" on public.servers;
drop policy if exists "Users can delete their own servers" on public.servers;
