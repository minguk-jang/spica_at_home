from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from webworkflows.argument_examples import record_successful_argument_example
from webworkflows.cold_init import WorkflowMaterializer, discovery_from_workflow_json
from webworkflows.cold_init_types import ArtifactTrace
from webworkflows.eval_loop import EvalAndEvolveLoop
from webworkflows.executor import WorkflowExecutor
from webworkflows.loader import WorkflowSkillLoader
from webworkflows.page_memory import PageAnalysisStore, WorkflowKnowledgeStore, build_script_generation_knowledge
from webworkflows.services.evolution_runtime import WorkflowEvolutionRuntime
from webworkflows.storage import WorkflowSkillStore, dumps, loads
from webworkflows.synthesis import DEFAULT_CODEX_SYNTHESIS_MODEL


class WorkflowSynthesizer(Protocol):
    provider: str
    model: str

    def synthesize_json(self, trace: ArtifactTrace):
        ...


class CreationTraceCollector(Protocol):
    provider: str

    def collect(
        self,
        *,
        start_url: str,
        user_task: str,
        final_state: str,
        arguments: dict[str, Any],
    ) -> ArtifactTrace:
        ...


class GenericBrowserTraceCollector:
    provider = "generic_browser_trace"

    def __init__(self, *, output_dir: str | Path, headed: bool = False, browser_name: str = "chromium"):
        self.output_dir = Path(output_dir)
        self.headed = headed
        self.browser_name = browser_name

    def collect(
        self,
        *,
        start_url: str,
        user_task: str,
        final_state: str,
        arguments: dict[str, Any],
    ) -> ArtifactTrace:
        page_text, title, final_url, screenshots = asyncio.run(self._collect_trace(start_url))
        return ArtifactTrace(
            provider=self.provider,
            user_request=user_task,
            arguments={
                **arguments,
                "start_url": start_url,
                "final_state": final_state,
            },
            page_text=page_text,
            title=title,
            final_url=final_url,
            screenshots=screenshots,
        )

    async def _collect_trace(self, start_url: str) -> tuple[str, str, str, list[str]]:
        trace: ArtifactTrace | None = None
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required for generic browser workflow creation. "
                "Run with reference/webwright/.venv/bin/python or install playwright."
            ) from exc

        screenshots_dir = self.output_dir / "creation_traces"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshots_dir / f"create_trace_{int(time.time() * 1000)}.png"

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
            await page.screenshot(path=str(screenshot_path), full_page=True)
            page_text = await page.locator("body").inner_text(timeout=15000)
            title = await page.title()
            final_url = page.url
            await browser.close()
        return page_text, title, final_url, [str(screenshot_path)]


class StaticCreationTraceCollector:
    provider = "static_create_trace"

    def __init__(self, *, page_text: str, title: str = "", final_url: str = ""):
        self.page_text = page_text
        self.title = title
        self.final_url = final_url

    def collect(
        self,
        *,
        start_url: str,
        user_task: str,
        final_state: str,
        arguments: dict[str, Any],
    ) -> ArtifactTrace:
        return ArtifactTrace(
            provider=self.provider,
            user_request=user_task,
            arguments={
                **arguments,
                "start_url": start_url,
                "final_state": final_state,
            },
            page_text=self.page_text,
            title=self.title,
            final_url=self.final_url or start_url,
            screenshots=[],
        )


