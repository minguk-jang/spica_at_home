# Guided Workflow Steps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users provide rough workflow steps during desktop workflow creation and have core generation use them as a synthesis scaffold.

**Architecture:** Desktop owns editing and normalization, Electron owns CLI argument transport, and core owns validation, persistence, and prompt shaping. The guide is stored as `arguments.step_guide` so existing creation-session audit storage and synthesis trace plumbing can carry it without a schema migration.

**Tech Stack:** React, Electron command builders, Python unittest, WebMCP workflow synthesis.

---

### Task 1: Desktop Payload

**Files:**
- Modify: `apps/desktop/src/workflowDashboard.ts`
- Modify: `apps/desktop/src/vite-env.d.ts`
- Test: `apps/desktop/tests/workflowDashboard.test.ts`

**Steps:**
1. Add a `WorkflowStepGuideItem` payload type with `name`, `description`, and `step_type`.
2. Add `CreateWorkflowStepGuideItem` for UI state with `stepType`.
3. Normalize and trim guide rows in `buildCreateWorkflowPayload`.
4. Drop rows where both name and description are blank.
5. Run `node --test tests/workflowDashboard.test.ts`.

### Task 2: Desktop UI

**Files:**
- Modify: `apps/desktop/src/main.tsx`
- Modify: `apps/desktop/src/styles.css`
- Test: `apps/desktop/tests/jsToolStudio.test.ts`

**Steps:**
1. Add `createStepGuide` state.
2. Pass it into `buildCreateWorkflowPayload`.
3. Add a Step guide section to `CreateWorkflowSheet`.
4. Add icon-first add/remove controls and compact row styling.
5. Run `node --test tests/jsToolStudio.test.ts`.

### Task 3: CLI And Core Prompt

**Files:**
- Modify: `apps/desktop/electron/update-command.cjs`
- Modify: `core/webworkflows/cli.py`
- Modify: `core/webworkflows/synthesis.py`
- Test: `apps/desktop/tests/updateCommand.test.cjs`
- Test: `core/tests/test_workflow_creation_runtime_service.py`

**Steps:**
1. Add `--step-guide-json` only to create-workflow args.
2. Parse and validate the JSON array in core CLI.
3. Store parsed rows in `arguments["step_guide"]`.
4. Add a dedicated prompt section for human-authored guide JSON.
5. Run targeted desktop and core tests.

### Task 4: Verification

**Files:**
- Test: `core/tests`
- Test: `apps/desktop/tests`

**Steps:**
1. Run guided creation smoke examples for Books to Scrape, Dynamic Controls, and Dynamic Ad.
2. Run `PYTHONPATH=. python3 -m unittest tests.test_page_memory tests.test_workflow_creation_runtime_service`.
3. Run `PYTHONPATH=. python3 -m unittest discover -s tests`.
4. Run desktop unit tests and type/build checks.
5. Run `git diff --check`.
