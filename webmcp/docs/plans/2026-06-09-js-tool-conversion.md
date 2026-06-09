# JavaScript Tool Conversion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert existing SQLite-backed WebMCP workflow tools into runnable JavaScript tools, while renaming the canonical DB tool tables away from `workflow_tools`.

**Architecture:** Add a Python compiler that exports a DB workflow tool to a Node-compatible JavaScript module with a manifest and `run(args)` entrypoint. Add a small JS runtime template that interprets the existing workflow step JSON and supports deterministic local execution for `goto`, `wait_for_text`, `run_handler`, `assert_output`, and `render_report`. Rename canonical DB tables from `workflow_tool_*` to `workflow_tool_*`, and migrate old DB files on initialize.

**Tech Stack:** Python standard library, SQLite, Node.js CommonJS, existing WebMCP workflow JSON model, unittest.

---

### Task 1: DB Tool Table Rename

**Files:**
- Modify: `core/webworkflows/storage.py`
- Modify: core modules and tests that query `workflow_tools` or `workflow_tool_*`
- Modify: `apps/desktop/rust/webmcp-sidecar/src/lib.rs`

**Steps:**
1. Write a failing test that initializes a DB and asserts canonical tables are `workflow_tools`, `workflow_tool_versions`, `workflow_tool_arguments`, `workflow_tool_steps`, `workflow_tool_resources`, and `workflow_tool_examples`.
2. Add migration logic that renames existing old tables before schema creation.
3. Update SQL references to the new canonical table names.
4. Run the targeted DB/tool tests.

### Task 2: JavaScript Tool Compiler

**Files:**
- Create: `core/webworkflows/js_tool.py`
- Test: `core/tests/test_js_tool_conversion.py`

**Steps:**
1. Write a failing test that seeds `naver_stock_report`, exports it to a directory, and asserts `manifest.json`, `tool.cjs`, and `workflow.json` exist.
2. Implement export from `WorkflowSkillLoader` plus `workflow_json_from_skill`.
3. Include a JS runtime template in `tool.cjs` with `module.exports = { manifest, run }`.
4. Run the targeted export test.

### Task 3: JavaScript Tool Execution

**Files:**
- Modify: `core/webworkflows/js_tool.py`
- Modify: `core/webworkflows/cli.py`
- Test: `core/tests/test_js_tool_conversion.py`

**Steps:**
1. Write failing tests for three tools: Naver stock, Naver map transit, and a generic no-handler report workflow.
2. Implement `run_js_tool()` that invokes Node with JSON args and returns parsed JSON.
3. Implement JS handler equivalents for built-in `naver_stock.extract_stock_card` and `naver_map.extract_subway_duration`.
4. Add CLI commands `export-js-tool` and `run-js-tool`.
5. Run the three targeted example tests.

### Task 4: Eval Compatibility

**Files:**
- Modify: `core/webworkflows/js_tool.py`
- Modify: `core/webworkflows/cli.py`
- Test: `core/tests/test_js_tool_conversion.py`

**Steps:**
1. Write a failing test that calls a JS eval wrapper with expected required output markers.
2. Implement `eval_js_tool()` as a deterministic output contract check that can be called from CLI with `eval-js-tool`.
3. Keep browser VLM eval on the existing Python workflow path; JS eval validates generated JS tool output parity and required keys.
4. Run targeted tests and full core unittest discovery.

### Task 5: Docs

**Files:**
- Modify: `README.md`
- Modify: `core/README.md`
- Modify: `docs/WORKFLOWS.md`

**Steps:**
1. Document the canonical `workflow_tools` naming.
2. Document `export-js-tool`, `run-js-tool`, and `eval-js-tool`.
3. Include three example commands.
4. Run docs-adjacent tests and JSON/style checks.
