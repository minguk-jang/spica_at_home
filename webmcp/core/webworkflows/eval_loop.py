from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from webworkflows.dynamic_browser import (
    DYNAMIC_BROWSER_ACTION_STEP_TYPE,
    CodexAppServerDynamicBrowserActionPlanner,
    DynamicBrowserActionPlanner,
    collect_dynamic_page_context,
    execute_dynamic_browser_action,
)
from webworkflows.loader import WorkflowSkill, WorkflowStep


@dataclass(frozen=True)
class StepEvaluation:
    step_name: str
    step_type: str
    status: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    suggested_update: str = ""
    failure_kind: str = ""
    expected_state: str = ""
    observed_state: str = ""
    repair_focus: str = ""
    evidence_artifacts: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "step_type": self.step_type,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "problems": self.problems,
            "suggested_update": self.suggested_update,
            "failure_kind": self.failure_kind,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "repair_focus": self.repair_focus,
            "evidence_artifacts": self.evidence_artifacts,
        }


@dataclass(frozen=True)
class WorkflowEvaluationReport:
    status: str
    page_text: str = ""
    step_evaluations: list[StepEvaluation] = field(default_factory=list)
    final_evaluation: StepEvaluation | None = None

    @property
    def passed(self) -> bool:
        return self.status == "passed" and self.failed_step() is None

    def failed_step(self) -> StepEvaluation | None:
        for evaluation in self.step_evaluations:
            if not evaluation.passed:
                return evaluation
        if self.final_evaluation and not self.final_evaluation.passed:
            return self.final_evaluation
        return None

    def all_evaluations(self) -> list[StepEvaluation]:
        evaluations = list(self.step_evaluations)
        if self.final_evaluation:
            evaluations.append(self.final_evaluation)
        return evaluations

    def by_step_name(self) -> dict[str, StepEvaluation]:
        return {evaluation.step_name: evaluation for evaluation in self.step_evaluations}

    def as_dict(self) -> dict[str, Any]:
        failed = self.failed_step()
        return {
            "status": "passed" if self.passed else "failed",
            "page_text_excerpt": self.page_text[:2000],
            "failed_step": failed.as_dict() if failed else None,
            "step_evaluations": [evaluation.as_dict() for evaluation in self.step_evaluations],
            "final_evaluation": self.final_evaluation.as_dict() if self.final_evaluation else None,
        }


class WorkflowEvaluationError(RuntimeError):
    def __init__(self, report: WorkflowEvaluationReport):
        failed = report.failed_step()
        if failed:
            message = f"workflow evaluation failed at {failed.step_name}: {failed.summary}"
        else:
            message = "workflow evaluation failed"
        super().__init__(message)
        self.report = report


class EvalAndEvolveLoop(Protocol):
    def run(
        self,
        *,
        skill: WorkflowSkill,
        user_request: str,
        arguments: dict[str, Any],
        run_id: int,
        output_dir: Path,
    ) -> WorkflowEvaluationReport:
        ...


@dataclass(frozen=True)
class EvaluationSnapshot:
    step_name: str
    step_type: str
    phase: str
    user_request: str
    url: str
    title: str
    page_text: str
    screenshot_path: str
    output: dict[str, Any]
    assertion_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "step_type": self.step_type,
            "phase": self.phase,
            "user_request": self.user_request,
            "url": self.url,
            "title": self.title,
            "page_text_excerpt": self.page_text[:4000],
            "screenshot_path": self.screenshot_path,
            "output": self.output,
            "assertion_error": self.assertion_error,
        }


class VisionLanguageEvaluator(Protocol):
    name: str

    def evaluate(self, snapshot: EvaluationSnapshot, criteria: dict[str, Any]) -> StepEvaluation:
        ...


