-- Run this complete script in Supabase SQL Editor.
-- The legacy project_workspaces table is retained so the app can import existing data.

create table if not exists public.project_workspaces (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  deadline date not null,
  summary text not null default '',
  top_risk text not null default '',
  next_step text not null default '',
  is_public boolean not null default false,
  public_slug text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  parent_id uuid references public.tasks(id) on delete cascade,
  risk text not null check (risk in ('H', 'M', 'L')),
  title text not null,
  responsible text not null,
  start_date date not null,
  duration integer not null check (duration >= 1),
  status text not null check (status in ('Open', 'Ongoing', 'Closed')),
  completed_date date,
  note text not null default '',
  display_order bigint not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.task_progress_entries (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  task_id uuid not null references public.tasks(id) on delete cascade,
  entry_date date not null,
  planned_progress integer not null check (planned_progress between 0 and 100),
  actual_progress integer not null check (actual_progress between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (task_id, entry_date)
);

create table if not exists public.daily_logs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  task_id uuid not null references public.tasks(id) on delete cascade,
  log_date date not null,
  responsible text not null,
  plan_text text not null,
  actual_text text not null,
  planned_progress integer not null check (planned_progress between 0 and 100),
  actual_progress integer not null check (actual_progress between 0 and 100),
  result text not null check (result in ('完成', '部分完成', '延期')),
  delay_reason text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (task_id, log_date)
);

create index if not exists tasks_project_idx on public.tasks(project_id);
create index if not exists progress_task_date_idx on public.task_progress_entries(task_id, entry_date desc);
create index if not exists logs_project_date_idx on public.daily_logs(project_id, log_date desc);

alter table public.project_workspaces enable row level security;
alter table public.projects enable row level security;
alter table public.tasks enable row level security;
alter table public.task_progress_entries enable row level security;
alter table public.daily_logs enable row level security;

drop policy if exists "Users can read their workspace" on public.project_workspaces;
create policy "Users can read their workspace" on public.project_workspaces for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Users can insert their workspace" on public.project_workspaces;
create policy "Users can insert their workspace" on public.project_workspaces for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "Users can update their workspace" on public.project_workspaces;
create policy "Users can update their workspace" on public.project_workspaces for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Owners manage projects" on public.projects;
create policy "Owners manage projects" on public.projects for all to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);

drop policy if exists "Owners manage tasks" on public.tasks;
create policy "Owners manage tasks" on public.tasks for all to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);

drop policy if exists "Owners manage progress" on public.task_progress_entries;
create policy "Owners manage progress" on public.task_progress_entries for all to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);

drop policy if exists "Owners manage logs" on public.daily_logs;
create policy "Owners manage logs" on public.daily_logs for all to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);

create or replace function public.get_public_project_snapshot(p_slug text)
returns jsonb
language sql
security definer
stable
set search_path = public
as $$
  select jsonb_build_object(
    'name', p.name,
    'deadline', p.deadline,
    'summary', p.summary,
    'topRisk', p.top_risk,
    'nextStep', p.next_step,
    'taskCount', (select count(*) from public.tasks t where t.project_id = p.id and t.parent_id is null),
    'closedTasks', (select count(*) from public.tasks t where t.project_id = p.id and t.parent_id is null and t.status = 'Closed'),
    'plannedProgress', coalesce((
      select round(avg(coalesce(latest.planned_progress, 0)))::integer
      from public.tasks t
      left join lateral (
        select pe.planned_progress
        from public.task_progress_entries pe
        where pe.task_id = t.id
        order by pe.entry_date desc
        limit 1
      ) latest on true
      where t.project_id = p.id and t.parent_id is null
    ), 0),
    'actualProgress', coalesce((
      select round(avg(coalesce(latest.actual_progress, 0)))::integer
      from public.tasks t
      left join lateral (
        select pe.actual_progress
        from public.task_progress_entries pe
        where pe.task_id = t.id
        order by pe.entry_date desc
        limit 1
      ) latest on true
      where t.project_id = p.id and t.parent_id is null
    ), 0),
    'tasks', coalesce((
      select jsonb_agg(jsonb_build_object(
        'title', t.title,
        'status', t.status,
        'actualProgress', coalesce(latest.actual_progress, 0)
      ) order by t.display_order, t.created_at)
      from public.tasks t
      left join lateral (
        select pe.actual_progress
        from public.task_progress_entries pe
        where pe.task_id = t.id
        order by pe.entry_date desc
        limit 1
      ) latest on true
      where t.project_id = p.id and t.parent_id is null
    ), '[]'::jsonb)
  )
  from public.projects p
  where p.public_slug = p_slug and p.is_public = true
  limit 1;
$$;

revoke all on function public.get_public_project_snapshot(text) from public;
grant execute on function public.get_public_project_snapshot(text) to anon, authenticated;
