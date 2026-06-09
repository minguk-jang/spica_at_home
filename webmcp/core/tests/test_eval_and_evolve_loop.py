from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
import argparse
import asyncio
from pathlib import Path
from typing import Any

from webworkflows.cold_init import (
    ColdInitRunner,
    DiscoveryResult,
    StaticDiscoveryRunner,
    WorkflowMaterializer,
    discovery_from_workflow_json,
)
from webworkflows.cli import add_eval_loop_args, build_evaluation_loop
from webworkflows.eval_loop import (
    EvaluationSnapshot,
    StepEvaluation,
    WorkflowEvaluationError,
    WorkflowEvaluationReport,
)
from webworkflows.executor import WorkflowExecutor
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.loader import WorkflowSkillLoader, WorkflowStep
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import validate_workflow_json
from webworkflows.vlm_codex import (
    CodexAppServerVisionLanguageEvaluator,
    CodexCliVisionLanguageEvaluator,
    CodexResponsesVisionLanguageEvaluator,
)


STALE_PAGE_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
295,500원
전일대비 하락 33,500 (-10.18%)
"""

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


def dynamic_ad_workflow_json() -> dict[str, Any]:
    return {
        "skill_name": "dynamic_ad_demo",
        "slug": "dynamic-ad-demo",
        "description": "Dismiss a variable ad and render a completion report.",
        "domain": "example.test",
        "task_type": "dynamic_ad_demo",
        "body_md": "Uses a scriptless dynamic browser step for variable ad dismissal.",
        "input_schema": {"start_url": {"type": "string", "required": True}},
        "output_schema": {"report_text": "string"},
        "arguments": [
            {
                "name": "start_url",
                "description": "Initial page URL.",
                "type": "string",
                "required": True,
                "default_value": None,
                "validation": {},
                "examples": ["https://example.test/demo"],
                "is_dynamic": True,
                "order_index": 0,
            }
        ],
        "steps": [
            {
                "name": "open_dynamic_ad_demo",
                "description": "Open the demo page.",
                "step_type": "goto",
                "handler_ref": None,
                "action": {"url_template": "{{start_url}}"},
                "argument_bindings": {},
                "assertions": {"url_contains": "example.test"},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "dismiss_variable_ad",
                "description": "Use runtime LLM-generated browser code to dismiss whichever ad is visible.",
                "step_type": "llm_browser_action",
                "handler_ref": None,
                "action": {
                    "instruction": "Close any visible ad or sponsored popup without leaving the page.",
                    "success_criteria": ["No ad overlay or sponsored popup remains visible."],
                    "allowed_operations": ["click"],
                    "timeout_ms": 15000,
                },
                "argument_bindings": {},
                "assertions": {"contains_any": []},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "render_dynamic_ad_report",
                "description": "Render the final report.",
                "step_type": "render_report",
                "handler_ref": None,
                "action": {"template_resource": "dynamic_ad_report_markdown"},
                "argument_bindings": {},
                "assertions": {"required_output": ["report_text"]},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
        ],
        "resources": [
            {
                "resource_type": "report_template",
                "name": "dynamic_ad_report_markdown",
                "description": "Markdown report template for dynamic ad dismissal.",
                "content_json": None,
                "content_text": "# Dynamic Ad Demo\n\nStatus: {{status}}\n\n{{page_text}}\n",
                "load_when": {"step": "render_dynamic_ad_report"},
            }
        ],
        "handlers": [],
    }


class FakeEvalLoop:
    def __init__(self, report: WorkflowEvaluationReport):
        self.report = report
        self.calls: list[dict[str, Any]] = []

    def run(self, *, skill, user_request: str, arguments: dict[str, Any], run_id: int, output_dir: Path):
        self.calls.append(
            {
                "skill": skill.name,
                "user_request": user_request,
                "arguments": dict(arguments),
                "run_id": run_id,
                "output_dir": output_dir,
            }
        )
        return self.report


class FakeCodexAppServerClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def run_turn(self, *, prompt: str, output_schema: dict[str, Any], image_paths: list[Path], model: str):
        self.calls.append(
            {
                "prompt": prompt,
                "output_schema": output_schema,
                "image_paths": list(image_paths),
                "model": model,
            }
        )
        return {
            "text": self.response_text,
            "thread_id": "thread_test",
            "turn_id": "turn_test",
        }

    def close(self) -> None:
        self.closed = True


class FakeBrowserPage:
    def __init__(self, *, url: str = "https://example.test", title: str = "Example", body_text: str = "Example") -> None:
        self.fills: list[tuple[str, str]] = []
        self.clicks: list[str] = []
        self.text_clicks: list[str] = []
        self.dynamic_evaluations: list[dict[str, Any]] = []
        self.url = url
        self._title = title
        self.body_text = body_text

    def locator(self, selector: str):
        return FakeLocator(self, selector)

    def get_by_text(self, text: str, *, exact: bool):
        return FakeTextLocator(self, text)

    async def wait_for_timeout(self, ms: int) -> None:
        self.last_timeout_ms = ms

    async def title(self) -> str:
        return self._title

    async def evaluate(self, script: str, arg: Any = None) -> Any:
        if isinstance(arg, dict) and "actionSource" in arg:
            self.dynamic_evaluations.append(arg)
            self.body_text = self.body_text.replace("Sponsored popup", "")
            return {"status": "passed", "clicked_text": "Close ad"}
        return [
            {
                "text": "Close ad",
                "tag": "button",
                "selector": "button[data-testid='ad-close']",
            }
        ]


class FakeLocator:
    def __init__(self, page: FakeBrowserPage, selector: str):
        self.page = page
        self.selector = selector

    def nth(self, index: int):
        self.index = index
        return self

    async def fill(self, value: str, timeout: int) -> None:
        self.page.fills.append((self.selector, value))

    async def click(self, timeout: int) -> None:
        self.page.clicks.append(self.selector)

    async def inner_text(self, timeout: int) -> str:
        return self.page.body_text


class FakeTextLocator:
    def __init__(self, page: FakeBrowserPage, text: str):
        self.page = page
        self.text = text

    def nth(self, index: int):
        self.index = index
        return self

    async def click(self, timeout: int) -> None:
        self.page.text_clicks.append(self.text)


class EvalAndEvolveLoopTest(unittest.TestCase):
    def test_validate_workflow_json_accepts_scriptless_dynamic_browser_step(self) -> None:
        workflow = dynamic_ad_workflow_json()

        validate_workflow_json(workflow)

    def test_validate_workflow_json_rejects_stored_script_on_dynamic_browser_step(self) -> None:
        workflow = dynamic_ad_workflow_json()
        workflow["steps"][1]["action"]["javascript"] = "() => document.querySelector('button').click()"

        with self.assertRaises(ValueError) as ctx:
            validate_workflow_json(workflow)

        self.assertIn("must not store generated code", str(ctx.exception))

    def test_browser_dynamic_step_calls_runtime_planner_and_executes_generated_javascript(self) -> None:
        from webworkflows.dynamic_browser import DynamicBrowserAction

        class FakeDynamicPlanner:
            name = "fake_dynamic_planner"

            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def plan(self, **kwargs) -> DynamicBrowserAction:
                self.calls.append(kwargs)
                return DynamicBrowserAction(
                    javascript="async (input) => ({ status: 'passed', instruction: input.instruction })",
                    summary="Click the currently visible ad close button.",
                    provider=self.name,
                    model="fake-model",
                )

        page = FakeBrowserPage(body_text="Main content\nSponsored popup\nClose ad")
        planner = FakeDynamicPlanner()
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        loop.dynamic_action_planner = planner
        step = WorkflowStep(
            id=1,
            name="dismiss_variable_ad",
            description="Dismiss whichever ad overlay is currently visible.",
            step_type="llm_browser_action",
            handler_ref=None,
            action={
                "instruction": "Close any visible ad or sponsored popup without leaving the page.",
                "success_criteria": ["Sponsored popup is gone"],
                "allowed_operations": ["click"],
            },
            argument_bindings={},
            assertions={},
            fallback_policy={},
            update_policy={},
        )
        output: dict[str, Any] = {}

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=None,
                step=step,
                values={"start_url": "https://example.test"},
                output=output,
                user_request="Dismiss the ad and continue.",
            )
        )

        self.assertEqual("", error)
        self.assertEqual(1, len(planner.calls))
        self.assertEqual("Close any visible ad or sponsored popup without leaving the page.", planner.calls[0]["instruction"])
        self.assertEqual(1, len(page.dynamic_evaluations))
        dynamic_evidence = output["_dynamic_step_evidence"]["dismiss_variable_ad"]
        self.assertEqual("fake_dynamic_planner", dynamic_evidence["provider"])
        self.assertIn("generated_javascript", dynamic_evidence)
        self.assertEqual("passed", dynamic_evidence["result"]["status"])

    def test_executor_marks_dynamic_browser_workflow_as_llm_used_after_eval_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            WorkflowMaterializer(store).materialize(
                DiscoveryResult(
                    provider="test",
                    skill_name="dynamic_ad_demo",
                    slug="dynamic-ad-demo",
                    description="Dismiss a variable ad and render a report.",
                    domain="example.test",
                    task_type="dynamic_ad_demo",
                    body_md="Scriptless dynamic ad demo.",
                    input_schema={"start_url": {"type": "string", "required": True}},
                    output_schema={"report_text": "string"},
                    arguments=[
                        {
                            "name": "start_url",
                            "description": "Start URL",
                            "type": "string",
                            "required": True,
                            "default_value": None,
                            "validation": {},
                            "examples": ["https://example.test"],
                            "is_dynamic": True,
                            "order_index": 0,
                        }
                    ],
                    steps=dynamic_ad_workflow_json()["steps"],
                    resources=dynamic_ad_workflow_json()["resources"],
                    handlers=[],
                    page_text="Main content",
                )
            )
            skill = WorkflowSkillLoader(store).load_skill_by_name("dynamic_ad_demo")
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="passed",
                    page_text="Main content\nAd dismissed",
                    step_evaluations=[
                        StepEvaluation(
                            step_name="dismiss_variable_ad",
                            step_type="llm_browser_action",
                            status="passed",
                            summary="Runtime LLM generated and executed an ad dismissal action.",
                            evidence={
                                "url": "https://example.test/demo",
                                "title": "Dynamic Ad Demo",
                                "dynamic_action": {
                                    "provider": "fake_dynamic_planner",
                                    "generated_javascript": "async (input) => ({ status: 'passed' })",
                                },
                            },
                        )
                    ],
                )
            )

            result = WorkflowExecutor(store, output_dir=output_dir, evaluation_loop=eval_loop).run(
                skill,
                user_request="Dismiss the ad and report completion.",
                arguments={"start_url": "https://example.test/demo"},
            )

            self.assertTrue(result.llm_used)
            self.assertEqual("succeeded", result.status)
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                run = conn.execute("select llm_used, llm_reason from workflow_runs").fetchone()
                dynamic_step = conn.execute(
                    """
                    select action_json
                    from workflow_skill_steps
                    where step_type = 'llm_browser_action'
                    """
                ).fetchone()

            self.assertEqual(1, run["llm_used"])
            self.assertEqual("runtime_dynamic_browser_step", run["llm_reason"])
            action_json = json.loads(dynamic_step["action_json"])
            self.assertIn("instruction", action_json)
            self.assertNotIn("javascript", action_json)
            self.assertNotIn("script", action_json)

    def test_executor_rejects_dynamic_browser_step_without_browser_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            WorkflowMaterializer(store).materialize(
                DiscoveryResult(
                    provider="test",
                    skill_name="dynamic_ad_demo",
                    slug="dynamic-ad-demo",
                    description="Dismiss a variable ad and render a report.",
                    domain="example.test",
                    task_type="dynamic_ad_demo",
                    body_md="Scriptless dynamic ad demo.",
                    input_schema={"start_url": {"type": "string", "required": True}},
                    output_schema={"report_text": "string"},
                    arguments=[
                        {
                            "name": "start_url",
                            "description": "Start URL",
                            "type": "string",
                            "required": True,
                            "default_value": None,
                            "validation": {},
                            "examples": ["https://example.test"],
                            "is_dynamic": True,
                            "order_index": 0,
                        }
                    ],
                    steps=dynamic_ad_workflow_json()["steps"],
                    resources=dynamic_ad_workflow_json()["resources"],
                    handlers=[],
                    page_text="Main content",
                )
            )
            skill = WorkflowSkillLoader(store).load_skill_by_name("dynamic_ad_demo")

            with self.assertRaises(RuntimeError) as ctx:
                WorkflowExecutor(store, output_dir=output_dir).run(
                    skill,
                    user_request="Dismiss the ad and report completion.",
                    arguments={"start_url": "https://example.test/demo"},
                )

            self.assertIn("requires browser runtime", str(ctx.exception))

    def test_browser_fill_step_accepts_generated_source_and_input_key_action(self) -> None:
        page = FakeBrowserPage()
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        step = WorkflowStep(
            id=1,
            name="fill_username",
            description="Fill generated username action.",
            step_type="fill",
            handler_ref=None,
            action={"source": "#username", "input_key": "username"},
            argument_bindings={},
            assertions={},
            fallback_policy={},
            update_policy={},
        )

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=None,
                step=step,
                values={"username": "tomsmith"},
                output={},
            )
        )

        self.assertEqual("", error)
        self.assertEqual([("#username", "tomsmith")], page.fills)

    def test_browser_click_step_accepts_generated_source_action(self) -> None:
        page = FakeBrowserPage()
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        step = WorkflowStep(
            id=1,
            name="submit_login",
            description="Click generated login action.",
            step_type="click",
            handler_ref=None,
            action={"source": "button[type='submit']"},
            argument_bindings={},
            assertions={},
            fallback_policy={},
            update_policy={},
        )

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=None,
                step=step,
                values={},
                output={},
            )
        )

        self.assertEqual("", error)
        self.assertEqual(["button[type='submit']"], page.clicks)

    def test_browser_click_text_step_accepts_generated_source_action(self) -> None:
        page = FakeBrowserPage()
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        step = WorkflowStep(
            id=1,
            name="submit_login",
            description="Click generated login text action.",
            step_type="click_text",
            handler_ref=None,
            action={"source": "Login"},
            argument_bindings={},
            assertions={},
            fallback_policy={},
            update_policy={},
        )

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=None,
                step=step,
                values={},
                output={},
            )
        )

        self.assertEqual("", error)
        self.assertEqual(["Login"], page.text_clicks)

    def test_browser_assert_output_step_exposes_current_browser_state(self) -> None:
        page = FakeBrowserPage(
            url="https://the-internet.herokuapp.com/secure",
            title="The Internet",
            body_text="Secure Area\nYou logged into a secure area!\nLogout",
        )
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        output: dict[str, Any] = {}
        step = WorkflowStep(
            id=1,
            name="validate_secure_output",
            description="Validate browser state output.",
            step_type="assert_output",
            handler_ref=None,
            action={},
            argument_bindings={},
            assertions={"required_output": ["final_url", "page_title", "page_text"]},
            fallback_policy={},
            update_policy={},
        )

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=None,
                step=step,
                values={},
                output=output,
            )
        )

        self.assertEqual("", error)
        self.assertEqual("https://the-internet.herokuapp.com/secure", output["final_url"])
        self.assertEqual("The Internet", output["page_title"])
        self.assertIn("You logged into a secure area!", output["page_text"])

    def test_browser_render_report_step_exposes_report_aliases_and_status(self) -> None:
        page = FakeBrowserPage(
            url="https://the-internet.herokuapp.com/secure",
            title="The Internet",
            body_text="Secure Area\nYou logged into a secure area!",
        )
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        output: dict[str, Any] = {}
        step = WorkflowStep(
            id=1,
            name="render_secure_area_report",
            description="Render report.",
            step_type="render_report",
            handler_ref=None,
            action={"template_resource": "secure_area_report_template"},
            argument_bindings={},
            assertions={},
            fallback_policy={},
            update_policy={},
        )

        error = asyncio.run(
            loop._execute_browser_step(
                page=page,
                skill=argparse.Namespace(resources={"secure_area_report_template": "# Report\n{{final_url}}\n"}),
                step=step,
                values={},
                output=output,
            )
        )

        self.assertEqual("", error)
        self.assertEqual(output["report_text"], output["report_markdown"])
        self.assertEqual(output["report_text"], output["markdown_report"])
        self.assertEqual("passed", output["status"])

    def test_action_step_criteria_drop_generated_contains_any_assertions(self) -> None:
        loop = object.__new__(__import__("webworkflows.eval_loop").eval_loop.PlaywrightEvalAndEvolveLoop)
        loop.evaluator = argparse.Namespace(name="fake")
        step = WorkflowStep(
            id=1,
            name="submit_login",
            description="Submit login.",
            step_type="click",
            handler_ref=None,
            action={"source": "button[type='submit']"},
            argument_bindings={},
            assertions={"contains_any": ["Login"], "url_contains": None, "required_output": []},
            fallback_policy={},
            update_policy={},
        )

        criteria = loop._criteria_for_step(step)

        self.assertEqual([], criteria["assertions"]["contains_any"])
        self.assertIsNone(criteria["assertions"]["url_contains"])

    def test_executor_uses_browser_state_output_from_evaluation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            skill_id, _version_id = WorkflowMaterializer(store).materialize(
                DiscoveryResult(
                    provider="test",
                    skill_name="browser_state_report",
                    slug="browser-state-report",
                    description="Report browser state.",
                    domain="example.test",
                    task_type="browser_state",
                    body_md="Browser state report test workflow.",
                    input_schema={"start_url": {"type": "string", "required": True}},
                    output_schema={"final_url": "string", "page_title": "string", "page_text": "string"},
                    arguments=[
                        {
                            "name": "start_url",
                            "description": "Start URL",
                            "type": "string",
                            "required": True,
                            "default_value": None,
                            "validation": {},
                            "examples": ["https://example.test/login"],
                            "is_dynamic": True,
                            "order_index": 0,
                        }
                    ],
                    steps=[
                        {
                            "name": "open_page",
                            "description": "Open page.",
                            "step_type": "goto",
                            "handler_ref": None,
                            "action": {"url_template": "{{start_url}}"},
                            "argument_bindings": {},
                            "assertions": {},
                            "fallback_policy": {},
                            "update_policy": {},
                        },
                        {
                            "name": "validate_browser_state",
                            "description": "Validate browser state output.",
                            "step_type": "assert_output",
                            "handler_ref": None,
                            "action": {},
                            "argument_bindings": {},
                            "assertions": {"required_output": ["final_url", "page_title", "page_text"]},
                            "fallback_policy": {},
                            "update_policy": {},
                        },
                        {
                            "name": "render_report",
                            "description": "Render report.",
                            "step_type": "render_report",
                            "handler_ref": None,
                            "action": {"template_resource": "browser_state_template"},
                            "argument_bindings": {},
                            "assertions": {},
                            "fallback_policy": {},
                            "update_policy": {},
                        },
                    ],
                    resources=[
                        {
                            "resource_type": "report_template",
                            "name": "browser_state_template",
                            "description": "Browser state template.",
                            "content_json": None,
                            "content_text": "# Browser State\n{{final_url}}\n{{page_title}}\n{{page_text}}\n",
                            "load_when": {"step": "render_report"},
                        }
                    ],
                    handlers=[],
                    page_text="",
                )
            )
            skill = WorkflowSkillLoader(store).load_skill(skill_id)
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="passed",
                    page_text="Secure Area\nYou logged into a secure area!",
                    step_evaluations=[
                        StepEvaluation(
                            step_name="validate_browser_state",
                            step_type="assert_output",
                            status="passed",
                            summary="Browser state is visible.",
                            evidence={
                                "url": "https://example.test/secure",
                                "title": "The Internet",
                            },
                        )
                    ],
                    final_evaluation=StepEvaluation(
                        step_name="final",
                        step_type="final",
                        status="passed",
                        summary="Final state passed.",
                        evidence={
                            "url": "https://example.test/secure",
                            "title": "The Internet",
                        },
                    ),
                )
            )

            result = WorkflowExecutor(store, output_dir=output_dir, evaluation_loop=eval_loop).run(
                skill,
                user_request="browser state report",
                arguments={"start_url": "https://example.test/login"},
            )

        self.assertEqual("succeeded", result.status)
        self.assertEqual("https://example.test/secure", result.output["final_url"])
        self.assertEqual("The Internet", result.output["page_title"])
        self.assertIn("You logged into a secure area!", result.output["page_text"])
        self.assertEqual(result.output["report_text"], result.output["report_markdown"])
        self.assertEqual(result.output["report_text"], result.output["markdown_report"])
        self.assertEqual("passed", result.output["status"])

    def test_codex_app_server_vlm_evaluator_uses_codex_oauth_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screenshot_path = tmp_path / "step.png"
            screenshot_path.write_bytes(b"fake-png")
            fake_client = FakeCodexAppServerClient(
                json.dumps(
                    {
                        "status": "passed",
                        "summary": "네이버 지도 결과에 양재역, 사당역, 지하철 14분이 보입니다.",
                        "problems": [],
                        "suggested_update": "",
                        "failure_kind": "",
                        "expected_state": "양재역에서 사당역까지 지하철 시간이 보여야 합니다.",
                        "observed_state": "본문에 양재역, 사당역, 지하철 14분이 표시됩니다.",
                        "repair_focus": "",
                        "evidence_artifacts": [],
                    },
                    ensure_ascii=False,
                )
            )

            evaluator = CodexAppServerVisionLanguageEvaluator(
                model="gpt-5.5",
                app_server=fake_client,
            )
            result = evaluator.evaluate(
                EvaluationSnapshot(
                    step_name="wait_route_results",
                    step_type="wait_for_text",
                    phase="intermediate",
                    user_request="네이버 지도에서 양재역에서 사당역까지 지하철 시간",
                    url="https://map.naver.com/p/directions/example",
                    title="길찾기 - 네이버지도",
                    page_text="양재역 사당역 지하철 14분",
                    screenshot_path=str(screenshot_path),
                    output={},
                ),
                {"assertions": {"contains_any": ["지하철", "사당역", "분"]}},
            )
            evaluator.close()

        self.assertEqual("passed", result.status)
        self.assertEqual("codex_app_server", result.evidence["vlm_evaluator"])
        self.assertEqual("gpt-5.5", result.evidence["codex_model"])
        self.assertEqual("thread_test", result.evidence["codex_thread_id"])
        self.assertEqual("turn_test", result.evidence["codex_turn_id"])
        self.assertEqual([screenshot_path.resolve()], fake_client.calls[0]["image_paths"])
        self.assertEqual("gpt-5.5", fake_client.calls[0]["model"])
        self.assertEqual("object", fake_client.calls[0]["output_schema"]["type"])
        self.assertIn("WebMCP Playwright workflow step", fake_client.calls[0]["prompt"])
        self.assertTrue(fake_client.closed)

    def test_codex_app_server_vlm_evaluator_resolves_relative_screenshot_against_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screenshot_path = tmp_path / "step.png"
            screenshot_path.write_bytes(b"fake-png")
            fake_client = FakeCodexAppServerClient(
                json.dumps(
                    {
                        "status": "passed",
                        "summary": "상대 경로 screenshot이 app-server에 절대 경로로 전달되었습니다.",
                        "problems": [],
                        "suggested_update": "",
                        "failure_kind": "",
                        "expected_state": "이미지가 읽혀야 합니다.",
                        "observed_state": "이미지가 전달되었습니다.",
                        "repair_focus": "",
                        "evidence_artifacts": [],
                    },
                    ensure_ascii=False,
                )
            )

            evaluator = CodexAppServerVisionLanguageEvaluator(
                model="gpt-5.5",
                cwd=tmp_path,
                app_server=fake_client,
            )
            evaluator.evaluate(
                EvaluationSnapshot(
                    step_name="relative_screenshot",
                    step_type="wait_for_text",
                    phase="intermediate",
                    user_request="relative screenshot path test",
                    url="https://example.test",
                    title="Example",
                    page_text="ok",
                    screenshot_path="step.png",
                    output={},
                ),
                {"assertions": {"contains_any": ["ok"]}},
            )

        self.assertEqual([screenshot_path.resolve()], fake_client.calls[0]["image_paths"])

    def test_codex_responses_vlm_evaluator_posts_screenshot_to_responses_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screenshot_path = tmp_path / "step.png"
            screenshot_path.write_bytes(b"fake-png")
            calls: list[dict[str, Any]] = []

            def fake_http_post(endpoint, payload, headers, timeout_seconds):
                calls.append(
                    {
                        "endpoint": endpoint,
                        "payload": payload,
                        "headers": headers,
                        "timeout_seconds": timeout_seconds,
                    }
                )
                return {
                    "id": "resp_test",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "status": "passed",
                                            "summary": "네이버 지도 결과에 양재역, 사당역, 지하철 14분이 보입니다.",
                                            "problems": [],
                                            "suggested_update": "",
                                            "failure_kind": "",
                                            "expected_state": "양재역에서 사당역까지 지하철 시간이 보여야 합니다.",
                                            "observed_state": "본문에 양재역, 사당역, 지하철 14분이 표시됩니다.",
                                            "repair_focus": "",
                                            "evidence_artifacts": [],
                                        },
                                        ensure_ascii=False,
                                    ),
                                }
                            ],
                        }
                    ],
                }

            evaluator = CodexResponsesVisionLanguageEvaluator(
                model="gpt-5.5",
                api_key="test-key",
                http_post=fake_http_post,
            )
            result = evaluator.evaluate(
                EvaluationSnapshot(
                    step_name="wait_route_results",
                    step_type="wait_for_text",
                    phase="intermediate",
                    user_request="네이버 지도에서 양재역에서 사당역까지 지하철 시간",
                    url="https://map.naver.com/p/directions/example",
                    title="길찾기 - 네이버지도",
                    page_text="양재역 사당역 지하철 14분",
                    screenshot_path=str(screenshot_path),
                    output={},
                ),
                {"assertions": {"contains_any": ["지하철", "사당역", "분"]}},
            )

        self.assertEqual("passed", result.status)
        self.assertEqual("codex_responses", result.evidence["vlm_evaluator"])
        self.assertEqual("gpt-5.5", result.evidence["codex_model"])
        self.assertEqual("resp_test", result.evidence["openai_response_id"])
        self.assertEqual("https://api.openai.com/v1/responses", calls[0]["endpoint"])
        self.assertEqual("Bearer test-key", calls[0]["headers"]["Authorization"])
        payload = calls[0]["payload"]
        self.assertEqual("gpt-5.5", payload["model"])
        self.assertIs(payload["store"], False)
        self.assertTrue(payload["text"]["format"]["strict"])
        content = payload["input"][0]["content"]
        self.assertEqual("input_text", content[0]["type"])
        self.assertEqual("input_image", content[1]["type"])
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))

    def test_codex_vlm_evaluator_parses_model_judgment_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screenshot_path = tmp_path / "step.png"
            screenshot_path.write_bytes(b"fake-png")
            calls: list[dict[str, Any]] = []

            def fake_run(command, **kwargs):
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(
                    json.dumps(
                        {
                            "status": "passed",
                            "summary": "삼성전자 증권정보 카드와 현재가 텍스트가 화면에 표시됩니다.",
                            "problems": [],
                            "suggested_update": "",
                            "failure_kind": "",
                            "expected_state": "네이버 검색 결과에 삼성전자 현재가 카드가 보여야 합니다.",
                            "observed_state": "검색 결과 본문에 삼성전자, 현재가, 310,500원이 보입니다.",
                            "repair_focus": "",
                            "evidence_artifacts": [str(screenshot_path)],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                calls.append({"command": command, "kwargs": kwargs})
                return subprocess.CompletedProcess(command, 0, stdout='{"event":"done"}', stderr="")

            evaluator = CodexCliVisionLanguageEvaluator(
                model="gpt-5.5",
                cwd=tmp_path,
                run_command=fake_run,
            )
            result = evaluator.evaluate(
                EvaluationSnapshot(
                    step_name="wait_stock_card",
                    step_type="wait_for_text",
                    phase="intermediate",
                    user_request="네이버에서 삼성전자 주가 리포트",
                    url="https://search.naver.com/search.naver?query=삼성전자%20주가",
                    title="삼성전자 주가 : 네이버 검색",
                    page_text=LIVE_PAGE_TEXT,
                    screenshot_path=str(screenshot_path),
                    output={},
                ),
                {"assertions": {"contains_any": ["증권정보", "현재가"]}},
            )

        self.assertEqual("passed", result.status)
        self.assertEqual("삼성전자 증권정보 카드와 현재가 텍스트가 화면에 표시됩니다.", result.summary)
        self.assertEqual("네이버 검색 결과에 삼성전자 현재가 카드가 보여야 합니다.", result.expected_state)
        self.assertEqual("검색 결과 본문에 삼성전자, 현재가, 310,500원이 보입니다.", result.observed_state)
        self.assertEqual("codex_cli", result.evidence["vlm_evaluator"])
        self.assertEqual("gpt-5.5", result.evidence["codex_model"])
        self.assertIn("--image", calls[0]["command"])
        self.assertEqual(str(screenshot_path), calls[0]["command"][calls[0]["command"].index("--image") + 1])
        self.assertIn("WebMCP Playwright workflow step", calls[0]["kwargs"]["input"])

    def test_codex_cli_vlm_evaluator_raises_when_model_is_at_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screenshot_path = tmp_path / "step.png"
            screenshot_path.write_bytes(b"fake-png")

            def fake_run(command, **kwargs):
                raise subprocess.CalledProcessError(
                    1,
                    command,
                    output="",
                    stderr="ERROR: Selected model is at capacity. Please try a different model.",
                )

            evaluator = CodexCliVisionLanguageEvaluator(
                model="gpt-5.5",
                cwd=tmp_path,
                run_command=fake_run,
            )
            with self.assertRaisesRegex(RuntimeError, "codex VLM evaluation failed"):
                evaluator.evaluate(
                    EvaluationSnapshot(
                        step_name="wait_route_results",
                        step_type="wait_for_text",
                        phase="intermediate",
                        user_request="네이버 지도에서 양재역에서 사당역까지",
                        url="https://map.naver.com/p/directions/example",
                        title="길찾기 - 네이버지도",
                        page_text="양재역 사당역 지하철 14분",
                        screenshot_path=str(screenshot_path),
                        output={},
                    ),
                    {"assertions": {"contains_any": ["지하철", "사당역", "분"]}},
                )

    def test_eval_loop_cli_defaults_to_codex_vlm_and_rejects_non_codex_evaluator(self) -> None:
        parser = argparse.ArgumentParser()
        add_eval_loop_args(parser)

        args = parser.parse_args(["--eval-and-evolve"])
        loop = build_evaluation_loop(args)

        self.assertEqual("codex_app_server", loop.evaluator.name)
        self.assertEqual("gpt-5.5", loop.evaluator.model)
        self.assertEqual(Path(__file__).resolve().parents[1], loop.evaluator.app_server.cwd)

        args = parser.parse_args(["--eval-and-evolve", "--vlm-evaluator", "codex-cli"])
        loop = build_evaluation_loop(args)
        self.assertEqual("codex_cli", loop.evaluator.name)

        with self.assertRaises(SystemExit):
            parser.parse_args(["--eval-and-evolve", "--vlm-evaluator", "local-only"])

    def test_eval_loop_module_does_not_spawn_nested_codex_exec(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("webworkflows", "eval_loop.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('"exec"', source)
        self.assertNotIn("codex exec", source.lower())

    def test_executor_fails_run_when_browser_evaluation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            skill = WorkflowSkillLoader(store).load_skill_by_name("naver_stock_report")
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="failed",
                    page_text=LIVE_PAGE_TEXT,
                    step_evaluations=[
                        StepEvaluation(
                            step_name="wait_stock_card",
                            step_type="wait_for_text",
                            status="failed",
                            summary="VLM could not find the stock card after navigation.",
                            evidence={"screenshot_path": str(output_dir / "eval_runs" / "run_0001" / "step.png")},
                            problems=["stock card missing"],
                            suggested_update="Update the wait marker or selector for the Naver stock card.",
                        )
                    ],
                )
            )

            executor = WorkflowExecutor(store, output_dir=output_dir, evaluation_loop=eval_loop)
            with self.assertRaises(WorkflowEvaluationError) as ctx:
                executor.run(
                    skill,
                    user_request="네이버에서 삼성전자 주가 리포트",
                    arguments={
                        "company_name": "삼성전자",
                        "ticker": "005930",
                        "page_text": STALE_PAGE_TEXT,
                    },
                )

            self.assertIn("wait_stock_card", str(ctx.exception))
            self.assertEqual(1, len(eval_loop.calls))

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                run = conn.execute("select * from workflow_runs").fetchone()
                step_run = conn.execute("select * from step_runs").fetchone()

            self.assertEqual("failed", run["status"])
            output = json.loads(run["output_json"])
            self.assertEqual("workflow_evaluation_failed", output["error_type"])
            self.assertEqual("wait_stock_card", output["evaluation"]["failed_step"]["step_name"])

            self.assertEqual("failed", step_run["status"])
            evidence = json.loads(step_run["evidence_json"])
            self.assertEqual("failed", evidence["browser_evaluation"]["status"])
            error = json.loads(step_run["error_json"])
            self.assertEqual("WorkflowEvaluationError", error["type"])

    def test_executor_uses_browser_evaluation_page_text_for_deterministic_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            skill = WorkflowSkillLoader(store).load_skill_by_name("naver_stock_report")
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="passed",
                    page_text=LIVE_PAGE_TEXT,
                    step_evaluations=[
                        StepEvaluation(
                            step_name="open_naver_stock_search",
                            step_type="goto",
                            status="passed",
                            summary="Navigation reached a Naver search result page.",
                            evidence={"url": "https://search.naver.com/search.naver?query=삼성전자%20주가"},
                        )
                    ],
                    final_evaluation=StepEvaluation(
                        step_name="final",
                        step_type="final",
                        status="passed",
                        summary="The final page contains a stock quote and report inputs.",
                        evidence={},
                    ),
                )
            )

            result = WorkflowExecutor(store, output_dir=output_dir, evaluation_loop=eval_loop).run(
                skill,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": STALE_PAGE_TEXT,
                },
            )

            self.assertEqual("succeeded", result.status)
            self.assertEqual(310500, result.output["current_price"])
            self.assertEqual("passed", result.evaluation["status"])

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                step_runs = conn.execute("select * from step_runs order by id").fetchall()

            self.assertEqual(len(skill.steps), len(step_runs))
            first_evidence = json.loads(step_runs[0]["evidence_json"])
            self.assertEqual("passed", first_evidence["browser_evaluation"]["status"])

    def test_executor_does_not_recheck_browser_wait_step_against_final_eval_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            workflow = dynamic_ad_workflow_json()
            workflow["steps"].insert(
                2,
                {
                    "name": "wait_intermediate_ad_dismissed",
                    "description": "Wait for an intermediate browser state that is gone by final page.",
                    "step_type": "wait_for_text",
                    "handler_ref": None,
                    "action": {"source": "page_text"},
                    "argument_bindings": {},
                    "assertions": {"contains_any": ["Ad dismissed"]},
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
            )
            WorkflowMaterializer(store).materialize(
                discovery_from_workflow_json(workflow, provider="test", page_text="Ad visible")
            )
            skill = WorkflowSkillLoader(store).load_skill_by_name("dynamic_ad_demo")
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="passed",
                    page_text="Launch review complete for Mina",
                    step_evaluations=[
                        StepEvaluation(
                            step_name="wait_intermediate_ad_dismissed",
                            step_type="wait_for_text",
                            status="passed",
                            summary="The intermediate ad dismissed text was visible.",
                            evidence={"url": "https://example.test/demo", "title": "Dynamic Ad Demo"},
                        )
                    ],
                )
            )

            result = WorkflowExecutor(store, output_dir=output_dir, evaluation_loop=eval_loop).run(
                skill,
                user_request="Dismiss ad and continue.",
                arguments={"start_url": "https://example.test/demo"},
            )

            self.assertEqual("succeeded", result.status)
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                wait_run = conn.execute(
                    """
                    select sr.evidence_json
                    from step_runs sr
                    join workflow_skill_steps ws on ws.id = sr.step_id
                    where ws.name = 'wait_intermediate_ad_dismissed'
                    """
                ).fetchone()
            evidence = json.loads(wait_run["evidence_json"])
            self.assertTrue(evidence["browser_evaluation_used"])

    def test_cold_init_first_run_uses_eval_and_evolve_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_skills.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            eval_loop = FakeEvalLoop(
                WorkflowEvaluationReport(
                    status="passed",
                    page_text=LIVE_PAGE_TEXT,
                    step_evaluations=[
                        StepEvaluation(
                            step_name="open_naver_stock_search",
                            step_type="goto",
                            status="passed",
                            summary="Browser reached Naver during first run.",
                            evidence={},
                        )
                    ],
                )
            )

            result = ColdInitRunner(
                store,
                output_dir=output_dir,
                discovery_runner=StaticDiscoveryRunner(page_text=STALE_PAGE_TEXT),
                evaluation_loop=eval_loop,
            ).run(
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={"company_name": "삼성전자", "ticker": "005930", "news_limit": 1},
            )

            self.assertEqual("succeeded", result.run_result.status)
            self.assertEqual(310500, result.run_result.output["current_price"])
            self.assertEqual(1, len(eval_loop.calls))


if __name__ == "__main__":
    unittest.main()
