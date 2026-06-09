from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from webworkflows.page_memory import canonical_url_without_query, normalize_url_key
from webworkflows.storage import WorkflowSkillStore, default_studio_db_path, dumps, loads


RECORD_TYPES = ("workflow_example", "page_analysis", "knowledge")
DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "workflow-memory"


@dataclass
class SyncResult:
    db_path: Path
    fixture_dir: Path
    dry_run: bool = False
    inserted: Counter[str] = field(default_factory=Counter)
    updated: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, object]:
        return {
            "db_path": str(self.db_path),
            "fixture_dir": str(self.fixture_dir),
            "dry_run": self.dry_run,
            "inserted": dict(self.inserted),
            "updated": dict(self.updated),
            "skipped": dict(self.skipped),
        }


def sync_workflow_memory(
    *,
    db_path: str | Path | None = None,
    fixture_dir: str | Path | None = None,
    dry_run: bool = False,
    only: Iterable[str] | None = None,
    tag: str | None = None,
) -> SyncResult:
    target_db = Path(db_path) if db_path is not None else default_studio_db_path()
    target_fixtures = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR
    selected_types = set(only or RECORD_TYPES)
    unknown_types = selected_types.difference(RECORD_TYPES)
    if unknown_types:
        raise ValueError(f"unknown fixture type: {', '.join(sorted(unknown_types))}")

    store = WorkflowSkillStore(target_db)
    store.initialize()

    result = SyncResult(db_path=target_db, fixture_dir=target_fixtures, dry_run=dry_run)
    records = list(load_fixture_records(target_fixtures))

    with store.connect() as conn:
        for record in records:
            record_type = str(record.get("type") or "")
            if record_type not in selected_types:
                continue
            if tag and not record_matches_tag(record, tag):
                continue
            if record_type == "workflow_example":
                sync_workflow_example(conn, record, result, dry_run=dry_run)
            elif record_type == "page_analysis":
                sync_page_analysis(conn, record, result, dry_run=dry_run)
            elif record_type == "knowledge":
                sync_knowledge(conn, record, result, dry_run=dry_run)
            else:
                result.skipped["unknown_type"] += 1

    return result


def load_fixture_records(fixture_dir: Path) -> Iterable[dict[str, Any]]:
    if not fixture_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(fixture_dir.glob("*.jsonl")):
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {error}") from error
            if not isinstance(record, dict):
                raise ValueError(f"fixture record must be an object at {path}:{line_number}")
            record["_fixture_path"] = str(path)
            record["_fixture_line"] = line_number
            records.append(record)
    return records


def sync_workflow_example(conn: Any, record: dict[str, Any], result: SyncResult, *, dry_run: bool) -> None:
    workflow_name = required_string(record, "workflow_name")
    skill = conn.execute(
        "select id, latest_version_id from workflow_skills where name = ?",
        (workflow_name,),
    ).fetchone()
    if not skill:
        result.skipped["missing_workflow"] += 1
        return

    arguments = required_dict(record, "normalized_arguments")
    arguments_json = dumps(arguments)
    existing = conn.execute(
        """
        select id
        from workflow_skill_examples
        where skill_id = ? and normalized_arguments_json = ?
        """,
        (skill["id"], arguments_json),
    ).fetchone()

    if existing:
        result.updated["workflow_example"] += 1
        if not dry_run:
            conn.execute(
                """
                update workflow_skill_examples
                set user_request = ?, expected_output_summary = ?
                where id = ?
                """,
                (
                    required_string(record, "user_request"),
                    required_string(record, "expected_output_summary"),
                    existing["id"],
                ),
            )
    else:
        result.inserted["workflow_example"] += 1
        if not dry_run:
            conn.execute(
                """
                insert into workflow_skill_examples
                  (skill_id, user_request, normalized_arguments_json, expected_output_summary)
                values (?, ?, ?, ?)
                """,
                (
                    skill["id"],
                    required_string(record, "user_request"),
                    arguments_json,
                    required_string(record, "expected_output_summary"),
                ),
            )

    if not dry_run and skill["latest_version_id"] is not None:
        merge_argument_examples(conn, int(skill["latest_version_id"]), arguments)


def merge_argument_examples(conn: Any, version_id: int, arguments: dict[str, Any]) -> None:
    for name, value in arguments.items():
        row = conn.execute(
            """
            select id, examples_json
            from workflow_skill_arguments
            where version_id = ? and name = ?
            """,
            (version_id, name),
        ).fetchone()
        if not row:
            continue
        examples = loads(row["examples_json"], [])
        if not isinstance(examples, list):
            examples = []
        if any(dumps(existing) == dumps(value) for existing in examples):
            continue
        examples.append(value)
        conn.execute(
            "update workflow_skill_arguments set examples_json = ? where id = ?",
            (dumps(examples), row["id"]),
        )


