from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from webworkflows.loader import WorkflowSkill, WorkflowSkillLoader
from webworkflows.providers.synthesis_provider import create_synthesis_backend
from webworkflows.storage import WorkflowSkillStore, dumps, loads
from webworkflows.synthesis import (
    DEFAULT_CODEX_SYNTHESIS_MODEL,
    WORKFLOW_JSON_SCHEMA,
    CodexCliSynthesisBackend,
    SynthesisBackend,
    bind_known_handlers,
    validate_workflow_json,
)


@dataclass(frozen=True)
class UpdateProposalResult:
    proposal_id: int
    workflow_name: str
    base_version: int
    proposed_version: int
    status: str
    diff: dict[str, Any]
    proposed_workflow_json: dict[str, Any]
    synthesis_duration_ms: int


@dataclass(frozen=True)
class ApplyProposalResult:
    proposal_id: int
    workflow_name: str
    status: str
    applied_version: int
    applied_version_id: int


class WorkflowUpdateProposalService:
    def __init__(
        self,
        store: WorkflowSkillStore,
        *,
        backend: SynthesisBackend | None = None,
        model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
        cwd: str | Path | None = None,
    ):
        self.store = store
        self.backend = backend or CodexCliSynthesisBackend(cwd=cwd)
        self.model = model

    @property
    def synthesizer_provider(self) -> str:
        return self.backend.provider

    def propose(
        self,
        *,
        workflow_name: str,
        base_version: int,
        instruction: str,
        page_text: str = "",
        discovery_provider: str = "none",
    ) -> UpdateProposalResult:
        if not instruction.strip():
            raise ValueError("instruction is required")

        loader = WorkflowSkillLoader(self.store)
        skill = loader.load_skill_version(workflow_name, base_version)
        base_workflow = workflow_json_from_skill(self.store, skill)
        prompt = build_update_prompt(
            base_workflow=base_workflow,
            instruction=instruction,
            page_text=page_text,
            discovery_provider=discovery_provider,
        )
        started = time.perf_counter()
        proposed = self.backend.synthesize(prompt=prompt, schema=WORKFLOW_JSON_SCHEMA, model=self.model)
        synthesis_duration_ms = _elapsed_ms(started)
        proposed = bind_known_handlers(proposed)
        validate_workflow_json(proposed)
        _validate_same_workflow(base_workflow, proposed)
        diff = diff_workflow_json(base_workflow, proposed)
        proposed_version = _next_version(self.store, skill.id)
        evidence = {
            "instruction": instruction,
            "discovery_provider": discovery_provider,
            "page_text_excerpt": page_text[:2000],
            "base_version": base_version,
        }

        with self.store.connect() as conn:
            proposal_id = int(
                conn.execute(
                    """
                    insert into workflow_update_proposals
                      (skill_id, base_version_id, proposed_version, instruction,
                       discovery_provider, synthesizer_provider, synthesizer_model, status,
                       proposed_workflow_json, diff_json, evidence_json, synthesis_duration_ms)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.id,
                        skill.version_id,
                        proposed_version,
                        instruction,
                        discovery_provider,
                        self.synthesizer_provider,
                        self.model,
                        "draft",
                        dumps(proposed),
                        dumps(diff),
                        dumps(evidence),
                        synthesis_duration_ms,
                    ),
                ).lastrowid
            )

        return UpdateProposalResult(
            proposal_id=proposal_id,
            workflow_name=workflow_name,
            base_version=base_version,
            proposed_version=proposed_version,
            status="draft",
            diff=diff,
            proposed_workflow_json=proposed,
            synthesis_duration_ms=synthesis_duration_ms,
        )

    def apply(self, *, proposal_id: int, approved_by: str = "desktop") -> ApplyProposalResult:
        with self.store.connect() as conn:
            proposal = conn.execute(
                """
                select p.*, s.name as workflow_name
                from workflow_update_proposals p
                join workflow_tools s on s.id = p.skill_id
                where p.id = ?
                """,
                (proposal_id,),
            ).fetchone()
            if not proposal:
                raise KeyError(f"workflow update proposal not found: {proposal_id}")
            if proposal["status"] == "applied" and proposal["applied_version_id"]:
                version_row = conn.execute(
                    "select version from workflow_tool_versions where id = ?",
                    (proposal["applied_version_id"],),
                ).fetchone()
                return ApplyProposalResult(
                    proposal_id=proposal_id,
                    workflow_name=proposal["workflow_name"],
                    status="applied",
                    applied_version=int(version_row["version"]),
                    applied_version_id=int(proposal["applied_version_id"]),
                )
            if proposal["status"] != "draft":
                raise ValueError(f"cannot apply proposal with status: {proposal['status']}")

            workflow = bind_known_handlers(loads(proposal["proposed_workflow_json"], {}))
            validate_workflow_json(workflow)
            base = conn.execute(
                "select version from workflow_tool_versions where id = ?",
                (proposal["base_version_id"],),
            ).fetchone()
            if not base:
                raise KeyError(f"base workflow version not found: {proposal['base_version_id']}")
            next_version = _next_version_from_conn(conn, int(proposal["skill_id"]))
            version_id = _insert_workflow_version(
                conn,
                skill_id=int(proposal["skill_id"]),
                workflow=workflow,
                version=next_version,
                summary=f"Updated from Desktop instruction: {proposal['instruction']}",
                created_from_run_id=None,
            )
            conn.execute(
                """
                update workflow_tools
                set latest_version_id = ?, description = ?, domain = ?, task_type = ?,
                    updated_at = current_timestamp
                where id = ?
                """,
                (
                    version_id,
                    workflow["description"],
                    workflow["domain"],
                    workflow["task_type"],
                    proposal["skill_id"],
                ),
            )
            event_diff = loads(proposal["diff_json"], {})
            event_diff["proposal_id"] = proposal_id
            conn.execute(
                """
                insert into workflow_tool_update_events
                  (skill_id, from_version_id, to_version_id, run_id, update_type, reason, diff_json, approved_by)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal["skill_id"],
                    proposal["base_version_id"],
                    version_id,
                    None,
                    "user_instruction",
                    proposal["instruction"],
                    dumps(event_diff),
                    approved_by,
                ),
            )
            conn.execute(
                """
                update workflow_update_proposals
                set status = 'applied', applied_version_id = ?, approved_by = ?,
                    updated_at = current_timestamp
                where id = ?
                """,
                (version_id, approved_by, proposal_id),
            )

        return ApplyProposalResult(
            proposal_id=proposal_id,
            workflow_name=proposal["workflow_name"],
            status="applied",
            applied_version=next_version,
            applied_version_id=version_id,
        )


