from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.sync_workflow_memory import sync_workflow_memory
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.storage import WorkflowSkillStore, dumps


class WorkflowMemorySyncTest(unittest.TestCase):
    def test_syncs_jsonl_fixtures_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "workflows.sqlite"
            fixture_dir = tmp_path / "fixtures"
            fixture_dir.mkdir()

            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            write_jsonl(
                fixture_dir / "examples.jsonl",
                [
                    {
                        "type": "workflow_example",
                        "workflow_name": "naver_stock_report",
                        "user_request": "네이버에서 카카오 주가 리포트",
                        "normalized_arguments": {
                            "company_name": "카카오",
                            "ticker": "035720",
                            "news_limit": 2,
                        },
                        "expected_output_summary": "Kakao stock markdown report",
                    },
                    {
                        "type": "workflow_example",
                        "workflow_name": "missing_workflow",
                        "user_request": "missing",
                        "normalized_arguments": {"start_url": "https://example.com"},
                        "expected_output_summary": "Skipped",
                    },
                ],
            )
            write_jsonl(
                fixture_dir / "page_analyses.jsonl",
                [
                    {
                        "type": "page_analysis",
                        "original_url": "https://search.naver.com/search.naver?query=카카오%20주가#stock",
                        "title": "카카오 주가 : 네이버 검색",
                        "framework_hints": ["naver_search"],
                        "frame_hints": [],
                        "locator_hints": ["prefer_text_markers"],
                        "analysis": {"page_type": "naver_stock_search_result"},
                        "evidence": {"markers": ["증권정보", "현재가", "035720"]},
                        "source": "fixture_test",
                    }
                ],
            )
            write_jsonl(
                fixture_dir / "knowledge.jsonl",
                [
                    {
                        "type": "knowledge",
                        "category": "script_generation",
                        "summary": "Prefer direct Naver stock search URLs",
                        "content": {"url_shape": "https://search.naver.com/search.naver?query={{company_name}} 주가"},
                        "source": "fixture_test",
                        "confidence": 0.93,
                        "tags": ["naver", "stock"],
                    }
                ],
            )

            first = sync_workflow_memory(db_path=db_path, fixture_dir=fixture_dir)
            second = sync_workflow_memory(db_path=db_path, fixture_dir=fixture_dir)

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                skill_id = conn.execute(
                    "select id from workflow_skills where name = ?",
                    ("naver_stock_report",),
                ).fetchone()["id"]
                example_rows = conn.execute(
                    """
                    select *
                    from workflow_skill_examples
                    where skill_id = ? and normalized_arguments_json = ?
                    """,
                    (
                        skill_id,
                        dumps({"company_name": "카카오", "ticker": "035720", "news_limit": 2}),
                    ),
                ).fetchall()
                page_rows = conn.execute(
                    "select * from page_analyses where url_key = ?",
                    ("search-naver-com-search-naver",),
                ).fetchall()
                knowledge_rows = conn.execute(
                    "select * from workflow_knowledge_entries where category = ? and summary = ?",
                    ("script_generation", "Prefer direct Naver stock search URLs"),
                ).fetchall()
                argument_examples = json.loads(
                    conn.execute(
                        """
                        select examples_json
                        from workflow_skill_arguments
                        where name = ? and version_id = (
                            select latest_version_id from workflow_skills where id = ?
                        )
                        """,
                        ("company_name", skill_id),
                    ).fetchone()["examples_json"]
                )

            self.assertEqual(1, first.inserted["workflow_example"])
            self.assertEqual(1, first.skipped["missing_workflow"])
            self.assertEqual(1, second.updated["workflow_example"])
            self.assertEqual(1, len(example_rows))
            self.assertEqual(1, len(page_rows))
            self.assertEqual("https://search.naver.com/search.naver", page_rows[0]["canonical_url"])
            self.assertEqual(1, len(knowledge_rows))
            self.assertIn("카카오", argument_examples)

    def test_dry_run_reports_without_mutating_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "workflows.sqlite"
            fixture_dir = tmp_path / "fixtures"
            fixture_dir.mkdir()

            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            write_jsonl(
                fixture_dir / "knowledge.jsonl",
                [
                    {
                        "type": "knowledge",
                        "category": "script_generation",
                        "summary": "Dry run knowledge",
                        "content": {"tip": "do not write"},
                        "source": "fixture_test",
                        "confidence": 0.5,
                        "tags": ["dry-run"],
                    }
                ],
            )

            result = sync_workflow_memory(db_path=db_path, fixture_dir=fixture_dir, dry_run=True)

            with sqlite3.connect(db_path) as conn:
                knowledge_count = conn.execute("select count(*) from workflow_knowledge_entries").fetchone()[0]

            self.assertEqual(1, result.inserted["knowledge"])
            self.assertEqual(0, knowledge_count)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
