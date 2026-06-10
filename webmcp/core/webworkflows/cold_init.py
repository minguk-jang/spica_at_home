from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import quote
import time
from dataclasses import dataclass, replace
from typing import Any, Protocol

from webworkflows.eval_loop import EvalAndEvolveLoop
from webworkflows.executor import WorkflowExecutor, WorkflowRunResult
from webworkflows.loader import WorkflowSkill, WorkflowSkillLoader
from webworkflows.cold_init_types import ArtifactTrace
from webworkflows.page_memory import PageAnalysisStore, WorkflowKnowledgeStore
from webworkflows.storage import WorkflowSkillStore, dumps


@dataclass(frozen=True)
class DiscoveryResult:
    provider: str
    skill_name: str
    slug: str
    description: str
    domain: str
    task_type: str
    body_md: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    arguments: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    handlers: list[dict[str, Any]]
    page_text: str


class DiscoveryRunner(Protocol):
    provider: str

    def discover(self, user_request: str, arguments: dict[str, Any]) -> DiscoveryResult:
        ...


class TraceCollector(Protocol):
    provider: str

    def collect(self, user_request: str, arguments: dict[str, Any]) -> ArtifactTrace:
        ...


class WorkflowSynthesizer(Protocol):
    provider: str
    model: str

    def synthesize_json(self, trace: ArtifactTrace):
        ...


