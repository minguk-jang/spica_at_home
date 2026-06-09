from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

DYNAMIC_BROWSER_ACTION_STEP_TYPE = "llm_browser_action"
DEFAULT_DYNAMIC_BROWSER_ACTION_MODEL = "gpt-5.5"
DYNAMIC_ACTION_SCRIPT_KEYS = {
    "code",
    "generated_code",
    "generated_javascript",
    "javascript",
    "playwright_code",
    "python_code",
    "script",
}
_FORBIDDEN_JAVASCRIPT_TOKENS = (
    "fetch(",
    "XMLHttpRequest",
    "localStorage",
    "sessionStorage",
    "indexedDB",
    "navigator.sendBeacon",
)


@dataclass(frozen=True)
class DynamicBrowserAction:
    javascript: str
    summary: str
    provider: str
    model: str
    confidence: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    def as_evidence(self) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "summary": self.summary,
            "generated_javascript": self.javascript,
        }
        if self.confidence is not None:
            evidence["confidence"] = self.confidence
        if self.raw_response:
            evidence["raw_response"] = self.raw_response
        return evidence


class DynamicBrowserActionPlanner(Protocol):
    name: str

    def plan(
        self,
        *,
        step_name: str,
        instruction: str,
        success_criteria: list[str],
        allowed_operations: list[str],
        user_request: str,
        values: dict[str, Any],
        page_context: dict[str, Any],
    ) -> DynamicBrowserAction:
        ...


