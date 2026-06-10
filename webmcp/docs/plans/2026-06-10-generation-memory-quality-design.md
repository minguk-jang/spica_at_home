# Generation Memory Quality Design

**Goal:** Make workflow generation store evidence-backed page analysis and reusable generation knowledge that is specific enough to guide later tool creation.

**Approved Direction:** Improve the existing `create-workflow` memory path rather than adding a separate DB. The user asked to proceed with the recommended direction after the current-state review.

**Architecture:** Keep `page_analyses` and `workflow_knowledge_entries` as the persistence layer. Add a post-run memory enrichment step that merges initial trace text, workflow step definitions, run output, step evidence, and eval/repair evidence into page analysis and knowledge. Reuse the same enrichment in `intelligent-cold-init` so older creation paths do not bypass memory context.

**Data Flow:**
- Initial trace still creates/looks up URL-keyed page analysis before synthesis.
- Synthesis receives page analysis and recent script-generation knowledge.
- After run/eval, Core derives verified selectors, wait markers, output keys, observed URLs/titles, dynamic action hints, and failure notes from DB step runs and evaluation payloads.
- Core upserts the improved page analysis under the same normalized URL key and appends a richer script-generation knowledge entry.

**Error Handling:** Failed runs still record knowledge, but confidence remains lower and failure notes include the failed step, assertion error, and repair focus where available.

**Testing:** Add deterministic unit tests for three examples: Books to Scrape pagination/product detail, Dynamic Controls async UI, and Dynamic Ad runtime LLM action. These tests should inspect the actual page analysis and knowledge rows produced by generation.