def backend_from_name(
    name: str,
    *,
    workflow_json_file: str | Path | None = None,
    base_workflow_json: dict[str, Any] | None = None,
    cwd: str | Path | None = None,
) -> SynthesisBackend:
    return create_synthesis_backend(
        name,
        workflow_json_file=workflow_json_file,
        base_workflow_json=base_workflow_json,
        cwd=cwd,
    )


def workflow_json_from_skill(store: WorkflowSkillStore, skill: WorkflowSkill) -> dict[str, Any]:
    with store.connect() as conn:
        skill_row = conn.execute(
            "select slug from workflow_tools where id = ?",
            (skill.id,),
        ).fetchone()
        resource_rows = conn.execute(
            """
            select resource_type, name, description, content_json, content_text, load_when_json
            from workflow_tool_resources
            where version_id = ?
            order by id
            """,
            (skill.version_id,),
        ).fetchall()
        handler_names = sorted({step.handler_ref for step in skill.steps if step.handler_ref})
        handler_rows = []
        if handler_names:
            placeholders = ",".join("?" for _ in handler_names)
            handler_rows = conn.execute(
                f"""
                select name, description, module, function, input_schema_json, output_schema_json, allowed_domains_json
                from handler_registry
                where name in ({placeholders})
                order by name
                """,
                tuple(handler_names),
            ).fetchall()

    return {
        "skill_name": skill.name,
        "slug": skill_row["slug"] if skill_row else skill.name.replace("_", "-"),
        "description": skill.description,
        "domain": skill.domain,
        "task_type": skill.task_type,
        "body_md": skill.body_md,
        "input_schema": skill.input_schema,
        "output_schema": skill.output_schema,
        "arguments": [
            {
                "name": argument.name,
                "description": argument.description,
                "type": argument.type,
                "required": argument.required,
                "default_value": argument.default_value,
                "validation": argument.validation,
                "examples": argument.examples,
                "is_dynamic": argument.is_dynamic,
                "order_index": index,
            }
            for index, argument in enumerate(skill.arguments)
        ],
        "steps": [
            {
                "name": step.name,
                "description": step.description,
                "step_type": step.step_type,
                "handler_ref": step.handler_ref,
                "action": step.action,
                "argument_bindings": step.argument_bindings,
                "assertions": step.assertions,
                "fallback_policy": step.fallback_policy,
                "update_policy": step.update_policy,
            }
            for step in skill.steps
        ],
        "resources": [
            {
                "resource_type": row["resource_type"],
                "name": row["name"],
                "description": row["description"],
                "content_json": loads(row["content_json"], None),
                "content_text": row["content_text"] or "",
                "load_when": loads(row["load_when_json"], {}),
            }
            for row in resource_rows
        ],
        "handlers": [
            {
                "name": row["name"],
                "description": row["description"],
                "module": row["module"],
                "function": row["function"],
                "input_schema": loads(row["input_schema_json"], {}),
                "output_schema": loads(row["output_schema_json"], {}),
                "allowed_domains": loads(row["allowed_domains_json"], []),
            }
            for row in handler_rows
        ],
    }


