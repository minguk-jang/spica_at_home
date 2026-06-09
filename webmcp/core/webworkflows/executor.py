from __future__ import annotations

import importlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


class WorkflowExecutor:
    def __init__(self, store: WorkflowSkillStore, output_dir: str | Path):
        self.store = store
        self.output_dir = Path(output_dir)

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
        }

        run_id = self._create_run(skill, user_request, resolved_args)
        run_started = time.perf_counter()
        status = "succeeded"
        error: dict[str, Any] | None = None

        try:
            for step in skill.steps:
                step_input = dict(context["arguments"])
                step_input.update({"url": context["url"], "output": context["output"]})
                step_started = time.perf_counter()
                try:
                    step_output, evidence = self._execute_step(skill, step, context)
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
        except Exception:
            self._finish_run(run_id, status, context["output"], context["report_path"], _elapsed_ms(run_started))
            raise

        self._finish_run(run_id, status, context["output"], context["report_path"], _elapsed_ms(run_started))
        return WorkflowRunResult(
            run_id=run_id,
            status=status,
            llm_used=False,
            output=context["output"],
            report_text=context["report_text"],
            report_path=context["report_path"],
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
            handler_output = handler(
                page_text=context["page_text"],
                company_name=context["arguments"].get("company_name", ""),
                ticker=context["arguments"].get("ticker"),
                news_limit=context["arguments"].get("news_limit", 3),
            )
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
            return {}, {"validated": True}

        if step.step_type == "render_report":
            template_name = step.action["template_resource"]
            template = skill.resources[template_name]
            render_context = dict(context["arguments"])
            render_context.update(context["output"])
            render_context["current_price_formatted"] = f"{context['output'].get('current_price', 0):,}"
            report_text = _render_template(template, render_context)
            report_path = self.output_dir / f"run_{context['arguments']['company_name']}_report.md"
            report_path.write_text(report_text, encoding="utf-8")
            context["report_text"] = report_text
            context["report_path"] = str(report_path)
            return {"report_text": report_text}, {"report_path": str(report_path)}

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

    def _create_run(self, skill: WorkflowSkill, user_request: str, arguments: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into workflow_runs
                      (skill_id, version_id, user_request, input_json, status, llm_used, llm_reason)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (skill.id, skill.version_id, user_request, dumps(arguments), "running", 0, None),
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


def _render_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        replacement = "" if value is None else str(value)
        rendered = rendered.replace("{{" + key + "}}", replacement)
        rendered = rendered.replace("${" + key + "}", replacement)
        rendered = rendered.replace("{" + key + "}", replacement)
    return rendered


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
