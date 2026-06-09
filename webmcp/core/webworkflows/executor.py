from __future__ import annotations

import importlib
import inspect
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from webworkflows.dynamic_browser import DYNAMIC_BROWSER_ACTION_STEP_TYPE
from webworkflows.eval_loop import EvalAndEvolveLoop, WorkflowEvaluationError, WorkflowEvaluationReport
from webworkflows.loader import WorkflowSkill, WorkflowStep
from webworkflows.storage import WorkflowSkillStore, dumps


@dataclass(frozen=True)
class WorkflowRunResult:
    run_id: int
    status: str
    llm_used: bool
    output: dict[str, Any]
    report_text: str
    report_path: str
    evaluation: dict[str, Any] | None = None


class WorkflowExecutor:
    def __init__(
        self,
        store: WorkflowSkillStore,
        output_dir: str | Path,
        *,
        evaluation_loop: EvalAndEvolveLoop | None = None,
    ):
        self.store = store
        self.output_dir = Path(output_dir)
        self.evaluation_loop = evaluation_loop

    def run(
        self,
        skill: WorkflowSkill,
        user_request: str,
        arguments: dict[str, Any],
    ) -> WorkflowRunResult:
        resolved_args = self._resolve_arguments(skill, arguments)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        context: dict[str, Any] = {
            "arguments": resolved_args,
            "url": None,
            "page_text": resolved_args.get("page_text", ""),
            "output": {},
            "report_text": "",
            "report_path": "",
            "browser_evaluation_completed": False,
        }

        runtime_llm_used = _workflow_uses_runtime_llm(skill)
        llm_reason = "runtime_dynamic_browser_step" if runtime_llm_used else None
        run_id = self._create_run(
            skill,
            user_request,
            resolved_args,
            llm_used=runtime_llm_used,
            llm_reason=llm_reason,
        )
        run_started = time.perf_counter()
        status = "succeeded"
        error: dict[str, Any] | None = None
        evaluation_report: WorkflowEvaluationReport | None = None

        try:
            if self.evaluation_loop:
                evaluation_report = self.evaluation_loop.run(
                    skill=skill,
                    user_request=user_request,
                    arguments=resolved_args,
                    run_id=run_id,
                    output_dir=self.output_dir,
                )
                self._record_evaluation_artifacts(run_id, evaluation_report)
                if evaluation_report.page_text:
                    context["page_text"] = evaluation_report.page_text
                if not evaluation_report.passed:
                    status = "failed"
                    error = {"type": "WorkflowEvaluationError", "message": str(WorkflowEvaluationError(evaluation_report))}
                    failed_step = evaluation_report.failed_step()
                    if failed_step:
                        matching_step = next(
                            (candidate for candidate in skill.steps if candidate.name == failed_step.step_name),
                            skill.steps[0],
                        )
                        self._record_step_run(
                            run_id,
                            matching_step,
                            "failed",
                            dict(context["arguments"]),
                            {},
                            {"browser_evaluation": failed_step.as_dict()},
                            error,
                            0,
                        )
                    context["output"] = {
                        "error_type": "workflow_evaluation_failed",
                        "evaluation": evaluation_report.as_dict(),
                    }
                    self._finish_run(run_id, status, context["output"], context["report_path"], _elapsed_ms(run_started))
                    raise WorkflowEvaluationError(evaluation_report)

            evaluation_by_step = evaluation_report.by_step_name() if evaluation_report else {}
            if evaluation_report:
                context["output"].update(_browser_state_output_from_evaluation(evaluation_report))
                context["browser_evaluation_completed"] = True
            for step in skill.steps:
                step_input = dict(context["arguments"])
                step_input.update({"url": context["url"], "output": context["output"]})
                step_started = time.perf_counter()
                try:
                    step_evaluation = evaluation_by_step.get(step.name)
                    if step_evaluation and step_evaluation.passed and _is_browser_eval_only_step(step):
                        step_output, evidence = {}, {"browser_evaluation_used": True}
                    else:
                        step_output, evidence = self._execute_step(skill, step, context)
                    if step_evaluation:
                        evidence["browser_evaluation"] = step_evaluation.as_dict()
                    step_duration_ms = _elapsed_ms(step_started)
                    context["output"].update(step_output)
                    self._record_step_run(
                        run_id, step, "succeeded", step_input, step_output, evidence, None, step_duration_ms
                    )
                except Exception as exc:
                    step_duration_ms = _elapsed_ms(step_started)
                    status = "failed"
                    error = {"type": type(exc).__name__, "message": str(exc), "step": step.name}
                    self._record_step_run(run_id, step, "failed", step_input, {}, {}, error, step_duration_ms)
                    raise
        except BaseException as exc:
            if status == "succeeded":
                status = "failed"
            if "error_type" not in context["output"]:
                context["output"].update(
                    {
                        "error_type": "unexpected_workflow_error",
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            self._finish_run(run_id, status, context["output"], context["report_path"], _elapsed_ms(run_started))
            raise

        self._finish_run(run_id, status, context["output"], context["report_path"], _elapsed_ms(run_started))
        return WorkflowRunResult(
            run_id=run_id,
            status=status,
            llm_used=runtime_llm_used,
            output=context["output"],
            report_text=context["report_text"],
            report_path=context["report_path"],
            evaluation=evaluation_report.as_dict() if evaluation_report else None,
        )

    def _resolve_arguments(self, skill: WorkflowSkill, arguments: dict[str, Any]) -> dict[str, Any]:
        resolved = dict(arguments)
        missing = []
        for argument in skill.arguments:
            if argument.name not in resolved and argument.default_value is not None:
                resolved[argument.name] = argument.default_value
            if argument.required and not resolved.get(argument.name):
                missing.append(argument.name)
        if missing:
            raise ValueError(f"missing required workflow arguments: {', '.join(missing)}")
        return resolved

    def _execute_step(
        self,
        skill: WorkflowSkill,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if step.step_type == "goto":
            url = _render_template(step.action["url_template"], context["arguments"])
            context["url"] = url
            return {"url": url}, {"url": url}

        if step.step_type in {"click", "click_text", "fill", "press", "select_suggestion"}:
            return {}, {"browser_action": step.step_type, "action": _render_value(step.action, context)}

        if step.step_type == DYNAMIC_BROWSER_ACTION_STEP_TYPE:
            if not context.get("browser_evaluation_completed"):
                raise RuntimeError("llm_browser_action requires browser runtime evaluation to execute")
            return {}, {
                "browser_action": DYNAMIC_BROWSER_ACTION_STEP_TYPE,
                "llm_runtime": "browser_evaluation",
                "action": _render_value(step.action, context),
            }

        if step.step_type == "wait_for_text":
            page_text = context["page_text"]
            expected = [_render_template(item, context["arguments"]) for item in step.assertions.get("contains_any", [])]
            if not any(item in page_text for item in expected):
                raise AssertionError(f"none of the expected text markers were found: {expected}")
            return {}, {"matched_any": [item for item in expected if item in page_text]}

        if step.step_type == "run_handler":
            if not step.handler_ref:
                raise ValueError(f"handler step missing handler_ref: {step.name}")
            handler = self._load_handler(step.handler_ref)
            handler_output = handler(**_handler_kwargs(handler, step, context))
            for required_key in step.assertions.get("required_output", []):
                if handler_output.get(required_key) in (None, ""):
                    raise AssertionError(f"handler output missing required key: {required_key}")
            return handler_output, {"handler_ref": step.handler_ref}

        if step.step_type == "assert_output":
            output = context["output"]
            equals = step.assertions.get("equals", {})
            optional_equals = step.assertions.get("optional_equals", {})
            for key, template in equals.items():
                if template is None:
                    continue
                expected = _render_template(template, context["arguments"])
                if str(output.get(key)) != expected:
                    raise AssertionError(f"output[{key!r}] expected {expected!r}, got {output.get(key)!r}")
            for key, template in optional_equals.items():
                if template is None:
                    continue
                expected = _render_template(template, context["arguments"])
                if expected and output.get(key) and str(output.get(key)) != expected:
                    raise AssertionError(f"output[{key!r}] expected {expected!r}, got {output.get(key)!r}")
            for required_key in step.assertions.get("required_output", []):
                if output.get(required_key) in (None, ""):
                    raise AssertionError(f"output missing required key: {required_key}")
            return {}, {"validated": True}

        if step.step_type == "render_report":
            template_name = step.action["template_resource"]
            template = skill.resources[template_name]
            render_context = dict(context["arguments"])
            render_context.update(context["output"])
            render_context["current_price_formatted"] = f"{context['output'].get('current_price', 0):,}"
            report_text = _render_template(template, render_context)
            report_label = _safe_report_label(
                str(
                    context["arguments"].get("company_name")
                    or _route_label(context["arguments"])
                    or context["arguments"].get("workflow_name")
                    or skill.name
                )
            )
            report_path = self.output_dir / f"run_{report_label}_report.md"
            report_path.write_text(report_text, encoding="utf-8")
            context["report_text"] = report_text
            context["report_path"] = str(report_path)
            return {
                "report_text": report_text,
                "report_markdown": report_text,
                "markdown_report": report_text,
                "status": "passed",
            }, {"report_path": str(report_path)}

        raise ValueError(f"unsupported workflow step type: {step.step_type}")

    def _load_handler(self, handler_ref: str) -> Callable[..., dict[str, Any]]:
        with self.store.connect() as conn:
            row = conn.execute(
                "select module, function from handler_registry where name = ?",
                (handler_ref,),
            ).fetchone()
        if not row:
            raise KeyError(f"handler not registered: {handler_ref}")
        module = importlib.import_module(row["module"])
        return getattr(module, row["function"])

    def _create_run(
        self,
        skill: WorkflowSkill,
        user_request: str,
        arguments: dict[str, Any],
        *,
        llm_used: bool = False,
        llm_reason: str | None = None,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into workflow_runs
                      (skill_id, version_id, user_request, input_json, status, llm_used, llm_reason)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (skill.id, skill.version_id, user_request, dumps(arguments), "running", int(llm_used), llm_reason),
                ).lastrowid
            )

    def _record_step_run(
        self,
        run_id: int,
        step: WorkflowStep,
        status: str,
        step_input: dict[str, Any],
        step_output: dict[str, Any],
        evidence: dict[str, Any],
        error: dict[str, Any] | None,
        duration_ms: int,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                insert into step_runs
                  (run_id, step_id, status, input_json, output_json, evidence_json, error_json, finished_at, duration_ms)
                values (?, ?, ?, ?, ?, ?, ?, current_timestamp, ?)
                """,
                (
                    run_id,
                    step.id,
                    status,
                    dumps(step_input),
                    dumps(step_output),
                    dumps(evidence),
                    dumps(error) if error else None,
                    duration_ms,
                ),
            )

    def _finish_run(
        self,
        run_id: int,
        status: str,
        output: dict[str, Any],
        report_path: str,
        duration_ms: int,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update workflow_runs
                set status = ?, output_json = ?, report_path = ?, finished_at = current_timestamp, duration_ms = ?
                where id = ?
                """,
                (status, dumps(output), report_path, duration_ms, run_id),
            )

    def _record_evaluation_artifacts(self, run_id: int, report: WorkflowEvaluationReport) -> None:
        rows = []
        for evaluation in report.all_evaluations():
            screenshot_path = evaluation.evidence.get("screenshot_path")
            if not screenshot_path:
                snapshot = evaluation.evidence.get("snapshot")
                if isinstance(snapshot, dict):
                    screenshot_path = snapshot.get("screenshot_path")
            if not screenshot_path:
                continue
            rows.append(
                (
                    run_id,
                    None,
                    "browser_eval_screenshot",
                    str(screenshot_path),
                    dumps(
                        {
                            "step_name": evaluation.step_name,
                            "step_type": evaluation.step_type,
                            "status": evaluation.status,
                        }
                    ),
                )
            )
        if not rows:
            return
        with self.store.connect() as conn:
            conn.executemany(
                """
                insert into artifacts
                  (run_id, step_run_id, artifact_type, path, metadata_json)
                values (?, ?, ?, ?, ?)
                """,
                rows,
            )


def _render_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        replacement = "" if value is None else str(value)
        rendered = rendered.replace("{{" + key + "}}", replacement)
        rendered = rendered.replace("${" + key + "}", replacement)
        rendered = rendered.replace("{" + key + "}", replacement)
    return rendered


def _browser_state_output_from_evaluation(report: WorkflowEvaluationReport) -> dict[str, Any]:
    evidence = _latest_browser_evidence(report)
    output: dict[str, Any] = {}
    url = evidence.get("url")
    if url:
        output["final_url"] = url
        output["current_url"] = url
    title = evidence.get("title")
    if title:
        output["page_title"] = title
    if report.page_text:
        output["page_text"] = report.page_text
    return output


def _latest_browser_evidence(report: WorkflowEvaluationReport) -> dict[str, Any]:
    if report.final_evaluation and report.final_evaluation.evidence:
        return report.final_evaluation.evidence
    for evaluation in reversed(report.step_evaluations):
        if evaluation.evidence:
            return evaluation.evidence
    return {}


def _render_value(value: Any, context: dict[str, Any]) -> Any:
    values = _template_values(context)
    if isinstance(value, str):
        return _render_template(value, values)
    if isinstance(value, list):
        return [_render_value(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, context) for key, item in value.items()}
    return value


def _handler_kwargs(handler: Callable[..., dict[str, Any]], step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
    inputs = step.action.get("inputs")
    if isinstance(inputs, dict) and inputs:
        return _render_value(inputs, context)

    legacy = {
        "page_text": context["page_text"],
        "company_name": context["arguments"].get("company_name", ""),
        "ticker": context["arguments"].get("ticker"),
        "news_limit": context["arguments"].get("news_limit", 3),
    }
    available = _template_values(context)
    available.update(legacy)
    parameters = inspect.signature(handler).parameters
    kwargs: dict[str, Any] = {}
    accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    for name in parameters:
        if name in available:
            kwargs[name] = available[name]
    if accepts_kwargs:
        kwargs.update(available)
    return kwargs or legacy


def _template_values(context: dict[str, Any]) -> dict[str, Any]:
    values = dict(context.get("arguments", {}))
    values.update(context.get("output", {}))
    values["page_text"] = context.get("page_text", "")
    values["url"] = context.get("url", "")
    return values


def _route_label(arguments: dict[str, Any]) -> str:
    start = arguments.get("start_station")
    end = arguments.get("end_station")
    if start and end:
        return f"{start}_to_{end}"
    return ""


def _safe_report_label(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_")
    return normalized or "workflow"


def _workflow_uses_runtime_llm(skill: WorkflowSkill) -> bool:
    return any(step.step_type == DYNAMIC_BROWSER_ACTION_STEP_TYPE for step in skill.steps)


def _is_browser_eval_only_step(step: WorkflowStep) -> bool:
    return step.step_type in {
        "click",
        "click_text",
        "fill",
        "press",
        "select_suggestion",
        "wait_for_text",
        DYNAMIC_BROWSER_ACTION_STEP_TYPE,
    }


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
