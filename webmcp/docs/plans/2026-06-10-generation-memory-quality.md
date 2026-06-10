# Generation Memory Quality Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve WebMCP workflow generation so page analysis and script-generation knowledge are backed by verified run/eval evidence.

**Architecture:** Extend `page_memory.py` with helpers that merge base page analysis with workflow steps, run output, step run evidence, and evaluation evidence. Call those helpers from `WorkflowCreationRuntime` after execution and from `IntelligentColdInitRunner` before synthesis. Keep the DB schema unchanged.

**Tech Stack:** Python unittest, SQLite, WebMCP Core services.

---

### Task 1: Add Failing Memory Quality Tests

**Files:**
- Modify: `core/tests/test_workflow_creation_runtime_service.py`
- Modify: `core/tests/test_page_memory.py`

**Steps:**
1. Add three deterministic `WorkflowCreationRuntime.create()` tests using existing fake/agent-json synthesis.
2. Assert page analysis contains stable markers, verified wait markers, selector hints, and workflow step hints.
3. Assert knowledge entries include URL shape, verified selectors, wait/assert markers, output keys, and failure/dynamic action tips.
4. Add an `IntelligentColdInitRunner` test proving synthesis prompts include page analysis/knowledge context.
5. Run targeted tests and verify failures before production code changes.

### Task 2: Implement Evidence-Backed Memory Derivation

**Files:**
- Modify: `core/webworkflows/page_memory.py`
- Modify: `core/webworkflows/services/creation_runtime.py`
- Modify: `core/webworkflows/cold_init.py`

**Steps:**
1. Add helpers to collect stable markers from output page text, wait assertions, browser evaluation excerpts, and final page text.
2. Add helpers to summarize verified selectors and step strategy from workflow steps and step run evidence.
3. Merge these into page analysis while preserving normalized URL key behavior.
4. Update creation runtime to upsert the improved analysis after execution and use it for knowledge recording.
5. Update intelligent cold-init to enrich trace with page memory before synthesis.

### Task 3: Verify Three Realistic Examples

**Files:**
- Test-only via temp SQLite DBs.

**Steps:**
1. Run targeted unit tests for page memory and creation runtime.
2. Run three CLI/static example creations against a temp DB:
   - Books to Scrape category/product flow.
   - The Internet Dynamic Controls async UI.
   - Local dynamic ad workflow with runtime LLM action represented by static workflow JSON and eval stub.
3. Inspect temp DB page analysis/knowledge rows for useful generated tips.
4. Run broader Core tests touched by the feature.
