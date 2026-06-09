from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from webworkflows.cold_init_types import ArtifactTrace


DEFAULT_CODEX_SYNTHESIS_MODEL = "gpt-5.3-codex-spark"


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


class CodexCliSynthesisBackend:
    provider = "codex_cli"

    def __init__(self, *, cwd: str | Path | None = None, timeout_seconds: int = 300):
        self.cwd = Path(cwd) if cwd else None
        self.timeout_seconds = timeout_seconds

    def synthesize(self, *, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "workflow_schema.json"
            output_path = Path(tmp) / "workflow_output.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            command = [
                "codex",
                "exec",
                "--model",
                model,
                "--ephemeral",
                "--ignore-rules",
                "--ignore-user-config",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                prompt,
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(self.cwd) if self.cwd else None,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "codex exec synthesis failed "
                    f"(exit={exc.returncode}, model={model}).\n"
                    f"STDERR:\n{exc.stderr}\nSTDOUT:\n{exc.stdout}"
                ) from exc
            raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        return json.loads(_extract_json(raw_output))


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
        self.backend = backend or CodexCliSynthesisBackend()
        self.model = model

    @property
    def provider(self) -> str:
        return f"llm_{self.backend.provider}"

    def synthesize_json(self, trace: ArtifactTrace) -> SynthesisResult:
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
    return (
        "You are synthesizing a reusable WebMCP workflow JSON for a deterministic browser workflow.\n"
        "Return only JSON matching the provided schema. Do not include Python code.\n"
        "Use repo handler refs only when suitable; for Naver stock extraction use "
        "`naver_stock.extract_stock_card`.\n\n"
        "Required top-level keys: skill_name, slug, description, domain, task_type, body_md, "
        "input_schema, output_schema, arguments, steps, resources, handlers.\n"
        "Allowed step_type values: goto, wait_for_text, run_handler, assert_output, render_report.\n"
        "Each step must include: name, description, step_type, handler_ref, action, "
        "argument_bindings, assertions, fallback_policy, update_policy.\n"
        "Because the schema is strict, include unused fields as null, empty arrays, or empty objects "
        "instead of omitting them.\n"
        "Use double-brace placeholders exactly like {{company_name}} and {{ticker}}.\n"
        "Do not invent executable code. Store templates, handler refs, assertions, and static JSON only.\n\n"
        "For a Naver stock report, prefer these semantic steps: open_naver_stock_search, "
        "wait_stock_card, extract_stock_card, validate_stock_output, render_stock_report.\n\n"
        f"User request: {trace.user_request}\n"
        f"Arguments JSON: {json.dumps(trace.arguments, ensure_ascii=False, sort_keys=True)}\n"
        f"Discovery provider: {trace.provider}\n"
        f"Final URL: {trace.final_url or ''}\n"
        f"Page title: {trace.title or ''}\n"
        "Page text excerpt:\n"
        f"{trace.page_text[:6000]}\n"
    )


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
    allowed_step_types = {"goto", "wait_for_text", "run_handler", "assert_output", "render_report"}
    for step in workflow["steps"]:
        for key in ["name", "description", "step_type", "action", "assertions"]:
            if key not in step:
                raise ValueError(f"workflow step missing required key: {key}")
        if step["step_type"] not in allowed_step_types:
            raise ValueError(f"unsupported synthesized step_type: {step['step_type']}")
        if step["step_type"] == "run_handler" and not step.get("handler_ref"):
            raise ValueError(f"run_handler step missing handler_ref: {step['name']}")


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
            "additionalProperties": False,
            "required": ["company_name", "ticker", "page_text", "news_limit"],
            "properties": {
                "company_name": STRING_FIELD_SCHEMA,
                "ticker": STRING_FIELD_SCHEMA,
                "page_text": STRING_FIELD_SCHEMA,
                "news_limit": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "required", "default"],
                    "properties": {
                        "type": {"type": "string"},
                        "required": {"type": "boolean"},
                        "default": {"type": "integer"},
                    },
                },
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["company_name", "ticker", "current_price", "change_text", "report_text"],
            "properties": {
                "company_name": {"type": "string"},
                "ticker": {"type": "string"},
                "current_price": {"type": "string"},
                "change_text": {"type": "string"},
                "report_text": {"type": "string"},
            },
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
                        "additionalProperties": False,
                        "required": ["min_length", "pattern", "minimum", "maximum"],
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
                        "additionalProperties": False,
                        "required": ["url_template", "source", "input_key", "template_resource"],
                        "properties": {
                            "url_template": {"type": ["string", "null"]},
                            "source": {"type": ["string", "null"]},
                            "input_key": {"type": ["string", "null"]},
                            "template_resource": {"type": ["string", "null"]},
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


def _extract_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Codex synthesis output did not contain JSON")
    return stripped[start : end + 1]
