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

## Standalone Harness Template

The current default is Codex OAuth:

```bash
cd reference/webwright
git apply ../../patches/webwright-codex-oauth-text-vision.patch
./scripts/run_text_vision_demo.sh
```

To switch later to an OpenAI-compatible provider, edit
`plugins/webwright-text-vision/config/model_openai_compatible_text_vision.yaml`
or the mirrored file under `reference/webwright/src/webwright/config/`, then run:

```bash
cd reference/webwright
WEBWRIGHT_MODEL_CONFIG=model_openai_compatible_text_vision.yaml ./scripts/run_text_vision_demo.sh
```

The config split is:

- `model_codex_oauth_text_vision.yaml`: current mode, Codex OAuth through
  `codex exec`, defaulting to `gpt-5.3-codex-spark` plus `gpt-5.5` vision.
- `model_openai_compatible_text_vision.yaml`: future mode, direct
  OpenAI-compatible `openai_endpoint`, `openai_api_key`, and `model_name`.
- `model_text_default_vision_fallback.yaml`: compatibility alias for the current
  Codex OAuth mode.

Codex Spark is a Codex model choice, not a Platform API key replacement. The
standalone Python harness uses the added `codex_cli` backend when running in
OAuth mode.

## Reference Patch

`reference/webwright` is a local clone used for development and is ignored to
avoid committing the upstream repository, virtualenv, and run outputs. The
Webwright harness changes are packaged as:

```bash
patches/webwright-codex-oauth-text-vision.patch
```

Apply that patch inside the reference clone before running the standalone
harness.