def build_update_prompt(
    *,
    base_workflow: dict[str, Any],
    instruction: str,
    page_text: str,
    discovery_provider: str,
) -> str:
    return (
        "You are updating an existing reusable WebMCP workflow JSON.\n"
        "Return the full next workflow JSON, not a patch. Return only JSON matching the schema.\n"
        "Preserve the same skill_name and slug unless the user explicitly asks to rename the workflow.\n"
        "Use only declarative steps, resources, handler refs, assertions, templates, and scriptless dynamic instructions.\n"
        "If a browser step is variable across runs, such as closing ads/popups/modals or handling unstable page chrome, "
        "use `llm_browser_action`. Store only action.instruction, action.success_criteria, action.allowed_operations, "
        "and action.timeout_ms. Do not store generated JavaScript, Python, Playwright code, script, or runtime selectors "
        "in the workflow JSON; the runtime LLM generates and executes that code during the run.\n"
        "If browser evidence is needed but absent, make the smallest safe workflow/template/schema update and keep "
        "existing selectors/handlers stable.\n\n"
        f"User update instruction: {instruction}\n"
        f"Discovery provider: {discovery_provider}\n"
        "Discovery/page evidence excerpt:\n"
        f"{page_text[:6000]}\n\n"
        "Current workflow JSON:\n"
        f"{json.dumps(base_workflow, ensure_ascii=False, sort_keys=True)}\n"
    )


