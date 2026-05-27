create table if not exists public.project_workspaces (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.project_workspaces enable row level security;

drop policy if exists "Users can read their workspace" on public.project_workspaces;
create policy "Users can read their workspace"
  on public.project_workspaces
  for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert their workspace" on public.project_workspaces;
create policy "Users can insert their workspace"
  on public.project_workspaces
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their workspace" on public.project_workspaces;
create policy "Users can update their workspace"
  on public.project_workspaces
  for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
