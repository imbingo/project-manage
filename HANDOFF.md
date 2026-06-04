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
- Export supports full workspace JSON, task CSV, and an Excel-readable project table with overview, task ledger, daily logs, and Gantt timeline.
- Import supports workspace JSON, single-project JSON, Supabase legacy payloads, wrapped `data/workspace/payload` exports, and legacy localStorage keys. The UI previews counts and diagnostics before merge or replace.
- Mobile layout suppresses dense grids and presents outstanding tasks plus quick daily entry.

## WeChat Mini Program MVP

- Source lives in `miniapp/` and uses native WeChat Mini Program pages, not browser APIs.
- Runtime configuration is copied from `miniapp/config.example.js` to ignored `miniapp/config.js`.
- Supabase access is through `wx.request` in `miniapp/utils/supabase.js`; no `supabase-js` dependency is used.
- Data mapping between camelCase and Supabase snake_case lives in `miniapp/utils/models.js`.
- The miniapp shares `projects`, `tasks`, `task_progress_entries`, and `daily_logs` with the web app.
- MVP pages:
  - `pages/login`: Supabase email/password login.
  - `pages/home`: mobile-first today view, project selector, open/overdue tasks, quick daily entry.
  - `pages/project-detail`: overview, project create/edit, task list.
  - `pages/task-form`: task create/edit with parent task, risk, owner, dates, status, note, and initial progress.
  - `pages/daily-form`: daily log submission plus progress upsert and task status update.
- Public sharing remains web-only through `?share=slug` for now.

## Local Desktop MVP

- Source lives in `local_desktop/`.
- Runtime is Python + PySide6; data is local JSON under `%APPDATA%/ProjectDeskLocal/workspace.json`.
- Non-GUI compatibility logic lives in `local_desktop/src/import_export.py`.
- The desktop app imports web workspace JSON, single-project JSON, Supabase legacy payloads, wrapped `data/workspace/payload` exports, and old localStorage keys.
- Excel export writes `.xlsx` with project overview, task ledger, daily logs, and a Gantt timeline.
- The first desktop UI focuses on reading, importing, backup/export, and dashboard-style review. Full create/edit dialogs are still a follow-up.

## Technical Follow-Ups Worth Considering

- Consider adding automated import/export fixture tests around the new browser-side JSON compatibility logic.
- Add optimistic concurrency/version checks if several people will edit the same project.
- Add collaborators and role-based project membership; current ownership is single-user.
- Add automated browser tests for auth-free public snapshot rendering and local preview forms.
- Add WeChat openid login through a server-side function or trusted backend.
- Add project deletion, public share rendering, and compact Gantt/roadmap views to the miniapp after MVP validation.