class PlaywrightEvalAndEvolveLoop:
    def __init__(
        self,
        *,
        evaluator: VisionLanguageEvaluator,
        headed: bool = False,
        browser_name: str = "chromium",
        dynamic_action_planner: DynamicBrowserActionPlanner | None = None,
    ):
        self.evaluator = evaluator
        self.headed = headed
        self.browser_name = browser_name
        self.dynamic_action_planner = dynamic_action_planner

    def run(
        self,
        *,
        skill: WorkflowSkill,
        user_request: str,
        arguments: dict[str, Any],
        run_id: int,
        output_dir: Path,
    ) -> WorkflowEvaluationReport:
        try:
            return asyncio.run(
                self._run_async(
                    skill=skill,
                    user_request=user_request,
                    arguments=arguments,
                    run_id=run_id,
                    output_dir=output_dir,
                )
            )
        finally:
            close = getattr(self.evaluator, "close", None)
            if callable(close):
                close()

    async def _run_async(
        self,
        *,
        skill: WorkflowSkill,
        user_request: str,
        arguments: dict[str, Any],
        run_id: int,
        output_dir: Path,
    ) -> WorkflowEvaluationReport:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError("Playwright is required for eval-and-evolve browser monitoring.") from exc

        eval_dir = output_dir / "eval_runs" / f"run_{run_id:04d}"
        eval_dir.mkdir(parents=True, exist_ok=True)
        values = dict(arguments)
        output: dict[str, Any] = {}
        page_text = values.get("page_text", "")
        step_evaluations: list[StepEvaluation] = []

        async with async_playwright() as playwright:
            browser_type = getattr(playwright, self.browser_name)
            browser = await browser_type.launch(headless=not self.headed)
            context = await browser.new_context(viewport={"width": 1280, "height": 1800})
            page = await context.new_page()
            try:
                for index, step in enumerate(skill.steps, start=1):
                    assertion_error = await self._execute_browser_step(
                        page=page,
                        skill=skill,
                        step=step,
                        values=values,
                        output=output,
                        user_request=user_request,
                    )
                    try:
                        page_text = await page.locator("body").inner_text(timeout=15000)
                    except Exception:
                        page_text = page_text or values.get("page_text", "")
                    screenshot_path = eval_dir / f"step_{index:02d}_{_safe_name(step.name)}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    snapshot = EvaluationSnapshot(
                        step_name=step.name,
                        step_type=step.step_type,
                        phase="intermediate",
                        user_request=user_request,
                        url=page.url,
                        title=await page.title(),
                        page_text=page_text,
                        screenshot_path=str(screenshot_path),
                        output=dict(output),
                        assertion_error=assertion_error,
                    )
                    evaluation = self.evaluator.evaluate(snapshot, self._criteria_for_step(step))
                    if assertion_error and evaluation.passed:
                        evaluation = StepEvaluation(
                            step_name=step.name,
                            step_type=step.step_type,
                            status="failed",
                            summary=assertion_error,
                            evidence=evaluation.evidence,
                            problems=[assertion_error],
                            suggested_update=evaluation.suggested_update,
                        )
                    step_evaluations.append(evaluation)
                    if not evaluation.passed:
                        return WorkflowEvaluationReport(
                            status="failed",
                            page_text=page_text,
                            step_evaluations=step_evaluations,
                        )

                final_screenshot = eval_dir / "final.png"
                await page.screenshot(path=str(final_screenshot), full_page=True)
                final_snapshot = EvaluationSnapshot(
                    step_name="final",
                    step_type="final",
                    phase="final",
                    user_request=user_request,
                    url=page.url,
                    title=await page.title(),
                    page_text=page_text,
                    screenshot_path=str(final_screenshot),
                    output=dict(output),
                )
                final_evaluation = self.evaluator.evaluate(
                    final_snapshot,
                    {
                        "expected_output_schema": skill.output_schema,
                        "required_report": True,
                    },
                )
                status = "passed" if final_evaluation.passed else "failed"
                return WorkflowEvaluationReport(
                    status=status,
                    page_text=page_text,
                    step_evaluations=step_evaluations,
                    final_evaluation=final_evaluation,
                )
            finally:
                await browser.close()

    async def _execute_browser_step(
        self,
        *,
        page,
        skill: WorkflowSkill,
        step: WorkflowStep,
        values: dict[str, Any],
        output: dict[str, Any],
        user_request: str = "",
    ) -> str:
        try:
            if step.step_type == "goto":
                url = _render_template(step.action.get("url_template", ""), values)
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                return ""
            if step.step_type == "click":
                selector = _render_template(_action_selector(step.action), values)
                nth = int(step.action.get("nth", 0) or 0)
                await page.locator(selector).nth(nth).click(timeout=15000)
                await page.wait_for_timeout(int(step.action.get("settle_ms", 800) or 800))
                return ""
            if step.step_type == "click_text":
                text = _render_template(_action_text(step.action), values)
                nth = int(step.action.get("nth", 0) or 0)
                exact = bool(step.action.get("exact", True))
                await page.get_by_text(text, exact=exact).nth(nth).click(timeout=15000)
                await page.wait_for_timeout(int(step.action.get("settle_ms", 800) or 800))
                return ""
            if step.step_type == "fill":
                selector = _render_template(_action_selector(step.action), values)
                value = _render_template(_action_fill_value(step.action, values), values)
                nth = int(step.action.get("nth", 0) or 0)
                await page.locator(selector).nth(nth).fill(value, timeout=15000)
                await page.wait_for_timeout(int(step.action.get("settle_ms", 1200) or 1200))
                return ""
            if step.step_type == "press":
                selector = _render_template(_action_selector(step.action), values)
                key = str(step.action.get("key", "Enter"))
                nth = int(step.action.get("nth", 0) or 0)
                await page.locator(selector).nth(nth).press(key, timeout=15000)
                await page.wait_for_timeout(int(step.action.get("settle_ms", 800) or 800))
                return ""
            if step.step_type == "select_suggestion":
                markers = [_render_template(str(item), values) for item in step.action.get("markers", [])]
                selector = str(step.action.get("candidate_selector", "button,a,li,div"))
                await page.wait_for_function(
                    "(markers) => markers.every((marker) => document.body.innerText.includes(marker))",
                    arg=markers,
                    timeout=10000,
                )
                clicked = await _click_visible_candidate(page, markers=markers, selector=selector)
                if not clicked:
                    return f"no visible suggestion matched all markers: {markers}"
                await page.wait_for_timeout(int(step.action.get("settle_ms", 1200) or 1200))
                return ""
            if step.step_type == DYNAMIC_BROWSER_ACTION_STEP_TYPE:
                planner = self._dynamic_action_planner()
                page_context = await collect_dynamic_page_context(page)
                instruction = _render_template(str(step.action.get("instruction") or step.description), values)
                success_criteria = [
                    _render_template(str(item), values) for item in step.action.get("success_criteria", [])
                ]
                allowed_operations = [str(item) for item in step.action.get("allowed_operations", ["click"])]
                dynamic_action = planner.plan(
                    step_name=step.name,
                    instruction=instruction,
                    success_criteria=success_criteria,
                    allowed_operations=allowed_operations,
                    user_request=user_request,
                    values=values,
                    page_context=page_context,
                )
                result = await execute_dynamic_browser_action(
                    page,
                    dynamic_action,
                    instruction=instruction,
                    step_action=step.action,
                    values=values,
                    page_context=page_context,
                )
                output.setdefault("_dynamic_step_evidence", {})[step.name] = {
                    **dynamic_action.as_evidence(),
                    "instruction": instruction,
                    "success_criteria": success_criteria,
                    "allowed_operations": allowed_operations,
                    "result": result,
                    "page_context": {
                        "url": page_context.get("url", ""),
                        "title": page_context.get("title", ""),
                        "candidate_count": len(page_context.get("candidates", [])),
                    },
                }
                await page.wait_for_timeout(int(step.action.get("settle_ms", 1000) or 1000))
                return ""
            if step.step_type == "wait_for_text":
                page_text = await page.locator("body").inner_text(timeout=15000)
                expected = [_render_template(item, values) for item in step.assertions.get("contains_any", [])]
                if expected and not any(item in page_text for item in expected):
                    return f"none of the expected text markers were found: {expected}"
                return ""
            if step.step_type == "run_handler":
                page_text = await page.locator("body").inner_text(timeout=15000)
                handler = _load_handler_from_registry(skill, step.handler_ref)
                handler_values = dict(values)
                handler_values["page_text"] = page_text
                handler_values.update(output)
                handler_output = handler(**_handler_kwargs(handler, step, handler_values))
                output.update(handler_output)
                for required_key in step.assertions.get("required_output", []):
                    if handler_output.get(required_key) in (None, ""):
                        return f"handler output missing required key: {required_key}"
                return ""
            if step.step_type == "assert_output":
                await _merge_browser_state_output(page, output)
                return _assert_output(values, output, step.assertions)
            if step.step_type == "render_report":
                await _merge_browser_state_output(page, output)
                template_name = step.action.get("template_resource", "")
                template = skill.resources.get(template_name, "")
                render_values = dict(values)
                render_values.update(output)
                render_values["current_price_formatted"] = f"{output.get('current_price', 0):,}"
                output["report_text"] = _render_template(template, render_values)
                output.setdefault("report_markdown", output["report_text"])
                output.setdefault("markdown_report", output["report_text"])
                output.setdefault("status", "passed")
                return ""
            return f"unsupported workflow step type for browser evaluation: {step.step_type}"
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def _criteria_for_step(self, step: WorkflowStep) -> dict[str, Any]:
        return {
            "step_name": step.name,
            "step_type": step.step_type,
            "action": step.action,
            "assertions": _criteria_assertions_for_step(step),
            "evaluator": self.evaluator.name,
        }

    def _dynamic_action_planner(self) -> DynamicBrowserActionPlanner:
        planner = getattr(self, "dynamic_action_planner", None)
        if planner is None:
            planner = CodexAppServerDynamicBrowserActionPlanner()
            self.dynamic_action_planner = planner
        return planner


