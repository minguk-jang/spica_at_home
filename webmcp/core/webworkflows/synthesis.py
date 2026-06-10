from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from webworkflows.cold_init_types import ArtifactTrace
from webworkflows.dynamic_browser import DYNAMIC_BROWSER_ACTION_STEP_TYPE, validate_dynamic_step_action


DEFAULT_CODEX_SYNTHESIS_MODEL = "gpt-5.5"


class SynthesisBackend(Protocol):
    provider: str

    def synthesize(self, *, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        ...


class FakeSynthesisBackend:
    provider = "fake"

    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.last_model: str | None = None
        self.last_prompt: str | None = None

    def synthesize(self, *, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        self.last_model = model
        self.last_prompt = prompt
        return self.response


class AgentJsonSynthesisBackend:
    provider = "agent_json"

    def __init__(
        self,
        *,
        workflow_json: dict[str, Any] | None = None,
        workflow_json_path: str | Path | None = None,
    ):
        if workflow_json is None and workflow_json_path is None:
            raise ValueError("AgentJsonSynthesisBackend requires workflow_json or workflow_json_path")
        self.workflow_json = workflow_json
        self.workflow_json_path = Path(workflow_json_path) if workflow_json_path else None
        self.last_model: str | None = None
        self.last_prompt: str | None = None

    def synthesize(self, *, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        self.last_model = model
        self.last_prompt = prompt
        if self.workflow_json is not None:
            return json.loads(json.dumps(self.workflow_json, ensure_ascii=False))
        if self.workflow_json_path is None:
            raise ValueError("workflow_json_path is required")
        return json.loads(self.workflow_json_path.read_text(encoding="utf-8"))


class CodexAppServerSynthesisBackend:
    provider = "codex_app_server"

    def __init__(
        self,
        *,
        cwd: str | Path | None = None,
        timeout_seconds: int = 180,
        app_server: Any | None = None,
    ):
        self.cwd = Path(cwd) if cwd else None
        self.timeout_seconds = timeout_seconds
        self.app_server = app_server or self._new_app_server()

    def synthesize(self, *, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        result = self.app_server.run_turn(
            prompt=_prompt_with_schema(prompt, schema),
            output_schema=schema,
            image_paths=[],
            model=model,
        )
        return json.loads(_extract_json(str(result.get("text") or "")))

    def close(self) -> None:
        close = getattr(self.app_server, "close", None)
        if callable(close):
            close()

    def _new_app_server(self):
        from webworkflows.vlm_codex import CodexAppServerJsonRpcClient

        return CodexAppServerJsonRpcClient(
            cwd=self.cwd,
            timeout_seconds=self.timeout_seconds,
            client_info={
                "name": "webmcp-workflow-synthesis",
                "title": "WebMCP Workflow Synthesis",
                "version": "0.1.0",
            },
            base_instructions=(
                "You synthesize reusable WebMCP workflow JSON from user-provided browser evidence. "
                "Do not use tools, shell commands, file reads, skills, web, or repo context."
            ),
            developer_instructions=(
                "Return only JSON matching the provided workflow schema. "
                "Do not include Markdown, Python, JavaScript, or Playwright code."
            ),
            request_error_message="WebMCP workflow synthesizer does not handle requests",
        )


@dataclass(frozen=True)
class SynthesisResult:
    provider: str
    model: str
    workflow_json: dict[str, Any]


class LLMWorkflowSynthesizer:
    def __init__(
        self,
        *,
        backend: SynthesisBackend | None = None,
        model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
    ):
        self.backend = backend or CodexAppServerSynthesisBackend()
        self.model = model

    @property
    def provider(self) -> str:
        return f"llm_{self.backend.provider}"

    def synthesize_json(self, trace: ArtifactTrace) -> SynthesisResult:
        known_workflow = known_workflow_json_for_trace(trace)
        if known_workflow:
            validate_workflow_json(known_workflow)
            return SynthesisResult(
                provider=str(known_workflow.get("_synthesis_provider") or "known_workflow"),
                model=self.model,
                workflow_json=_without_private_keys(known_workflow),
            )

        prompt = build_synthesis_prompt(trace)
        workflow_json = self.backend.synthesize(
            prompt=prompt,
            schema=WORKFLOW_JSON_SCHEMA,
            model=self.model,
        )
        workflow_json = bind_known_handlers(workflow_json)
        validate_workflow_json(workflow_json)
        return SynthesisResult(provider=self.provider, model=self.model, workflow_json=workflow_json)

    def synthesize(self, trace: ArtifactTrace):
        from webworkflows.cold_init import discovery_from_workflow_json

        result = self.synthesize_json(trace)
        return discovery_from_workflow_json(result.workflow_json, provider=result.provider, page_text=trace.page_text)


def build_synthesis_prompt(trace: ArtifactTrace) -> str:
    page_analysis_context_json = json.dumps(
        trace.page_analysis_context or {},
        ensure_ascii=False,
        sort_keys=True,
    )
    knowledge_context_json = json.dumps(
        trace.knowledge_context or [],
        ensure_ascii=False,
        sort_keys=True,
    )
    step_guide_json = json.dumps(
        _normalized_step_guide(trace.arguments.get("step_guide")),
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        "You are synthesizing a reusable WebMCP workflow JSON for a browser workflow.\n"
        "Return only JSON matching the provided schema. Do not include Python code.\n"
        "Use repo handler refs only when suitable; for Naver stock extraction use "
        "`naver_stock.extract_stock_card`.\n\n"
        "Required top-level keys: skill_name, slug, description, domain, task_type, body_md, "
        "input_schema, output_schema, arguments, steps, resources, handlers.\n"
        "Allowed step_type values: goto, click, click_text, fill, press, select_suggestion, "
        "llm_browser_action, wait_for_text, run_handler, assert_output, render_report.\n"
        "Each step must include: name, description, step_type, handler_ref, action, "
        "argument_bindings, assertions, fallback_policy, update_policy.\n"
        "Because the schema is strict, include unused fields as null, empty arrays, or empty objects "
        "instead of omitting them.\n"
        "Use double-brace placeholders for dynamic values, for example {{start_url}} or {{company_name}}.\n"
        "Infer arguments from the user task and final state. Do not add stock-specific arguments "
        "such as company_name or ticker unless the requested task is actually a stock workflow.\n"
        "When no repo handler exists for extraction, prefer a deterministic workflow with goto, "
        "wait_for_text, and render_report steps. Do not invent new handler modules or functions.\n"
        "For variable browser work such as closing ads/popups/modals, selecting UI that changes per run, or "
        "handling unstable page chrome, use `llm_browser_action`. Store only action.instruction, "
        "action.success_criteria, action.allowed_operations, and action.timeout_ms. Do not store generated JavaScript, "
        "Python, Playwright code, script, or selectors produced by the runtime LLM in the workflow JSON; that code is "
        "generated at runtime only.\n"
        "Do not invent executable code. Store templates, handler refs, assertions, dynamic instructions, and static JSON only.\n\n"
        "If Human-authored step guide JSON is non-empty, treat it as a scaffold: preserve the guide order "
        "and intent, keep recognizable step names when valid, and translate rough step types/descriptions into "
        "executable WebMCP steps using discovered page evidence. Fill missing selectors, actions, waits, "
        "handlers, and assertions; do not copy vague guide text as the final assertion.\n\n"
        "For a Naver stock report, prefer these semantic steps: open_naver_stock_search, "
        "wait_stock_card, extract_stock_card, validate_stock_output, render_stock_report.\n\n"
        f"User request: {trace.user_request}\n"
        f"Arguments JSON: {json.dumps(trace.arguments, ensure_ascii=False, sort_keys=True)}\n"
        f"Start URL: {trace.arguments.get('start_url', '')}\n"
        f"Expected final browser state: {trace.arguments.get('final_state', '')}\n"
        f"Discovery provider: {trace.provider}\n"
        f"Final URL: {trace.final_url or ''}\n"
        f"Page title: {trace.title or ''}\n"
        "Human-authored step guide JSON:\n"
        f"{step_guide_json[:3000]}\n"
        "Reusable page analysis context JSON:\n"
        f"{page_analysis_context_json[:3000]}\n"
        "Reusable script generation knowledge JSON:\n"
        f"{knowledge_context_json[:3000]}\n"
        "Page text excerpt:\n"
        f"{trace.page_text[:6000]}\n"
    )


def _normalized_step_guide(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    guide: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        step_type = str(item.get("step_type") or item.get("stepType") or "").strip()
        if not name and not description:
            continue
        guide.append(
            {
                "name": name or f"step_{index + 1}",
                "description": description,
                "step_type": step_type or "click",
            }
        )
    return guide


def validate_workflow_json(workflow: dict[str, Any]) -> None:
    required = [
        "skill_name",
        "slug",
        "description",
        "domain",
        "task_type",
        "body_md",
        "input_schema",
        "output_schema",
        "arguments",
        "steps",
        "resources",
        "handlers",
    ]
    for key in required:
        if key not in workflow:
            raise ValueError(f"workflow JSON missing required key: {key}")
    if not isinstance(workflow["steps"], list) or not workflow["steps"]:
        raise ValueError("workflow JSON requires at least one step")
    allowed_step_types = {
        "goto",
        "click",
        "click_text",
        "fill",
        "press",
        "select_suggestion",
        "wait_for_text",
        "run_handler",
        "assert_output",
        "render_report",
    }
    allowed_step_types.add(DYNAMIC_BROWSER_ACTION_STEP_TYPE)
    for step in workflow["steps"]:
        for key in ["name", "description", "step_type", "action", "assertions"]:
            if key not in step:
                raise ValueError(f"workflow step missing required key: {key}")
        if step["step_type"] not in allowed_step_types:
            raise ValueError(f"unsupported synthesized step_type: {step['step_type']}")
        if step["step_type"] == "run_handler" and not step.get("handler_ref"):
            raise ValueError(f"run_handler step missing handler_ref: {step['name']}")
        if step["step_type"] == DYNAMIC_BROWSER_ACTION_STEP_TYPE:
            validate_dynamic_step_action(step.get("action") or {}, step_name=str(step.get("name") or "unknown"))


def bind_known_handlers(workflow: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(workflow, ensure_ascii=False))
    handler_refs = {
        step.get("handler_ref")
        for step in normalized.get("steps", [])
        if step.get("step_type") == "run_handler" and step.get("handler_ref")
    }
    handlers = list(normalized.get("handlers", []))

    if "naver_stock.extract_stock_card" in handler_refs:
        handlers = [
            handler
            for handler in handlers
            if handler.get("name") not in {"extract_stock_card", "naver_stock.extract_stock_card"}
        ]
        handlers.append(_known_naver_stock_handler())
    if "naver_map.extract_subway_duration" in handler_refs:
        handlers = [
            handler
            for handler in handlers
            if handler.get("name") not in {"extract_subway_duration", "naver_map.extract_subway_duration"}
        ]
        handlers.append(_known_naver_map_handler())

    normalized["handlers"] = handlers
    return normalized


def _known_naver_stock_handler() -> dict[str, Any]:
    return {
        "name": "naver_stock.extract_stock_card",
        "description": "Extract stock quote fields from Naver stock search text.",
        "module": "webworkflows.handlers.naver_stock",
        "function": "extract_stock_card",
        "input_schema": {"page_text": "string", "company_name": "string", "ticker": "string"},
        "output_schema": {"company_name": "string", "current_price": "string"},
        "allowed_domains": ["naver.com", "search.naver.com", "finance.naver.com"],
    }


def _known_naver_map_handler() -> dict[str, Any]:
    return {
        "name": "naver_map.extract_subway_duration",
        "description": "Extract a subway route duration from Naver Map transit results.",
        "module": "webworkflows.handlers.naver_map",
        "function": "extract_subway_duration",
        "input_schema": {"page_text": "string", "start_station": "string", "end_station": "string"},
        "output_schema": {"duration_text": "string", "duration_minutes": "integer", "route_summary": "string"},
        "allowed_domains": ["naver.com", "map.naver.com"],
    }


def known_workflow_json_for_trace(trace: ArtifactTrace) -> dict[str, Any] | None:
    if not _looks_like_naver_map_route(trace):
        return None
    start_station, end_station = _station_pair(trace)
    if not start_station or not end_station:
        return None
    return naver_map_transit_route_workflow_json(
        start_station=start_station,
        end_station=end_station,
        start_url=str(trace.arguments.get("start_url") or "https://www.naver.com"),
    )


def naver_map_transit_route_workflow_json(
    *,
    start_station: str = "양재역",
    end_station: str = "사당역",
    start_url: str = "https://www.naver.com",
) -> dict[str, Any]:
    return {
        "_synthesis_provider": "known_naver_map_route",
        "skill_name": "naver_map_transit_route",
        "slug": "naver-map-transit-route",
        "description": "네이버 지도에서 출발역과 도착역 사이의 지하철 대중교통 소요 시간을 검색하고 요약한다.",
        "domain": "map.naver.com",
        "task_type": "transit_route_duration",
        "body_md": "Deterministic browser workflow for Naver Map subway transit route duration.",
        "input_schema": {
            "start_station": {"type": "string", "required": True},
            "end_station": {"type": "string", "required": True},
            "start_url": {"type": "string", "required": False, "default": start_url},
            "page_text": {"type": "string", "required": False},
        },
        "output_schema": {
            "start_station": "string",
            "end_station": "string",
            "duration_text": "string",
            "duration_minutes": "integer",
            "route_summary": "string",
            "report_text": "string",
        },
        "arguments": [
            _argument("start_station", "출발 지하철역", "string", True, None, {"min_length": 1}, [start_station], True, 0),
            _argument("end_station", "도착 지하철역", "string", True, None, {"min_length": 1}, [end_station], True, 1),
            _argument("start_url", "네이버 시작 URL", "string", False, start_url, {}, [start_url], False, 2),
            _argument("page_text", "브라우저 평가 또는 캐시 실행에 사용할 페이지 전체 텍스트", "string", False, None, {}, [], True, 3),
        ],
        "steps": [
            {
                "name": "open_naver_home",
                "description": "Open the requested Naver start page.",
                "step_type": "goto",
                "handler_ref": None,
                "action": {"url_template": "{{start_url}}"},
                "argument_bindings": {},
                "assertions": {"url_contains": "naver.com"},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "open_naver_map_directions",
                "description": "Open Naver Map's public transit direction panel.",
                "step_type": "goto",
                "handler_ref": None,
                "action": {"url_template": "https://map.naver.com/p/directions/-/-/-/transit?c=15.00,0,0,0,dh"},
                "argument_bindings": {},
                "assertions": {"url_contains": "map.naver.com"},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "wait_direction_form",
                "description": "Wait until the route form is visible.",
                "step_type": "wait_for_text",
                "handler_ref": None,
                "action": {"source": "page_text"},
                "argument_bindings": {},
                "assertions": {"contains_any": ["출발지 입력", "도착지 입력", "대중교통"]},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "fill_start_station",
                "description": "Enter the start station.",
                "step_type": "fill",
                "handler_ref": None,
                "action": {"selector": "input.input_search", "nth": 0, "value_template": "{{start_station}}"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "select_start_station",
                "description": "Select the station autocomplete result for the start station.",
                "step_type": "select_suggestion",
                "handler_ref": None,
                "action": {"markers": ["지하철,전철", "{{start_station}}"], "candidate_selector": "button,a,li,div"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "fill_end_station",
                "description": "Enter the end station.",
                "step_type": "fill",
                "handler_ref": None,
                "action": {"selector": "input.input_search", "nth": 1, "value_template": "{{end_station}}"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "select_end_station",
                "description": "Select the station autocomplete result for the end station.",
                "step_type": "select_suggestion",
                "handler_ref": None,
                "action": {"markers": ["지하철,전철", "{{end_station}}"], "candidate_selector": "button,a,li,div"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "submit_route_search",
                "description": "Run the route search.",
                "step_type": "click",
                "handler_ref": None,
                "action": {"selector": "button.btn_direction.search", "nth": 0},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "wait_route_results",
                "description": "Wait for route duration results.",
                "step_type": "wait_for_text",
                "handler_ref": None,
                "action": {"source": "page_text"},
                "argument_bindings": {},
                "assertions": {"contains_any": ["지하철", "{{end_station}}", "분"]},
                "fallback_policy": {"retry": 1},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "extract_subway_duration",
                "description": "Extract the subway route duration from Naver Map result text.",
                "step_type": "run_handler",
                "handler_ref": "naver_map.extract_subway_duration",
                "action": {
                    "inputs": {
                        "page_text": "{{page_text}}",
                        "start_station": "{{start_station}}",
                        "end_station": "{{end_station}}",
                    }
                },
                "argument_bindings": {},
                "assertions": {"required_output": ["duration_text", "duration_minutes", "route_summary"]},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "validate_route_output",
                "description": "Validate that the route output matches the requested stations.",
                "step_type": "assert_output",
                "handler_ref": None,
                "action": {},
                "argument_bindings": {},
                "assertions": {
                    "equals": {"start_station": "{{start_station}}", "end_station": "{{end_station}}"},
                    "required_output": ["duration_text", "duration_minutes"],
                },
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
            {
                "name": "render_route_report",
                "description": "Render a Markdown route summary.",
                "step_type": "render_report",
                "handler_ref": None,
                "action": {"template_resource": "route_report_markdown"},
                "argument_bindings": {},
                "assertions": {"required_output": ["report_text"]},
                "fallback_policy": {"retry": 0},
                "update_policy": {"record_update_event": True},
            },
        ],
        "resources": [
            {
                "resource_type": "report_template",
                "name": "route_report_markdown",
                "description": "Markdown template for a Naver Map route duration report.",
                "content_json": None,
                "content_text": (
                    "# 네이버 지도 지하철 경로\n\n"
                    "- 출발: {{start_station}}\n"
                    "- 도착: {{end_station}}\n"
                    "- 소요 시간: {{duration_text}}\n\n"
                    "{{route_summary}}\n"
                ),
                "load_when": {"step": "render_route_report"},
            }
        ],
        "handlers": [_known_naver_map_handler()],
    }


def naver_stock_workflow_json() -> dict[str, Any]:
    return {
        "skill_name": "naver_stock_report",
        "slug": "naver-stock-report",
        "description": "네이버에서 기업 주가를 검색하고 현재가, 등락률, 종목코드, 관련 뉴스 기반 리포트를 작성한다.",
        "domain": "naver.com",
        "task_type": "stock_report",
        "body_md": "LLM synthesized this workflow from discovery evidence for a Naver stock report task.",
        "input_schema": {
            "company_name": {"type": "string", "required": True},
            "ticker": {"type": "string", "required": False},
            "page_text": {"type": "string", "required": False},
            "news_limit": {"type": "integer", "required": False, "default": 3},
        },
        "output_schema": {
            "company_name": "string",
            "ticker": "string",
            "current_price": "integer",
            "change_text": "string",
            "report_text": "string",
        },
        "arguments": [
            _argument("company_name", "검색할 기업명", "string", True, None, {"min_length": 1}, ["삼성전자"], True, 0),
            _argument("ticker", "종목코드", "string", False, None, {"pattern": "^[0-9]{6}$"}, ["005930"], True, 1),
            _argument("page_text", "탐색 또는 캐시 실행에 사용할 페이지 전체 텍스트", "string", False, None, {}, [], True, 2),
            _argument("news_limit", "리포트에 포함할 뉴스 수", "integer", False, 3, {"minimum": 0, "maximum": 10}, [3], True, 3),
        ],
        "steps": [
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
                "description": "Extract stock quote fields from Naver text.",
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
        "resources": [
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
        "handlers": [
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
    }


STRING_FIELD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "required"],
    "properties": {"type": {"type": "string"}, "required": {"type": "boolean"}},
}

WORKFLOW_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "skill_name",
        "slug",
        "description",
        "domain",
        "task_type",
        "body_md",
        "input_schema",
        "output_schema",
        "arguments",
        "steps",
        "resources",
        "handlers",
    ],
    "properties": {
        "skill_name": {"type": "string"},
        "slug": {"type": "string"},
        "description": {"type": "string"},
        "domain": {"type": "string"},
        "task_type": {"type": "string"},
        "body_md": {"type": "string"},
        "input_schema": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": True,
                "required": ["type", "required"],
                "properties": {
                    "type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "default": {"type": ["string", "integer", "number", "boolean", "null"]},
                },
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "arguments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "name",
                    "description",
                    "type",
                    "required",
                    "default_value",
                    "validation",
                    "examples",
                    "is_dynamic",
                    "order_index",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "default_value": {"type": ["string", "integer", "null"]},
                    "validation": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "min_length": {"type": ["integer", "null"]},
                            "pattern": {"type": ["string", "null"]},
                            "minimum": {"type": ["integer", "null"]},
                            "maximum": {"type": ["integer", "null"]},
                        },
                    },
                    "examples": {"type": "array", "items": {"type": ["string", "integer"]}},
                    "is_dynamic": {"type": "boolean"},
                    "order_index": {"type": "integer"},
                },
            },
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "name",
                    "description",
                    "step_type",
                    "handler_ref",
                    "action",
                    "argument_bindings",
                    "assertions",
                    "fallback_policy",
                    "update_policy",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "step_type": {"type": "string"},
                    "handler_ref": {"type": ["string", "null"]},
                    "action": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": [],
                        "properties": {
                            "url_template": {"type": ["string", "null"]},
                            "selector": {"type": ["string", "null"]},
                            "source": {"type": ["string", "null"]},
                            "input_key": {"type": ["string", "null"]},
                            "value_template": {"type": ["string", "null"]},
                            "text": {"type": ["string", "null"]},
                            "template_resource": {"type": ["string", "null"]},
                            "instruction": {"type": ["string", "null"]},
                            "success_criteria": {"type": "array", "items": {"type": "string"}},
                            "allowed_operations": {"type": "array", "items": {"type": "string"}},
                            "timeout_ms": {"type": ["integer", "null"]},
                            "settle_ms": {"type": ["integer", "null"]},
                            "nth": {"type": ["integer", "null"]},
                            "exact": {"type": ["boolean", "null"]},
                        },
                    },
                    "argument_bindings": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {},
                        "required": [],
                    },
                    "assertions": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "url_contains",
                            "contains_any",
                            "required_output",
                            "equals",
                            "optional_equals",
                        ],
                        "properties": {
                            "url_contains": {"type": ["string", "null"]},
                            "contains_any": {"type": "array", "items": {"type": "string"}},
                            "required_output": {"type": "array", "items": {"type": "string"}},
                            "equals": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["company_name"],
                                "properties": {"company_name": {"type": ["string", "null"]}},
                            },
                            "optional_equals": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["ticker"],
                                "properties": {"ticker": {"type": ["string", "null"]}},
                            },
                        },
                    },
                    "fallback_policy": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["retry"],
                        "properties": {"retry": {"type": "integer"}},
                    },
                    "update_policy": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["record_update_event"],
                        "properties": {"record_update_event": {"type": "boolean"}},
                    },
                },
            },
        },
        "resources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "resource_type",
                    "name",
                    "description",
                    "content_json",
                    "content_text",
                    "load_when",
                ],
                "properties": {
                    "resource_type": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "content_json": {"type": "null"},
                    "content_text": {"type": "string"},
                    "load_when": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["step"],
                        "properties": {"step": {"type": "string"}},
                    },
                },
            },
        },
        "handlers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "name",
                    "description",
                    "module",
                    "function",
                    "input_schema",
                    "output_schema",
                    "allowed_domains",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "module": {"type": "string"},
                    "function": {"type": "string"},
                    "input_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["page_text", "company_name", "ticker"],
                        "properties": {
                            "page_text": {"type": "string"},
                            "company_name": {"type": "string"},
                            "ticker": {"type": "string"},
                        },
                    },
                    "output_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["company_name", "current_price"],
                        "properties": {
                            "company_name": {"type": "string"},
                            "current_price": {"type": "string"},
                        },
                    },
                    "allowed_domains": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


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


