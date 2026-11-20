-- Board: database setup for Supabase.
-- Run this once in the Supabase dashboard (SQL Editor > New query > Run).
-- It is safe to run again.

create table if not exists public.cards (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title       text not null,
  type        text not null default 'other',
  topic       text not null default '',
  url         text not null default '',
  notes       text not null default '',
  status      text not null default 'todo',
  sort_order  double precision not null default 0,
  created_at  timestamptz not null default now()
);

-- Row-level security: a signed-in user can only see and change their own cards.
alter table public.cards enable row level security;

drop policy if exists "Users manage their own cards" on public.cards;
create policy "Users manage their own cards" on public.cards
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Live updates, so a change on one device shows up on the others.
do $$
begin
  alter publication supabase_realtime add table public.cards;
exception
  when duplicate_object then null;
end $$;
