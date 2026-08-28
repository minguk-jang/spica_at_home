# Browser Workflow

## Snapshot

ALWAYS use `snapshot()` as the primary way to read a webpage.

```ts
async function snapshot(
  page: Page,
  options?: {
    interactive?: boolean; // show interactive elements only
    showHidden?: boolean; // include hidden elements (e.g. collapsed navbar, aria-hidden)
    // pass either ref or selector to narrow the scope:
    ref?: string; // e.g. "e31"
    selector?: string; // e.g. "button.about-this-result", '[role="dialog"]'. NOTE: the tree uses ARIA role names (e.g. "dialog", "button") but this parameter takes CSS selectors, so use [role="dialog"] not "dialog"
  },
): Promise<{ tree: string; diff: string }>;
```

- Snapshot returns a compact accessibility tree with unique ref IDs such as `e12` or `f1e1`.
- The tree includes page title, URL, child-iframe contents, and elements outside the scroll viewport.
- Ref IDs are virtual locator IDs, not actual DOM properties. Safe to pass them directly to `page.locator('e31')`. NEVER treat ref IDs as DOM properties or mix them into CSS selectors.
- Each new snapshot invalidates all earlier ref IDs. Take a new snapshot after each action.
- Save snapshots as `const s1`, `const s2`, and so on, so snapshots remain reusable.
- Start with printing `tree`. After an action, ALWAYS print `diff` to capture the changes only.
- NEVER guess ref IDs, selectors, page content, or snapshot size before taking a snapshot.
- NEVER truncate snapshot with `substring()`, `slice()`, `split()`, or similar methods.

## Reading Escalation

Use this order:

1. `snapshot(page, { interactive: true })`
2. `snapshot(page)`
3. Wait briefly and snapshot again only if the page is still changing
4. Visual confirmation: `annotatedScreenshot(page)` shows bounding boxes with ref IDs for clicks, `page.screenshot()` for raw visual state

Avoid `page.content()` and `page.evaluate()` unless you know the exact selector.

## Navigation and Actions

- Use Playwright APIs through the global `page` object in REPL.
- ALWAYS use `openTab()` and `closeTab()` for tab management. NEVER use `page.context().newPage()` or `page.close()`; they leak memory.
- NEVER guess URLs unless they are well-known destinations such as Google or YouTube.
- Use locator actions with ref IDs over `page.evaluate()` for UI interaction.
- Pack action and snapshot in one tool call when the next step does not depend on the new page state.
- Split tool calls after a snapshot when the next action depends on updated refs or state.
- Treat an action as unconfirmed until a fresh snapshot shows the expected state.
- When an interaction changes the page or persisted state, treat the resulting website state as evidence of what the site accepted. Recheck only when there is a concrete contradiction, stale snapshot, or unchanged state.
- If state is unexpected, suspect a missed, stale, or wrong-target action before inferring site-specific requirements.
- `openTab()` and `click()` already wait for interactivity and DOM stability.
- NEVER add redundant `sleep()` immediately after navigation or action. Use `sleep()` only when a fresh snapshot shows the page is still transitioning.
- No scroll needed. Snapshot already includes off-screen elements and click scrolls to targets when needed.

## Forms, Autofill, and Login

- When you encounter autofillable forms (e.g. ID/PW, email, payment, address, etc.), prefer available autofill paths when they are present.
- Autofill menu should be shown (in 0.5s-1s) as you click the form if user is using password manager.
- **ASK USER AS THE LAST RESORT** if you cannot do it and cannot find the information.

## Recovery

- Dismiss blocking popups, modals, and cookie banners first.
- If an action fails, take a fresh snapshot before retrying.
- If the same path fails 2-3 times, switch strategy.
- If a click fails as "obscured", inspect the real hit target before retrying.
- If you encounter a CAPTCHA, solve it before retrying.

## Site Strategy

- Use the site's own filters, sorting, and result UI first. Trust accepted site state; try search, direct URLs, APIs, or manual inspection only when the site cannot produce results or omits a required criterion.
- For short waits under a minute, use a small `sleep()` loop. For long polls, use notification-activation or heartbeats with routine_updates. REPL `sleep()` times out at 120s and will not keep a channel thread alive.
- If the current version of the website is not available, try using archive.org as a last resort.
