# WebMCP Desktop

Electron + React desktop app for inspecting and managing WebMCP workflows from
the sibling `skill_evaluator` repo.

## Run

```bash
cd /Users/mingukjang/git/spica_at_home/skill_evaluator_desktop
npm install
npm run dev
```

`npm run dev` builds the Rust sidecar, starts the Vite dev server, and opens the
Electron window against that dev server.

For a production-style local launch:

```bash
npm run app
```

The default DB is:

```text
/Users/mingukjang/git/spica_at_home/skill_evaluator/outputs/webmcp_plugin_cold_iter_check/workflows.sqlite
```

## Structure

- `electron/main.cjs`: Electron window, IPC, Rust sidecar calls, sequential run
  state, selected-version headless/headed runs.
- `electron/handler-source.cjs`: maps handler registry modules to local Python
  source files and attaches source text to workflow detail responses.
- `electron/preload.cjs`: safe renderer bridge.
- `src/`: React dashboard.
- `src/script-preview/`: generated Python + Playwright previews and the
  enforced handler-source visibility rules.
- `rust/webmcp-sidecar/`: Rust SQLite sidecar.

## Workflow Runs

The run panel executes one selected workflow version at a time. Select the
version from the `Versions` tab; the run panel only displays the current
selection.

- `Run selected headless`: runs the selected version with `WEBWRIGHT_HEADLESS=1`.
- `Run selected headed`: runs the selected version with `WEBWRIGHT_HEADLESS=0`
  and opens the workflow output URL in the system browser when available.

Every Desktop run collects fresh Naver page text first by calling
`webworkflows.cli run-version --live-page-text`. The app does not pass the
stale fixture file used by automated tests. The default Python runtime is the
repo's Webwright venv:

```text
/Users/mingukjang/git/spica_at_home/skill_evaluator/reference/webwright/.venv/bin/python
```

This avoids launching every version when the UI can only inspect one visible
browser run at a time.

## Workflow Implementation

Workflow steps are not JavaScript snippets. They are stored as declarative DB
records:

- Built-in steps such as `goto`, `wait_for_text`, `assert_output`, and
  `render_report` are JSON actions interpreted by the Python
  `WorkflowExecutor`.
- `run_handler` steps call Python handlers from `handler_registry`, such as
  `webworkflows.handlers.naver_stock.extract_stock_card`.
- Report output usually comes from Markdown resource templates stored in
  `workflow_skill_resources`.

The `Implementation` tab shows a generated Python + Playwright preview first.
Generated previews are single-file inspection scripts: every `run_handler`
module is inlined as real Python function code, not displayed as comments and
not hidden behind `from webworkflows... import ...`. If a handler file cannot be
read, the preview generates a real stub function that raises `RuntimeError` with
the missing handler id.

Below the preview, the tab shows the step-level mapping: step type, execution
kind, Python module/function when applicable, stored DB field, action JSON,
argument bindings, assertions, handler registry metadata, handler source, and
resource templates.

After each run, the app shows the parsed CLI result in two places:

- `Latest Run Result`: the most recent live run output, including key result
  fields, report path, and raw CLI JSON.
- `Runs`: stored DB run history, including output JSON/report text and per-step
  evidence for each run.

## Update Studio

The `Update` tab turns WebMCP Desktop into a workflow editing surface:

1. Select a base version in `Versions`.
2. Open `Update`.
3. Enter a change instruction.
4. Choose update mode:
   - `코드만 보고 수정`: use the existing workflow JSON, steps, resources,
     implementation details, and instruction only. Internally this sends
     `--discovery-provider none`.
   - `브라우저를 조작하며 수정`: let Webwright open and operate the browser
     before synthesis, then include the collected evidence. Internally this sends
     `--discovery-provider webwright`.
5. Confirm the Codex model.
6. Generate a draft. The app runs the proposal CLI in the Electron main process
   with `--synthesizer codex`; `fake-copy` is not exposed in Desktop.
7. Inspect the generated diff/evidence/proposed JSON, then apply it.

Electron controls these jobs by spawning:

```bash
<configured-python> -m webworkflows.cli propose-update ...
<configured-python> -m webworkflows.cli apply-proposal ...
```

For proposal generation, Electron waits for the background CLI process and
records stdout, stderr, exit status, parsed JSON output, and timing in the app's
run event stream.

Drafts are stored in `workflow_update_proposals`. Applying a draft creates the
next `workflow_skill_versions` row and records a `skill_update_events` entry.

## Verification

```bash
npm run test:unit
npm run sidecar:test
npm run typecheck
npm run build
npm run sidecar:build
WEBMCP_DEV_SMOKE=1 npm run dev
```
