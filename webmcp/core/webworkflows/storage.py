from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


class WorkflowSkillStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists workflow_skills (
                    id integer primary key autoincrement,
                    name text not null unique,
                    slug text not null unique,
                    description text not null,
                    domain text not null,
                    task_type text not null,
                    status text not null,
                    latest_version_id integer,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp
                );

                create table if not exists workflow_skill_versions (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id) on delete cascade,
                    version integer not null,
                    summary text not null,
                    input_schema_json text not null,
                    output_schema_json text not null,
                    body_md text not null,
                    load_policy_json text not null,
                    status text not null,
                    created_from_run_id integer,
                    created_at text not null default current_timestamp,
                    unique(skill_id, version)
                );

                create table if not exists workflow_skill_examples (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id) on delete cascade,
                    user_request text not null,
                    normalized_arguments_json text not null,
                    expected_output_summary text not null,
                    success_count integer not null default 0,
                    last_used_at text
                );

                create table if not exists workflow_skill_arguments (
                    id integer primary key autoincrement,
                    version_id integer not null references workflow_skill_versions(id) on delete cascade,
                    name text not null,
                    description text not null,
                    type text not null,
                    required integer not null,
                    default_value_json text,
                    validation_json text not null,
                    examples_json text not null,
                    is_dynamic integer not null,
                    order_index integer not null
                );

                create table if not exists workflow_skill_steps (
                    id integer primary key autoincrement,
                    version_id integer not null references workflow_skill_versions(id) on delete cascade,
                    order_index integer not null,
                    name text not null,
                    description text not null,
                    step_type text not null,
                    handler_ref text,
                    action_json text not null,
                    argument_bindings_json text not null,
                    assertions_json text not null,
                    fallback_policy_json text not null,
                    update_policy_json text not null
                );

                create table if not exists workflow_skill_resources (
                    id integer primary key autoincrement,
                    version_id integer not null references workflow_skill_versions(id) on delete cascade,
                    resource_type text not null,
                    name text not null,
                    description text not null,
                    content_json text,
                    content_text text,
                    load_when_json text not null
                );

                create table if not exists selector_registry (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id) on delete cascade,
                    logical_name text not null,
                    description text not null,
                    selector_type text not null,
                    selector text not null,
                    fallback_selectors_json text not null,
                    assertions_json text not null,
                    confidence real not null,
                    last_verified_at text,
                    failure_count integer not null default 0,
                    unique(skill_id, logical_name)
                );

                create table if not exists handler_registry (
                    id integer primary key autoincrement,
                    name text not null unique,
                    description text not null,
                    module text not null,
                    function text not null,
                    input_schema_json text not null,
                    output_schema_json text not null,
                    allowed_domains_json text not null
                );

                create table if not exists workflow_runs (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id),
                    version_id integer not null references workflow_skill_versions(id),
                    user_request text not null,
                    input_json text not null,
                    status text not null,
                    llm_used integer not null,
                    llm_reason text,
                    started_at text not null default current_timestamp,
                    finished_at text,
                    duration_ms integer,
                    output_json text,
                    report_path text
                );

                create table if not exists step_runs (
                    id integer primary key autoincrement,
                    run_id integer not null references workflow_runs(id) on delete cascade,
                    step_id integer not null references workflow_skill_steps(id),
                    status text not null,
                    input_json text not null,
                    output_json text,
                    evidence_json text,
                    error_json text,
                    started_at text not null default current_timestamp,
                    finished_at text,
                    duration_ms integer
                );

                create table if not exists artifacts (
                    id integer primary key autoincrement,
                    run_id integer not null references workflow_runs(id) on delete cascade,
                    step_run_id integer references step_runs(id) on delete set null,
                    artifact_type text not null,
                    path text not null,
                    metadata_json text not null
                );

                create table if not exists skill_update_events (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id) on delete cascade,
                    from_version_id integer references workflow_skill_versions(id),
                    to_version_id integer references workflow_skill_versions(id),
                    run_id integer references workflow_runs(id),
                    update_type text not null,
                    reason text not null,
                    diff_json text not null,
                    approved_by text,
                    created_at text not null default current_timestamp
                );

                create table if not exists cold_init_runs (
                    id integer primary key autoincrement,
                    user_request text not null,
                    input_json text not null,
                    status text not null,
                    discovery_provider text not null,
                    discovery_duration_ms integer,
                    synthesis_duration_ms integer,
                    synthesis_run_id integer references workflow_synthesis_runs(id),
                    materialization_duration_ms integer,
                    first_run_duration_ms integer,
                    created_skill_id integer references workflow_skills(id),
                    created_version_id integer references workflow_skill_versions(id),
                    workflow_run_id integer references workflow_runs(id),
                    error_json text,
                    started_at text not null default current_timestamp,
                    finished_at text
                );

                create table if not exists workflow_synthesis_runs (
                    id integer primary key autoincrement,
                    user_request text not null,
                    trace_json text not null,
                    status text not null,
                    synthesizer_provider text not null,
                    synthesizer_model text not null,
                    llm_used integer not null,
                    duration_ms integer,
                    output_skill_json text,
                    error_json text,
                    started_at text not null default current_timestamp,
                    finished_at text
                );

                create table if not exists workflow_update_proposals (
                    id integer primary key autoincrement,
                    skill_id integer not null references workflow_skills(id) on delete cascade,
                    base_version_id integer not null references workflow_skill_versions(id),
                    proposed_version integer not null,
                    instruction text not null,
                    discovery_provider text not null,
                    synthesizer_provider text not null,
                    synthesizer_model text not null,
                    status text not null,
                    proposed_workflow_json text not null,
                    diff_json text not null,
                    evidence_json text not null,
                    synthesis_duration_ms integer,
                    error_json text,
                    applied_version_id integer references workflow_skill_versions(id),
                    approved_by text,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp
                );
                """
            )
            _ensure_column(conn, "workflow_runs", "duration_ms", "integer")
            _ensure_column(conn, "step_runs", "duration_ms", "integer")
            _ensure_column(conn, "cold_init_runs", "synthesis_duration_ms", "integer")
            _ensure_column(conn, "cold_init_runs", "synthesis_run_id", "integer references workflow_synthesis_runs(id)")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as conn:
            cursor = conn.execute(sql, tuple(params))
            return int(cursor.lastrowid)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"pragma table_info({table})")}
    if column not in existing:
        conn.execute(f"alter table {table} add column {column} {definition}")
