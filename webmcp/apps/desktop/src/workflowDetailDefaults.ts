import type { WorkflowDetail, WorkflowExample, WorkflowHandler, WorkflowUpdateProposal } from "./vite-env";

type LegacyWorkflowDetail = Omit<WorkflowDetail, "handlers" | "examples" | "proposals"> & {
  handlers?: WorkflowHandler[];
  examples?: WorkflowExample[];
  proposals?: WorkflowUpdateProposal[];
};

export function normalizeWorkflowDetail(detail: LegacyWorkflowDetail): WorkflowDetail {
  return {
    ...detail,
    handlers: Array.isArray(detail.handlers) ? detail.handlers : [],
    examples: Array.isArray(detail.examples) ? detail.examples : [],
    proposals: Array.isArray(detail.proposals) ? detail.proposals : []
  };
}
