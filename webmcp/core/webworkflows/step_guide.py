from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from webworkflows.synthesis import DEFAULT_CODEX_SYNTHESIS_MODEL
from webworkflows.vlm_codex import CodexAppServerJsonRpcClient


ALLOWED_STEP_GUIDE_TYPES = {
    "goto",
    "click",
    "click_text",
    "fill",
    "press",
    "select_suggestion",
    "llm_browser_action",
    "wait_for_text",
    "run_handler",
    "assert_output",
    "render_report",
}

STEP_GUIDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "step_type": {"type": "string", "enum": sorted(ALLOWED_STEP_GUIDE_TYPES)},
                },
                "required": ["name", "description", "step_type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class StepGuideSuggestion:
    provider: str
    model: str
    step_guide: list[dict[str, str]]


class StepGuideSuggester:
    def __init__(
        self,
        *,
        model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
        app_server: Any | None = None,
        cwd: str | Path | None = None,
        timeout_seconds: int = 60,
    ):
        self.model = model
        self.app_server = app_server or CodexAppServerJsonRpcClient(
            cwd=Path(cwd) if cwd else None,
            timeout_seconds=timeout_seconds,
            client_info={
                "name": "webmcp-step-guide",
                "title": "WebMCP Step Guide",
                "version": "0.1.0",
            },
            base_instructions=(
                "You draft concise, human-editable WebMCP workflow step guides as JSON. "
                "Do not use tools, shell commands, file reads, skills, web, or repo context."
            ),
            developer_instructions="Return only JSON matching the provided step-guide schema.",
            request_error_message="WebMCP step-guide suggester does not handle requests",
        )

    @property
    def provider(self) -> str:
        return "codex_app_server"

    def suggest(
        self,
        *,
        start_url: str,
        task: str,
        final_state: str,
        page_analysis_context: dict[str, Any] | None = None,
        knowledge_context: list[dict[str, Any]] | None = None,
    ) -> StepGuideSuggestion:
        prompt = build_step_guide_prompt(
            start_url=start_url,
            task=task,
            final_state=final_state,
            page_analysis_context=page_analysis_context or {},
            knowledge_context=knowledge_context or [],
        )
        result = self.app_server.run_turn(
            prompt=prompt,
            output_schema=STEP_GUIDE_SCHEMA,
            image_paths=[],
            model=self.model,
        )
        payload = json.loads(_extract_json(str(result.get("text") or "")))
        return StepGuideSuggestion(
            provider=self.provider,
            model=self.model,
            step_guide=normalize_step_guide_items(payload.get("steps") or payload.get("step_guide") or payload),
        )

    def close(self) -> None:
        close = getattr(self.app_server, "close", None)
        if callable(close):
            close()


def build_step_guide_prompt(
    *,
    start_url: str,
    task: str,
    final_state: str,
    page_analysis_context: dict[str, Any],
    knowledge_context: list[dict[str, Any]],
) -> str:
    return (
        "You are drafting a human-editable WebMCP workflow step guide, not a final executable workflow.\n"
        "Return only JSON with a top-level `steps` array. Each item must have name, description, and step_type.\n"
        "Use short snake_case names and keep 4-8 steps. Preserve a practical browser route from opening the page "
        "to waiting for the requested final state and rendering a report when useful.\n"
        "Prefer deterministic types such as goto, click, fill, wait_for_text, and render_report. Use "
        "llm_browser_action only for variable popups, dynamic UI chrome, or a broad action that needs runtime judgment.\n"
        "Do not include selectors, generated scripts, Python, JavaScript, or Playwright code.\n\n"
        f"Start URL: {start_url}\n"
        f"Human task: {task}\n"
        f"Expected final browser state: {final_state}\n"
        "Reusable page analysis context JSON:\n"
        f"{json.dumps(page_analysis_context, ensure_ascii=False, sort_keys=True)[:3000]}\n"
        "Reusable script generation knowledge JSON:\n"
        f"{json.dumps(knowledge_context, ensure_ascii=False, sort_keys=True)[:3000]}\n"
    )


def heuristic_step_guide(*, start_url: str, task: str, final_state: str) -> list[dict[str, str]]:
    task_summary = _compact_sentence(task, fallback="Complete the requested browser task.")
    final_summary = _compact_sentence(final_state, fallback="Wait for the requested final state.")
    guide = [
        {
            "name": "open_start_url",
            "description": f"Open {start_url}.",
            "step_type": "goto",
        },
        {
            "name": _safe_step_name(task_summary, fallback="complete_task"),
            "description": task_summary,
            "step_type": "llm_browser_action",
        },
        {
            "name": _safe_step_name(final_summary, fallback="wait_final_state", prefix="wait"),
            "description": final_summary,
            "step_type": "wait_for_text",
        },
        {
            "name": "render_report",
            "description": "Render a concise Markdown report from the final browser state.",
            "step_type": "render_report",
        },
    ]
    return normalize_step_guide_items(guide)


def normalize_step_guide_items(value: Any) -> list[dict[str, str]]:
    source = value
    if isinstance(value, dict):
        source = value.get("steps") or value.get("step_guide") or []
    if not isinstance(source, list):
        return []
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        step_type = str(item.get("step_type") or item.get("stepType") or "").strip()
        if not name and not description:
            continue
        if step_type not in ALLOWED_STEP_GUIDE_TYPES:
            step_type = "click"
        normalized.append(
            {
                "name": _safe_name(name or description or f"step_{index + 1}", fallback=f"step_{index + 1}"),
                "description": description,
                "step_type": step_type,
            }
        )
    return normalized


def _compact_sentence(value: str, *, fallback: str) -> str:
    text = " ".join(value.strip().split())
    if not text:
        return fallback
    return text[:180]


def _safe_step_name(value: str, *, fallback: str, prefix: str = "") -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    if not words:
        return fallback
    name = "_".join(words[:5])
    if prefix and not name.startswith(f"{prefix}_"):
        name = f"{prefix}_{name}"
    return _safe_name(name, fallback=fallback)


def _safe_name(value: str, *, fallback: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower()).strip("_")
    name = re.sub(r"_+", "_", name)
    if not name:
        return fallback
    if name[0].isdigit():
        name = f"step_{name}"
    return name[:64]


def _extract_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise ValueError(f"Codex step guide suggester did not return JSON: {raw[:500]}")
