# WebMCP Agent Instructions

This file governs the whole `webmcp` repository.

## Persistent SQLite DB

- The persistent WebMCP Studio SQLite database is `~/.webmcp-studio/db/workflows.sqlite`.
- Core CLI code must default to `WEBMCP_STUDIO_DB_PATH` when that environment variable is set, otherwise to `~/.webmcp-studio/db/workflows.sqlite`.
- Do not use `core/outputs/**/workflows.sqlite` as the persistent product DB. Use `core/outputs/**` only for throwaway run artifacts, smoke tests, screenshots, and reproducible temporary checks.
- When demonstrating stored workflow memory, inspect the persistent DB under `~/.webmcp-studio/db` unless the user explicitly asks for an isolated test DB.

## Page Analysis And Script Knowledge

- Page analysis must be actionable enough to guide future script generation. Do not store only generic labels such as `react`, `iframe`, or `Workflow creation succeeded`.
- For each analyzed page, store stable wait/assert markers, page type, recommended interaction strategy, extraction strategy, selector strategy, risk notes, and evidence excerpts.
- For script-generation knowledge, write entries as reusable tips. A useful entry should answer: what URL shape should be reused, what should be waited for, which selectors or handlers are preferred, what failure modes matter, and which output keys should be asserted.
- URL keys must be generated consistently by removing query strings/fragments and converting host/path to kebab-case. The same normalization must be used when saving and looking up page analysis.

## Naver Stock Workflows

- Prefer direct Naver search URLs such as `https://search.naver.com/search.naver?query={{company_name}} 주가` over driving the Naver home search box.
- For Naver stock cards, wait for text markers such as `증권정보`, `현재가`, and the six-digit ticker before extraction.
- Prefer the registered `naver_stock.extract_stock_card` handler over scraping individual stock DOM nodes.
- Treat price numbers and market status text as volatile; validate structured output fields such as `company_name`, `ticker`, `current_price`, and `report_text`.