class CodexCliDynamicBrowserActionPlanner:
    name = "codex_cli_dynamic_browser_action"

    def __init__(
        self,
        *,
        model: str = DEFAULT_DYNAMIC_BROWSER_ACTION_MODEL,
        cwd: str | Path | None = None,
        timeout_seconds: int = 180,
        run_command=subprocess.run,
    ):
        self.model = model
        self.cwd = Path(cwd) if cwd else None
        self.timeout_seconds = timeout_seconds
        self.run_command = run_command

    def plan(
        self,
        *,
        step_name: str,
        instruction: str,
        success_criteria: list[str],
        allowed_operations: list[str],
        user_request: str,
        values: dict[str, Any],
        page_context: dict[str, Any],
    ) -> DynamicBrowserAction:
        prompt = build_dynamic_browser_action_prompt(
            step_name=step_name,
            instruction=instruction,
            success_criteria=success_criteria,
            allowed_operations=allowed_operations,
            user_request=user_request,
            values=values,
            page_context=page_context,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "dynamic_browser_action.json"
            command = [
                "codex",
                "exec",
                "--model",
                self.model,
                "--ephemeral",
                "--ignore-rules",
                "--ignore-user-config",
                "--sandbox",
                "read-only",
                "--output-last-message",
                str(output_path),
                prompt,
            ]
            try:
                completed = self.run_command(
                    command,
                    cwd=str(self.cwd) if self.cwd else None,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "codex dynamic browser action synthesis failed "
                    f"(exit={exc.returncode}, model={self.model}).\n"
                    f"STDERR:\n{exc.stderr}\nSTDOUT:\n{exc.stdout}"
                ) from exc
            raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        parsed = json.loads(_extract_json(raw_output))
        javascript = str(parsed.get("javascript") or "")
        validate_dynamic_javascript(javascript)
        confidence = parsed.get("confidence")
        return DynamicBrowserAction(
            javascript=javascript,
            summary=str(parsed.get("summary") or ""),
            provider=self.name,
            model=self.model,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            raw_response=parsed,
        )


def build_dynamic_browser_action_prompt(
    *,
    step_name: str,
    instruction: str,
    success_criteria: list[str],
    allowed_operations: list[str],
    user_request: str,
    values: dict[str, Any],
    page_context: dict[str, Any],
) -> str:
    contract = {
        "type": "object",
        "required": ["javascript", "summary", "confidence"],
        "properties": {
            "javascript": {
                "type": "string",
                "description": "A JavaScript function expression: async (input) => { ... }",
            },
            "summary": {"type": "string"},
            "confidence": {"type": "number"},
        },
    }
    return (
        "Generate a one-time JavaScript browser action for a WebMCP dynamic workflow step.\n"
        "Return only JSON matching the response contract. Do not use Markdown.\n"
        "The workflow database stores only the dynamic instruction and criteria; this JavaScript is runtime-only.\n"
        "The JavaScript must be a function expression, preferably `async (input) => { ... }`.\n"
        "Use the provided candidate selectors and visible text. Do not call network APIs, browser storage, or navigate "
        "unless the instruction explicitly requires navigation.\n"
        "Return a small object such as `{ status: 'passed', clicked_text: 'Close' }` from the function.\n\n"
        f"Step name: {step_name}\n"
        f"Instruction: {instruction}\n"
        f"Success criteria JSON: {json.dumps(success_criteria, ensure_ascii=False)}\n"
        f"Allowed operations JSON: {json.dumps(allowed_operations, ensure_ascii=False)}\n"
        f"User request: {user_request}\n"
        f"Values JSON: {json.dumps(values, ensure_ascii=False, sort_keys=True)[:4000]}\n"
        f"Page context JSON: {json.dumps(page_context, ensure_ascii=False, sort_keys=True)[:12000]}\n"
        f"Response contract JSON: {json.dumps(contract, ensure_ascii=False, sort_keys=True)}\n"
    )


async def collect_dynamic_page_context(page, *, max_candidates: int = 80) -> dict[str, Any]:
    try:
        page_text = await page.locator("body").inner_text(timeout=15000)
    except Exception:
        page_text = ""
    try:
        title = await page.title()
    except Exception:
        title = ""
    candidates = await page.evaluate(
        """
        ({ maxCandidates }) => {
          const visible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            return rect.width > 0 && rect.height > 0 &&
              style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
          };
          const cssEscape = (value) => {
            if (window.CSS && CSS.escape) return CSS.escape(value);
            return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
          };
          const selectorFor = (element) => {
            const testId = element.getAttribute('data-testid') || element.getAttribute('data-test');
            if (testId) return `[data-testid="${cssEscape(testId)}"],[data-test="${cssEscape(testId)}"]`;
            const aria = element.getAttribute('aria-label');
            if (aria) return `${element.tagName.toLowerCase()}[aria-label="${cssEscape(aria)}"]`;
            if (element.id) return `#${cssEscape(element.id)}`;
            const name = element.getAttribute('name');
            if (name) return `${element.tagName.toLowerCase()}[name="${cssEscape(name)}"]`;
            const classes = Array.from(element.classList || []).slice(0, 3).map(cssEscape);
            if (classes.length) return `${element.tagName.toLowerCase()}.${classes.join('.')}`;
            return element.tagName.toLowerCase();
          };
          const textOf = (element) => (element.innerText || element.textContent || element.getAttribute('aria-label') || '')
            .replace(/\\s+/g, ' ')
            .trim()
            .slice(0, 240);
          return Array.from(document.querySelectorAll('button,a,[role="button"],input,select,textarea,[aria-label]'))
            .filter(visible)
            .slice(0, maxCandidates)
            .map((element) => ({
              tag: element.tagName.toLowerCase(),
              text: textOf(element),
              selector: selectorFor(element),
              aria_label: element.getAttribute('aria-label') || '',
              type: element.getAttribute('type') || '',
              href: element.getAttribute('href') || '',
            }));
        }
        """,
        {"maxCandidates": max_candidates},
    )
    return {
        "url": getattr(page, "url", ""),
        "title": title,
        "page_text_excerpt": page_text[:4000],
        "candidates": candidates,
    }


async def execute_dynamic_browser_action(
    page,
    action: DynamicBrowserAction,
    *,
    instruction: str,
    step_action: dict[str, Any],
    values: dict[str, Any],
    page_context: dict[str, Any],
) -> Any:
    validate_dynamic_javascript(action.javascript)
    return await page.evaluate(
        """
        async ({ actionSource, payload }) => {
          const source = String(actionSource).trim();
          const expression = (source.startsWith('function') || source.startsWith('async function'))
            ? `(${source})`
            : source;
          const fn = (0, eval)(expression);
          if (typeof fn !== 'function') {
            throw new Error('dynamic browser action did not evaluate to a function');
          }
          return await fn(payload);
        }
        """,
        {
            "actionSource": action.javascript,
            "payload": {
                "instruction": instruction,
                "action": step_action,
                "values": values,
                "page": page_context,
            },
        },
    )


def validate_dynamic_step_action(action: dict[str, Any], *, step_name: str) -> None:
    instruction = str(action.get("instruction") or "").strip()
    if not instruction:
        raise ValueError(f"llm_browser_action step requires action.instruction: {step_name}")
    forbidden_key = _find_forbidden_script_key(action)
    if forbidden_key:
        raise ValueError(
            f"llm_browser_action step must not store generated code in action.{forbidden_key}: {step_name}"
        )


def validate_dynamic_javascript(javascript: str) -> None:
    source = javascript.strip()
    if not source:
        raise ValueError("dynamic browser action javascript is required")
    if not (
        source.startswith("(")
        or source.startswith("async (")
        or source.startswith("async function")
        or source.startswith("function")
    ):
        raise ValueError("dynamic browser action javascript must be a function expression")
    for token in _FORBIDDEN_JAVASCRIPT_TOKENS:
        if token in source:
            raise ValueError(f"dynamic browser action javascript uses forbidden token: {token}")


def _find_forbidden_script_key(value: Any) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DYNAMIC_ACTION_SCRIPT_KEYS:
                return key
            nested = _find_forbidden_script_key(item)
            if nested:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _find_forbidden_script_key(item)
            if nested:
                return nested
    return ""


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = None
    depth = 0
    start = None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                match = text[start : index + 1]
    if not match:
        raise ValueError(f"no JSON object found in dynamic browser action output: {text[:500]}")
    return match
