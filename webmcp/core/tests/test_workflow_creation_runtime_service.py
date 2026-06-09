from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from webworkflows.services.creation_runtime import WorkflowCreationRuntime
from webworkflows.eval_loop import StepEvaluation, WorkflowEvaluationReport
from webworkflows.cold_init import WorkflowMaterializer, discovery_from_workflow_json
from webworkflows.page_memory import PageAnalysisStore, WorkflowKnowledgeStore
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import (
    CodexCliSynthesisBackend,
    FakeSynthesisBackend,
    LLMWorkflowSynthesizer,
    build_synthesis_prompt,
    naver_stock_workflow_json,
)
from webworkflows.update_proposal import build_update_prompt


TRACE_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
295,500원
전일대비 하락 33,500 (-10.18%)
"""

FLIGHT_TEXT = """
Google Flights
SEA to JFK
Sat, Aug 15
Thu, Aug 20
Best departing flights
"""

NAVER_HOME_TEXT = """
NAVER
검색
메일
카페
블로그
쇼핑
뉴스
증권
부동산
지도
웹툰
"""

NAVER_MAP_TRANSIT_TEXT = """
네이버지도
길찾기
대중교통
전체버스 10지하철 1버스 + 지하철 3
최적 경로순
30분
오후 5:07 도착
1,550원
기후동행
도보
7분
3호선지하철
4분
양재역
교대역 방면
도보
1분
2호선지하철
6분
교대역
하차
사당역
상세보기
"""


def generic_flight_workflow_json() -> dict:
    return {
        "skill_name": "flight_search_report",
        "slug": "flight-search-report",
        "description": "Search a flight page and render a report from observed browser text.",
        "domain": "google.com",
        "task_type": "flight_search",
        "body_md": "Workflow created from a browser task creation session.",
        "input_schema": {
            "start_url": {"type": "string", "required": True},
            "page_text": {"type": "string", "required": False},
        },
        "output_schema": {
            "report_text": "string",
        },
        "arguments": [
            {
                "name": "start_url",
                "description": "Initial page URL",
                "type": "string",
                "required": True,
                "default_value": None,
                "validation": {},
                "examples": ["https://www.google.com/flights"],
                "is_dynamic": True,
                "order_index": 0,
            },
            {
                "name": "page_text",
                "description": "Observed browser text",
                "type": "string",
                "required": False,
                "default_value": None,
                "validation": {},
                "examples": [],
                "is_dynamic": True,
                "order_index": 1,
            },
        ],
        "steps": [
            {
                "name": "open_start_url",
                "description": "Open the requested start URL.",
                "step_type": "goto",
                "handler_ref": None,
                "action": {"url_template": "{{start_url}}"},
                "argument_bindings": {},
                "assertions": {"url_contains": "google.com"},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "wait_flight_results",
                "description": "Require flight result text to be present.",
                "step_type": "wait_for_text",
                "handler_ref": None,
                "action": {"source": "page_text"},
                "argument_bindings": {},
                "assertions": {"contains_any": ["Best departing flights", "SEA to JFK"]},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "render_flight_report",
                "description": "Render the observed flight search report.",
                "step_type": "render_report",
                "handler_ref": None,
                "action": {"template_resource": "flight_report_markdown"},
                "argument_bindings": {},
                "assertions": {"required_output": ["report_text"]},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
        ],
        "resources": [
            {
                "resource_type": "report_template",
                "name": "flight_report_markdown",
                "description": "Markdown template for flight search results.",
                "content_json": None,
                "content_text": "# Flight Search Report\n\nStart URL: {{start_url}}\n\n{{page_text}}\n",
                "load_when": {"step": "render_flight_report"},
            }
        ],
        "handlers": [],
    }


class StaticCreateTraceCollector:
    provider = "static_create_trace"

    def __init__(self, page_text: str = TRACE_TEXT):
        self.page_text = page_text

    def collect(self, *, start_url: str, user_task: str, final_state: str, arguments: dict):
        from webworkflows.cold_init_types import ArtifactTrace

        return ArtifactTrace(
            provider=self.provider,
            user_request=user_task,
            arguments={
                **arguments,
                "start_url": start_url,
                "final_state": final_state,
            },
            page_text=self.page_text,
            title="삼성전자 주가 : 네이버 검색",
            final_url=start_url,
            screenshots=[],
        )


class QueueEvalLoop:
    def __init__(self, reports: list[WorkflowEvaluationReport]):
        self.reports = list(reports)
        self.calls: list[dict] = []

    def run(self, *, skill, user_request: str, arguments: dict, run_id: int, output_dir: Path):
        self.calls.append(
            {
                "version": skill.version,
                "version_id": skill.version_id,
                "run_id": run_id,
                "user_request": user_request,
                "arguments": dict(arguments),
                "output_dir": output_dir,
            }
        )
        if not self.reports:
            raise AssertionError("QueueEvalLoop has no remaining reports")
        return self.reports.pop(0)


class FailingSynthesisBackend:
    provider = "failing"

    def synthesize(self, *, prompt: str, schema: dict, model: str) -> dict:
        raise AssertionError("known Naver Map workflow should not call the generic LLM backend")


class RecordingFakeSynthesisBackend(FakeSynthesisBackend):
    def __init__(self, response: dict):
        super().__init__(response=response)
        self.prompts: list[str] = []

    def synthesize(self, *, prompt: str, schema: dict, model: str) -> dict:
        self.prompts.append(prompt)
        return super().synthesize(prompt=prompt, schema=schema, model=model)


class WorkflowCreationRuntimeServiceTest(unittest.TestCase):
    def test_creation_and_update_prompts_require_scriptless_runtime_dynamic_steps(self) -> None:
        from webworkflows.cold_init_types import ArtifactTrace

        trace = ArtifactTrace(
            provider="static_create_trace",
            user_request="광고 팝업을 닫고 본문을 확인하는 워크플로우를 만들어줘.",
            arguments={
                "start_url": "https://example.test/dynamic-ad-demo",
                "final_state": "광고가 닫히고 본문이 보여야 한다.",
            },
            page_text="Article body\nSponsored popup\nClose ad",
            title="Dynamic Ad Demo",
            final_url="https://example.test/dynamic-ad-demo",
            screenshots=[],
        )
        create_prompt = build_synthesis_prompt(trace)
        update_prompt = build_update_prompt(
            base_workflow=generic_flight_workflow_json(),
            instruction="광고 닫기처럼 변할 수 있는 단계는 런타임 LLM 액션으로 바꿔줘.",
            page_text="Sponsored popup Close ad",
            discovery_provider="static",
        )

        for prompt in (create_prompt, update_prompt):
            self.assertIn("llm_browser_action", prompt)
            self.assertIn("Do not store generated JavaScript", prompt)
            self.assertIn("runtime", prompt)

    def test_materializer_reuses_existing_workflow_when_slug_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowSkillStore(Path(tmp) / "workflow_tools.sqlite")
            store.initialize()
            first = generic_flight_workflow_json()
            second = {**generic_flight_workflow_json(), "skill_name": "renamed_flight_search_report"}

            first_ids = WorkflowMaterializer(store).materialize(
                discovery_from_workflow_json(first, provider="test", page_text=FLIGHT_TEXT)
            )
            second_ids = WorkflowMaterializer(store).materialize(
                discovery_from_workflow_json(second, provider="test", page_text=FLIGHT_TEXT)
            )

        self.assertEqual(first_ids, second_ids)

    def test_codex_synthesis_backend_does_not_send_dynamic_workflow_schema_as_response_schema(self) -> None:
        calls = []

        def fake_run(command, **kwargs):
            calls.append({"command": command, "kwargs": kwargs})
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(generic_flight_workflow_json(), ensure_ascii=False),
                stderr="",
            )

        backend = CodexCliSynthesisBackend(run_command=fake_run)
        workflow = backend.synthesize(
            prompt="Return a workflow JSON.",
            schema={"type": "object", "additionalProperties": {"type": "string"}},
            model="gpt-5.5",
        )

        self.assertEqual("flight_search_report", workflow["skill_name"])
        self.assertNotIn("--output-schema", calls[0]["command"])
        self.assertIn("Return only JSON", calls[0]["command"][-1])

    def test_create_workflow_updates_page_analysis_and_reuses_knowledge_for_three_url_examples(self) -> None:
        examples = [
            (
                "https://example.com/search/results?query=alpha&utm=ad",
                "ExampleReady Best departing flights SEA to JFK iframe src='/results-frame' frame_locator needed",
            ),
            (
                "https://app.example.com/dashboard?tab=home",
                "ExampleReady Best departing flights SEA to JFK __NEXT_DATA__ data-reactroot React dashboard",
            ),
            (
                "https://shop.example.com/products/widget?ref=campaign",
                "ExampleReady Best departing flights SEA to JFK Vue createApp product picker",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            backend = RecordingFakeSynthesisBackend(response=generic_flight_workflow_json())
            synthesizer = LLMWorkflowSynthesizer(backend=backend)

            for start_url, page_text in examples:
                payload = WorkflowCreationRuntime(
                    store,
                    output_dir=output_dir,
                    trace_collector=StaticCreateTraceCollector(page_text=page_text),
                    synthesizer=synthesizer,
                ).create(
                    start_url=start_url,
                    user_task=f"Create a reusable script for {start_url}",
                    final_state="ExampleReady flight-like results are visible.",
                    arguments={"start_url": start_url},
                )
                self.assertEqual("succeeded", payload["status"])

            page_store = PageAnalysisStore(store)
            checkout = page_store.lookup("https://example.com/search/results?query=beta")
            dashboard = page_store.lookup("https://app.example.com/dashboard?tab=other")
            product = page_store.lookup("https://shop.example.com/products/widget?ref=other")
            knowledge_entries = WorkflowKnowledgeStore(store).recent(limit=10)

        self.assertIsNotNone(checkout)
        self.assertIn("iframe", checkout.frame_hints)
        self.assertIn("frame_locator", checkout.locator_hints)
        self.assertIsNotNone(dashboard)
        self.assertIn("react", dashboard.framework_hints)
        self.assertIn("nextjs", dashboard.framework_hints)
        self.assertIsNotNone(product)
        self.assertIn("vue", product.framework_hints)
        self.assertEqual(3, len(knowledge_entries))
        self.assertEqual(3, len(backend.prompts))
        self.assertIn("Reusable page analysis context JSON", backend.prompts[0])
        self.assertIn("example-com-search-results", backend.prompts[0])
        self.assertIn("Prefer frame_locator", backend.prompts[1])
        self.assertIn("Prefer role selectors", backend.prompts[2])
        self.assertIn("actionable_tips", knowledge_entries[0].content)
        self.assertGreaterEqual(len(knowledge_entries[0].content["actionable_tips"]), 2)

    def test_naver_map_route_task_uses_start_and_end_station_arguments(self) -> None:
        from webworkflows.cold_init_types import ArtifactTrace

        trace = ArtifactTrace(
            provider="static_create_trace",
            user_request=(
                "네이버 홈에서 네이버 지도로 이동한 뒤, 지하철 대중교통 경로로 "
                "양재역에서 사당역까지 몇 분 걸리는지 검색한다."
            ),
            arguments={
                "start_url": "https://www.naver.com",
                "final_state": "네이버 지도 대중교통 길찾기 결과가 표시되어야 한다.",
                "start_station": "양재역",
                "end_station": "사당역",
            },
            page_text=NAVER_HOME_TEXT,
            title="NAVER",
            final_url="https://www.naver.com",
            screenshots=[],
        )

        result = LLMWorkflowSynthesizer(backend=FailingSynthesisBackend()).synthesize_json(trace)

        self.assertEqual("known_naver_map_route", result.provider)
        workflow = result.workflow_json
        self.assertEqual("naver_map_transit_route", workflow["skill_name"])
        self.assertEqual(["start_station", "end_station"], [argument["name"] for argument in workflow["arguments"][:2]])
        self.assertIn("select_suggestion", [step["step_type"] for step in workflow["steps"]])
        self.assertIn("naver_map.extract_subway_duration", [handler["name"] for handler in workflow["handlers"]])

    def test_create_workflow_runs_naver_map_route_with_browser_evaluation_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=NAVER_MAP_TRANSIT_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_route_results",
                                step_type="wait_for_text",
                                status="passed",
                                summary="네이버 지도 대중교통 결과가 표시된다.",
                            )
                        ],
                        final_evaluation=StepEvaluation(
                            step_name="final",
                            step_type="final",
                            status="passed",
                            summary="양재역에서 사당역까지 지하철 경로 소요시간이 표시된다.",
                        ),
                    )
                ]
            )

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(page_text=NAVER_HOME_TEXT),
                synthesizer=LLMWorkflowSynthesizer(backend=FailingSynthesisBackend()),
                evaluation_loop=eval_loop,
            ).create(
                start_url="https://www.naver.com",
                user_task=(
                    "네이버 홈에서 네이버 지도로 이동한 뒤, 지하철 대중교통 경로로 "
                    "양재역에서 사당역까지 몇 분 걸리는지 검색한다."
                ),
                final_state="네이버 지도 대중교통 길찾기 결과에 지하철 소요 시간이 표시되어야 한다.",
                arguments={"start_station": "양재역", "end_station": "사당역"},
                max_attempts=1,
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("naver_map_transit_route", payload["workflow"])
            self.assertEqual("30분", payload["output"]["duration_text"])
            self.assertEqual(30, payload["output"]["duration_minutes"])
            self.assertIn("양재역에서 사당역", payload["output"]["report_text"])

    def test_create_workflow_uses_inferred_station_examples_for_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=NAVER_MAP_TRANSIT_TEXT,
                        step_evaluations=[],
                        final_evaluation=StepEvaluation(
                            step_name="final",
                            step_type="final",
                            status="passed",
                            summary="지하철 경로 결과가 표시된다.",
                        ),
                    )
                ]
            )

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(page_text=NAVER_HOME_TEXT),
                synthesizer=LLMWorkflowSynthesizer(backend=FailingSynthesisBackend()),
                evaluation_loop=eval_loop,
            ).create(
                start_url="https://www.naver.com",
                user_task="네이버 지도에서 양재역에서 사당역까지 지하철로 몇 분 걸리는지 검색한다.",
                final_state="네이버 지도 대중교통 길찾기 결과에 지하철 소요 시간이 표시되어야 한다.",
                arguments={},
                max_attempts=1,
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("양재역", eval_loop.calls[0]["arguments"]["start_station"])
            self.assertEqual("사당역", eval_loop.calls[0]["arguments"]["end_station"])

    def test_create_workflow_records_argument_example_metadata_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=NAVER_MAP_TRANSIT_TEXT,
                        step_evaluations=[],
                        final_evaluation=StepEvaluation(
                            step_name="final",
                            step_type="final",
                            status="passed",
                            summary="지하철 경로 결과가 표시된다.",
                        ),
                    )
                ]
            )
            user_task = "네이버 지도에서 양재역에서 사당역까지 지하철로 몇 분 걸리는지 검색한다."
            final_state = "네이버 지도 대중교통 길찾기 결과에 지하철 소요 시간이 표시되어야 한다."

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(page_text=NAVER_HOME_TEXT),
                synthesizer=LLMWorkflowSynthesizer(backend=FailingSynthesisBackend()),
                evaluation_loop=eval_loop,
            ).create(
                start_url="https://www.naver.com",
                user_task=user_task,
                final_state=final_state,
                arguments={},
                max_attempts=1,
            )

            self.assertEqual("succeeded", payload["status"])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                example = conn.execute(
                    """
                    select user_request, normalized_arguments_json, expected_output_summary, success_count
                    from workflow_tool_examples
                    where skill_id = ?
                    """,
                    (payload["created_skill_id"],),
                ).fetchone()

            self.assertIsNotNone(example)
            self.assertEqual(user_task, example["user_request"])
            normalized_args = json.loads(example["normalized_arguments_json"])
            self.assertEqual("양재역", normalized_args["start_station"])
            self.assertEqual("사당역", normalized_args["end_station"])
            self.assertEqual("https://www.naver.com", normalized_args["start_url"])
            self.assertNotIn("page_text", normalized_args)
            self.assertNotIn("final_state", normalized_args)
            self.assertEqual(final_state, example["expected_output_summary"])
            self.assertEqual(1, example["success_count"])

    def test_create_workflow_materializes_verified_tool_and_records_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            workflow_json = naver_stock_workflow_json()
            synthesizer = LLMWorkflowSynthesizer(backend=FakeSynthesisBackend(response=workflow_json))

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(),
                synthesizer=synthesizer,
            ).create(
                start_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
                user_task="네이버에서 삼성전자 주가 리포트",
                final_state="삼성전자 증권정보 카드와 현재가가 보여야 한다.",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("naver_stock_report", payload["workflow"])
            self.assertEqual(1, payload["workflow_version"])
            self.assertEqual(payload["created_skill_id"], payload["created_tool_id"])
            self.assertGreaterEqual(payload["creation_session_id"], 1)
            self.assertGreaterEqual(payload["discovery_duration_ms"], 0)
            self.assertGreaterEqual(payload["synthesis_duration_ms"], 0)
            self.assertGreaterEqual(payload["first_run_duration_ms"], 0)
            self.assertEqual("gpt-5.5", payload["synthesizer_model"])
            self.assertIn("295500", json.dumps(payload["output"], ensure_ascii=False))

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                session = conn.execute("select * from workflow_creation_sessions").fetchone()
                attempt = conn.execute("select * from workflow_creation_attempts").fetchone()
                skill_count = conn.execute("select count(*) from workflow_tools").fetchone()[0]

            self.assertEqual(1, skill_count)
            self.assertEqual("succeeded", session["status"])
            self.assertEqual("https://search.naver.com/search.naver?query=삼성전자%20주가", session["start_url"])
            self.assertEqual("네이버에서 삼성전자 주가 리포트", session["user_task"])
            self.assertEqual("삼성전자 증권정보 카드와 현재가가 보여야 한다.", session["final_state_description"])
            self.assertEqual("succeeded", attempt["status"])
            self.assertEqual("static_create_trace", attempt["discovery_provider"])
            self.assertEqual("llm_fake", attempt["synthesis_provider"])

    def test_create_workflow_supports_generic_non_stock_workflow_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(page_text=FLIGHT_TEXT),
                synthesizer=LLMWorkflowSynthesizer(
                    backend=FakeSynthesisBackend(response=generic_flight_workflow_json())
                ),
            ).create(
                start_url="https://www.google.com/flights",
                user_task="Search flights from SEA to JFK",
                final_state="Flight results are visible.",
                arguments={"start_url": "https://www.google.com/flights"},
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("flight_search_report", payload["workflow"])
            self.assertIn("Flight Search Report", payload["output"]["report_text"])

    def test_create_workflow_publishes_repaired_final_version_after_eval_evolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=TRACE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="failed",
                                summary="Stock card was not ready.",
                                problems=["missing stock card"],
                                suggested_update="Repair the workflow wait step.",
                            )
                        ],
                    ),
                    WorkflowEvaluationReport(
                        status="passed",
                        page_text=TRACE_TEXT,
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

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(),
                synthesizer=LLMWorkflowSynthesizer(backend=FakeSynthesisBackend(response=naver_stock_workflow_json())),
                evaluation_loop=eval_loop,
            ).create(
                start_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
                user_task="네이버에서 삼성전자 주가 리포트",
                final_state="삼성전자 증권정보 카드와 현재가가 보여야 한다.",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=2,
                repair_synthesizer="fake-copy",
            )

            self.assertEqual("succeeded", payload["status"])
            self.assertEqual(2, payload["workflow_version"])
            self.assertEqual(2, payload["evolution"]["final_version"])
            self.assertEqual([1, 2], [call["version"] for call in eval_loop.calls])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                skill = conn.execute("select * from workflow_tools where name = ?", ("naver_stock_report",)).fetchone()
                latest_version = conn.execute(
                    "select version from workflow_tool_versions where id = ?",
                    (skill["latest_version_id"],),
                ).fetchone()
                session = conn.execute("select * from workflow_creation_sessions").fetchone()

            self.assertEqual(2, latest_version["version"])
            self.assertEqual(payload["created_version_id"], skill["latest_version_id"])
            self.assertEqual(payload["created_version_id"], session["created_version_id"])

    def test_create_workflow_keeps_repaired_versions_draft_when_eval_evolve_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = QueueEvalLoop(
                [
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=TRACE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="wait_stock_card",
                                step_type="wait_for_text",
                                status="failed",
                                summary="Stock card was not ready.",
                                suggested_update="Repair the workflow wait step.",
                            )
                        ],
                    ),
                    WorkflowEvaluationReport(
                        status="failed",
                        page_text=TRACE_TEXT,
                        step_evaluations=[
                            StepEvaluation(
                                step_name="render_stock_report",
                                step_type="render_report",
                                status="failed",
                                summary="Final report still omitted the price.",
                                suggested_update="Repair the report template.",
                            )
                        ],
                    ),
                ]
            )

            payload = WorkflowCreationRuntime(
                store,
                output_dir=output_dir,
                trace_collector=StaticCreateTraceCollector(),
                synthesizer=LLMWorkflowSynthesizer(backend=FakeSynthesisBackend(response=naver_stock_workflow_json())),
                evaluation_loop=eval_loop,
            ).create(
                start_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
                user_task="네이버에서 삼성전자 주가 리포트",
                final_state="삼성전자 증권정보 카드와 현재가가 보여야 한다.",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
                max_attempts=2,
                repair_synthesizer="fake-copy",
            )

            self.assertEqual("failed", payload["status"])
            self.assertEqual(1, payload["workflow_version"])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                skill = conn.execute("select * from workflow_tools where name = ?", ("naver_stock_report",)).fetchone()
                versions = conn.execute(
                    "select id, version, status from workflow_tool_versions order by version"
                ).fetchall()
                session = conn.execute("select * from workflow_creation_sessions").fetchone()

            self.assertEqual("draft", skill["status"])
            self.assertEqual(1, skill["latest_version_id"])
            self.assertEqual([(1, "draft"), (2, "draft")], [(row["version"], row["status"]) for row in versions])
            self.assertEqual("failed", session["status"])
            self.assertEqual(1, session["created_version_id"])

    def test_cli_create_workflow_accepts_start_url_task_and_final_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            page_text_path = Path(tmp) / "page.txt"
            page_text_path.write_text(TRACE_TEXT, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "create-workflow",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--start-url",
                    "https://search.naver.com/search.naver?query=삼성전자%20주가",
                    "--task",
                    "네이버에서 삼성전자 주가 리포트",
                    "--final-state",
                    "삼성전자 증권정보 카드와 현재가가 보여야 한다.",
                    "--company-name",
                    "삼성전자",
                    "--ticker",
                    "005930",
                    "--page-text-file",
                    str(page_text_path),
                    "--discovery-provider",
                    "static",
                    "--synthesizer",
                    "fake-naver-stock",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("naver_stock_report", payload["workflow"])
            self.assertEqual(1, payload["workflow_version"])
            self.assertEqual("static_create_trace", payload["discovery_provider"])

    def test_cli_create_workflow_does_not_inject_stock_arguments_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            page_text_path = Path(tmp) / "page.txt"
            workflow_path = Path(tmp) / "flight_workflow.json"
            page_text_path.write_text(FLIGHT_TEXT, encoding="utf-8")
            workflow_path.write_text(json.dumps(generic_flight_workflow_json(), ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "create-workflow",
                    "--db",
                    str(db_path),
                    "--output-dir",
                    str(output_dir),
                    "--start-url",
                    "https://www.google.com/flights",
                    "--task",
                    "Search flights from SEA to JFK",
                    "--final-state",
                    "Flight results are visible.",
                    "--page-text-file",
                    str(page_text_path),
                    "--discovery-provider",
                    "static",
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

            payload = json.loads(completed.stdout)
            self.assertEqual("succeeded", payload["status"])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                session = conn.execute("select * from workflow_creation_sessions").fetchone()

            self.assertNotIn("news_limit", json.loads(session["input_json"]))


if __name__ == "__main__":
    unittest.main()
