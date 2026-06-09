# Page Analysis And Knowledge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist reusable page analysis and script-generation knowledge, retrieve both during workflow creation, and verify the behavior with three deterministic examples.

**Architecture:** Add a URL utility and a repository module over the existing `WorkflowSkillStore` SQLite DB. Enrich `ArtifactTrace` with retrieved page-analysis and knowledge context before synthesis, and update the stores during workflow creation.

**Tech Stack:** Python 3, SQLite, `unittest`, existing `webworkflows` core modules.

---

### Task 1: URL Normalization And Store API

**Files:**
- Create: `core/webworkflows/page_memory.py`
- Modify: `core/webworkflows/storage.py`
- Test: `core/tests/test_page_memory.py`

**Steps:**
1. Write failing tests for query stripping, kebab-case key generation, page-analysis upsert/lookup, and knowledge append/list.
2. Run `python3 -m unittest tests/test_page_memory.py`.
3. Add tables in `WorkflowSkillStore.initialize()`.
4. Implement `normalize_url_key`, `PageAnalysisStore`, and `WorkflowKnowledgeStore`.
5. Re-run the test until green.

### Task 2: Trace Context And Synthesis Prompt

**Files:**
- Modify: `core/webworkflows/cold_init_types.py`
- Modify: `core/webworkflows/synthesis.py`
- Test: `core/tests/test_page_memory.py`

**Steps:**
1. Write a failing test that builds a trace with page/knowledge context and asserts the prompt includes it.
2. Add `page_analysis_context` and `knowledge_context` to `ArtifactTrace`.
3. Add concise context blocks to `build_synthesis_prompt`.
4. Re-run the focused tests.

### Task 3: Workflow Creation Integration

**Files:**
- Modify: `core/webworkflows/services/creation_runtime.py`
- Test: `core/tests/test_workflow_creation_runtime_service.py`

**Steps:**
1. Write failing tests using three static traces and a fake synthesizer that records prompt input.
2. After trace collection, derive and upsert page analysis, retrieve prior context, enrich the trace, and append outcome knowledge.
3. Ensure existing creation session and attempt records still behave the same.
4. Run creation tests and the page-memory tests.

### Task 4: Verification

**Commands:**
- `cd core && python3 -m unittest tests/test_page_memory.py tests/test_workflow_creation_runtime_service.py`
- `cd core && python3 -m unittest tests/test_workflow_tools.py tests/test_synthesis_provider_port.py`

**Expected:** All selected tests pass, including at least three deterministic examples proving storage, lookup, prompt retrieval, and update behavior.
