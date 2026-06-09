/// <reference types="vite/client" />

export type WorkflowCard = {
  id: number;
  name: string;
  slug: string;
  description: string;
  domain: string;
  taskType: string;
  status: string;
  latestVersion: number;
  versionCount: number;
  stepCount: number;
  runCount: number;
  updateCount: number;
  lastRunStatus: string | null;
  lastRunDurationMs: number | null;
  lastRunAt: string | null;
  updatedAt: string;
};

export type WorkflowVersion = {
  id: number;
  version: number;
  summary: string;
  bodyMd: string;
  inputSchema: unknown;
  outputSchema: unknown;
  status: string;
  createdFromRunId: number | null;
  createdAt: string;
};

export type WorkflowArgument = {
  id: number;
  versionId: number;
  name: string;
  description: string;
  valueType: string;
  required: boolean;
  defaultValue: unknown;
  validation: unknown;
  examples: unknown;
  isDynamic: boolean;
  orderIndex: number;
};

export type WorkflowStep = {
  id: number;
  versionId: number;
  orderIndex: number;
  name: string;
  description: string;
  stepType: string;
  handlerRef: string | null;
  action: unknown;
  argumentBindings: unknown;
  assertions: unknown;
  fallbackPolicy: unknown;
  updatePolicy: unknown;
};

export type WorkflowResource = {
  id: number;
  versionId: number;
  resourceType: string;
  name: string;
  description: string;
  contentJson: unknown;
  contentText: string;
  loadWhen: unknown;
};

export type WorkflowHandler = {
  id: number;
  name: string;
  description: string;
  module: string;
  function: string;
  inputSchema: unknown;
  outputSchema: unknown;
  allowedDomains: unknown;
  sourcePath?: string;
  sourceText?: string;
};

export type WorkflowRun = {
  id: number;
  versionId: number;
  userRequest: string;
  input: unknown;
  status: string;
  llmUsed: boolean;
  startedAt: string;
  finishedAt: string | null;
  durationMs: number | null;
  output: unknown;
  reportPath: string | null;
};

export type StepRun = {
  id: number;
  runId: number;
  stepId: number;
  status: string;
  input: unknown;
  output: unknown;
  evidence: unknown;
  error: unknown;
  startedAt: string;
  finishedAt: string | null;
  durationMs: number | null;
};

export type UpdateEvent = {
  id: number;
  fromVersionId: number | null;
  toVersionId: number | null;
  runId: number | null;
  updateType: string;
  reason: string;
  diff: unknown;
  approvedBy: string | null;
  createdAt: string;
};

export type WorkflowUpdateProposal = {
  id: number;
  skillId: number;
  baseVersionId: number;
  proposedVersion: number;
  instruction: string;
  discoveryProvider: string;
  synthesizerProvider: string;
  synthesizerModel: string;
  status: string;
  proposedWorkflow: unknown;
  diff: unknown;
  evidence: unknown;
  synthesisDurationMs: number | null;
  error: unknown;
  appliedVersionId: number | null;
  approvedBy: string | null;
  createdAt: string;
  updatedAt: string;
};

export type WorkflowExample = {
  id: number;
  skillId: number;
  userRequest: string;
  normalizedArguments: unknown;
  expectedOutputSummary: string;
  successCount: number;
  lastUsedAt: string | null;
};

export type WorkflowDetail = {
  workflow: WorkflowCard;
  versions: WorkflowVersion[];
  arguments: WorkflowArgument[];
  steps: WorkflowStep[];
  resources: WorkflowResource[];
  handlers: WorkflowHandler[];
  runs: WorkflowRun[];
  stepRuns: StepRun[];
  updateEvents: UpdateEvent[];
  examples: WorkflowExample[];
  proposals: WorkflowUpdateProposal[];
};

export type PageAnalysisMemory = {
  id: number;
  urlKey: string;
  canonicalUrl: string;
  originalUrl: string;
  title: string | null;
  frameworkHints: unknown;
  frameHints: unknown;
  locatorHints: unknown;
  analysis: unknown;
  evidence: unknown;
  source: string;
  observationCount: number;
  createdAt: string;
  updatedAt: string;
  lastSeenAt: string;
};

