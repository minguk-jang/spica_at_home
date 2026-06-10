# Guided Workflow Steps Design

## Problem

Some browser tasks are too broad for a cold workflow generator to solve from only start URL, task, and done state. Users often know the rough route already, such as opening a category, applying a search, waiting for a result list, and rendering a report. WebMCP should accept that route as a human-authored scaffold and let the generator turn it into executable workflow steps.

## Design

The desktop create workflow modal adds an optional Step guide editor. Each guide row stores a name, description, and rough WebMCP step type. Empty rows are ignored, and the desktop payload normalizes UI `stepType` to core `step_type`.

Electron passes the normalized guide as `--step-guide-json` only for `create-workflow`. Core parses the JSON array, validates item shape, trims fields, and stores it under `arguments["step_guide"]`. Creation sessions already persist arguments in `workflow_creation_sessions.input_json`, so the guide becomes part of the generation audit trail.

The synthesis prompt exposes a dedicated `Human-authored step guide JSON` section. The instruction tells the generator to preserve guide order and intent, keep recognizable names when valid, and fill in selectors, waits, handlers, and assertions from discovered page evidence. The guide is a scaffold, not executable code and not a substitute for verified page analysis.

## Testing

Coverage spans the three product seams:

- Desktop payload normalization filters blank rows and emits `step_type`.
- Electron create args include `--step-guide-json`.
- Core synthesis prompt and stored session input include the guide.

Three guided smoke examples should exercise Books to Scrape, Dynamic Controls, and a dynamic action page to prove guided creation still stores page analysis and script knowledge.
