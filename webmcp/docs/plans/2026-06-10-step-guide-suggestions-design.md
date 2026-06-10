# Step Guide Suggestions Design

## Problem

Manual step guide entry is useful, but adding one row at a time is slow for broad tasks. Users need an initial draft that captures the likely browser route, then fast controls to refine, reorder, duplicate, and delete rows.

## Design

Desktop adds a `Suggest Draft` button to the Create workflow step guide editor. The button sends start URL, task, done state, DB path, repo root, Python path, and Codex model to a new Electron/Core command. The response is a `step_guide` JSON array that is converted back into editable UI rows.

Core adds `suggest-step-guide`. The default `--suggester codex` path builds a focused LLM prompt from the creation context plus saved page analysis and script-generation knowledge, then sends it through the same Codex app-server JSON-RPC path used by VLM evaluation. It does not spawn a nested `codex exec` process. The command also supports `--suggester heuristic` for deterministic tests and fallback. If Codex fails, the CLI returns a heuristic scaffold instead of leaving the UI empty.

The UI keeps row editing compact:

- `Suggest Draft` creates a first pass.
- `Add Step` keeps manual append available.
- Rows can be reordered by drag/drop or by up/down icon buttons.
- Rows can be duplicated and deleted from icon buttons.

## Testing

Coverage verifies the core suggester prompt and normalization, CLI JSON output, Electron args, core client event flow, IPC/preload bridge, renderer affordances, and full desktop/core regression suites.
