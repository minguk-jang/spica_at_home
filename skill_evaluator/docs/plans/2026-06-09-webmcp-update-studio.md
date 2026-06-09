# WebMCP Update Studio Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a WebMCP Desktop update flow where the user enters a change instruction, a CLI-controlled Codex/Webwright proposal job creates a draft next workflow version, and the user can review and apply it.

**Architecture:** Electron remains the process controller and invokes Python CLI jobs. Python owns workflow proposal storage, Codex synthesis, optional discovery evidence, and version materialization. The Rust sidecar remains the read API for Desktop and is extended to return proposals.

**Tech Stack:** Python `webworkflows`, SQLite, Electron IPC, Rust `rusqlite` sidecar, React/TypeScript UI.

---

### Task 1: Backend Proposal Core

**Files:**
- Modify: `webworkflows/storage.py`
- Create: `webworkflows/update_proposal.py`
- Modify: `tests/test_workflow_skills.py`

**Steps:**
1. Write failing tests for `propose-update` and `apply-proposal`.
2. Add `workflow_update_proposals` table.
3. Add serializer from current `WorkflowSkill` to workflow JSON.
4. Add proposal generator that can use `AgentJsonSynthesisBackend` for tests and Codex by default.
5. Add materializer that inserts a new version from proposed workflow JSON after approval.

### Task 2: CLI Integration

**Files:**
- Modify: `webworkflows/cli.py`
- Modify: `tests/test_workflow_skills.py`

**Steps:**
1. Add `propose-update` subcommand.
2. Add `apply-proposal` subcommand.
3. Ensure JSON stdout includes proposal id, base/proposed versions, diff, status, and applied version id.

### Task 3: Sidecar Read Model

**Files:**
- Modify: `skill_evaluator_desktop/rust/webmcp-sidecar/src/lib.rs`
- Modify: `skill_evaluator_desktop/rust/webmcp-sidecar/src/main.rs`

**Steps:**
1. Add proposal structs to workflow detail.
2. Query latest proposals by workflow id.
3. Add Rust tests covering proposal rows.

### Task 4: Electron IPC

**Files:**
- Modify: `skill_evaluator_desktop/electron/main.cjs`
- Modify: `skill_evaluator_desktop/electron/preload.cjs`
- Modify: `skill_evaluator_desktop/src/vite-env.d.ts`

**Steps:**
1. Add IPC handlers for `webmcp:propose-update` and `webmcp:apply-proposal`.
2. Emit update job events with stdout/stderr and parsed output.
3. Keep all Python execution controlled from Electron main.

### Task 5: Desktop Update Studio UI

**Files:**
- Modify: `skill_evaluator_desktop/src/main.tsx`
- Modify: `skill_evaluator_desktop/src/styles.css`
- Modify: `skill_evaluator_desktop/README.md`

**Steps:**
1. Add `Update` tab.
2. Add instruction field, discovery/synthesizer controls, generate button, apply button.
3. Show proposal diff, generated workflow JSON, status, and applied version id.
4. Refresh workflow detail after propose/apply.

### Verification

Run:
- `python3 -m unittest tests/test_workflow_skills.py tests/test_text_default_vision_fallback.py`
- `npm run test:unit`
- `npm run sidecar:test`
- `npm run typecheck`
- `npm run build`
- `WEBMCP_DEV_SMOKE=1 npm run dev`