export type WorkflowKnowledgeMemory = {
  id: number;
  category: string;
  summary: string;
  content: unknown;
  source: string;
  confidence: number;
  tags: unknown;
  createdAt: string;
};

export type MemoryOverview = {
  pageAnalyses: PageAnalysisMemory[];
  knowledgeEntries: WorkflowKnowledgeMemory[];
  pageAnalysisCount: number;
  knowledgeEntryCount: number;
};

export type DefaultPaths = {
  repoRoot: string;
  dbPath: string;
  outputDir: string;
  pythonPath: string;
  sidecarPath: string;
};

export type RunPayload = {
  dbPath: string;
  repoRoot: string;
  outputDir: string;
  pythonPath?: string;
  workflowName: string;
  versions?: number[];
  version?: number;
  headed?: boolean;
  request: string;
  companyName?: string;
  ticker?: string;
  newsLimit?: number;
  extraArguments?: Record<string, unknown>;
  evalAndEvolve?: boolean;
  vlmEvaluator?: "codex";
  evalBrowser?: "chromium" | "firefox" | "webkit";
};

export type UpdateProposalPayload = {
  dbPath: string;
  repoRoot: string;
  outputDir: string;
  pythonPath?: string;
  workflowName: string;
  baseVersion: number;
  instruction: string;
  companyName?: string;
  ticker?: string;
  discoveryProvider: "none" | "static" | "webwright";
  synthesizerModel: string;
  workflowJsonFile?: string;
  headed?: boolean;
};

export type EvolveWorkflowPayload = {
  dbPath: string;
  repoRoot: string;
  outputDir: string;
  pythonPath?: string;
  workflowName: string;
  baseVersion: number;
  request: string;
  companyName?: string;
  ticker?: string;
  newsLimit?: number;
  extraArguments?: Record<string, unknown>;
  maxAttempts?: number;
  repairSynthesizer?: "agent-json" | "fake-copy" | "codex";
  repairWorkflowJsonFile?: string;
  synthesizerModel?: string;
  headed?: boolean;
  vlmEvaluator?: "codex";
  evalBrowser?: "chromium" | "firefox" | "webkit";
};

export type CreateWorkflowPayload = {
  dbPath: string;
  repoRoot: string;
  outputDir: string;
  pythonPath?: string;
  startUrl: string;
  task: string;
  finalState: string;
  maxAttempts?: number;
  headed?: boolean;
  synthesizerModel?: string;
  evalBrowser?: "chromium" | "firefox" | "webkit";
};

export type ApplyProposalPayload = {
  dbPath: string;
  repoRoot: string;
  pythonPath?: string;
  proposalId: number;
  approvedBy: string;
};

export type RunEvent = {
  type: string;
  jobId?: number;
  proposalId?: number;
  workflowName?: string;
  version?: number;
  headed?: boolean;
  status?: string;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  total?: number;
  results?: unknown[];
  output?: unknown;
};

declare global {
  interface Window {
    webmcp?: {
      getDefaultPaths: () => Promise<DefaultPaths>;
      listWorkflows: (dbPath: string) => Promise<WorkflowCard[]>;
      getWorkflowDetail: (dbPath: string, workflowId: number, repoRoot?: string) => Promise<WorkflowDetail>;
      getMemoryOverview: (dbPath: string) => Promise<MemoryOverview>;
      runVersion: (payload: RunPayload) => Promise<unknown>;
      runVersions: (payload: RunPayload) => Promise<unknown[]>;
      watchVersion: (payload: RunPayload) => Promise<unknown>;
      evolveWorkflow: (payload: EvolveWorkflowPayload) => Promise<unknown>;
      createWorkflow: (payload: CreateWorkflowPayload) => Promise<unknown>;
      pauseCurrentJob: () => Promise<unknown>;
      resumeCurrentJob: () => Promise<unknown>;
      proposeUpdate: (payload: UpdateProposalPayload) => Promise<unknown>;
      applyProposal: (payload: ApplyProposalPayload) => Promise<unknown>;
      openPath: (targetPath: string) => Promise<string>;
      onRunEvent: (listener: (event: RunEvent) => void) => () => void;
    };
  }
}
