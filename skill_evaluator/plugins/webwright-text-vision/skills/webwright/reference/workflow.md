# Text-Default Workflow

This local Webwright variant keeps the original code-as-action loop but changes
the evidence model. The active Codex agent should behave as if it cannot read images.
It should use Playwright to expose page state as text and structured data, then
reserve screenshots for audit and vision fallback.

Reusable optimized runs are called **WebMCP workflows**. Do not call them
workflow skills; that name conflicts with Codex agent skills.

## DOM-First Evidence

Use these before vision:

- `locator.inner_text()` for visible labels and result cards.
- `locator.get_attribute()` for selected values, ARIA state, hrefs, and form
  attributes.
- `locator.is_visible()`, `is_checked()`, and `count()` for UI state.
- `page.url`, title, response JSON, and local storage/session state.
- `aria_snapshot` when accessible structure is more reliable than raw HTML.

## Vision Fallback

Use vision fallback only when a critical point is visual by nature or the DOM is
misleading. Record the fallback as a short statement:

```text
vision_fallback:
  screenshot: final_runs/run_001/screenshots/final_execution_3_results.png
  claim: The selected red color swatch is visibly active.
  reason: The swatch active state is canvas-rendered and not exposed in DOM/ARIA.
```

## Completion Gate

Do not finish until every critical point has one of:

- text evidence from DOM, URL, ARIA, response, or action log;
- a vision fallback judgment with a screenshot path and exact visual claim.
