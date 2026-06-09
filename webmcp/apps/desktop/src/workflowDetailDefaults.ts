import type { WorkflowDetail, WorkflowHandler, WorkflowUpdateProposal } from "./vite-env";

type LegacyWorkflowDetail = Omit<WorkflowDetail, "handlers" | "proposals"> & {
  handlers?: WorkflowHandler[];
  proposals?: WorkflowUpdateProposal[];
};

export function normalizeWorkflowDetail(detail: LegacyWorkflowDetail): WorkflowDetail {
  return {
    ...detail,
    handlers: Array.isArray(detail.handlers) ? detail.handlers : [],
    proposals: Array.isArray(detail.proposals) ? detail.proposals : []
  };
}
