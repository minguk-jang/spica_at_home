# `/webwright:craft`

Use Webwright text-default mode to create a reusable CLI tool for the requested
web workflow.

Run directly in the current Codex session. Do not start the standalone
`python -m webwright.run.cli` harness unless the user explicitly asks for a
harness test.

1. Create a workspace and write `plan.md`.
2. Identify task parameters and record each parameter in `plan.md`.
3. Explore DOM-first with Playwright, including visible text, ARIA snapshots,
   locator state, URLs, and response data.
4. Use screenshots for auditability. Route screenshots to vision fallback only
   for critical points that cannot be proven from structured evidence.
5. Write `final_script.py` as a CLI tool. Every parameter must exist as a typed
   function argument and an `argparse` `--flag` with the concrete task value as
   the default.
6. Run the script with no arguments in a new `final_runs/run_<id>/` folder.
7. Verify all critical points, clearly separating text evidence from vision
   fallback judgments.

Task:

```text
$ARGUMENTS
```
