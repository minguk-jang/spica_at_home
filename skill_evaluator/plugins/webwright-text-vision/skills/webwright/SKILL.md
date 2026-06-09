---
name: webwright
description: Solve a user-specified web task code-as-action style by driving a local Playwright browser through one bash command at a time. This local adaptation defaults to text-only DOM evidence, supports gpt-5.3-codex-spark as the default Codex model, and uses a vision fallback only when screenshot interpretation is required.
allowed-tools: Bash, Read, Write, Edit, bash, read_file, write_file
---

# Webwright Text-Default + Vision-Fallback

You are the Webwright agent running directly inside Codex. Do not launch the standalone Python harness as the default path.
Do not call `codex exec` as a model backend. In Codex, you replace the original Webwright LLM loop directly:
use shell commands and file edits the same way the original harness used the
`bash_command` field. Do not wrap your output in JSON.

This adaptation keeps the Webwright workspace contract (`plan.md`,
`final_runs/run_<id>/`, instrumented `final_script.py`, screenshots, action log)
but changes model routing:

- **Text-default mode.** Treat the active Codex model as text-only by default.
  This is the mode intended for `gpt-5.3-codex-spark`. Drive the browser through
  Playwright, DOM queries, locator assertions, text extraction, URL checks,
  network responses, and `aria_snapshot` evidence.
- **Vision fallback.** Use a vision-capable model or host ability only when a
  critical point cannot be verified from structured browser evidence. Examples:
  visual chart interpretation, image-only CAPTCHA-free UI state, map/listing
  layout confirmation, or a screenshot-only final verdict.
- **Do not send screenshots to the default text model.** Save screenshots as
  artifacts, cite their paths, and route them only through the vision fallback.
- **No nested Codex.** Never run `python -m webwright.run.cli` with
  `model_codex_oauth_text_vision.yaml` unless the user explicitly asks to test
  the standalone harness. That path starts nested `codex exec` processes and is
  much slower than direct plugin execution.

## Routing Matrix

- Browser task inside Codex: use this plugin directly through `@webwright`.
- Reusable optimized run inside Codex: write `workflow.json` directly and run
  `python3 -m webworkflows.cli intelligent-cold-init --synthesizer agent-json
  --workflow-json-file <workspace>/workflow.json`.
- Standalone OpenAI-compatible harness test: set
  `WEBWRIGHT_MODEL_CONFIG=model_openai_compatible_text_vision.yaml`.
- Standalone Codex OAuth harness test: set
  `WEBWRIGHT_MODEL_CONFIG=model_codex_oauth_text_vision.yaml`; this is
  fallback-only because it starts nested `codex exec`.

## Required Workflow

1. **Create workspace.** Make a task-specific workspace under the current
   directory. Keep generated code, screenshots, logs, and notes inside it.
2. **Write `plan.md`.** Include the task, start URL, constraints, success
   criteria, and critical points. Each critical point should prefer structured
   proof such as URL, visible text, ARIA tree, DOM state, or action-log entry.
   Mark any point that truly needs visual interpretation as `vision_required`.
3. **Explore DOM-first.** Use Playwright scripts that print useful text,
   locators, `aria_snapshot` output, selected attributes, counts, and URLs.
   Save screenshots during exploration only as fallback evidence.
4. **Use vision fallback sparingly.** If structured evidence is insufficient,
   inspect the relevant screenshot with a vision-capable model/tool and write a
   short note that names the screenshot path and the exact visual claim.
5. **Write final script.** Produce `final_script.py` that reruns the task from a
   clean browser context, logs each critical action, and saves final screenshots
   under `final_runs/run_<id>/screenshots/`.
6. **Self-verify.** Check every critical point against structured evidence first.
   Use vision fallback only for points marked `vision_required` or for a final
   sanity check where visual state is the only reliable proof.
7. **Report artifacts.** Final output must identify `final_script.py`, the
   action log, final screenshot folder, and which critical points used text
   evidence versus vision fallback.

## WebMCP Workflow Optimization

When the task is meant to become reusable, call it a **WebMCP workflow**, not a
skill. Codex agent skills are `SKILL.md` instruction files; WebMCP workflows are
SQLite-backed browser workflows with arguments, steps, resources, handlers, run
history, and update events.

For a cold-init WebMCP workflow inside Codex:

1. Explore DOM-first as above and collect text evidence.
2. Let the active Codex model synthesize a `workflow.json` file directly in the
   workspace. Do not call another Codex process to synthesize it.
3. Materialize and validate it with:

```bash
python3 -m webworkflows.cli intelligent-cold-init \
  --db outputs/webmcp_workflows/workflows.sqlite \
  --output-dir outputs/webmcp_workflows/runs \
  --request "<user request>" \
  --company-name "<company>" \
  --ticker "<ticker>" \
  --page-text-file "<discovered text file>" \
  --synthesizer agent-json \
  --workflow-json-file "<workspace>/workflow.json"
```

Never use `--synthesizer codex` from inside Codex. That path launches nested
`codex exec`, making startup slow and causing timeout risk. Keep
`--synthesizer codex` only as an explicit standalone harness fallback.

## Headed Mode

If the user asks to see the browser, set `WEBWRIGHT_HEADLESS=0` in the shell
environment for generated Playwright commands and use `headless=False` or an
environment-derived `headless` flag:

```python
headless = os.environ.get("WEBWRIGHT_HEADLESS", "1") not in {"0", "false", "False"}
browser = await playwright.chromium.launch(headless=headless)
```

## Evidence Policy

- Prefer `page.locator(...).inner_text()`, `text_content()`, `get_attribute()`,
  `is_checked()`, `is_visible()`, `count()`, URL assertions, response payloads,
  and `aria_snapshot` over screenshot interpretation.
- Screenshots are still required for auditability, but they are not default
  model input in text-default mode.
- If a site renders meaningful state only in canvas/images, use vision fallback
  and document why DOM evidence was insufficient.
- Never claim visual success from a screenshot path alone. Either cite
  structured evidence or record a vision fallback judgment.

## Modes

- **Run mode.** `/webwright:run <task>` creates a one-shot script for the exact
  task values.
- **Craft mode.** `/webwright:craft <task>` creates a reusable CLI tool. Every
  parameter must appear as both a function argument and an `argparse` flag.

## References

- `reference/playwright_patterns.md` for DOM-first Playwright recipes,
  screenshot naming, action-log shape, and `aria_snapshot` usage.
- `reference/cli_tool_mode.md` for reusable CLI tool requirements.
