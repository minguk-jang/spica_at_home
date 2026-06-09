# WebMCP Workflows MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a SQLite-backed WebMCP workflow MVP that dynamically loads reusable Webwright-style workflows by name/description metadata, executes deterministic steps, and records runs without using an LLM on cache-hit execution.

**Architecture:** Store workflow metadata, versions, steps, resources, handlers, runs, and step runs in SQLite. Load only metadata for matching, lazy-load the selected version and steps, then execute a small deterministic step set through repo handler functions. Keep executable code in repo modules and store handler references in DB.

**Tech Stack:** Python standard library, SQLite, JSON, unittest, optional Playwright-compatible handler interfaces.

---

### Task 1: Tests

**Files:**
- Create: `tests/test_workflow_skills.py`

**Steps:**
1. Write tests for DB initialization and seed data.
2. Write tests for metadata-only search and lazy loading.
3. Write tests for deterministic execution using fake page text.
4. Run tests and confirm they fail because implementation modules do not exist.

### Task 2: Storage

**Files:**
- Create: `webworkflows/__init__.py`
- Create: `webworkflows/storage.py`
- Create: `webworkflows/seeds.py`

**Steps:**
1. Implement SQLite schema creation.
2. Implement JSON helpers and row mapping.
3. Implement `seed_naver_stock_report`.
4. Run storage tests.

### Task 3: Loader

**Files:**
- Create: `webworkflows/loader.py`

**Steps:**
1. Implement metadata search over workflow name, description, domain, task type, and examples.
2. Implement lazy loading of selected workflow version, arguments, steps, and resources.
3. Run loader tests.

### Task 4: Executor

**Files:**
- Create: `webworkflows/executor.py`
- Create: `webworkflows/handlers/naver_stock.py`
- Create: `webworkflows/handlers/__init__.py`

**Steps:**
1. Implement step types: `goto`, `wait_for_text`, `run_handler`, `assert_output`, `render_report`.
2. Implement run and step-run persistence.
3. Implement handler import via `handler_registry`.
4. Implement a text fixture path for deterministic tests.
5. Run executor tests.

### Task 5: Verification

**Files:**
- Modify: as needed.

**Steps:**
1. Run `python3 -m unittest tests/test_workflow_skills.py`.
2. Run existing `python3 -m unittest tests/test_text_default_vision_fallback.py`.
3. Run plugin and WebMCP workflow validators.
4. Inspect `git status --short`.
