# Webwright Text + Vision Variant

This directory contains a local Codex plugin variant based on
`reference/webwright`. It keeps Webwright's code-as-action Playwright workflow
but changes model routing:

- default work is text-only and DOM-first, suitable for `gpt-5.3-codex-spark`;
- screenshots are saved as artifacts but are not sent to the default text model;
- vision-capable models are used only for screenshot interpretation or final
  visual checks that cannot be proven from DOM, ARIA, URL, response, or logs.

## Codex Usage

Start a new Codex session with Spark, then invoke the plugin:

```bash
codex -m gpt-5.3-codex-spark
```

```text
@webwright <web task>
```

For tasks where visual state is required, switch to a vision-capable Codex model
for that check or delegate the screenshot judgment to a separate vision model.

## Routing Matrix

- Inside Codex for browser work: use `@webwright`; the active Codex model drives
  Playwright directly.
- Inside Codex for reusable optimized runs: write `workflow.json` directly and
  materialize it with `python3 -m webworkflows.cli intelligent-cold-init
  --synthesizer agent-json --workflow-json-file ...`.
- Standalone OpenAI-compatible harness testing: set
  `WEBWRIGHT_MODEL_CONFIG=model_openai_compatible_text_vision.yaml`.
- Standalone Codex OAuth harness testing: set
  `WEBWRIGHT_MODEL_CONFIG=model_codex_oauth_text_vision.yaml`; this is
  fallback-only because it starts nested `codex exec`.

## Standalone Harness Template

The standalone Python harness is fallback-only. Inside Codex, prefer `@webwright`
and the `webworkflows` `--synthesizer agent-json` path so the active Codex model
does the reasoning directly. The harness script now requires
`WEBWRIGHT_MODEL_CONFIG` to be set explicitly.

For OpenAI-compatible provider testing:

```bash
cd reference/webwright
git apply ../../patches/webwright-codex-oauth-text-vision.patch
WEBWRIGHT_MODEL_CONFIG=model_openai_compatible_text_vision.yaml ./scripts/run_text_vision_demo.sh
```

To explicitly test the nested Codex OAuth fallback:

```bash
cd reference/webwright
WEBWRIGHT_MODEL_CONFIG=model_codex_oauth_text_vision.yaml ./scripts/run_text_vision_demo.sh
```

The config split is:

- `model_openai_compatible_text_vision.yaml`: direct
  OpenAI-compatible `openai_endpoint`, `openai_api_key`, and `model_name`.
- `model_codex_oauth_text_vision.yaml`: explicit fallback mode, Codex OAuth
  through nested `codex exec`, defaulting to `gpt-5.3-codex-spark` plus
  `gpt-5.5` vision.
- `model_text_default_vision_fallback.yaml`: compatibility alias for the Codex
  OAuth fallback mode.

Codex Spark is a Codex model choice, not a Platform API key replacement. The
standalone Python harness uses the added `codex_cli` backend only when explicitly
running in OAuth fallback mode.

## Reference Patch

`reference/webwright` is a local clone used for development and is ignored to
avoid committing the upstream repository, virtualenv, and run outputs. The
Webwright harness changes are packaged as:

```bash
patches/webwright-codex-oauth-text-vision.patch
```

Apply that patch inside the reference clone before running the standalone
harness.

## WebMCP Workflows MVP

`webworkflows` is a SQLite-backed cache layer for repeated Webwright-style
tasks. It treats successful browser runs as dynamically loadable **WebMCP
workflows**. This is intentionally separate from Codex agent skills, which are
`SKILL.md` instruction files:

1. search lightweight metadata (`name`, `description`, schema, examples);
2. lazy-load the selected WebMCP workflow version;
3. execute deterministic steps through repo handlers;
4. store run, step, output, and report evidence;
5. reserve LLM/Webwright repair for missing or broken workflows.

Run the seeded Naver stock report workflow with fixture text:

```bash
python3 -m webworkflows.cli run \
  --db outputs/webmcp_workflows.sqlite \
  --output-dir outputs/workflow_runs \
  --request "네이버에서 삼성전자 주가 리포트" \
  --company-name 삼성전자 \
  --ticker 005930 \
  --page-text-file tests/fixtures/naver_stock_text.txt
```

The MVP keeps executable logic in repo handlers such as
`webworkflows.handlers.naver_stock.extract_stock_card`; the database stores
WebMCP workflow metadata, arguments, steps, resources, handler references, and
run history.

For a cold-init run that starts with an empty DB and discovers the Naver page
through Playwright before materializing `naver_stock_report` v1:

```bash
reference/webwright/.venv/bin/python -m webworkflows.cli cold-init \
  --db outputs/workflow_cold_init_browser/workflows.sqlite \
  --output-dir outputs/workflow_cold_init_browser/runs \
  --request "네이버에서 삼성전자 주가 리포트" \
  --company-name 삼성전자 \
  --ticker 005930 \
  --news-limit 1 \
  --discovery-provider naver-browser
```

This records `cold_init_runs.discovery_duration_ms`,
`materialization_duration_ms`, and `first_run_duration_ms`. The current
`naver-browser` provider performs browser discovery and deterministic
materialization; it does not yet invoke an LLM/Webwright repair loop.

For an intelligent cold-init run inside Codex, let the active Codex Spark model
create a `workflow.json` file directly, then pass that file to the local
materializer. This avoids the slow nested `codex exec` path:

```bash
reference/webwright/.venv/bin/python -m webworkflows.cli intelligent-cold-init \
  --db outputs/intelligent_cold_init_agent_json/workflows.sqlite \
  --output-dir outputs/intelligent_cold_init_agent_json/runs \
  --request "네이버에서 삼성전자 주가 리포트" \
  --company-name 삼성전자 \
  --ticker 005930 \
  --news-limit 1 \
  --page-text-file outputs/naver_stock_page_text.txt \
  --synthesizer agent-json \
  --workflow-json-file outputs/naver_stock_workflow.json
```

The default synthesizer model label remains `gpt-5.3-codex-spark`, but
`--synthesizer agent-json` does not launch another Codex process. The legacy
`--synthesizer codex` backend is kept only for explicit standalone harness
testing because it calls `codex exec` internally. Tests use
`--synthesizer fake-naver-stock` to avoid live model calls while still verifying
the same materialization path.
