import type {
  CreateWorkflowPayload,
  WorkflowArgument,
  WorkflowExample,
  WorkflowRun,
  WorkflowStep,
  WorkflowUpdateProposal
} from "./vite-env";

export type StepCard = {
  id: number;
  label: string;
  name: string;
  description: string;
  type: string;
  handlerRef: string | null;
};

export type ArgumentExample = {
  id: string;
  label: string;
  description: string;
  values: {
    request: string;
    companyName: string;
    ticker: string;
    newsLimit: number;
    extraArguments: Record<string, unknown>;
  };
};

export type CreateWorkflowForm = {
  dbPath: string;
  repoRoot: string;
  outputDir: string;
  pythonPath?: string;
  startUrl: string;
  task: string;
  finalState: string;
  headed: boolean;
  synthesizerModel: string;
};

export type OperationControlState = {
  busy: boolean;
  pauseResumeVisible: boolean;
  pauseResumeAction: "pause" | "resume";
  pauseResumeLabel: string;
};

export const CREATE_WORKFLOW_MAX_ATTEMPTS = 10;
const INTERNAL_ARGUMENT_KEYS = ["page_text"];

export function buildStepCards(steps: WorkflowStep[]): StepCard[] {
  return [...steps]
    .sort((left, right) => left.orderIndex - right.orderIndex)
    .map((step, index) => ({
      id: step.id,
      label: `Step ${index + 1}`,
      name: step.name,
      description: step.description,
      type: step.stepType,
      handlerRef: step.handlerRef
    }));
}

export function buildArgumentExamples(examples: WorkflowExample[]): ArgumentExample[] {
  const seen = new Set<string>();
  const result: ArgumentExample[] = [];

  for (const example of examples) {
    const normalizedArguments = asRecord(example.normalizedArguments);
    const companyName = stringField(normalizedArguments, "company_name") ?? stringField(normalizedArguments, "companyName");
    const ticker = stringField(normalizedArguments, "ticker");
    const fingerprint = argumentExampleFingerprint(normalizedArguments, companyName, ticker);
    if (seen.has(fingerprint)) {
      continue;
    }
    seen.add(fingerprint);

    const newsLimit = numberField(normalizedArguments, "news_limit") ?? numberField(normalizedArguments, "newsLimit") ?? 3;
    result.push({
      id: String(example.id),
      label: companyName || example.userRequest,
      description: example.expectedOutputSummary || "저장된 실행 예시",
      values: {
        request: example.userRequest,
        companyName: companyName ?? "",
        ticker: ticker ?? "",
        newsLimit,
        extraArguments: extraArguments(normalizedArguments, [
          "company_name",
          "companyName",
          "ticker",
          "news_limit",
          "newsLimit",
          ...INTERNAL_ARGUMENT_KEYS
        ])
      }
    });

    if (result.length === 3) {
      break;
    }
  }

  return result;
}

export function argumentExampleMeta(example: ArgumentExample): string {
  const parts: string[] = [];
  if (example.values.ticker) {
    parts.push(example.values.ticker);
  }
  if (example.values.newsLimit !== 3 || example.values.ticker) {
    parts.push(`뉴스 ${example.values.newsLimit}`);
  }

  const extraParts = Object.entries(example.values.extraArguments)
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${formatArgumentValue(value)}`);

  return [...parts, ...extraParts].join(" · ") || "저장된 argument";
}

export function argumentDisplayRows(argumentsList: WorkflowArgument[]): Array<{
  id: number;
  name: string;
  description: string;
  type: string;
  required: string;
  dynamic: string;
  examples: string;
}> {
  return [...argumentsList]
    .sort((left, right) => left.orderIndex - right.orderIndex)
    .map((argument) => ({
      id: argument.id,
      name: argument.name,
      description: argument.description || "설명 없음",
      type: argument.valueType,
      required: argument.required ? "필수" : "선택",
      dynamic: argument.isDynamic ? "실행 시 입력" : "고정",
      examples: formatExamples(argument.examples)
    }));
}

export function findLatestDraftProposal(proposals: WorkflowUpdateProposal[]): WorkflowUpdateProposal | null {
  return proposals
    .filter((proposal) => proposal.status === "draft")
    .sort((left, right) => proposalTimestamp(right) - proposalTimestamp(left))[0] ?? null;
}

export function canCreateWorkflow(form: Pick<CreateWorkflowForm, "startUrl" | "task" | "finalState">): boolean {
  return [form.startUrl, form.task, form.finalState].every((value) => value.trim().length > 0);
}

export function buildCreateWorkflowPayload(form: CreateWorkflowForm): CreateWorkflowPayload {
  const payload: CreateWorkflowPayload = {
    dbPath: form.dbPath,
    repoRoot: form.repoRoot,
    outputDir: form.outputDir,
    pythonPath: form.pythonPath,
    startUrl: form.startUrl.trim(),
    task: form.task.trim(),
    finalState: form.finalState.trim(),
    maxAttempts: CREATE_WORKFLOW_MAX_ATTEMPTS,
    headed: form.headed,
    synthesizerModel: form.synthesizerModel,
    evalBrowser: "chromium"
  };
  return payload;
}

export function buildOperationControlState(input: { running: boolean; paused: boolean }): OperationControlState {
  return {
    busy: input.running && !input.paused,
    pauseResumeVisible: input.running,
    pauseResumeAction: input.paused ? "resume" : "pause",
    pauseResumeLabel: input.paused ? "Resume current job" : "Pause current job"
  };
}

export function storedRunDisplayStatus(
  run: Pick<WorkflowRun, "status" | "finishedAt">,
  activeJobRunning: boolean
): string {
  if (run.status === "running" && run.finishedAt === null && !activeJobRunning) {
    return "interrupted";
  }
  return run.status;
}

function proposalTimestamp(proposal: WorkflowUpdateProposal): number {
  const parsed = Date.parse(proposal.updatedAt || proposal.createdAt);
  return Number.isFinite(parsed) ? parsed : proposal.id;
}

function formatExamples(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "-";
  }
  return value.map((item) => String(item)).join(", ");
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function stringField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function numberField(record: Record<string, unknown>, key: string): number | null {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function extraArguments(record: Record<string, unknown>, knownKeys: string[]): Record<string, unknown> {
  const known = new Set(knownKeys);
  return Object.fromEntries(Object.entries(record).filter(([key]) => !known.has(key)));
}

function argumentExampleFingerprint(
  normalizedArguments: Record<string, unknown>,
  companyName: string | null,
  ticker: string | null
): string {
  if (companyName || ticker) {
    return `stock:${companyName ?? ""}:${ticker ?? ""}`;
  }
  return stableJson(normalizedArguments);
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function formatArgumentValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
