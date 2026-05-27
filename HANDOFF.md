# Project Desk Development Handoff

## Current Deployment

- GitHub repository: <https://github.com/imbingo/project-manage>
- Production URL: <https://imbingo.github.io/project-manage/>
- Backend project URL: `https://bgchvbxemcyolpqxikvz.supabase.co`
- Frontend deploy method: GitHub Pages workflow on `main`

## Required One-Time Action

Run the complete contents of `supabase/schema.sql` in the Supabase SQL Editor after pulling the latest `main` branch. Until this migration is executed, signed-in users continue working through the existing `project_workspaces` JSON storage in a labelled compatibility mode; public sharing and relation-level conflict reduction require the migration.

The app automatically migrates legacy `project_workspaces.payload` JSON into relational tables if the relational tables are empty for the logged-in user.

## Data Model

- `projects`: user-owned projects and public-sharing metadata.
- `tasks`: hierarchy through `parent_id`; only internal authenticated reads.
- `task_progress_entries`: unique `(task_id, entry_date)` planned and actual progress history.
- `daily_logs`: unique `(task_id, log_date)` daily reporting records.
- `project_workspaces`: retained only as legacy import source.
- `get_public_project_snapshot(slug)`: security-definer read-only RPC returning a restricted public summary.

All tables use Supabase Row Level Security. Authenticated users can CRUD only rows where `owner_id = auth.uid()`. Anonymous users access only the restricted RPC for projects explicitly marked public.

## Implemented Product Behavior

- Email confirmation and password-reset links redirect to the GitHub Pages site through `config.js.siteUrl`.
- Project settings control public sharing and produce `?share=<slug>` URLs.
- Daily log submission writes both a daily log and a dated progress record.
- Task overview displays latest recorded progress; the log view shows plan vs actual for the selected date.
- Export supports complete project JSON and task CSV.
- Mobile layout suppresses dense grids and presents outstanding tasks plus quick daily entry.

## Technical Follow-Ups Worth Considering

- Import JSON backups through the UI.
- Add optimistic concurrency/version checks if several people will edit the same project.
- Add collaborators and role-based project membership; current ownership is single-user.
- Add automated browser tests for auth-free public snapshot rendering and local preview forms.
