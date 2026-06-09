from __future__ import annotations

from pathlib import Path
from typing import Any

from webworkflows.loader import WorkflowSkillLoader
from webworkflows.providers.synthesis_provider import create_synthesis_backend
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import DEFAULT_CODEX_SYNTHESIS_MODEL
from webworkflows.update_proposal import WorkflowUpdateProposalService, workflow_json_from_skill


class WorkflowUpdateRuntime:
    def __init__(self, store: WorkflowSkillStore, *, cwd: str | Path | None = None):
        self.store = store
        self.cwd = Path(cwd) if cwd else Path(__file__).resolve().parents[2]

    def propose_update(
        self,
        *,
        workflow_name: str,
        base_version: int,
        instruction: str,
        page_text: str = "",
        discovery_provider: str = "none",
        synthesizer: str = "codex",
        workflow_json_file: str | Path | None = None,
        synthesizer_model: str = DEFAULT_CODEX_SYNTHESIS_MODEL,
    ) -> dict[str, Any]:
        loader = WorkflowSkillLoader(self.store)
        base_skill = loader.load_skill_version(workflow_name, base_version)
        base_workflow = workflow_json_from_skill(self.store, base_skill)
        backend = create_synthesis_backend(
            synthesizer,
            workflow_json_file=workflow_json_file,
            base_workflow_json=base_workflow,
            cwd=self.cwd,
        )
        result = WorkflowUpdateProposalService(
            self.store,
            backend=backend,
            model=synthesizer_model,
            cwd=self.cwd,
        ).propose(
            workflow_name=workflow_name,
            base_version=base_version,
            instruction=instruction,
            page_text=page_text,
            discovery_provider=discovery_provider,
        )
        return {
            "proposal_id": result.proposal_id,
            "workflow": result.workflow_name,
            "base_version": result.base_version,
            "proposed_version": result.proposed_version,
            "status": result.status,
            "synthesizer": synthesizer,
            "synthesizer_model": synthesizer_model,
            "synthesis_duration_ms": result.synthesis_duration_ms,
            "diff": result.diff,
            "proposed_workflow_json": result.proposed_workflow_json,
        }

    def apply_proposal(self, *, proposal_id: int, approved_by: str = "desktop") -> dict[str, Any]:
        result = WorkflowUpdateProposalService(self.store).apply(
            proposal_id=proposal_id,
            approved_by=approved_by,
        )
        return {
            "proposal_id": result.proposal_id,
            "workflow": result.workflow_name,
            "status": result.status,
            "applied_version": result.applied_version,
            "applied_version_id": result.applied_version_id,
        }