class WorkflowCreationRuntime:
    def __init__(
        self,
        store: WorkflowSkillStore,
        *,
        output_dir: str | Path,
        trace_collector: CreationTraceCollector,
        synthesizer: WorkflowSynthesizer,
        evaluation_loop: EvalAndEvolveLoop | None = None,
        cwd: str | Path | None = None,
    ):
        self.store = store
        self.output_dir = Path(output_dir)
        self.trace_collector = trace_collector
        self.synthesizer = synthesizer
        self.evaluation_loop = evaluation_loop
        self.cwd = Path(cwd) if cwd else Path(__file__).resolve().parents[2]

    def create(
        self,
        *,
        start_url: str,
        user_task: str,
        final_state: str,
        arguments: dict[str, Any],
        max_attempts: int = 3,
        repair_synthesizer: str = "codex",
        synthesizer_model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
    ) -> dict[str, Any]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        session_started = time.perf_counter()
        run_arguments = dict(arguments)
        run_arguments["start_url"] = start_url
        run_arguments["final_state"] = final_state

        session_id = self._create_session(
            start_url=start_url,
            user_task=user_task,
            final_state=final_state,
            arguments=run_arguments,
            max_attempts=max_attempts,
        )
        attempt_id = self._create_attempt(
            session_id=session_id,
            attempt_index=1,
            discovery_provider=self.trace_collector.provider,
        )

        try:
            discovery_started = time.perf_counter()
            trace = self.trace_collector.collect(
                start_url=start_url,
                user_task=user_task,
                final_state=final_state,
                arguments=run_arguments,
            )
            trace = self._enrich_trace_with_page_memory(trace)
            discovery_duration_ms = _elapsed_ms(discovery_started)
            self._record_trace_artifacts(session_id, attempt_id, trace)

            synthesis_started = time.perf_counter()
            synthesis_result = self.synthesizer.synthesize_json(trace)
            synthesis_duration_ms = _elapsed_ms(synthesis_started)

            materialization_started = time.perf_counter()
            discovery = discovery_from_workflow_json(
                synthesis_result.workflow_json,
                provider=synthesis_result.provider,
                page_text=trace.page_text,
            )
            skill_id, version_id = WorkflowMaterializer(self.store).materialize(
                discovery,
                skill_status="draft",
                version_status="draft",
            )
            materialization_duration_ms = _elapsed_ms(materialization_started)
            publication_state = self._publication_state(skill_id=skill_id, version_id=version_id)

            loader = WorkflowSkillLoader(self.store)
            skill = loader.load_skill(skill_id)
            first_run_arguments = _first_run_arguments(skill, run_arguments)
            first_run_arguments.setdefault("page_text", trace.page_text)
            first_run_duration_ms: int
            workflow_run_id: int | None
            run_payload: dict[str, Any]
            status: str
            created_version_id = version_id
            created_workflow_version = skill.version

            if self.evaluation_loop:
                evolution_payload = WorkflowEvolutionRuntime(
                    self.store,
                    output_dir=self.output_dir,
                    evaluation_loop=self.evaluation_loop,
                    cwd=self.cwd,
                ).evolve(
                    workflow_name=skill.name,
                    base_version=skill.version,
                    user_request=user_task,
                    arguments=first_run_arguments,
                    max_attempts=max_attempts,
                    repair_synthesizer=repair_synthesizer,
                    synthesizer_model=synthesizer_model,
                    argument_example_summary=final_state,
                )
                status = evolution_payload["status"]
                workflow_run_id = evolution_payload.get("final_run_id")
                first_run_duration_ms = self._run_duration_ms(workflow_run_id)
                if status == "succeeded" and evolution_payload.get("final_version"):
                    final_skill = loader.load_skill_version(skill.name, int(evolution_payload["final_version"]))
                    created_version_id = final_skill.version_id
                    created_workflow_version = final_skill.version
                run_payload = {
                    "evolution": evolution_payload,
                    "output": _load_run_output(self.store, workflow_run_id),
                    "report_path": _load_run_report_path(self.store, workflow_run_id),
                }
            else:
                run_started = time.perf_counter()
                run_result = WorkflowExecutor(self.store, output_dir=self.output_dir).run(
                    skill,
                    user_request=user_task,
                    arguments=first_run_arguments,
                )
                first_run_duration_ms = self._run_duration_ms(run_result.run_id, fallback=_elapsed_ms(run_started))
                workflow_run_id = run_result.run_id
                status = run_result.status
                run_payload = {
                    "output": run_result.output,
                    "report_path": run_result.report_path,
                }

            if status == "succeeded":
                self._publish_created_workflow(skill_id=skill_id, version_id=created_version_id)
                record_successful_argument_example(
                    self.store,
                    skill_id=skill_id,
                    version_id=created_version_id,
                    user_request=user_task,
                    expected_output_summary=final_state,
                    arguments=first_run_arguments,
                )
            else:
                self._restore_publication_state(publication_state)
            self._record_creation_knowledge(
                status=status,
                workflow_name=skill.name,
                workflow_version=created_workflow_version,
                start_url=start_url,
                user_task=user_task,
                final_state=final_state,
                run_payload=run_payload,
                page_analysis=trace.page_analysis_context if trace else None,
            )

            self._finish_attempt(
                attempt_id=attempt_id,
                status=status,
                synthesis_provider=synthesis_result.provider,
                synthesis_model=synthesis_result.model,
                workflow_json=synthesis_result.workflow_json,
                workflow_run_id=workflow_run_id,
                discovery_duration_ms=discovery_duration_ms,
                synthesis_duration_ms=synthesis_duration_ms,
                materialization_duration_ms=materialization_duration_ms,
                first_run_duration_ms=first_run_duration_ms,
                evaluation=run_payload.get("evolution"),
            )
            self._finish_session(
                session_id=session_id,
                status=status,
                created_skill_id=skill_id,
                created_version_id=created_version_id,
                workflow_run_id=workflow_run_id,
                duration_ms=_elapsed_ms(session_started),
            )

            return {
                "status": status,
                "creation_session_id": session_id,
                "creation_attempt_id": attempt_id,
                "workflow": skill.name,
                "workflow_version": created_workflow_version,
                "created_skill_id": skill_id,
                "created_version_id": created_version_id,
                "workflow_run_id": workflow_run_id,
                "synthesizer": synthesis_result.provider,
                "synthesizer_model": synthesis_result.model,
                "discovery_provider": self.trace_collector.provider,
                "discovery_duration_ms": discovery_duration_ms,
                "synthesis_duration_ms": synthesis_duration_ms,
                "materialization_duration_ms": materialization_duration_ms,
                "first_run_duration_ms": first_run_duration_ms,
                **run_payload,
            }
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            self._record_creation_knowledge(
                status="failed",
                workflow_name="",
                workflow_version=None,
                start_url=start_url,
                user_task=user_task,
                final_state=final_state,
                run_payload={"error": error},
                page_analysis=trace.page_analysis_context if trace else None,
            )
            self._finish_attempt(
                attempt_id=attempt_id,
                status="failed",
                synthesis_provider=None,
                synthesis_model=None,
                workflow_json=None,
                workflow_run_id=None,
                discovery_duration_ms=None,
                synthesis_duration_ms=None,
                materialization_duration_ms=None,
                first_run_duration_ms=None,
                evaluation=None,
                error=error,
            )
            self._finish_session(
                session_id=session_id,
                status="failed",
                created_skill_id=None,
                created_version_id=None,
                workflow_run_id=None,
                duration_ms=_elapsed_ms(session_started),
                error=error,
            )
            raise

    def _enrich_trace_with_page_memory(self, trace: ArtifactTrace) -> ArtifactTrace:
        page_analysis = PageAnalysisStore(self.store).upsert_from_trace(trace, source="workflow_creation")
        knowledge_entries = WorkflowKnowledgeStore(self.store).recent(category="script_generation", limit=5)
        return replace(
            trace,
            page_analysis_context=page_analysis.as_context(),
            knowledge_context=[entry.as_context() for entry in knowledge_entries],
        )

    def _record_creation_knowledge(
        self,
        *,
        status: str,
        workflow_name: str,
        workflow_version: int | None,
        start_url: str,
        user_task: str,
        final_state: str,
        run_payload: dict[str, Any],
        page_analysis: dict[str, Any] | None,
    ) -> None:
        knowledge = build_script_generation_knowledge(
            status=status,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            start_url=start_url,
            user_task=user_task,
            final_state=final_state,
            output_keys=sorted((run_payload.get("output") or {}).keys()),
            page_analysis=page_analysis,
            error=run_payload.get("error"),
        )
        WorkflowKnowledgeStore(self.store).append(**knowledge)

    def _create_session(
        self,
        *,
        start_url: str,
        user_task: str,
        final_state: str,
        arguments: dict[str, Any],
        max_attempts: int,
    ) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into workflow_creation_sessions
                      (start_url, user_task, final_state_description, input_json,
                       status, max_attempts, output_dir)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        start_url,
                        user_task,
                        final_state,
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
        created_skill_id: int | None,
        created_version_id: int | None,
        workflow_run_id: int | None,
        duration_ms: int,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update workflow_creation_sessions
                set status = ?, created_skill_id = ?, created_version_id = ?,
                    workflow_run_id = ?, error_json = ?, finished_at = current_timestamp,
                    duration_ms = ?
                where id = ?
                """,
                (
                    status,
                    created_skill_id,
                    created_version_id,
                    workflow_run_id,
                    dumps(error) if error else None,
                    duration_ms,
                    session_id,
                ),
            )

    def _create_attempt(self, *, session_id: int, attempt_index: int, discovery_provider: str) -> int:
        with self.store.connect() as conn:
            return int(
                conn.execute(
                    """
                    insert into workflow_creation_attempts
                      (session_id, attempt_index, discovery_provider, status)
                    values (?, ?, ?, ?)
                    """,
                    (session_id, attempt_index, discovery_provider, "running"),
                ).lastrowid
            )

    def _finish_attempt(
        self,
        *,
        attempt_id: int,
        status: str,
        synthesis_provider: str | None,
        synthesis_model: str | None,
        workflow_json: dict[str, Any] | None,
        workflow_run_id: int | None,
        discovery_duration_ms: int | None,
        synthesis_duration_ms: int | None,
        materialization_duration_ms: int | None,
        first_run_duration_ms: int | None,
        evaluation: dict[str, Any] | None,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update workflow_creation_attempts
                set status = ?, synthesis_provider = ?, synthesis_model = ?,
                    workflow_json = ?, workflow_run_id = ?, evaluation_json = ?,
                    discovery_duration_ms = ?, synthesis_duration_ms = ?,
                    materialization_duration_ms = ?, first_run_duration_ms = ?,
                    error_json = ?, finished_at = current_timestamp
                where id = ?
                """,
                (
                    status,
                    synthesis_provider,
                    synthesis_model,
                    dumps(workflow_json) if workflow_json else None,
                    workflow_run_id,
                    dumps(evaluation) if evaluation else None,
                    discovery_duration_ms,
                    synthesis_duration_ms,
                    materialization_duration_ms,
                    first_run_duration_ms,
                    dumps(error) if error else None,
                    attempt_id,
                ),
            )

    def _record_trace_artifacts(self, session_id: int, attempt_id: int, trace: ArtifactTrace) -> None:
        with self.store.connect() as conn:
            for screenshot in trace.screenshots or []:
                conn.execute(
                    """
                    insert into workflow_creation_artifacts
                      (session_id, attempt_id, artifact_type, path, metadata_json)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        attempt_id,
                        "screenshot",
                        screenshot,
                        dumps({"provider": trace.provider, "final_url": trace.final_url, "title": trace.title}),
                    ),
                )

    def _publish_created_workflow(self, *, skill_id: int, version_id: int) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update workflow_skills
                set status = 'stable', latest_version_id = ?, updated_at = current_timestamp
                where id = ?
                """,
                (version_id, skill_id),
            )
            conn.execute(
                "update workflow_skill_versions set status = 'stable' where id = ?",
                (version_id,),
            )

    def _publication_state(self, *, skill_id: int, version_id: int) -> dict[str, Any]:
        with self.store.connect() as conn:
            skill = conn.execute(
                "select status, latest_version_id from workflow_skills where id = ?",
                (skill_id,),
            ).fetchone()
            version = conn.execute(
                "select version, status from workflow_skill_versions where id = ?",
                (version_id,),
            ).fetchone()
        if not skill or not version:
            raise KeyError(f"workflow publication state not found: skill={skill_id}, version={version_id}")
        return {
            "skill_id": skill_id,
            "version_id": version_id,
            "skill_status": skill["status"],
            "latest_version_id": int(skill["latest_version_id"]),
            "version": int(version["version"]),
            "version_status": version["status"],
        }

    def _restore_publication_state(self, state: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                update workflow_skills
                set status = ?, latest_version_id = ?, updated_at = current_timestamp
                where id = ?
                """,
                (state["skill_status"], state["latest_version_id"], state["skill_id"]),
            )
            conn.execute(
                "update workflow_skill_versions set status = ? where id = ?",
                (state["version_status"], state["version_id"]),
            )
            conn.execute(
                """
                update workflow_skill_versions
                set status = 'draft'
                where skill_id = ? and version > ?
                """,
                (state["skill_id"], state["version"]),
            )

    def _run_duration_ms(self, run_id: int | None, fallback: int = 0) -> int:
        if run_id is None:
            return fallback
        with self.store.connect() as conn:
            row = conn.execute("select duration_ms from workflow_runs where id = ?", (run_id,)).fetchone()
        if row and row["duration_ms"] is not None:
            return int(row["duration_ms"])
        return fallback


def _load_run_output(store: WorkflowSkillStore, run_id: int | None) -> dict[str, Any]:
    if run_id is None:
        return {}
    with store.connect() as conn:
        row = conn.execute("select output_json from workflow_runs where id = ?", (run_id,)).fetchone()
    return loads(row["output_json"], {}) if row else {}


def _load_run_report_path(store: WorkflowSkillStore, run_id: int | None) -> str:
    if run_id is None:
        return ""
    with store.connect() as conn:
        row = conn.execute("select report_path from workflow_runs where id = ?", (run_id,)).fetchone()
    return row["report_path"] if row and row["report_path"] else ""


def _first_run_arguments(skill, run_arguments: dict[str, Any]) -> dict[str, Any]:
    arguments = dict(run_arguments)
    for argument in skill.arguments:
        if arguments.get(argument.name) not in (None, ""):
            continue
        if argument.default_value is not None:
            arguments[argument.name] = argument.default_value
            continue
        if argument.examples:
            arguments[argument.name] = argument.examples[0]
    return arguments


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
