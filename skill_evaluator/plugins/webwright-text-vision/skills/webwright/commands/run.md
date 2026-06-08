# `/webwright:run`

Use Webwright text-default mode for the requested one-shot web task.

1. Create a workspace for this run.
2. Write `plan.md` with critical points. Prefer DOM/text/ARIA/log evidence and
   mark only genuinely visual checks as `vision_required`.
3. Explore with short Playwright scripts. Print locators, visible text, URL,
   selected attributes, and `aria_snapshot` evidence before using screenshots.
4. Save screenshots as artifacts, but do not send screenshots to the default
   text model.
5. Invoke vision fallback only when structured evidence cannot establish a
   required UI state.
6. Write and run `final_script.py` inside `final_runs/run_<id>/`.
7. Verify every critical point and report which evidence was text-only versus
   vision fallback.

Task:

```text
$ARGUMENTS
```
