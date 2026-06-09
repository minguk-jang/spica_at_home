from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from webworkflows.argument_examples import record_successful_argument_example
from webworkflows.eval_loop import EvalAndEvolveLoop, WorkflowEvaluationError
from webworkflows.executor import WorkflowExecutor, WorkflowRunResult
from webworkflows.loader import WorkflowSkill, WorkflowSkillLoader
from webworkflows.services.update_runtime import WorkflowUpdateRuntime
from webworkflows.storage import WorkflowSkillStore, dumps, loads
from webworkflows.synthesis import DEFAULT_CODEX_SYNTHESIS_MODEL
from webworkflows.update_proposal import workflow_json_from_skill


class WorkflowEvolutionRuntime:
    def __init__(
        self,
        store: WorkflowSkillStore,
        *,
        output_dir: str | Path,
        evaluation_loop: EvalAndEvolveLoop | None,
        cwd: str | Path | None = None,
    ):
        if evaluation_loop is None:
            raise ValueError("WorkflowEvolutionRuntime requires an evaluation_loop")
        self.store = store
        self.output_dir = Path(output_dir)
        self.evaluation_loop = evaluation_loop
        self.cwd = Path(cwd) if cwd else Path(__file__).resolve().parents[2]

    def evolve(
        self,
        *,
        workflow_name: str,
        base_version: int,
        user_request: str,
        arguments: dict[str, Any],
        max_attempts: int = 3,
        repair_synthesizer: str = "agent-json",
        repair_workflow_json_file: str | Path | None = None,
        synthesizer_model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
        argument_example_summary: str | None = None,
    ) -> dict[str, Any]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        loader = WorkflowSkillLoader(self.store)
        base_skill = loader.load_skill_version(workflow_name, base_version)
        session_started = time.perf_counter()
        session_id = self._create_session(
            skill=base_skill,
            workflow_name=workflow_name,
            base_version=base_version,
            user_request=user_request,
            arguments=arguments,
            max_attempts=max_attempts,
        )
        session_dir = self.output_dir / "evolution" / f"session_{session_id:04d}"
        session_dir.mkdir(parents=True, exist_ok=True)
        attempts: list[dict[str, Any]] = []
        current_version = base_version

        try:
            for attempt_index in range(1, max_attempts + 1):
                skill = loader.load_skill_version(workflow_name, current_version)
                attempt_started = time.perf_counter()
                attempt_id = self._create_attempt(
                    session_id=session_id,
                    attempt_index=attempt_index,
                    skill=skill,
                )
                try:
                    result = WorkflowExecutor(
                        self.store,
                        output_dir=self.output_dir,
                        evaluation_loop=self.evaluation_loop,
                    ).run(
                        skill,
                        user_request=user_request,
                        arguments=arguments,
                    )
                    attempt_payload = self._passed_attempt_payload(
                        attempt_id=attempt_id,
                        attempt_index=attempt_index,
                        skill=skill,
                        result=result,
                        duration_ms=_elapsed_ms(attempt_started),
                    )
                    attempts.append(attempt_payload)
                    self._finish_attempt(
                        attempt_id=attempt_id,
                        status="succeeded",
                        workflow_run_id=result.run_id,
                        evaluation=result.evaluation,
                        duration_ms=attempt_payload["duration_ms"],
                    )
                    record_successful_argument_example(
                        self.store,
                        skill_id=skill.id,
                        version_id=skill.version_id,
                        user_request=user_request,
                        expected_output_summary=argument_example_summary or "Verified eval-and-evolve run",
                        arguments=arguments,
                    )
                    payload = {
                        "status": "succeeded",
                        "session_id": session_id,
                        "workflow": workflow_name,
                        "base_version": base_version,
                        "final_version": skill.version,
                        "final_run_id": result.run_id,
                        "attempt_count": len(attempts),
                        "attempts": attempts,
                    }
                    self._finish_session(
                        session_id=session_id,
                        status="succeeded",
                        final_version=skill.version,
                        final_version_id=skill.version_id,
                        final_run_id=result.run_id,
                        duration_ms=_elapsed_ms(session_started),
                    )
                    return payload
                except WorkflowEvaluationError as exc:
                    run_id = self._latest_run_id(skill.version_id)
                    evaluation = exc.report.as_dict()
                    duration_ms = _elapsed_ms(attempt_started)
                    repair_request_path = session_dir / f"attempt_{attempt_index:02d}" / "repair_request.json"
                    repair_request = self._build_repair_request(
                        session_id=session_id,
                        attempt_id=attempt_id,
                        attempt_index=attempt_index,
                        skill=skill,
                        workflow_run_id=run_id,
                        user_request=user_request,
                        arguments=arguments,
                        evaluation=evaluation,
                        repair_synthesizer=repair_synthesizer,
                    )
                    repair_request_path.parent.mkdir(parents=True, exist_ok=True)
                    repair_request_path.write_text(json.dumps(repair_request, ensure_ascii=False, indent=2), encoding="utf-8")
                    repair_request_id = self._record_repair_request(
                        session_id=session_id,
                        attempt_id=attempt_id,
                        skill=skill,
                        workflow_run_id=run_id,
                        request=repair_request,
                        request_path=repair_request_path,
                    )

                    failed_attempt = {
                        "attempt_index": attempt_index,
                        "version": skill.version,
                        "version_id": skill.version_id,
                        "run_id": run_id,
                        "status": "failed",
                        "error_type": "workflow_evaluation_failed",
                        "failed_step": evaluation.get("failed_step"),
                        "evaluation": evaluation,
                        "duration_ms": duration_ms,
                        "step_runs": self._step_run_summaries(run_id),
                        "repair_request_id": repair_request_id,
                        "repair_request_path": str(repair_request_path),
                    }

                    if attempt_index >= max_attempts:
                        attempts.append(failed_attempt)
                        self._finish_attempt(
                            attempt_id=attempt_id,
                            status="failed",
                            workflow_run_id=run_id,
                            evaluation=evaluation,
                            duration_ms=duration_ms,
                            repair_request_id=repair_request_id,
                            error={"type": "WorkflowEvaluationError", "message": str(exc)},
                        )
                        payload = {
                            "status": "failed",
                            "session_id": session_id,
                            "workflow": workflow_name,
                            "base_version": base_version,
                            "current_version": skill.version,
                            "attempt_count": len(attempts),
                            "attempts": attempts,
                            "repair_request_id": repair_request_id,
                            "repair_request_path": str(repair_request_path),
                            "error": {
                                "type": "MaxAttemptsExceeded",
                                "message": f"exhausted {max_attempts} attempts",
                            },
                        }
                        self._finish_session(
                            session_id=session_id,
                            status="failed",
                            final_version=None,
                            final_version_id=None,
                            final_run_id=None,
                            duration_ms=_elapsed_ms(session_started),
                            error=payload["error"],
                        )
                        return payload

                    if repair_synthesizer == "agent-json" and not repair_workflow_json_file:
                        attempts.append(failed_attempt)
                        self._finish_attempt(
                            attempt_id=attempt_id,
                            status="repair_requested",
                            workflow_run_id=run_id,
                            evaluation=evaluation,
                            duration_ms=duration_ms,
                            repair_request_id=repair_request_id,
                            error={"type": "WorkflowEvaluationError", "message": str(exc)},
                        )
                        payload = {
                            "status": "waiting_for_repair",
                            "session_id": session_id,
                            "workflow": workflow_name,
                            "base_version": base_version,
                            "current_version": skill.version,
                            "attempt_count": len(attempts),
                            "attempts": attempts,
                            "repair_request_id": repair_request_id,
                            "repair_request_path": str(repair_request_path),
                        }
                        self._finish_session(
                            session_id=session_id,
                            status="waiting_for_repair",
                            final_version=None,
                            final_version_id=None,
                            final_run_id=None,
                            duration_ms=_elapsed_ms(session_started),
                        )
                        return payload

                    proposal = WorkflowUpdateRuntime(self.store, cwd=self.cwd).propose_update(
                        workflow_name=workflow_name,
                        base_version=skill.version,
                        instruction=repair_request["instruction"],
                        page_text=exc.report.page_text,
                        discovery_provider="eval-and-evolve",
                        synthesizer=repair_synthesizer,
                        workflow_json_file=repair_workflow_json_file,
                        synthesizer_model=synthesizer_model,
                    )
                    applied = WorkflowUpdateRuntime(self.store, cwd=self.cwd).apply_proposal(
                        proposal_id=proposal["proposal_id"],
                        approved_by="evolution-runtime",
                    )
                    response_path = repair_request_path.parent / "repair_response.json"
                    response = {
                        "repair_request_id": repair_request_id,
                        "proposal": proposal,
                        "applied": applied,
                    }
                    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
                    repair_response_id = self._record_repair_response(
                        repair_request_id=repair_request_id,
                        proposal_id=proposal["proposal_id"],
                        applied_version_id=applied["applied_version_id"],
                        response=response,
                        response_path=response_path,
                    )
                    failed_attempt["status"] = "repair_applied"
                    failed_attempt["proposal_id"] = proposal["proposal_id"]
                    failed_attempt["applied_version"] = applied["applied_version"]
                    failed_attempt["applied_version_id"] = applied["applied_version_id"]
                    failed_attempt["repair_response_id"] = repair_response_id
                    failed_attempt["repair_response_path"] = str(response_path)
                    attempts.append(failed_attempt)
                    self._finish_attempt(
                        attempt_id=attempt_id,
                        status="repair_applied",
                        workflow_run_id=run_id,
                        evaluation=evaluation,
                        duration_ms=duration_ms,
                        repair_request_id=repair_request_id,
                        repair_response_id=repair_response_id,
                        applied_proposal_id=proposal["proposal_id"],
                        applied_version_id=applied["applied_version_id"],
                        error={"type": "WorkflowEvaluationError", "message": str(exc)},
                    )
                    current_version = int(applied["applied_version"])

            payload = {
                "status": "failed",
                "session_id": session_id,
                "workflow": workflow_name,
                "base_version": base_version,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "error": {"type": "MaxAttemptsExceeded", "message": f"exhausted {max_attempts} attempts"},
            }
            self._finish_session(
                session_id=session_id,
                status="failed",
                final_version=None,
                final_version_id=None,
                final_run_id=None,
                duration_ms=_elapsed_ms(session_started),
                error=payload["error"],
            )
            return payload
        except Exception as exc:
            self._finish_session(
                session_id=session_id,
                status="failed",
                final_version=None,
                final_version_id=None,
                final_run_id=None,
                duration_ms=_elapsed_ms(session_started),
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise

    def _passed_attempt_payload(
        self,
        *,
        attempt_id: int,
        attempt_index: int,
        skill: WorkflowSkill,
        result: WorkflowRunResult,
        duration_ms: int,
    ) -> dict[str, Any]:
        return {
            "attempt_id": attempt_id,
            "attempt_index": attempt_index,
            "version": skill.version,
            "version_id": skill.version_id,
            "run_id": result.run_id,
            "status": result.status,
            "duration_ms": duration_ms,
            "evaluation": result.evaluation,
            "step_runs": self._step_run_summaries(result.run_id),
            "output": result.output,
            "report_path": result.report_path,
        }

    def _build_repair_request(
        self,
        *,
        session_id: int,
        attempt_id: int,
        attempt_index: int,
        skill: WorkflowSkill,
        workflow_run_id: int | None,
        user_request: str,
        arguments: dict[str, Any],
        evaluation: dict[str, Any],
        repair_synthesizer: str,
    ) -> dict[str, Any]:
        failed_step = evaluation.get("failed_step") or {}
        run = self._load_run(workflow_run_id) if workflow_run_id else None
        return {
            "schema_version": 1,
            "session_id": session_id,
            "attempt_id": attempt_id,
            "attempt_index": attempt_index,
            "workflow_name": skill.name,
            "base_version": skill.version,
            "base_version_id": skill.version_id,
            "user_request": user_request,
            "arguments": arguments,
            "run": run,
            "evaluation": evaluation,
            "instruction": _repair_instruction(failed_step),
            "workflow_json": workflow_json_from_skill(self.store, skill),
            "response_contract": {
                "recommended_synthesizer": repair_synthesizer,
                "format": "full_next_workflow_json",
                "write_path_hint": "repair_response.json may include proposal/apply payloads; workflow JSON should be supplied through --repair-workflow-json-file for agent-json.",
                "requirements": [
                    "Preserve skill_name and slug unless explicitly renaming.",
                    "Return a complete workflow JSON, not a patch.",
                    "For variable browser actions such as ads, popups, modals, or unstable page chrome, use a scriptless llm_browser_action step.",
                    "Do not store generated JavaScript, Python, Playwright code, script, or runtime selectors inside workflow JSON.",
                    "Keep deterministic executable implementation in the workflow version resources/handlers viewable from Implementation.",
                    "Do not invoke nested codex exec from WebMCP core.",
                ],
            },
        }

    def _create_session(
        self,
        *,
        skill: WorkflowSkill,
        workflow_name: str,
        base_version: int,
        user_request: str,
        arguments: dict[str, Any],
        max_attempts: int,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into evolution_sessions
                      (skill_id, workflow_name, base_version, user_request, input_json,
                       status, max_attempts, output_dir)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.id,
                        workflow_name,
                        base_version,
                        user_request,
                        dumps(arguments),
                        "running",
                        max_attempts,
                        str(self.output_dir),
                    ),
                ).lastrowid
            )

    def _finish_session(
        self,
        *,
        session_id: int,
        status: str,
        final_version: int | None,
        final_version_id: int | None,
        final_run_id: int | None,
        duration_ms: int,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update evolution_sessions
                set status = ?, final_version = ?, final_version_id = ?, final_run_id = ?,
                    error_json = ?, finished_at = current_timestamp, duration_ms = ?
                where id = ?
                """,
                (
                    status,
                    final_version,
                    final_version_id,
                    final_run_id,
                    dumps(error) if error else None,
                    duration_ms,
                    session_id,
                ),
            )

    def _create_attempt(self, *, session_id: int, attempt_index: int, skill: WorkflowSkill) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into evolution_attempts
                      (session_id, attempt_index, version, version_id, status)
                    values (?, ?, ?, ?, ?)
                    """,
                    (session_id, attempt_index, skill.version, skill.version_id, "running"),
                ).lastrowid
            )

    def _finish_attempt(
        self,
        *,
        attempt_id: int,
        status: str,
        workflow_run_id: int | None,
        evaluation: dict[str, Any] | None,
        duration_ms: int,
        repair_request_id: int | None = None,
        repair_response_id: int | None = None,
        applied_proposal_id: int | None = None,
        applied_version_id: int | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update evolution_attempts
                set status = ?, workflow_run_id = ?, evaluation_json = ?,
                    repair_request_id = coalesce(?, repair_request_id),
                    repair_response_id = coalesce(?, repair_response_id),
                    applied_proposal_id = coalesce(?, applied_proposal_id),
                    applied_version_id = coalesce(?, applied_version_id),
                    error_json = ?, finished_at = current_timestamp, duration_ms = ?
                where id = ?
                """,
                (
                    status,
                    workflow_run_id,
                    dumps(evaluation) if evaluation else None,
                    repair_request_id,
                    repair_response_id,
                    applied_proposal_id,
                    applied_version_id,
                    dumps(error) if error else None,
                    duration_ms,
                    attempt_id,
                ),
            )

    def _record_repair_request(
        self,
        *,
        session_id: int,
        attempt_id: int,
        skill: WorkflowSkill,
        workflow_run_id: int | None,
        request: dict[str, Any],
        request_path: Path,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into repair_requests
                      (session_id, attempt_id, skill_id, base_version_id, workflow_run_id,
                       status, request_json, request_path)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        attempt_id,
                        skill.id,
                        skill.version_id,
                        workflow_run_id,
                        "created",
                        dumps(request),
                        str(request_path),
                    ),
                ).lastrowid
            )

    def _record_repair_response(
        self,
        *,
        repair_request_id: int,
        proposal_id: int,
        applied_version_id: int,
        response: dict[str, Any],
        response_path: Path,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into repair_responses
                      (repair_request_id, proposal_id, applied_version_id, status,
                       response_json, response_path)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repair_request_id,
                        proposal_id,
                        applied_version_id,
                        "applied",
                        dumps(response),
                        str(response_path),
                    ),
                ).lastrowid
            )

    def _latest_run_id(self, version_id: int) -> int | None:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                select id
                from workflow_runs
                where version_id = ?
                order by id desc
                limit 1
                """,
                (version_id,),
            ).fetchone()
        return int(row["id"]) if row else None

    def _load_run(self, run_id: int | None) -> dict[str, Any] | None:
        if run_id is None:
            return None
        with self.store.connect() as conn:
            row = conn.execute(
                """
                select id, status, duration_ms, output_json, report_path
                from workflow_runs
                where id = ?
                """,
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "output": loads(row["output_json"], {}),
            "report_path": row["report_path"],
        }

    def _step_run_summaries(self, run_id: int | None) -> list[dict[str, Any]]:
        if run_id is None:
            return []
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                select sr.id, sr.step_id, sr.status, sr.duration_ms, sr.evidence_json,
                       sr.error_json, ws.name as step_name, ws.step_type, ws.order_index
                from step_runs sr
                join workflow_tool_steps ws on ws.id = sr.step_id
                where sr.run_id = ?
                order by ws.order_index, sr.id
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "step_id": int(row["step_id"]),
                "step_name": row["step_name"],
                "step_type": row["step_type"],
                "order_index": int(row["order_index"]),
                "status": row["status"],
                "duration_ms": row["duration_ms"],
                "evidence": loads(row["evidence_json"], {}),
                "error": loads(row["error_json"], None),
            }
            for row in rows
        ]


def _repair_instruction(failed_step: dict[str, Any]) -> str:
    step_name = failed_step.get("step_name") or "unknown_step"
    summary = failed_step.get("summary") or "The workflow evaluation failed."
    suggested_update = failed_step.get("suggested_update") or "Repair the workflow so the browser evaluation passes."
    failure_kind = failed_step.get("failure_kind") or "unspecified"
    expected_state = failed_step.get("expected_state") or ""
    observed_state = failed_step.get("observed_state") or ""
    repair_focus = failed_step.get("repair_focus") or step_name
    return (
        f"Repair WebMCP workflow after evaluation failure at `{step_name}`.\n"
        f"Failure kind: {failure_kind}\n"
        f"Summary: {summary}\n"
        f"Expected state: {expected_state}\n"
        f"Observed state: {observed_state}\n"
        f"Repair focus: {repair_focus}\n"
        f"Suggested update: {suggested_update}"
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