def diff_workflow_json(base: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    return {
        "body_changed": base.get("body_md") != proposed.get("body_md"),
        "input_schema_changed": base.get("input_schema") != proposed.get("input_schema"),
        "output_schema_changed": base.get("output_schema") != proposed.get("output_schema"),
        "arguments_added": _added_names(base.get("arguments", []), proposed.get("arguments", [])),
        "arguments_removed": _removed_names(base.get("arguments", []), proposed.get("arguments", [])),
        "arguments_changed": _changed_named_items(base.get("arguments", []), proposed.get("arguments", [])),
        "steps_added": _added_names(base.get("steps", []), proposed.get("steps", [])),
        "steps_removed": _removed_names(base.get("steps", []), proposed.get("steps", [])),
        "steps_changed": _changed_named_items(base.get("steps", []), proposed.get("steps", [])),
        "resources_added": _added_names(base.get("resources", []), proposed.get("resources", [])),
        "resources_removed": _removed_names(base.get("resources", []), proposed.get("resources", [])),
        "resources_changed": _changed_named_items(base.get("resources", []), proposed.get("resources", [])),
    }


def _insert_workflow_version(
    conn,
    *,
    skill_id: int,
    workflow: dict[str, Any],
    version: int,
    summary: str,
    created_from_run_id: int | None,
) -> int:
    version_id = int(
        conn.execute(
            """
            insert into workflow_tool_versions
              (skill_id, version, summary, input_schema_json, output_schema_json,
               body_md, load_policy_json, created_from_run_id, status)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill_id,
                version,
                summary,
                dumps(workflow["input_schema"]),
                dumps(workflow["output_schema"]),
                workflow["body_md"],
                dumps({"metadata_first": True, "lazy_load_steps": True}),
                created_from_run_id,
                "stable",
            ),
        ).lastrowid
    )
    for index, argument in enumerate(workflow["arguments"]):
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
                dumps(argument["default_value"]) if argument.get("default_value") is not None else None,
                dumps(argument["validation"]),
                dumps(argument["examples"]),
                int(argument["is_dynamic"]),
                argument.get("order_index", index),
            ),
        )
    for index, step in enumerate(workflow["steps"]):
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
                step.get("handler_ref"),
                dumps(step["action"]),
                dumps(step.get("argument_bindings", {})),
                dumps(step["assertions"]),
                dumps(step.get("fallback_policy", {})),
                dumps(step.get("update_policy", {})),
            ),
        )
    for resource in workflow["resources"]:
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
                dumps(resource["content_json"]) if resource.get("content_json") is not None else None,
                resource.get("content_text"),
                dumps(resource.get("load_when", {})),
            ),
        )
    for handler in workflow.get("handlers", []):
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
    return version_id


def _validate_same_workflow(base: dict[str, Any], proposed: dict[str, Any]) -> None:
    if proposed["skill_name"] != base["skill_name"]:
        raise ValueError("proposed workflow must keep the same skill_name")
    if proposed["slug"] != base["slug"]:
        raise ValueError("proposed workflow must keep the same slug")


def _next_version(store: WorkflowSkillStore, skill_id: int) -> int:
    with store.connect() as conn:
        return _next_version_from_conn(conn, skill_id)


def _next_version_from_conn(conn, skill_id: int) -> int:
    row = conn.execute(
        "select coalesce(max(version), 0) + 1 as next_version from workflow_tool_versions where skill_id = ?",
        (skill_id,),
    ).fetchone()
    return int(row["next_version"])


def _added_names(base_items: list[dict[str, Any]], proposed_items: list[dict[str, Any]]) -> list[str]:
    return sorted(set(_by_name(proposed_items)) - set(_by_name(base_items)))


def _removed_names(base_items: list[dict[str, Any]], proposed_items: list[dict[str, Any]]) -> list[str]:
    return sorted(set(_by_name(base_items)) - set(_by_name(proposed_items)))


def _changed_named_items(base_items: list[dict[str, Any]], proposed_items: list[dict[str, Any]]) -> list[str]:
    base_by_name = _by_name(base_items)
    proposed_by_name = _by_name(proposed_items)
    return sorted(
        name
        for name in set(base_by_name) & set(proposed_by_name)
        if base_by_name[name] != proposed_by_name[name]
    )


def _by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("name")): item for item in items if item.get("name")}


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