def sync_page_analysis(conn: Any, record: dict[str, Any], result: SyncResult, *, dry_run: bool) -> None:
    original_url = required_string(record, "original_url")
    url_key = normalize_url_key(original_url)
    canonical_url = canonical_url_without_query(original_url)
    existing = conn.execute("select id from page_analyses where url_key = ?", (url_key,)).fetchone()
    values = (
        canonical_url,
        original_url,
        string_value(record.get("title")),
        dumps(list_value(record.get("framework_hints"))),
        dumps(list_value(record.get("frame_hints"))),
        dumps(list_value(record.get("locator_hints"))),
        dumps(dict_value(record.get("analysis"))),
        dumps(dict_value(record.get("evidence"))),
        string_value(record.get("source")) or "fixture",
    )

    if existing:
        result.updated["page_analysis"] += 1
        if not dry_run:
            conn.execute(
                """
                update page_analyses
                set canonical_url = ?, original_url = ?, title = ?,
                    framework_hints_json = ?, frame_hints_json = ?, locator_hints_json = ?,
                    analysis_json = ?, evidence_json = ?, source = ?,
                    updated_at = current_timestamp,
                    last_seen_at = current_timestamp
                where id = ?
                """,
                (*values, existing["id"]),
            )
    else:
        result.inserted["page_analysis"] += 1
        if not dry_run:
            conn.execute(
                """
                insert into page_analyses
                  (url_key, canonical_url, original_url, title,
                   framework_hints_json, frame_hints_json, locator_hints_json,
                   analysis_json, evidence_json, source)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (url_key, *values),
            )


def sync_knowledge(conn: Any, record: dict[str, Any], result: SyncResult, *, dry_run: bool) -> None:
    category = required_string(record, "category")
    summary = required_string(record, "summary")
    existing = conn.execute(
        """
        select id
        from workflow_knowledge_entries
        where category = ? and summary = ?
        """,
        (category, summary),
    ).fetchone()
    values = (
        dumps(dict_value(record.get("content"))),
        string_value(record.get("source")) or "fixture",
        float(record.get("confidence", 0.5)),
        dumps(list_value(record.get("tags"))),
    )

    if existing:
        result.updated["knowledge"] += 1
        if not dry_run:
            conn.execute(
                """
                update workflow_knowledge_entries
                set content_json = ?, source = ?, confidence = ?, tags_json = ?
                where id = ?
                """,
                (*values, existing["id"]),
            )
    else:
        result.inserted["knowledge"] += 1
        if not dry_run:
            conn.execute(
                """
                insert into workflow_knowledge_entries
                  (category, summary, content_json, source, confidence, tags_json)
                values (?, ?, ?, ?, ?, ?)
                """,
                (category, summary, *values),
            )


def record_matches_tag(record: dict[str, Any], tag: str) -> bool:
    normalized = tag.strip().lower()
    if not normalized:
        return True
    tags = [str(item).lower() for item in list_value(record.get("tags"))]
    return (
        normalized in tags
        or normalized in str(record.get("workflow_name", "")).lower()
        or normalized in str(record.get("category", "")).lower()
        or normalized in str(record.get("original_url", "")).lower()
    )


def required_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string in {fixture_location(record)}")
    return value.strip()


def required_dict(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object in {fixture_location(record)}")
    return value


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def fixture_location(record: dict[str, Any]) -> str:
    path = record.get("_fixture_path", "<memory>")
    line = record.get("_fixture_line", "?")
    return f"{path}:{line}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync reviewed WebMCP workflow memory fixtures into SQLite.")
    parser.add_argument("--db", default=None, help="SQLite DB path. Defaults to WEBMCP_STUDIO_DB_PATH or ~/.webmcp-studio/db/workflows.sqlite.")
    parser.add_argument("--fixture-dir", default=str(DEFAULT_FIXTURE_DIR), help="Directory containing *.jsonl memory fixtures.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing rows.")
    parser.add_argument("--only", action="append", choices=RECORD_TYPES, help="Sync only this fixture type. Can be repeated.")
    parser.add_argument("--tag", help="Sync only records matching this tag/category/workflow/url token.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args(argv)

    result = sync_workflow_memory(
        db_path=args.db,
        fixture_dir=args.fixture_dir,
        dry_run=args.dry_run,
        only=args.only,
        tag=args.tag,
    )
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(format_summary(result))
    return 0


def format_summary(result: SyncResult) -> str:
    lines = [
        f"db: {result.db_path}",
        f"fixtures: {result.fixture_dir}",
        f"dry_run: {str(result.dry_run).lower()}",
    ]
    for label, counter in (
        ("inserted", result.inserted),
        ("updated", result.updated),
        ("skipped", result.skipped),
    ):
        values = ", ".join(f"{key}={counter[key]}" for key in sorted(counter))
        lines.append(f"{label}: {values or 'none'}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
