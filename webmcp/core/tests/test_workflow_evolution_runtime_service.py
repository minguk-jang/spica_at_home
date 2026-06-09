from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from webworkflows.eval_loop import StepEvaluation, WorkflowEvaluationReport
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.services.evolution_runtime import WorkflowEvolutionRuntime
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import naver_stock_workflow_json


LIVE_PAGE_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
310,500원
전일대비 상승 4,500 (+1.47%)
KRX 06.09. 16:10 장마감
"""


class QueueEvalLoop:
    def __init__(self, reports: list[WorkflowEvaluationReport]):
        self.reports = list(reports)
        self.calls: list[dict[str, Any]] = []

    def run(self, *, skill, user_request: str, arguments: dict[str, Any], run_id: int, output_dir: Path):
        self.calls.append(
            {
                "version": skill.version,
                "run_id": run_id,
                "user_request": user_request,
                "arguments": dict(arguments),
                "output_dir": output_dir,
            }
        )
        if not self.reports:
            raise AssertionError("QueueEvalLoop has no remaining reports")
        return self.reports.pop(0)


class WorkflowEvolutionRuntimeServiceTest(unittest.TestCase):
    def test_evolve_records_argument_example_metadata_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            with store.connect() as conn:
                skill_id = int(
                    conn.execute("select id from workflow_skills where name = ?", ("naver_stock_report",)).fetchone()[
                        "id"
                    ]
                )
                conn.execute("delete from workflow_skill_examples where skill_id = ?", (skill_id,))

            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="passed",
                                summary="Stock card is visible.",
                            )
                        ],
                    )
                ]
            )

            payload = WorkflowEvolutionRuntime(store, output_dir=output_dir, evaluation_loop=eval_loop).evolve(
                workflow_name="naver_stock_report",
                base_version=1,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=1,
            )

            self.assertEqual("succeeded", payload["status"])
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                example = conn.execute(
                    """
                    select user_request, normalized_arguments_json, expected_output_summary, success_count
                    from workflow_skill_examples
                    where skill_id = ?
                    """,
                    (skill_id,),
                ).fetchone()

            self.assertIsNotNone(example)
            self.assertEqual("네이버에서 삼성전자 주가 리포트", example["user_request"])
            normalized_args = json.loads(example["normalized_arguments_json"])
            self.assertEqual("삼성전자", normalized_args["company_name"])
            self.assertEqual("005930", normalized_args["ticker"])
            self.assertEqual(1, normalized_args["news_limit"])
            self.assertNotIn("page_text", normalized_args)
            self.assertEqual("Verified eval-and-evolve run", example["expected_output_summary"])
            self.assertEqual(1, example["success_count"])

    def test_evolve_applies_agent_json_repair_and_reruns_until_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            repaired_workflow_path = Path(tmp) / "repaired_workflow.json"
            repaired_workflow = naver_stock_workflow_json()
            repaired_workflow["body_md"] += "\n\nRepair: wait for the live stock card before extraction."
            repaired_workflow_path.write_text(json.dumps(repaired_workflow, ensure_ascii=False), encoding="utf-8")

            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="failed",
                                summary="Stock card did not become visible before extraction.",
                                problems=["stock card missing"],
                                suggested_update="Wait for Naver's stock card text before extracting fields.",
                                failure_kind="missing_expected_ui",
                                expected_state="Naver stock card with 현재가 text is visible.",
                                observed_state="Search page loaded without the expected stock card marker.",
                                repair_focus="wait_stock_card assertion and timing",
                            )
                        ],
                    ),
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="passed",
                                summary="Stock card is visible.",
                            )
                        ],
                    ),
                ]
            )

            payload = WorkflowEvolutionRuntime(store, output_dir=output_dir, evaluation_loop=eval_loop).evolve(
                workflow_name="naver_stock_report",
                base_version=1,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=2,
                repair_synthesizer="agent-json",
                repair_workflow_json_file=repaired_workflow_path,
                synthesizer_model="gpt-5.5",
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual(2, payload["final_version"])
            self.assertEqual(2, payload["attempt_count"])
            self.assertEqual([1, 2], [call["version"] for call in eval_loop.calls])
            self.assertEqual("workflow_evaluation_failed", payload["attempts"][0]["error_type"])
            self.assertEqual("succeeded", payload["attempts"][1]["status"])
            self.assertIn("step_runs", payload["attempts"][1])
            self.assertGreaterEqual(len(payload["attempts"][1]["step_runs"]), 1)
            self.assertIn("duration_ms", payload["attempts"][1]["step_runs"][0])

            repair_request_path = Path(payload["attempts"][0]["repair_request_path"])
            repair_response_path = Path(payload["attempts"][0]["repair_response_path"])
            self.assertTrue(repair_request_path.exists())
            self.assertTrue(repair_response_path.exists())
            repair_request = json.loads(repair_request_path.read_text(encoding="utf-8"))
            self.assertEqual("wait_stock_card", repair_request["evaluation"]["failed_step"]["step_name"])
            self.assertEqual("missing_expected_ui", repair_request["evaluation"]["failed_step"]["failure_kind"])
            self.assertEqual("agent-json", repair_request["response_contract"]["recommended_synthesizer"])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                session = conn.execute("select * from evolution_sessions").fetchone()
                attempts = conn.execute("select * from evolution_attempts order by attempt_index").fetchall()
                repair_request_row = conn.execute("select * from repair_requests").fetchone()
                repair_response_row = conn.execute("select * from repair_responses").fetchone()

            self.assertEqual("succeeded", session["status"])
            self.assertEqual(2, len(attempts))
            self.assertEqual("repair_applied", attempts[0]["status"])
            self.assertEqual("succeeded", attempts[1]["status"])
            self.assertEqual(str(repair_request_path), repair_request_row["request_path"])
            self.assertEqual(str(repair_response_path), repair_response_row["response_path"])

    def test_evolve_stops_with_repair_request_when_agent_response_is_not_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="final",
                                step_type="final",
                                status="failed",
                                summary="Final report omitted the current price.",
                                problems=["missing current price"],
                                suggested_update="Include current_price in the report template.",
                            )
                        ],
                    )
                ]
            )

            payload = WorkflowEvolutionRuntime(store, output_dir=output_dir, evaluation_loop=eval_loop).evolve(
                workflow_name="naver_stock_report",
                base_version=1,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=3,
                repair_synthesizer="agent-json",
                repair_workflow_json_file=None,
            )

            self.assertEqual("waiting_for_repair", payload["status"])
            self.assertEqual(1, payload["attempt_count"])
            self.assertTrue(Path(payload["repair_request_path"]).exists())
            self.assertEqual("final", payload["attempts"][0]["failed_step"]["step_name"])

    def test_evolve_auto_synthesizer_repairs_without_manual_workflow_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="failed",
                                summary="Stock card did not become visible.",
                                problems=["stock card missing"],
                                suggested_update="Wait for the stock card before extraction.",
                            )
                        ],
                    ),
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=LIVE_PAGE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="passed",
                                summary="Stock card is visible.",
                            )
                        ],
                    ),
                ]
            )

            payload = WorkflowEvolutionRuntime(store, output_dir=output_dir, evaluation_loop=eval_loop).evolve(
                workflow_name="naver_stock_report",
                base_version=1,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=2,
                repair_synthesizer="fake-copy",
                repair_workflow_json_file=None,
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual(2, payload["attempt_count"])
            self.assertEqual("repair_applied", payload["attempts"][0]["status"])
            self.assertEqual("succeeded", payload["attempts"][1]["status"])
            self.assertTrue(Path(payload["attempts"][0]["repair_response_path"]).exists())
            self.assertEqual([1, 2], [call["version"] for call in eval_loop.calls])


if __name__ == "__main__":
    unittest.main()
