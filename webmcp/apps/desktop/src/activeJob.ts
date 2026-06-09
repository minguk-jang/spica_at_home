export type ActiveJobKind = "run" | "update" | "apply" | "evolution" | "creation";

export type ActiveJob = {
  kind: ActiveJobKind;
  paused: boolean;
  workflowName?: string;
  version?: number;
  proposalId?: number;
  startUrl?: string;
};

export function activeJobTitle(job: ActiveJob): string {
  switch (job.kind) {
    case "run":
      return withWorkflowVersion("Run", job);
    case "update":
      return withWorkflowVersion("Codex draft", job);
    case "apply":
      return job.proposalId ? `Apply proposal #${job.proposalId}` : "Apply proposal";
    case "evolution":
      return withWorkflowVersion("Eval & evolve", job);
    case "creation":
      return "Create workflow from browser task";
  }
}

export function activeJobControlLabel(job: ActiveJob): string {
  return job.paused ? "Resume job" : "Pause job";
}

export function activeJobStatusText(job: ActiveJob): string {
  return job.paused ? "Paused" : "Running";
}

function withWorkflowVersion(prefix: string, job: ActiveJob): string {
  const workflowName = job.workflowName ?? "workflow";
  const version = Number.isFinite(job.version) ? ` v${job.version}` : "";
  return `${prefix} for ${workflowName}${version}`;
}
