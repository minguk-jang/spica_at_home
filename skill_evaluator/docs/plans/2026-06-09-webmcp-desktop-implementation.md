# WebMCP Desktop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an Electron + React desktop app backed by a Rust sidecar for inspecting and running local WebMCP workflows.

**Architecture:** Electron owns windows and IPC, React renders the dashboard, and Rust owns SQLite reads plus command DTOs. Existing WebMCP workflow tables remain unchanged; the app adapts them into UI-friendly JSON.

**Tech Stack:** Electron, React, Vite, TypeScript, Rust, rusqlite, serde, Node child_process.

---

### Task 1: Scaffold Desktop App

**Files:**
- Create: `../skill_evaluator_desktop/package.json`
- Create: `../skill_evaluator_desktop/tsconfig.json`
- Create: `../skill_evaluator_desktop/vite.config.ts`
- Create: `../skill_evaluator_desktop/index.html`
- Create: `../skill_evaluator_desktop/src/main.tsx`
- Create: `../skill_evaluator_desktop/src/styles.css`
- Create: `../skill_evaluator_desktop/electron/main.cjs`
- Create: `../skill_evaluator_desktop/electron/preload.cjs`

**Steps:**
1. Add npm scripts for `dev`, `build`, `typecheck`, `electron`, and sidecar build.
2. Add Vite React entrypoint and Electron preload bridge.
3. Keep renderer isolated from Node APIs.

### Task 2: Implement Rust DB Sidecar With Tests

**Files:**
- Create: `../skill_evaluator_desktop/rust/webmcp-sidecar/Cargo.toml`
- Create: `../skill_evaluator_desktop/rust/webmcp-sidecar/src/main.rs`
- Create: `../skill_evaluator_desktop/rust/webmcp-sidecar/src/lib.rs`

**Steps:**
1. Write tests that create a temp WebMCP SQLite DB.
2. Verify `list-workflows` returns workflow cards.
3. Verify `workflow-detail` returns versions, arguments, steps, resources, runs, and update events.
4. Implement the minimal rusqlite queries to pass.

### Task 3: Wire Electron IPC

**Files:**
- Modify: `../skill_evaluator_desktop/electron/main.cjs`
- Modify: `../skill_evaluator_desktop/electron/preload.cjs`

**Steps:**
1. Add `webmcp:listWorkflows` and `webmcp:getWorkflowDetail`.
2. Add sequential run queue IPC.
3. Add headed watch command IPC.
4. Capture stdout/stderr/status for each job.

### Task 4: Build React Dashboard

**Files:**
- Modify: `../skill_evaluator_desktop/src/main.tsx`
- Modify: `../skill_evaluator_desktop/src/styles.css`

**Steps:**
1. Render DB path controls and workflow cards.
2. Render detail tabs for steps, script/resources, versions, updates, and runs.
3. Render run queue panel and watch actions.
4. Use accessible buttons, labels, focus states, and stable table layouts.

### Task 5: Verify

**Commands:**
- `cargo test --manifest-path ../skill_evaluator_desktop/rust/webmcp-sidecar/Cargo.toml`
- `npm --prefix ../skill_evaluator_desktop install`
- `npm --prefix ../skill_evaluator_desktop run typecheck`
- `npm --prefix ../skill_evaluator_desktop run build`
- `npm --prefix ../skill_evaluator_desktop run sidecar:build`
