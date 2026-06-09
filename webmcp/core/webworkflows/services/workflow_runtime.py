from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from webworkflows.executor import WorkflowExecutor
from webworkflows.loader import WorkflowSkill, WorkflowSkillLoader
from webworkflows.storage import WorkflowSkillStore


@dataclass(frozen=True)
class PageTextEvidence:
    source: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, **self.details}


class WorkflowRuntime:
    def __init__(self, store: WorkflowSkillStore, *, output_dir: str | Path):
        self.store = store
        self.output_dir = Path(output_dir)

    def run_latest(
        self,
        *,
        user_request: str,
        arguments: dict[str, Any],
        page_text_evidence: PageTextEvidence | dict[str, Any],
    ) -> dict[str, Any]:
        loader = WorkflowSkillLoader(self.store)
        candidates = loader.search(user_request)
        if not candidates:
            raise ValueError(f"no WebMCP workflow matched request: {user_request}")
        skill = loader.load_skill(candidates[0]["id"])
        return self._run_skill(
            skill,
            user_request=user_request,
            arguments=arguments,
            page_text_evidence=page_text_evidence,
        )

    def run_version(
        self,
        *,
        workflow_name: str,
        version: int,
        user_request: str,
        arguments: dict[str, Any],
        page_text_evidence: PageTextEvidence | dict[str, Any],
    ) -> dict[str, Any]:
        skill = WorkflowSkillLoader(self.store).load_skill_version(workflow_name, version)
        return self._run_skill(
            skill,
            user_request=user_request,
            arguments=arguments,
            page_text_evidence=page_text_evidence,
        )

    def _run_skill(
        self,
        skill: WorkflowSkill,
        *,
        user_request: str,
        arguments: dict[str, Any],
        page_text_evidence: PageTextEvidence | dict[str, Any],
    ) -> dict[str, Any]:
        result = WorkflowExecutor(self.store, output_dir=self.output_dir).run(
            skill,
            user_request=user_request,
            arguments=arguments,
        )
        evidence = page_text_evidence.as_dict() if isinstance(page_text_evidence, PageTextEvidence) else page_text_evidence
        return {
            "workflow": skill.name,
            "workflow_version": skill.version,
            "run_id": result.run_id,
            "status": result.status,
            "llm_used": result.llm_used,
            "page_text_evidence": evidence,
            "output": result.output,
            "report_path": result.report_path,
        }
