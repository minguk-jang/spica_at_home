# WebMCP Desktop FSD Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the WebMCP Desktop renderer with Feature-Sliced Design while preserving current behavior and Electron/Core contracts.

**Architecture:** Keep Electron and Rust sidecar code as existing adapters. Refactor the React renderer into `app`, `pages`, `widgets`, `features`, `entities`, and `shared` layers, with `main.tsx` and `styles.css` acting as entrypoint aggregators. Add a structure guard test so the boundary stays visible.

**Tech Stack:** React 19, Vite, TypeScript, Node test runner, Electron, Rust sidecar.

---

### Task 1: Add FSD Structure Guard

**Files:**
- Create: `apps/desktop/tests/fsdStructure.test.cjs`

**Step 1: Write the failing test**

Add a Node test that checks:

- `src/app`, `src/pages`, `src/widgets`, `src/features`, `src/entities`,
  `src/shared`, and `src/styles` exist.
- `src/main.tsx` has fewer than 60 lines and imports `./app`.
- `src/app/App.tsx` exists and exports `App`.
- TypeScript imports do not point from lower layers to higher layers.
- legacy flat source files such as `src/workflowDashboard.ts`,
  `src/runResultSummary.ts`, and `src/activeJob.ts` are absent.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/desktop
node --test tests/fsdStructure.test.cjs
```

Expected: FAIL because layer directories and `src/app/App.tsx` do not exist,
and `src/main.tsx` is still large.

### Task 2: Create Shared and Entity Modules

**Files:**
- Create: `apps/desktop/src/shared/api/webmcpBridge.ts`
- Create: `apps/desktop/src/shared/lib/format.ts`
- Create: `apps/desktop/src/shared/lib/json.ts`
- Create: `apps/desktop/src/shared/ui/*`
- Create: `apps/desktop/src/entities/workflow/model/types.ts`
- Create: `apps/desktop/src/entities/workflow/model/detailDefaults.ts`
- Create: `apps/desktop/src/entities/run/model/runResultSummary.ts`
- Create: `apps/desktop/src/entities/memory/model/memoryFacts.ts`
- Modify: `apps/desktop/src/vite-env.d.ts`

**Step 1: Move shared logic**

Move generic UI primitives and helpers out of `main.tsx`, and move existing
typed models from `vite-env.d.ts` into entity/shared modules. Keep
`vite-env.d.ts` as the Vite reference and global `Window.webmcp` declaration.

**Step 2: Update tests**

Update tests importing flat modules to import from the new public APIs.

**Step 3: Run targeted tests**

Run:

```bash
cd apps/desktop
node --test tests/runResultSummary.test.ts tests/workflowDetailDefaults.test.ts
node --test tests/fsdStructure.test.cjs
```

Expected: behavior tests pass; structure test may still fail until all layers
are moved.

### Task 3: Move Feature Models

**Files:**
- Create: `apps/desktop/src/features/active-job/model/activeJob.ts`
- Create: `apps/desktop/src/features/create-workflow/model/createWorkflow.ts`
- Create: `apps/desktop/src/features/evolve-workflow/model/evolutionDisplay.ts`
- Create: `apps/desktop/src/features/evolve-workflow/model/evolutionSummary.ts`
- Create: `apps/desktop/src/features/js-tool/model/jsToolDefaults.ts`
- Create: `apps/desktop/src/features/run-workflow/model/runControlFields.ts`
- Create: `apps/desktop/src/features/update-workflow/model/updateModeOptions.ts`
- Remove flat legacy modules after imports are updated.

**Step 1: Move existing tested code**

Relocate the current helper implementations without changing behavior.

**Step 2: Update tests**

Update tests for active jobs, run controls, update modes, evolution display,
evolution summary, JS tool defaults, and workflow dashboard helpers.

**Step 3: Run targeted tests**

Run:

```bash
cd apps/desktop
node --test tests/activeJob.test.ts tests/runControlFields.test.ts tests/updateModeOptions.test.ts tests/evolutionDisplay.test.ts tests/evolutionSummary.test.ts tests/jsToolDefaults.test.ts tests/workflowDashboard.test.ts
```

Expected: PASS.

### Task 4: Split Renderer Components

**Files:**
- Create: `apps/desktop/src/app/App.tsx`
- Create: `apps/desktop/src/app/appTypes.ts`
- Create: `apps/desktop/src/app/defaults.ts`
- Create: page and widget component files under `pages/` and `widgets/`
- Modify: `apps/desktop/src/main.tsx`

**Step 1: Extract components**

Move components from `main.tsx` to the target layers:

- `LandingView` to `pages/home`.
- `MemoryView` and cards to `pages/memory`.
- `JsToolAppView` to `pages/js-tool`.
- workflow shell to `pages/workflows`.
- `WorkflowMainDashboard`, tab panels, proposal list, run views, and result
  views to `widgets/workflow-detail`.
- `CreateWorkflowSheet` to `widgets/create-workflow-sheet`.
- `RunEvents` to `widgets/run-queue`.
- `AppNav` to `widgets/app-nav`.

**Step 2: Keep app orchestration in App**

`App.tsx` keeps state, effects, and `window.webmcp` calls for now. It composes
pages and passes callbacks down.

**Step 3: Shrink entrypoint**

`main.tsx` should only import React, `createRoot`, `App`, and styles, then
render `<App />`.

**Step 4: Run targeted tests**

Run:

```bash
cd apps/desktop
node --test tests/landingPage.test.ts tests/jsToolStudio.test.ts tests/fsdStructure.test.cjs
```

Expected: PASS after source-reading tests are updated.

### Task 5: Split Styles

**Files:**
- Create: `apps/desktop/src/styles/base.css`
- Create: `apps/desktop/src/styles/layout.css`
- Create: `apps/desktop/src/styles/shared.css`
- Create page/widget/feature CSS files as needed.
- Modify: `apps/desktop/src/styles.css`
- Modify: `apps/desktop/tests/mobileLayout.test.cjs`
- Modify: `apps/desktop/tests/modalLayout.test.cjs`

**Step 1: Move CSS blocks**

Move related CSS blocks from `styles.css` into layer-specific files. Keep
`styles.css` as an import list.

**Step 2: Update CSS tests**

Make CSS source tests read `styles.css` and recursively resolve `@import`
files before checking rules.

**Step 3: Run CSS tests**

Run:

```bash
cd apps/desktop
node --test tests/mobileLayout.test.cjs tests/modalLayout.test.cjs tests/fsdStructure.test.cjs
```

Expected: PASS.

### Task 6: Full Verification

**Files:**
- No new files unless fixes are required.

**Step 1: Run all desktop checks**

Run:

```bash
cd apps/desktop
npm run test:unit
npm run typecheck
npm run build
npm run sidecar:test
```

Expected: all pass.

**Step 2: Review worktree**

Run:

```bash
git status --short -- apps/desktop docs/plans
```

Expected: only intended files are modified or added.