def _prompt_with_schema(prompt: str, schema: dict[str, Any]) -> str:
    return (
        f"{prompt}\n\n"
        "Return only JSON. The following JSON Schema is a validation reference; "
        "do not wrap the response in Markdown.\n"
        f"{json.dumps(schema, ensure_ascii=False, sort_keys=True)}"
    )


def _without_private_keys(workflow: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in workflow.items() if not key.startswith("_")}


def _looks_like_naver_map_route(trace: ArtifactTrace) -> bool:
    text = " ".join(
        [
            trace.user_request or "",
            str(trace.arguments.get("final_state") or ""),
            str(trace.arguments.get("start_url") or ""),
            trace.final_url or "",
            trace.title or "",
        ]
    ).lower()
    return (
        ("naver" in text or "네이버" in text)
        and "지도" in text
        and any(token in text for token in ["길찾기", "대중교통", "지하철", "route", "transit"])
    )


def _station_pair(trace: ArtifactTrace) -> tuple[str | None, str | None]:
    arguments = trace.arguments
    start = _first_string(
        arguments,
        [
            "start_station",
            "origin_station",
            "from_station",
            "departure_station",
            "start",
            "origin",
        ],
    )
    end = _first_string(
        arguments,
        [
            "end_station",
            "destination_station",
            "to_station",
            "arrival_station",
            "end",
            "destination",
        ],
    )
    if start and end:
        return start, end

    station_pattern = re.compile(r"([가-힣A-Za-z0-9]+역)\s*(?:에서|출발).*?([가-힣A-Za-z0-9]+역)\s*(?:까지|으로|로|도착)")
    match = station_pattern.search(trace.user_request) or station_pattern.search(str(arguments.get("final_state") or ""))
    if match:
        return start or match.group(1), end or match.group(2)

    simple_match = re.search(r"([가-힣A-Za-z0-9]+역)\s*에서\s*([가-힣A-Za-z0-9]+역)", trace.user_request)
    if simple_match:
        return start or simple_match.group(1), end or simple_match.group(2)
    return start, end


def _first_string(arguments: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Codex synthesis output did not contain JSON")
    return stripped[start : end + 1]
