# Completion and Verification

- Treat the task as incomplete until every requested deliverable is done or explicitly marked `[blocked]` with what is missing.
- If a lookup returns empty, partial, or suspiciously narrow results without accepted site filters/sort explaining that result set, retry with a different strategy before concluding no result exists.
- Earlier snapshots are supporting evidence only. Never present them as current page state unless re-verified.
- Before reporting completion, verify that:
  - You actually accomplished the request, not just attempted it.
  - Extracted data came from inspected evidence, not memory or assumption.
  - Requested criteria such as count, format, filters, and source boundaries were met.
  - The final response matches the requested format.
  - Any external side effect was confirmed when confirmation was required.
