from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from webworkflows.storage import WorkflowSkillStore, loads


@dataclass(frozen=True)
class WorkflowArgument:
    id: int
    name: str
    description: str
    type: str
    required: bool
    default_value: Any
    validation: dict[str, Any]
    examples: list[Any]
    is_dynamic: bool


@dataclass(frozen=True)
class WorkflowStep:
    id: int
    name: str
    description: str
    step_type: str
    handler_ref: str | None
    action: dict[str, Any]
    argument_bindings: dict[str, Any]
    assertions: dict[str, Any]
    fallback_policy: dict[str, Any]
    update_policy: dict[str, Any]


@dataclass(frozen=True)
class WorkflowSkill:
    id: int
    version_id: int
    name: str
    description: str
    domain: str
    task_type: str
    version: int
    body_md: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    arguments: list[WorkflowArgument]
    steps: list[WorkflowStep]
    resources: dict[str, str]


class WorkflowSkillLoader:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def search(self, user_request: str, limit: int = 5) -> list[dict[str, Any]]:
        query = user_request.lower()
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                select
                    s.id, s.name, s.description, s.domain, s.task_type, s.status,
                    v.input_schema_json,
                    coalesce(group_concat(e.user_request, ' '), '') as examples
                from workflow_skills s
                join workflow_skill_versions v on v.id = s.latest_version_id
                left join workflow_skill_examples e on e.skill_id = s.id
                where s.status = 'stable'
                group by s.id
                """
            ).fetchall()

        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            haystack = " ".join(
                [
                    row["name"],
                    row["description"],
                    row["domain"],
                    row["task_type"],
                    row["examples"],
                ]
            ).lower()
            score = 0
            for token in _tokens(query):
                if token and token in haystack:
                    score += 2 if token in row["name"].lower() else 1
            if "주가" in user_request and row["task_type"] == "stock_report":
                score += 5
            if "네이버" in user_request and "naver" in row["domain"]:
                score += 3
            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            "id": row["id"],
                            "name": row["name"],
                            "description": row["description"],
                            "domain": row["domain"],
                            "task_type": row["task_type"],
                            "status": row["status"],
                            "input_schema": loads(row["input_schema_json"], {}),
                        },
                    )
                )

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def load_skill_by_name(self, name: str) -> WorkflowSkill:
        with self.store.connect() as conn:
            row = conn.execute("select id from workflow_skills where name = ?", (name,)).fetchone()
        if not row:
            raise KeyError(f"WebMCP workflow not found: {name}")
        return self.load_skill(int(row["id"]))

    def load_skill_version(self, name: str, version: int) -> WorkflowSkill:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                select id
                from workflow_skill_versions
                where skill_id = (select id from workflow_skills where name = ?)
                  and version = ?
                """,
                (name, version),
            ).fetchone()
        if not row:
            raise KeyError(f"WebMCP workflow version not found: {name} v{version}")
        return self._load_skill_version_id(int(row["id"]))

    def load_skill(self, skill_id: int) -> WorkflowSkill:
        with self.store.connect() as conn:
            skill_row = conn.execute(
                """
                select
                    s.id, s.name, s.description, s.domain, s.task_type,
                    v.id as version_id, v.version, v.body_md,
                    v.input_schema_json, v.output_schema_json
                from workflow_skills s
                join workflow_skill_versions v on v.id = s.latest_version_id
                where s.id = ?
                """,
                (skill_id,),
            ).fetchone()
            if not skill_row:
                raise KeyError(f"WebMCP workflow not found: {skill_id}")
        return self._hydrate_skill(skill_row)

    def _load_skill_version_id(self, version_id: int) -> WorkflowSkill:
        with self.store.connect() as conn:
            skill_row = conn.execute(
                """
                select
                    s.id, s.name, s.description, s.domain, s.task_type,
                    v.id as version_id, v.version, v.body_md,
                    v.input_schema_json, v.output_schema_json
                from workflow_skills s
                join workflow_skill_versions v on v.skill_id = s.id
                where v.id = ?
                """,
                (version_id,),
            ).fetchone()
            if not skill_row:
                raise KeyError(f"WebMCP workflow version not found: {version_id}")
        return self._hydrate_skill(skill_row)

    def _hydrate_skill(self, skill_row: Any) -> WorkflowSkill:
        with self.store.connect() as conn:
            argument_rows = conn.execute(
                """
                select * from workflow_skill_arguments
                where version_id = ?
                order by order_index
                """,
                (skill_row["version_id"],),
            ).fetchall()
            step_rows = conn.execute(
                """
                select * from workflow_skill_steps
                where version_id = ?
                order by order_index
                """,
                (skill_row["version_id"],),
            ).fetchall()
            resource_rows = conn.execute(
                """
                select name, content_text from workflow_skill_resources
                where version_id = ?
                """,
                (skill_row["version_id"],),
            ).fetchall()

        return WorkflowSkill(
            id=int(skill_row["id"]),
            version_id=int(skill_row["version_id"]),
            name=skill_row["name"],
            description=skill_row["description"],
            domain=skill_row["domain"],
            task_type=skill_row["task_type"],
            version=int(skill_row["version"]),
            body_md=skill_row["body_md"],
            input_schema=loads(skill_row["input_schema_json"], {}),
            output_schema=loads(skill_row["output_schema_json"], {}),
            arguments=[
                WorkflowArgument(
                    id=int(row["id"]),
                    name=row["name"],
                    description=row["description"],
                    type=row["type"],
                    required=bool(row["required"]),
                    default_value=loads(row["default_value_json"], None),
                    validation=loads(row["validation_json"], {}),
                    examples=loads(row["examples_json"], []),
                    is_dynamic=bool(row["is_dynamic"]),
                )
                for row in argument_rows
            ],
            steps=[
                WorkflowStep(
                    id=int(row["id"]),
                    name=row["name"],
                    description=row["description"],
                    step_type=row["step_type"],
                    handler_ref=row["handler_ref"],
                    action=loads(row["action_json"], {}),
                    argument_bindings=loads(row["argument_bindings_json"], {}),
                    assertions=loads(row["assertions_json"], {}),
                    fallback_policy=loads(row["fallback_policy_json"], {}),
                    update_policy=loads(row["update_policy_json"], {}),
                )
                for row in step_rows
            ],
            resources={row["name"]: row["content_text"] for row in resource_rows},
        )


def _tokens(text: str) -> list[str]:
    return [token.strip(".,:;!?()[]{}\"'") for token in text.split()]
