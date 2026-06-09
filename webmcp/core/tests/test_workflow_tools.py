from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from webworkflows.executor import WorkflowExecutor
from webworkflows.evolver import WorkflowSkillEvolver
from webworkflows.cold_init import (
    ColdInitRunner,
    IntelligentColdInitRunner,
    StaticDiscoveryRunner,
    StaticTraceCollector,
)
from webworkflows.loader import WorkflowSkillLoader
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.synthesis import (
    AgentJsonSynthesisBackend,
    DEFAULT_CODEX_SYNTHESIS_MODEL,
    FakeSynthesisBackend,
    LLMWorkflowSynthesizer,
    naver_stock_workflow_json,
)
from webworkflows.storage import WorkflowSkillStore


NAVER_STOCK_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
295,500원
전일대비 하락 33,500 (-10.18%)
KRX 06.08. 16:10 장마감
관련 뉴스
삼성전자와 SK하이닉스가 반도체 업황 변동으로 하락했다.
"""
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "naver_stock_text.txt"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class WorkflowSkillStoreTest(unittest.TestCase):
    def test_seed_creates_skill_like_metadata_and_lazy_version_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            loader = WorkflowSkillLoader(store)
            candidates = loader.search("네이버에서 삼성전자 주가 검색해서 리포트 써줘")

            self.assertGreaterEqual(len(candidates), 1)
            self.assertEqual("naver_stock_report", candidates[0]["name"])
            self.assertIn("description", candidates[0])
            self.assertNotIn("steps", candidates[0])

            skill = loader.load_skill(candidates[0]["id"])

            self.assertEqual("naver_stock_report", skill.name)
            self.assertEqual("company_name", skill.arguments[0].name)
            self.assertGreaterEqual(len(skill.steps), 5)
            self.assertEqual("open_naver_stock_search", skill.steps[0].name)
            self.assertIn("stock_report_markdown", skill.resources)

    def test_seed_restores_distinct_stock_report_examples_for_existing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            with sqlite3.connect(db_path) as conn:
                skill_id = conn.execute(
                    "select id from workflow_tools where name = ?",
                    ("naver_stock_report",),
                ).fetchone()[0]
                conn.execute(
                    "delete from workflow_tool_examples where skill_id = ? and user_request != ?",
                    (skill_id, "네이버에서 삼성전자 주가 리포트"),
                )
                conn.execute(
                    """
                    insert into workflow_tool_examples
                      (skill_id, user_request, normalized_arguments_json, expected_output_summary)
                    values (?, ?, ?, ?)
                    """,
                    (
                        skill_id,
                        "네이버에서 삼성전자 주가 리포트 iter duplicate",
                        canonical_json({"company_name": "삼성전자", "ticker": "005930", "news_limit": 3}),
                        "Markdown stock report",
                    ),
                )

            seed_naver_stock_report(store)

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    """
                    select normalized_arguments_json
                    from workflow_tool_examples
                    where skill_id = ?
                    """,
                    (skill_id,),
                ).fetchall()

            distinct_examples = {
                canonical_json(json.loads(row[0]))
                for row in rows
            }
            self.assertIn(
                canonical_json({"company_name": "삼성전자", "ticker": "005930", "news_limit": 3}),
                distinct_examples,
            )
            self.assertIn(
                canonical_json({"company_name": "SK하이닉스", "ticker": "000660", "news_limit": 3}),
                distinct_examples,
            )
            self.assertIn(
                canonical_json({"company_name": "NAVER", "ticker": "035420", "news_limit": 3}),
                distinct_examples,
            )

    def test_executor_runs_seeded_skill_without_llm_and_records_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            loader = WorkflowSkillLoader(store)
            skill = loader.load_skill(loader.search("삼성전자 주가 리포트")[0]["id"])
            executor = WorkflowExecutor(store, output_dir=output_dir)

            result = executor.run(
                skill,
                user_request="삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": NAVER_STOCK_TEXT,
                },
            )

            self.assertFalse(result.llm_used)
            self.assertEqual("succeeded", result.status)
            self.assertEqual("삼성전자", result.output["company_name"])
            self.assertEqual("005930", result.output["ticker"])
            self.assertEqual(295500, result.output["current_price"])
            self.assertIn("삼성전자 주가 리포트", result.report_text)
            self.assertTrue(Path(result.report_path).exists())

            with sqlite3.connect(db_path) as conn:
                run_count = conn.execute("select count(*) from workflow_runs").fetchone()[0]
                step_count = conn.execute("select count(*) from step_runs").fetchone()[0]
                run_duration_ms = conn.execute("select duration_ms from workflow_runs").fetchone()[0]
                step_durations = [
                    row[0] for row in conn.execute("select duration_ms from step_runs order by id")
                ]

            self.assertEqual(1, run_count)
            self.assertEqual(len(skill.steps), step_count)
            self.assertIsInstance(run_duration_ms, int)
            self.assertGreaterEqual(run_duration_ms, 0)
            self.assertEqual(len(skill.steps), len(step_durations))
            self.assertTrue(all(isinstance(value, int) and value >= 0 for value in step_durations))

    def test_executor_fails_fast_when_required_argument_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            skill = WorkflowSkillLoader(store).load_skill_by_name("naver_stock_report")

            executor = WorkflowExecutor(store, output_dir=Path(tmp) / "runs")

            with self.assertRaises(ValueError) as ctx:
                executor.run(
                    skill,
                    user_request="주가 리포트",
                    arguments={"page_text": NAVER_STOCK_TEXT},
                )

            self.assertIn("company_name", str(ctx.exception))

    def test_executor_marks_run_failed_when_evaluation_loop_crashes(self) -> None:
        class CrashingEvaluationLoop:
            def run(self, **_kwargs: object) -> None:
                raise RuntimeError("browser monitor crashed")

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            skill = WorkflowSkillLoader(store).load_skill_by_name("naver_stock_report")

            executor = WorkflowExecutor(
                store,
                output_dir=Path(tmp) / "runs",
                evaluation_loop=CrashingEvaluationLoop(),
            )

            with self.assertRaisesRegex(RuntimeError, "browser monitor crashed"):
                executor.run(
                    skill,
                    user_request="삼성전자 주가 리포트",
                    arguments={
                        "company_name": "삼성전자",
                        "ticker": "005930",
                        "page_text": NAVER_STOCK_TEXT,
                    },
                )

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                run = conn.execute("select status, output_json, finished_at from workflow_runs").fetchone()

            self.assertEqual("failed", run["status"])
            self.assertIsNotNone(run["finished_at"])
            output = json.loads(run["output_json"])
            self.assertEqual("unexpected_workflow_error", output["error_type"])
            self.assertEqual("RuntimeError", output["exception_type"])

    def test_cli_seeds_and_runs_workflow_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "run",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--request",
                    "네이버에서 삼성전자 주가 리포트",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(FIXTURE_PATH),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("naver_stock_report", completed.stdout)
            self.assertIn("295500", completed.stdout)
            self.assertTrue((output_dir / "run_삼성전자_report.md").exists())

    def test_loader_can_load_a_specific_workflow_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            loader = WorkflowSkillLoader(store)
            skill_v1 = loader.load_skill_by_name("naver_stock_report")
            result = WorkflowExecutor(store, output_dir=output_dir).run(
                skill_v1,
                user_request="삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": NAVER_STOCK_TEXT,
                },
            )
            WorkflowSkillEvolver(store).record_update(
                skill=skill_v1,
                run_id=result.run_id,
                update_type="new_example",
                reason="Observed successful request.",
                diff={"example": "삼성전자 주가 리포트"},
            )

            loaded_v1 = loader.load_skill_version("naver_stock_report", 1)
            loaded_v2 = loader.load_skill_version("naver_stock_report", 2)

            self.assertEqual(1, loaded_v1.version)
            self.assertEqual(2, loaded_v2.version)
            self.assertNotEqual(loaded_v1.version_id, loaded_v2.version_id)

    def test_cli_runs_specific_workflow_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "run-version",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--workflow-name",
                    "naver_stock_report",
                    "--version",
                    "1",
                    "--request",
                    "네이버에서 삼성전자 주가 리포트",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(FIXTURE_PATH),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual("naver_stock_report", payload["workflow"])
            self.assertEqual(1, payload["workflow_version"])
            self.assertEqual("succeeded", payload["status"])

    def test_cli_resolves_live_page_text_with_browser_trace_collector(self) -> None:
        from webworkflows.cli import resolve_run_page_text

        args = SimpleNamespace(
            page_text_file=None,
            live_page_text=True,
            output_dir="/tmp/webmcp-live-test",
            headed=False,
            request="네이버에서 삼성전자 주가 리포트",
            company_name="삼성전자",
            ticker="005930",
        )

        trace = SimpleNamespace(
            page_text="삼성전자\n현재가\n310,500원",
            provider="naver_browser_trace",
            final_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
            title="삼성전자 주가 : 네이버 검색",
            screenshots=["/tmp/webmcp-live-test/discovery_screenshots/live.png"],
        )
        with patch("webworkflows.cli.NaverBrowserTraceCollector") as collector_cls:
            collector_cls.return_value.collect.return_value = trace
            page_text, evidence = resolve_run_page_text(args)

        self.assertIn("310,500원", page_text)
        self.assertEqual("live_naver_browser", evidence["source"])
        self.assertEqual(trace.final_url, evidence["final_url"])
        collector_cls.assert_called_once_with(output_dir=args.output_dir, headed=False)

    def test_cli_proposes_and_applies_workflow_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            workflow_json_path = Path(tmp) / "proposal.json"
            proposed = naver_stock_workflow_json()
            proposed["body_md"] = proposed["body_md"] + "\n\nInclude valuation metrics in the report."
            proposed["summary"] = "Add valuation metrics."
            proposed["output_schema"]["valuation_summary"] = "string"
            proposed["resources"][0]["content_text"] = (
                proposed["resources"][0]["content_text"]
                + "\n## 밸류에이션\n{{valuation_summary}}\n"
            )
            workflow_json_path.write_text(json.dumps(proposed, ensure_ascii=False), encoding="utf-8")

            propose_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "propose-update",
                    "--db",
                    str(db_path),
                    "--workflow-name",
                    "naver_stock_report",
                    "--base-version",
                    "1",
                    "--instruction",
                    "리포트에 PER/PBR 같은 밸류에이션 섹션을 추가해줘",
                    "--synthesizer",
                    "agent-json",
                    "--workflow-json-file",
                    str(workflow_json_path),
                    "--page-text-file",
                    str(FIXTURE_PATH),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            proposal_payload = json.loads(propose_completed.stdout)
            self.assertEqual("draft", proposal_payload["status"])
            self.assertEqual(1, proposal_payload["base_version"])
            self.assertEqual(2, proposal_payload["proposed_version"])
            self.assertIn("resources_changed", proposal_payload["diff"])
            self.assertGreaterEqual(proposal_payload["proposal_id"], 1)

            apply_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "apply-proposal",
                    "--db",
                    str(db_path),
                    "--proposal-id",
                    str(proposal_payload["proposal_id"]),
                    "--approved-by",
                    "desktop-test",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            apply_payload = json.loads(apply_completed.stdout)
            self.assertEqual("applied", apply_payload["status"])
            self.assertEqual(2, apply_payload["applied_version"])

            store = WorkflowSkillStore(db_path)
            loaded = WorkflowSkillLoader(store).load_skill_version("naver_stock_report", 2)
            self.assertEqual(2, loaded.version)
            self.assertIn("밸류에이션", loaded.resources["stock_report_markdown"])

    def test_cli_cold_init_creates_skill_and_records_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "cold-init",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--request",
                    "네이버에서 삼성전자 주가 리포트",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(FIXTURE_PATH),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("cold_init_run_id", completed.stdout)
            self.assertIn("discovery_duration_ms", completed.stdout)
            self.assertIn("first_run_duration_ms", completed.stdout)
            self.assertTrue((output_dir / "run_삼성전자_report.md").exists())

            with sqlite3.connect(db_path) as conn:
                cold_count = conn.execute("select count(*) from cold_init_runs").fetchone()[0]
                skill_count = conn.execute("select count(*) from workflow_tools").fetchone()[0]

            self.assertEqual(1, cold_count)
            self.assertEqual(1, skill_count)

    def test_cli_intelligent_cold_init_defaults_to_gpt_55_model_with_fake_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "intelligent-cold-init",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--request",
                    "네이버에서 삼성전자 주가 리포트",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(FIXTURE_PATH),
                    "--synthesizer",
                    "fake-naver-stock",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("intelligent_cold_init", completed.stdout)
            self.assertIn("gpt-5.5", completed.stdout)
            self.assertTrue((output_dir / "run_삼성전자_report.md").exists())

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                synthesis_run = conn.execute("select * from workflow_synthesis_runs").fetchone()

            self.assertEqual("gpt-5.5", synthesis_run["synthesizer_model"])
            self.assertEqual(1, synthesis_run["llm_used"])

    def test_evolver_creates_new_skill_version_and_update_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)

            loader = WorkflowSkillLoader(store)
            skill_v1 = loader.load_skill_by_name("naver_stock_report")
            result = WorkflowExecutor(store, output_dir=output_dir).run(
                skill_v1,
                user_request="삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": NAVER_STOCK_TEXT,
                },
            )

            new_version_id = WorkflowSkillEvolver(store).record_update(
                skill=skill_v1,
                run_id=result.run_id,
                update_type="new_example",
                reason="Observed successful Samsung Electronics request.",
                diff={
                    "example": "삼성전자 주가 리포트",
                    "normalized_arguments": {"company_name": "삼성전자", "ticker": "005930"},
                },
            )
            skill_v2 = loader.load_skill_by_name("naver_stock_report")

            self.assertNotEqual(skill_v1.version_id, new_version_id)
            self.assertEqual(2, skill_v2.version)
            self.assertEqual(new_version_id, skill_v2.version_id)

            with sqlite3.connect(db_path) as conn:
                event_count = conn.execute("select count(*) from workflow_tool_update_events").fetchone()[0]
                version_count = conn.execute("select count(*) from workflow_tool_versions").fetchone()[0]

            self.assertEqual(1, event_count)
            self.assertEqual(2, version_count)

    def test_cold_init_creates_skill_from_discovery_without_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()

            runner = ColdInitRunner(
                store,
                output_dir=output_dir,
                discovery_runner=StaticDiscoveryRunner(page_text=NAVER_STOCK_TEXT),
            )
            result = runner.run(
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
            )

            self.assertEqual("succeeded", result.run_result.status)
            self.assertEqual("naver_stock_report", result.skill.name)
            self.assertEqual(1, result.skill.version)
            self.assertGreaterEqual(result.discovery_duration_ms, 0)
            self.assertGreaterEqual(result.materialization_duration_ms, 0)
            self.assertGreaterEqual(result.first_run_duration_ms, 0)
            self.assertFalse(result.run_result.llm_used)

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cold_run = conn.execute("select * from cold_init_runs").fetchone()
                skill_count = conn.execute("select count(*) from workflow_tools").fetchone()[0]
                version_count = conn.execute("select count(*) from workflow_tool_versions").fetchone()[0]

            self.assertEqual(1, skill_count)
            self.assertEqual(1, version_count)
            self.assertEqual("succeeded", cold_run["status"])
            self.assertEqual(1, cold_run["created_skill_id"])
            self.assertEqual(1, cold_run["created_version_id"])
            self.assertIsInstance(cold_run["discovery_duration_ms"], int)
            self.assertIsInstance(cold_run["materialization_duration_ms"], int)
            self.assertIsInstance(cold_run["first_run_duration_ms"], int)

    def test_llm_synthesizer_defaults_to_gpt_55_model(self) -> None:
        backend = FakeSynthesisBackend(response=naver_stock_workflow_json())
        synthesizer = LLMWorkflowSynthesizer(backend=backend)
        trace = StaticTraceCollector(page_text=NAVER_STOCK_TEXT).collect(
            "네이버에서 삼성전자 주가 리포트",
            {"company_name": "삼성전자", "ticker": "005930"},
        )

        discovery = synthesizer.synthesize(trace)

        self.assertEqual(DEFAULT_CODEX_SYNTHESIS_MODEL, backend.last_model)
        self.assertEqual("gpt-5.5", synthesizer.model)
        self.assertEqual("llm_fake", discovery.provider)
        self.assertEqual("naver_stock_report", discovery.skill_name)
        self.assertEqual("extract_stock_card", discovery.steps[2]["name"])

    def test_llm_synthesizer_binds_known_handler_registry_entries(self) -> None:
        workflow_json = naver_stock_workflow_json()
        workflow_json["handlers"] = [
            {
                "name": "extract_stock_card",
                "description": "Parse a Naver stock card.",
                "module": "naver_stock",
                "function": "extract_stock_card",
                "input_schema": {"page_text": "string", "company_name": "string", "ticker": "string"},
                "output_schema": {"company_name": "string", "current_price": "string"},
                "allowed_domains": ["search.naver.com"],
            }
        ]
        backend = FakeSynthesisBackend(response=workflow_json)
        trace = StaticTraceCollector(page_text=NAVER_STOCK_TEXT).collect(
            "네이버에서 삼성전자 주가 리포트",
            {"company_name": "삼성전자", "ticker": "005930"},
        )

        discovery = LLMWorkflowSynthesizer(backend=backend).synthesize(trace)

        self.assertEqual("naver_stock.extract_stock_card", discovery.handlers[0]["name"])
        self.assertEqual("webworkflows.handlers.naver_stock", discovery.handlers[0]["module"])

    def test_agent_json_synthesizer_loads_current_agent_workflow_without_codex_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(naver_stock_workflow_json(), ensure_ascii=False), encoding="utf-8")
            backend = AgentJsonSynthesisBackend(workflow_json_path=workflow_path)
            trace = StaticTraceCollector(page_text=NAVER_STOCK_TEXT).collect(
                "네이버에서 삼성전자 주가 리포트",
                {"company_name": "삼성전자", "ticker": "005930"},
            )

            discovery = LLMWorkflowSynthesizer(backend=backend).synthesize(trace)

            self.assertEqual(DEFAULT_CODEX_SYNTHESIS_MODEL, backend.last_model)
            self.assertIn("WebMCP workflow JSON", backend.last_prompt)
            self.assertEqual("llm_agent_json", discovery.provider)
            self.assertEqual("naver_stock_report", discovery.skill_name)
            self.assertEqual("naver_stock.extract_stock_card", discovery.handlers[0]["name"])

    def test_intelligent_cold_init_uses_llm_synthesizer_and_records_gpt_55_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            synthesizer = LLMWorkflowSynthesizer(
                backend=FakeSynthesisBackend(response=naver_stock_workflow_json())
            )

            result = IntelligentColdInitRunner(
                store,
                output_dir=output_dir,
                trace_collector=StaticTraceCollector(page_text=NAVER_STOCK_TEXT),
                synthesizer=synthesizer,
            ).run(
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
            )

            self.assertEqual("succeeded", result.run_result.status)
            self.assertEqual("naver_stock_report", result.skill.name)
            self.assertGreaterEqual(result.synthesis_duration_ms, 0)
            self.assertFalse(result.run_result.llm_used)

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                synthesis_run = conn.execute("select * from workflow_synthesis_runs").fetchone()
                cold_run = conn.execute("select * from cold_init_runs").fetchone()

            self.assertEqual("succeeded", synthesis_run["status"])
            self.assertEqual("gpt-5.5", synthesis_run["synthesizer_model"])
            self.assertEqual(1, synthesis_run["llm_used"])
            self.assertIsInstance(synthesis_run["duration_ms"], int)
            self.assertEqual(synthesis_run["id"], cold_run["synthesis_run_id"])
            self.assertIsInstance(cold_run["synthesis_duration_ms"], int)

    def test_cli_intelligent_cold_init_accepts_agent_json_without_nested_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(naver_stock_workflow_json(), ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "intelligent-cold-init",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--request",
                    "네이버에서 삼성전자 주가 리포트",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(FIXTURE_PATH),
                    "--synthesizer",
                    "agent-json",
                    "--workflow-json-file",
                    str(workflow_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("llm_agent_json", completed.stdout)
            self.assertNotIn("llm_codex_cli", completed.stdout)
            self.assertTrue((output_dir / "run_삼성전자_report.md").exists())

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                synthesis_run = conn.execute("select * from workflow_synthesis_runs").fetchone()

            self.assertEqual("llm_agent_json", synthesis_run["synthesizer_provider"])
            self.assertEqual("gpt-5.5", synthesis_run["synthesizer_model"])
            self.assertEqual(1, synthesis_run["llm_used"])


if __name__ == "__main__":
    unittest.main()