def _load_handler_from_registry(skill: WorkflowSkill, handler_ref: str | None):
    if not handler_ref:
        raise ValueError("handler_ref is required")
    if handler_ref == "naver_stock.extract_stock_card":
        from webworkflows.handlers.naver_stock import extract_stock_card

        return extract_stock_card
    if handler_ref == "naver_map.extract_subway_duration":
        from webworkflows.handlers.naver_map import extract_subway_duration

        return extract_subway_duration
    raise KeyError(f"handler not available in browser evaluation loop: {handler_ref}")


def _criteria_assertions_for_step(step: WorkflowStep) -> dict[str, Any]:
    assertions = dict(step.assertions)
    if step.step_type in {"click", "click_text", "fill", "press", "select_suggestion", DYNAMIC_BROWSER_ACTION_STEP_TYPE}:
        assertions["contains_any"] = []
    return assertions


def _assert_output(values: dict[str, Any], output: dict[str, Any], assertions: dict[str, Any]) -> str:
    for key, template in assertions.get("equals", {}).items():
        if template is None:
            continue
        expected = _render_template(template, values)
        if str(output.get(key)) != expected:
            return f"output[{key!r}] expected {expected!r}, got {output.get(key)!r}"
    for key, template in assertions.get("optional_equals", {}).items():
        if template is None:
            continue
        expected = _render_template(template, values)
        if expected and output.get(key) and str(output.get(key)) != expected:
            return f"output[{key!r}] expected {expected!r}, got {output.get(key)!r}"
    for required_key in assertions.get("required_output", []):
        if output.get(required_key) in (None, ""):
            return f"output missing required key: {required_key}"
    return ""