class StaticDiscoveryRunner:
    provider = "static_fixture"

    def __init__(self, page_text: str):
        self.page_text = page_text

    def discover(self, user_request: str, arguments: dict[str, Any]) -> DiscoveryResult:
        return DiscoveryResult(
            provider=self.provider,
            skill_name="naver_stock_report",
            slug="naver-stock-report",
            description="네이버에서 기업 주가를 검색하고 현재가, 등락률, 종목코드, 관련 뉴스 기반 리포트를 작성한다.",
            domain="naver.com",
            task_type="stock_report",
            body_md=(
                "Cold init created this workflow from discovery evidence for a Naver stock report task."
            ),
            input_schema={
                "company_name": {"type": "string", "required": True},
                "ticker": {"type": "string", "required": False},
                "page_text": {"type": "string", "required": False},
                "news_limit": {"type": "integer", "required": False, "default": 3},
            },
            output_schema={
                "company_name": "string",
                "ticker": "string",
                "current_price": "integer",
                "change_text": "string",
                "report_text": "string",
            },
            arguments=[
                _argument("company_name", "검색할 기업명", "string", True, None, {"min_length": 1}, ["삼성전자"], True, 0),
                _argument("ticker", "종목코드", "string", False, None, {"pattern": "^[0-9]{6}$"}, ["005930"], True, 1),
                _argument("page_text", "탐색 또는 캐시 실행에 사용할 페이지 전체 텍스트", "string", False, None, {}, [], True, 2),
                _argument("news_limit", "리포트에 포함할 뉴스 수", "integer", False, 3, {"minimum": 0, "maximum": 10}, [3], True, 3),
            ],
            steps=[
                {
                    "name": "open_naver_stock_search",
                    "description": "Build the Naver search URL for the company stock query.",
                    "step_type": "goto",
                    "handler_ref": None,
                    "action": {"url_template": "https://search.naver.com/search.naver?query={{company_name}} 주가"},
                    "argument_bindings": {},
                    "assertions": {"url_contains": "search.naver.com"},
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
                {
                    "name": "wait_stock_card",
                    "description": "Require stock result text to be present.",
                    "step_type": "wait_for_text",
                    "handler_ref": None,
                    "action": {"source": "page_text"},
                    "argument_bindings": {},
                    "assertions": {"contains_any": ["증권정보", "현재가", "{{company_name}}"]},
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
                {
                    "name": "extract_stock_card",
                    "description": "Extract stock quote fields from discovered Naver text.",
                    "step_type": "run_handler",
                    "handler_ref": "naver_stock.extract_stock_card",
                    "action": {"input_key": "page_text"},
                    "argument_bindings": {},
                    "assertions": {"required_output": ["company_name", "current_price"]},
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
                {
                    "name": "validate_stock_output",
                    "description": "Validate extracted fields against requested arguments.",
                    "step_type": "assert_output",
                    "handler_ref": None,
                    "action": {},
                    "argument_bindings": {},
                    "assertions": {
                        "equals": {"company_name": "{{company_name}}"},
                        "optional_equals": {"ticker": "{{ticker}}"},
                    },
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
                {
                    "name": "render_stock_report",
                    "description": "Render a Markdown report from extracted fields.",
                    "step_type": "render_report",
                    "handler_ref": None,
                    "action": {"template_resource": "stock_report_markdown"},
                    "argument_bindings": {},
                    "assertions": {"required_output": ["report_text"]},
                    "fallback_policy": {"retry": 0},
                    "update_policy": {"record_update_event": True},
                },
            ],
            resources=[
                {
                    "resource_type": "report_template",
                    "name": "stock_report_markdown",
                    "description": "Markdown template for a Naver stock report.",
                    "content_json": None,
                    "content_text": (
                        "# {{company_name}} 주가 리포트\n\n"
                        "- 종목코드: {{ticker}}\n"
                        "- 현재가: {{current_price_formatted}}원\n"
                        "- 등락 정보: {{change_text}}\n"
                        "- 시장 상태: {{market_status}}\n\n"
                        "## 관련 맥락\n"
                        "{{news_context}}\n"
                    ),
                    "load_when": {"step": "render_stock_report"},
                }
            ],
            handlers=[
                {
                    "name": "naver_stock.extract_stock_card",
                    "description": "Extract stock quote fields from Naver stock search text.",
                    "module": "webworkflows.handlers.naver_stock",
                    "function": "extract_stock_card",
                    "input_schema": {"page_text": "string", "company_name": "string", "ticker": "string optional"},
                    "output_schema": {"company_name": "string", "current_price": "integer"},
                    "allowed_domains": ["naver.com"],
                }
            ],
            page_text=self.page_text,
        )


class StaticTraceCollector:
    provider = "static_trace"

    def __init__(self, page_text: str):
        self.page_text = page_text

    def collect(self, user_request: str, arguments: dict[str, Any]) -> ArtifactTrace:
        return ArtifactTrace(
            provider=self.provider,
            user_request=user_request,
            arguments=dict(arguments),
            page_text=self.page_text,
        )


class NaverBrowserDiscoveryRunner:
    provider = "naver_browser"

    def __init__(self, *, output_dir, headed: bool = False, browser_name: str = "firefox"):
        self.output_dir = Path(output_dir)
        self.headed = headed
        self.browser_name = browser_name

    def discover(self, user_request: str, arguments: dict[str, Any]) -> DiscoveryResult:
        page_text = asyncio.run(self._collect_page_text(arguments))
        return replace(
            StaticDiscoveryRunner(page_text=page_text).discover(user_request, arguments),
            provider=self.provider,
        )

    async def _collect_page_text(self, arguments: dict[str, Any]) -> str:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required for naver-browser discovery. "
                "Run with reference/webwright/.venv/bin/python or install playwright."
            ) from exc

        company_name = arguments["company_name"]
        query = quote(f"{company_name} 주가")
        start_url = f"https://search.naver.com/search.naver?query={query}"
        screenshots = self.output_dir / "discovery_screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            browser_type = getattr(playwright, self.browser_name)
            browser = await browser_type.launch(headless=not self.headed)
            context = await browser.new_context(viewport={"width": 1280, "height": 1800})
            page = await context.new_page()
            await page.goto(start_url, wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            await page.screenshot(path=str(screenshots / "cold_init_naver_stock.png"))
            page_text = await page.locator("body").inner_text(timeout=15000)
            await browser.close()
        return page_text


class NaverBrowserTraceCollector:
    provider = "naver_browser_trace"

    def __init__(self, *, output_dir, headed: bool = False, browser_name: str = "firefox"):
        self.output_dir = Path(output_dir)
        self.headed = headed
        self.browser_name = browser_name

    def collect(self, user_request: str, arguments: dict[str, Any]) -> ArtifactTrace:
        page_text, title, final_url, screenshots = asyncio.run(self._collect_trace(arguments))
        return ArtifactTrace(
            provider=self.provider,
            user_request=user_request,
            arguments=dict(arguments),
            page_text=page_text,
            title=title,
            final_url=final_url,
            screenshots=screenshots,
        )

    async def _collect_trace(self, arguments: dict[str, Any]) -> tuple[str, str, str, list[str]]:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required for naver-browser trace collection. "
                "Run with reference/webwright/.venv/bin/python or install playwright."
            ) from exc

        company_name = arguments["company_name"]
        query = quote(f"{company_name} 주가")
        start_url = f"https://search.naver.com/search.naver?query={query}"
        screenshots_dir = self.output_dir / "discovery_screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshots_dir / "intelligent_cold_init_naver_stock.png"

        async with async_playwright() as playwright:
            browser_type = getattr(playwright, self.browser_name)
            browser = await browser_type.launch(headless=not self.headed)
            context = await browser.new_context(viewport={"width": 1280, "height": 1800})
            page = await context.new_page()
            await page.goto(start_url, wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            await page.screenshot(path=str(screenshot_path))
            page_text = await page.locator("body").inner_text(timeout=15000)
            title = await page.title()
            final_url = page.url
            await browser.close()
        return page_text, title, final_url, [str(screenshot_path)]


@dataclass(frozen=True)
class ColdInitResult:
    cold_init_run_id: int
    skill: WorkflowSkill
    run_result: WorkflowRunResult
    discovery_duration_ms: int
    materialization_duration_ms: int
    first_run_duration_ms: int


@dataclass(frozen=True)
class IntelligentColdInitResult:
    cold_init_run_id: int
    synthesis_run_id: int
    skill: WorkflowSkill
    run_result: WorkflowRunResult
    discovery_duration_ms: int
    synthesis_duration_ms: int
    materialization_duration_ms: int
    first_run_duration_ms: int


class WorkflowMaterializer:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def materialize(
        self,
        discovery: DiscoveryResult,
        *,
        skill_status: str = "stable",
        version_status: str = "stable",
    ) -> tuple[int, int]:
        with self.store.connect() as conn:
            existing = conn.execute(
                "select id, latest_version_id from workflow_tools where name = ? or slug = ?",
                (discovery.skill_name, discovery.slug),
            ).fetchone()
            if existing:
                return int(existing["id"]), int(existing["latest_version_id"])

            skill_id = int(
                conn.execute(
                    """
                    insert into workflow_tools
                      (name, slug, description, domain, task_type, status)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        discovery.skill_name,
                        discovery.slug,
                        discovery.description,
                        discovery.domain,
                        discovery.task_type,
                        skill_status,
                    ),
                ).lastrowid
            )
            version_id = int(
                conn.execute(
                    """
                    insert into workflow_tool_versions
                      (skill_id, version, summary, input_schema_json, output_schema_json,
                       body_md, load_policy_json, status)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill_id,
                        1,
                        f"Cold init workflow created by {discovery.provider}.",
                        dumps(discovery.input_schema),
                        dumps(discovery.output_schema),
                        discovery.body_md,
                        dumps({"metadata_first": True, "lazy_load_steps": True}),
                        version_status,
                    ),
                ).lastrowid
            )
            conn.execute(
                "update workflow_tools set latest_version_id = ? where id = ?",
                (version_id, skill_id),
            )
            for argument in discovery.arguments:
                conn.execute(
                    """
                    insert into workflow_tool_arguments
                      (version_id, name, description, type, required, default_value_json,
                       validation_json, examples_json, is_dynamic, order_index)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        argument["name"],
                        argument["description"],
                        argument["type"],
                        int(argument["required"]),
                        dumps(argument["default_value"]) if argument["default_value"] is not None else None,
                        dumps(argument["validation"]),
                        dumps(argument["examples"]),
                        int(argument["is_dynamic"]),
                        argument["order_index"],
                    ),
                )
            for index, step in enumerate(discovery.steps):
                conn.execute(
                    """
                    insert into workflow_tool_steps
                      (version_id, order_index, name, description, step_type, handler_ref,
                       action_json, argument_bindings_json, assertions_json,
                       fallback_policy_json, update_policy_json)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        index,
                        step["name"],
                        step["description"],
                        step["step_type"],
                        step["handler_ref"],
                        dumps(step["action"]),
                        dumps(step["argument_bindings"]),
                        dumps(step["assertions"]),
                        dumps(step["fallback_policy"]),
                        dumps(step["update_policy"]),
                    ),
                )
            for resource in discovery.resources:
                conn.execute(
                    """
                    insert into workflow_tool_resources
                      (version_id, resource_type, name, description, content_json, content_text, load_when_json)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        resource["resource_type"],
                        resource["name"],
                        resource["description"],
                        dumps(resource["content_json"]) if resource["content_json"] is not None else None,
                        resource["content_text"],
                        dumps(resource["load_when"]),
                    ),
                )
            for handler in discovery.handlers:
                conn.execute(
                    """
                    insert or ignore into handler_registry
                      (name, description, module, function, input_schema_json, output_schema_json, allowed_domains_json)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        handler["name"],
                        handler["description"],
                        handler["module"],
                        handler["function"],
                        dumps(handler["input_schema"]),
                        dumps(handler["output_schema"]),
                        dumps(handler["allowed_domains"]),
                    ),
                )
            return skill_id, version_id


def discovery_from_workflow_json(
    workflow: dict[str, Any],
    *,
    provider: str,
    page_text: str,
) -> DiscoveryResult:
    return DiscoveryResult(
        provider=provider,
        skill_name=workflow["skill_name"],
        slug=workflow["slug"],
        description=workflow["description"],
        domain=workflow["domain"],
        task_type=workflow["task_type"],
        body_md=workflow["body_md"],
        input_schema=workflow["input_schema"],
        output_schema=workflow["output_schema"],
        arguments=workflow["arguments"],
        steps=workflow["steps"],
        resources=workflow["resources"],
        handlers=workflow["handlers"],
        page_text=page_text,
    )


class ColdInitRunner:
    def __init__(
        self,
        store: WorkflowSkillStore,
        *,
        output_dir,
        discovery_runner: DiscoveryRunner,
        evaluation_loop: EvalAndEvolveLoop | None = None,
    ):
        self.store = store
        self.output_dir = output_dir
        self.discovery_runner = discovery_runner
        self.evaluation_loop = evaluation_loop

    def run(self, *, user_request: str, arguments: dict[str, Any]) -> ColdInitResult:
        cold_init_run_id = self._create_cold_init_run(user_request, arguments)
        try:
            discovery_started = time.perf_counter()
            discovery = self.discovery_runner.discover(user_request, arguments)
            discovery_duration_ms = _elapsed_ms(discovery_started)

            materialization_started = time.perf_counter()
            skill_id, version_id = WorkflowMaterializer(self.store).materialize(discovery)
            materialization_duration_ms = _elapsed_ms(materialization_started)

            skill = WorkflowSkillLoader(self.store).load_skill(skill_id)
            first_run_arguments = dict(arguments)
            first_run_arguments.setdefault("page_text", discovery.page_text)
            run_result = WorkflowExecutor(self.store, output_dir=self.output_dir, evaluation_loop=self.evaluation_loop).run(
                skill,
                user_request=user_request,
                arguments=first_run_arguments,
            )
            first_run_duration_ms = _duration_for_run(self.store, run_result.run_id)

            self._finish_cold_init_run(
                cold_init_run_id,
                status="succeeded",
                discovery_duration_ms=discovery_duration_ms,
                synthesis_duration_ms=None,
                synthesis_run_id=None,
                materialization_duration_ms=materialization_duration_ms,
                first_run_duration_ms=first_run_duration_ms,
                created_skill_id=skill_id,
                created_version_id=version_id,
                workflow_run_id=run_result.run_id,
                error=None,
            )
            return ColdInitResult(
                cold_init_run_id=cold_init_run_id,
                skill=skill,
                run_result=run_result,
                discovery_duration_ms=discovery_duration_ms,
                materialization_duration_ms=materialization_duration_ms,
                first_run_duration_ms=first_run_duration_ms,
            )
        except Exception as exc:
            self._finish_cold_init_run(
                cold_init_run_id,
                status="failed",
                discovery_duration_ms=None,
                synthesis_duration_ms=None,
                synthesis_run_id=None,
                materialization_duration_ms=None,
                first_run_duration_ms=None,
                created_skill_id=None,
                created_version_id=None,
                workflow_run_id=None,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise

    def _create_cold_init_run(self, user_request: str, arguments: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into cold_init_runs
                      (user_request, input_json, status, discovery_provider)
                    values (?, ?, ?, ?)
                    """,
                    (user_request, dumps(arguments), "running", self.discovery_runner.provider),
                ).lastrowid
            )

    def _finish_cold_init_run(
        self,
        cold_init_run_id: int,
        *,
        status: str,
        discovery_duration_ms: int | None,
        synthesis_duration_ms: int | None,
        synthesis_run_id: int | None,
        materialization_duration_ms: int | None,
        first_run_duration_ms: int | None,
        created_skill_id: int | None,
        created_version_id: int | None,
        workflow_run_id: int | None,
        error: dict[str, Any] | None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update cold_init_runs
                set status = ?, discovery_duration_ms = ?, synthesis_duration_ms = ?,
                    synthesis_run_id = ?, materialization_duration_ms = ?,
                    first_run_duration_ms = ?, created_skill_id = ?, created_version_id = ?,
                    workflow_run_id = ?, error_json = ?, finished_at = current_timestamp
                where id = ?
                """,
                (
                    status,
                    discovery_duration_ms,
                    synthesis_duration_ms,
                    synthesis_run_id,
                    materialization_duration_ms,
                    first_run_duration_ms,
                    created_skill_id,
                    created_version_id,
                    workflow_run_id,
                    dumps(error) if error else None,
                    cold_init_run_id,
                ),
            )


class IntelligentColdInitRunner:
    def __init__(
        self,
        store: WorkflowSkillStore,
        *,
        output_dir,
        trace_collector: TraceCollector,
        synthesizer: WorkflowSynthesizer,
        evaluation_loop: EvalAndEvolveLoop | None = None,
    ):
        self.store = store
        self.output_dir = output_dir
        self.trace_collector = trace_collector
        self.synthesizer = synthesizer
        self.evaluation_loop = evaluation_loop

    def run(self, *, user_request: str, arguments: dict[str, Any]) -> IntelligentColdInitResult:
        cold_init_run_id = self._create_cold_init_run(user_request, arguments)
        synthesis_run_id: int | None = None
        try:
            discovery_started = time.perf_counter()
            trace = self.trace_collector.collect(user_request, arguments)
            trace = self._enrich_trace_with_page_memory(trace)
            discovery_duration_ms = _elapsed_ms(discovery_started)

            synthesis_started = time.perf_counter()
            synthesis_result = self.synthesizer.synthesize_json(trace)
            synthesis_duration_ms = _elapsed_ms(synthesis_started)
            synthesis_run_id = self._record_synthesis_run(
                user_request=user_request,
                trace=trace,
                status="succeeded",
                duration_ms=synthesis_duration_ms,
                output_skill_json=synthesis_result.workflow_json,
                error=None,
            )

            discovery = discovery_from_workflow_json(
                synthesis_result.workflow_json,
                provider=synthesis_result.provider,
                page_text=trace.page_text,
            )
            materialization_started = time.perf_counter()
            skill_id, version_id = WorkflowMaterializer(self.store).materialize(discovery)
            materialization_duration_ms = _elapsed_ms(materialization_started)

            skill = WorkflowSkillLoader(self.store).load_skill(skill_id)
            first_run_arguments = dict(arguments)
            first_run_arguments.setdefault("page_text", trace.page_text)
            run_result = WorkflowExecutor(self.store, output_dir=self.output_dir, evaluation_loop=self.evaluation_loop).run(
                skill,
                user_request=user_request,
                arguments=first_run_arguments,
            )
            first_run_duration_ms = _duration_for_run(self.store, run_result.run_id)
            self._finish_cold_init_run(
                cold_init_run_id,
                status="succeeded",
                discovery_duration_ms=discovery_duration_ms,
                synthesis_duration_ms=synthesis_duration_ms,
                synthesis_run_id=synthesis_run_id,
                materialization_duration_ms=materialization_duration_ms,
                first_run_duration_ms=first_run_duration_ms,
                created_skill_id=skill_id,
                created_version_id=version_id,
                workflow_run_id=run_result.run_id,
                error=None,
            )
            return IntelligentColdInitResult(
                cold_init_run_id=cold_init_run_id,
                synthesis_run_id=synthesis_run_id,
                skill=skill,
                run_result=run_result,
                discovery_duration_ms=discovery_duration_ms,
                synthesis_duration_ms=synthesis_duration_ms,
                materialization_duration_ms=materialization_duration_ms,
                first_run_duration_ms=first_run_duration_ms,
            )
        except Exception as exc:
            if synthesis_run_id is None:
                synthesis_run_id = self._record_synthesis_run(
                    user_request=user_request,
                    trace=None,
                    status="failed",
                    duration_ms=None,
                    output_skill_json=None,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            self._finish_cold_init_run(
                cold_init_run_id,
                status="failed",
                discovery_duration_ms=None,
                synthesis_duration_ms=None,
                synthesis_run_id=synthesis_run_id,
                materialization_duration_ms=None,
                first_run_duration_ms=None,
                created_skill_id=None,
                created_version_id=None,
                workflow_run_id=None,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise

    def _enrich_trace_with_page_memory(self, trace: ArtifactTrace) -> ArtifactTrace:
        page_analysis = PageAnalysisStore(self.store).upsert_from_trace(trace, source="intelligent_cold_init")
        knowledge_entries = WorkflowKnowledgeStore(self.store).recent(category="script_generation", limit=5)
        return replace(
            trace,
            page_analysis_context=page_analysis.as_context(),
            knowledge_context=[entry.as_context() for entry in knowledge_entries],
        )

    def _create_cold_init_run(self, user_request: str, arguments: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into cold_init_runs
                      (user_request, input_json, status, discovery_provider)
                    values (?, ?, ?, ?)
                    """,
                    (user_request, dumps(arguments), "running", self.trace_collector.provider),
                ).lastrowid
            )

    def _record_synthesis_run(
        self,
        *,
        user_request: str,
        trace: ArtifactTrace | None,
        status: str,
        duration_ms: int | None,
        output_skill_json: dict[str, Any] | None,
        error: dict[str, Any] | None,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into workflow_synthesis_runs
                      (user_request, trace_json, status, synthesizer_provider, synthesizer_model,
                       llm_used, duration_ms, output_skill_json, error_json, finished_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
                    """,
                    (
                        user_request,
                        dumps(trace.to_json() if trace else {}),
                        status,
                        self.synthesizer.provider,
                        self.synthesizer.model,
                        1,
                        duration_ms,
                        dumps(output_skill_json) if output_skill_json else None,
                        dumps(error) if error else None,
                    ),
                ).lastrowid
            )

    def _finish_cold_init_run(
        self,
        cold_init_run_id: int,
        *,
        status: str,
        discovery_duration_ms: int | None,
        synthesis_duration_ms: int | None,
        synthesis_run_id: int | None,
        materialization_duration_ms: int | None,
        first_run_duration_ms: int | None,
        created_skill_id: int | None,
        created_version_id: int | None,
        workflow_run_id: int | None,
        error: dict[str, Any] | None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update cold_init_runs
                set status = ?, discovery_duration_ms = ?, synthesis_duration_ms = ?,
                    synthesis_run_id = ?, materialization_duration_ms = ?,
                    first_run_duration_ms = ?, created_skill_id = ?, created_version_id = ?,
                    workflow_run_id = ?, error_json = ?, finished_at = current_timestamp
                where id = ?
                """,
                (
                    status,
                    discovery_duration_ms,
                    synthesis_duration_ms,
                    synthesis_run_id,
                    materialization_duration_ms,
                    first_run_duration_ms,
                    created_skill_id,
                    created_version_id,
                    workflow_run_id,
                    dumps(error) if error else None,
                    cold_init_run_id,
                ),
            )


def _argument(
    name: str,
    description: str,
    typ: str,
    required: bool,
    default_value: Any,
    validation: dict[str, Any],
    examples: list[Any],
    is_dynamic: bool,
    order_index: int,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "type": typ,
        "required": required,
        "default_value": default_value,
        "validation": validation,
        "examples": examples,
        "is_dynamic": is_dynamic,
        "order_index": order_index,
    }


def _duration_for_run(store: WorkflowSkillStore, run_id: int) -> int:
    with store.connect() as conn:
        row = conn.execute("select duration_ms from workflow_runs where id = ?", (run_id,)).fetchone()
    return int(row["duration_ms"])


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
