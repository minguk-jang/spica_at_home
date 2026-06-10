# WebMCP Desktop FSD Refactor Design

## Background

`webmcp/` is already organized as a product-level feature slice: the Python
workflow engine lives under `core/`, the Electron app under `apps/desktop/`,
and supporting docs under `docs/`. The remaining issue is inside the Desktop
renderer. `apps/desktop/src/main.tsx` currently owns application state,
Electron bridge calls, top-level routing, page composition, feature widgets,
shared UI controls, and formatting helpers. `apps/desktop/src/styles.css` also
collects all layout and component styling in one global file.

That structure works, but it does not make feature ownership obvious. It also
makes future changes to workflow creation, JS tool export, memory browsing, and
update/evolution flows all touch the same files.

## Goal

Refactor the Desktop renderer toward Feature-Sliced Design without changing
runtime behavior or Electron/Core contracts.

## Target Structure

```text
apps/desktop/src/
  app/
    App.tsx
    appTypes.ts
    defaults.ts
    index.ts
  pages/
    home/
    js-tool/
    memory/
    workflows/
  widgets/
    app-nav/
    create-workflow-sheet/
    run-queue/
    workflow-detail/
    workflow-sidebar/
  features/
    active-job/
    create-workflow/
    evolve-workflow/
    js-tool/
    run-workflow/
    update-workflow/
  entities/
    memory/
    run/
    workflow/
  shared/
    api/
    lib/
    ui/
  styles/
```

The existing `src/main.tsx` stays as the Vite entrypoint, but it should only
mount the React app. `src/styles.css` stays as the CSS entrypoint imported by
the app, but it should aggregate layer-specific styles.

## Layer Responsibilities

- `app`: renderer bootstrap, application state orchestration, and top-level
  page selection.
- `pages`: route-sized screen composition. Pages receive data and callbacks;
  they do not call `window.webmcp` directly.
- `widgets`: larger reusable UI blocks such as sidebars, queue, workflow detail,
  modals, and tab panels.
- `features`: user operations and feature-specific view/model helpers:
  active job labels, workflow creation payloads, run controls, update modes,
  evolution summaries, and JS tool defaults/results.
- `entities`: domain types and display models for workflow, run, and memory
  data.
- `shared`: Electron bridge typing, generic formatting/parsing helpers, and
  small UI primitives.

Imports should flow downward only:

```text
app -> pages -> widgets -> features -> entities -> shared
```

Same-layer imports are allowed only within the same slice through local files
or public `index.ts` files. Shared code must not import from higher layers.

## Non-Goals

- Do not rewrite Electron IPC, Core CLI commands, or Rust sidecar behavior.
- Do not rename IPC channels or payload fields.
- Do not change visual behavior beyond file ownership.
- Do not move generated artifacts or dependency lockfiles.

## Testing Strategy

Add a structure guard test that fails before the refactor and proves:

- FSD layer directories exist.
- `src/main.tsx` is a small bootstrap file.
- `src/app/App.tsx` owns the app component.
- imports follow the layer order.
- legacy flat renderer modules are no longer the source of truth.

Keep existing unit tests as behavior guards and update their imports to the new
public APIs. Existing CSS source tests should read the aggregated CSS graph
instead of assuming all rules live in `src/styles.css`.
