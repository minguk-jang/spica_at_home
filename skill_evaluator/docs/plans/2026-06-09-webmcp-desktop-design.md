# WebMCP Desktop Design

## Goal

Build a desktop app for inspecting and managing the SQLite-backed WebMCP
workflows created by the local Webwright optimization work.

## Chosen Approach

Use Electron for the desktop shell, React/Vite for the frontend, and a Rust
sidecar CLI for local SQLite access and process orchestration. Electron keeps
the app packaging model familiar while Rust owns the DB boundary and workflow
execution commands.

## Architecture

- `skill_evaluator_desktop/` is a sibling app next to `skill_evaluator/`.
- The frontend calls `window.webmcp.*` methods exposed by Electron preload.
- Electron main proxies IPC calls to the Rust sidecar.
- Rust reads WebMCP SQLite files directly and returns JSON DTOs.
- Run requests are created in Electron as sequential jobs. Each job invokes the
  existing Python `webworkflows.cli run` command with a selected workflow
  version context where available.

## UI

The app opens directly into an operational dashboard, not a landing page.

- Left rail: workflow list with status, domain, task type, latest version, run
  count, and last updated time.
- Detail view: selected workflow metadata, argument schema, step timeline,
  script/resource viewer, version history, update events, and run history.
- Run panel: run all known versions sequentially in headless mode.
- Watch action: launch a headed replay/watch command for the selected workflow
  and version so the user can inspect browser behavior on demand.

The visual style should be dense, restrained, and work-focused: neutral
surfaces, readable tables, visible focus states, 44px interaction targets where
practical, stable dimensions, and no decorative hero or marketing sections.

## Data Model

The Rust sidecar reads the existing tables without renaming them:

- `workflow_skills`
- `workflow_skill_versions`
- `workflow_skill_steps`
- `workflow_skill_resources`
- `workflow_skill_arguments`
- `workflow_runs`
- `step_runs`
- `skill_update_events`
- `workflow_synthesis_runs`
- `cold_init_runs`

Public UI labels use "WebMCP workflow" to avoid confusion with Codex agent
skills.

## Error Handling

- Missing DB path returns an empty state with a clear UI status.
- Invalid DB schema returns a sidecar error string surfaced in the status bar.
- Run jobs capture stdout, stderr, exit code, duration, and status.
- The queue continues after a failed version and marks that item failed.

## Testing

- Rust unit tests create temporary SQLite DBs and verify summary/detail JSON.
- TypeScript typecheck verifies the renderer/preload API contract.
- Vite build verifies frontend bundling.
- Manual app launch is optional; automated validation focuses on sidecar,
  frontend compilation, and Electron process code syntax.
