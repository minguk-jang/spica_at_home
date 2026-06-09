from __future__ import annotations

from typing import Any

from webworkflows.storage import WorkflowSkillStore, dumps, loads


INTERNAL_ARGUMENT_NAMES = {"page_text", "final_state"}


def record_successful_argument_example(
    store: WorkflowSkillStore,
    *,
    skill_id: int,
    version_id: int,
    user_request: str,
    expected_output_summary: str,
    arguments: dict[str, Any],
) -> None:
    with store.connect() as conn:
        rows = conn.execute(
            """
            select id, name, examples_json
            from workflow_tool_arguments
            where version_id = ?
            order by order_index
            """,
            (version_id,),
        ).fetchall()

        normalized_arguments: dict[str, Any] = {}
        for row in rows:
            name = row["name"]
            if name in INTERNAL_ARGUMENT_NAMES:
                continue
            value = arguments.get(name)
            if value in (None, ""):
                continue
            normalized_arguments[name] = value

            merged_examples = _merge_argument_examples(loads(row["examples_json"], []), value)
            conn.execute(
                "update workflow_tool_arguments set examples_json = ? where id = ?",
                (dumps(merged_examples), row["id"]),
            )

        if not normalized_arguments:
            return

        normalized_json = dumps(normalized_arguments)
        existing = conn.execute(
            """
            select id
            from workflow_tool_examples
            where skill_id = ? and normalized_arguments_json = ?
            """,
            (skill_id, normalized_json),
        ).fetchone()
        if existing:
            return

        conn.execute(
            """
            insert into workflow_tool_examples
              (skill_id, user_request, normalized_arguments_json, expected_output_summary, success_count, last_used_at)
            values (?, ?, ?, ?, ?, current_timestamp)
            """,
            (skill_id, user_request, normalized_json, expected_output_summary, 1),
        )


def _merge_argument_examples(existing: Any, value: Any) -> list[Any]:
    examples = existing if isinstance(existing, list) else []
    if isinstance(value, (dict, list)) or value in (None, ""):
        return examples
    merged = [value]
    for example in examples:
        if example == value:
            continue
        merged.append(example)
        if len(merged) == 3:
            break
    return merged
