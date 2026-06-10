import React from "react";
import { ChevronRight } from "lucide-react";

import { duration } from "../../../shared/lib/format";
import { Badge, JsonBlock, StatusPill } from "../../../shared/ui";
import type { WorkflowUpdateProposal } from "../../../vite-env";

export function ProposalList({
  proposals,
  running,
  onApply
}: {
  proposals: WorkflowUpdateProposal[];
  running: boolean;
  onApply: (proposalId: number) => void;
}): React.ReactElement {
  if (proposals.length === 0) {
    return <div className="emptyState">No update proposals yet</div>;
  }
  return (
    <div className="proposalList">
      {proposals.map((proposal) => (
        <article className="proposalRow" key={proposal.id}>
          <div className="proposalHeader">
            <div>
              <h3>Proposal #{proposal.id}</h3>
              <p>{proposal.instruction}</p>
              <span className="metaRow">
                <StatusPill status={proposal.status} />
                <Badge>v{proposal.proposedVersion}</Badge>
                <Badge>{proposal.synthesizerProvider}</Badge>
                <Badge>{duration(proposal.synthesisDurationMs)}</Badge>
                {proposal.appliedVersionId ? <Badge>applied {proposal.appliedVersionId}</Badge> : null}
              </span>
            </div>
            {proposal.status === "draft" ? (
              <button
                className="iconButton success"
                aria-label={`Apply proposal ${proposal.id}`}
                title={`Apply proposal ${proposal.id}`}
                disabled={running}
                onClick={() => onApply(proposal.id)}
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            ) : null}
          </div>
          <div className="proposalGrid">
            <div>
              <h4>Diff</h4>
              <JsonBlock value={proposal.diff} compact />
            </div>
            <div>
              <h4>Evidence</h4>
              <JsonBlock value={proposal.evidence} compact />
            </div>
          </div>
          <details className="rawOutput">
            <summary>Proposed workflow JSON</summary>
            <JsonBlock value={proposal.proposedWorkflow} />
          </details>
        </article>
      ))}
    </div>
  );
}
