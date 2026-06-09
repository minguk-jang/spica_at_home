from __future__ import annotations

from typing import Any

from webworkflows.loader import WorkflowSkill
from webworkflows.storage import WorkflowSkillStore, dumps


class WorkflowSkillEvolver:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def record_update(
        self,
        *,
        skill: WorkflowSkill,
        run_id: int,
        update_type: str,
        reason: str,
        diff: dict[str, Any],
        approved_by: str | None = "system",
    ) -> int:
        with self.store.connect() as conn:
            latest = conn.execute(
                """
                select * from workflow_tool_versions
                where id = ?
                """,
                (skill.version_id,),
            ).fetchone()
            if not latest:
                raise KeyError(f"WebMCP workflow version not found: {skill.version_id}")

            next_version = int(latest["version"]) + 1
            body_md = latest["body_md"] + f"\n\nUpdate v{next_version}: {update_type} - {reason}"
            new_version_id = int(
                conn.execute(
                    """
                    insert into workflow_tool_versions
                      (skill_id, version, summary, input_schema_json, output_schema_json,
                       body_md, load_policy_json, created_from_run_id, status)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.id,
                        next_version,
                        f"{latest['summary']} Updated via {update_type}.",
                        latest["input_schema_json"],
                        latest["output_schema_json"],
                        body_md,
                        latest["load_policy_json"],
                        run_id,
                        "stable",
                    ),
                ).lastrowid
            )

            self._copy_arguments(conn, skill.version_id, new_version_id)
            self._copy_steps(conn, skill.version_id, new_version_id)
            self._copy_resources(conn, skill.version_id, new_version_id)

            if update_type == "new_example" and diff.get("example"):
                conn.execute(
                    """
                    insert into workflow_tool_examples
                      (skill_id, user_request, normalized_arguments_json, expected_output_summary, success_count)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        skill.id,
                        diff["example"],
                        dumps(diff.get("normalized_arguments", {})),
                        "Markdown stock report",
                        1,
                    ),
                )

            conn.execute(
                "update workflow_tools set latest_version_id = ?, updated_at = current_timestamp where id = ?",
                (new_version_id, skill.id),
            )
            conn.execute(
                """
                insert into workflow_tool_update_events
                  (skill_id, from_version_id, to_version_id, run_id, update_type, reason, diff_json, approved_by)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (skill.id, skill.version_id, new_version_id, run_id, update_type, reason, dumps(diff), approved_by),
            )
            return new_version_id

    def _copy_arguments(self, conn, from_version_id: int, to_version_id: int) -> None:
        rows = conn.execute(
            "select * from workflow_tool_arguments where version_id = ? order by order_index",
            (from_version_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                insert into workflow_tool_arguments
                  (version_id, name, description, type, required, default_value_json,
                   validation_json, examples_json, is_dynamic, order_index)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    to_version_id,
                    row["name"],
                    row["description"],
                    row["type"],
                    row["required"],
                    row["default_value_json"],
                    row["validation_json"],
                    row["examples_json"],
                    row["is_dynamic"],
                    row["order_index"],
                ),
            )

    def _copy_steps(self, conn, from_version_id: int, to_version_id: int) -> None:
        rows = conn.execute(
            "select * from workflow_tool_steps where version_id = ? order by order_index",
            (from_version_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                insert into workflow_tool_steps
                  (version_id, order_index, name, description, step_type, handler_ref,
                   action_json, argument_bindings_json, assertions_json,
                   fallback_policy_json, update_policy_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    to_version_id,
                    row["order_index"],
                    row["name"],
                    row["description"],
                    row["step_type"],
                    row["handler_ref"],
                    row["action_json"],
                    row["argument_bindings_json"],
                    row["assertions_json"],
                    row["fallback_policy_json"],
                    row["update_policy_json"],
                ),
            )

    def _copy_resources(self, conn, from_version_id: int, to_version_id: int) -> None:
        rows = conn.execute(
            "select * from workflow_tool_resources where version_id = ?",
            (from_version_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                insert into workflow_tool_resources
                  (version_id, resource_type, name, description, content_json, content_text, load_when_json)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    to_version_id,
                    row["resource_type"],
                    row["name"],
                    row["description"],
                    row["content_json"],
                    row["content_text"],
                    row["load_when_json"],
                ),
            )