async def _click_visible_candidate(page, *, markers: list[str], selector: str) -> bool:
    return bool(
        await page.evaluate(
            """
            ({ markers, selector }) => {
              const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 &&
                  style.visibility !== 'hidden' && style.display !== 'none';
              };
              const textOf = (element) => (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim();
              const candidates = Array.from(document.querySelectorAll(selector))
                .filter((element) => visible(element))
                .map((element) => ({ element, text: textOf(element) }))
                .filter((candidate) => markers.every((marker) => candidate.text.includes(marker)))
                .sort((left, right) => left.text.length - right.text.length);
              for (const candidate of candidates) {
                const element = candidate.element;
                const clickable = element.closest('.link_place,button,a,[role="button"],li,div') || element;
                clickable.click();
                return true;
              }
              return false;
            }
            """,
            {"markers": markers, "selector": selector},
        )
    )


async def _merge_browser_state_output(page, output: dict[str, Any]) -> None:
    output.setdefault("final_url", page.url)
    output.setdefault("current_url", page.url)
    try:
        output.setdefault("page_title", await page.title())
    except Exception:
        pass
    try:
        page_text = await page.locator("body").inner_text(timeout=15000)
    except Exception:
        page_text = ""
    if page_text:
        output.setdefault("page_text", page_text)


def _handler_kwargs(handler, step: WorkflowStep, values: dict[str, Any]) -> dict[str, Any]:
    inputs = step.action.get("inputs")
    if isinstance(inputs, dict) and inputs:
        return {key: _render_template(str(value), values) for key, value in inputs.items()}

    legacy = {
        "page_text": values.get("page_text", ""),
        "company_name": values.get("company_name", ""),
        "ticker": values.get("ticker"),
        "news_limit": values.get("news_limit", 3),
    }
    available = dict(values)
    available.update(legacy)
    parameters = inspect.signature(handler).parameters
    accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    kwargs = {name: available[name] for name in parameters if name in available}
    if accepts_kwargs:
        kwargs.update(available)
    return kwargs or legacy


def _render_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        replacement = "" if value is None else str(value)
        rendered = rendered.replace("{{" + key + "}}", replacement)
        rendered = rendered.replace("${" + key + "}", replacement)
        rendered = rendered.replace("{" + key + "}", replacement)
    return rendered


def _action_selector(action: dict[str, Any]) -> str:
    selector = action.get("selector")
    if selector not in (None, ""):
        return str(selector)
    source = action.get("source")
    return "" if source is None else str(source)


def _action_fill_value(action: dict[str, Any], values: dict[str, Any]) -> str:
    value_template = action.get("value_template")
    if value_template not in (None, ""):
        return str(value_template)
    input_key = action.get("input_key")
    if input_key in (None, ""):
        return ""
    return str(values.get(str(input_key), ""))


def _action_text(action: dict[str, Any]) -> str:
    text = action.get("text")
    if text not in (None, ""):
        return str(text)
    source = action.get("source")
    return "" if source is None else str(source)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)[:80]
