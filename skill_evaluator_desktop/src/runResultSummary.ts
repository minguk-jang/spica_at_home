type UnknownRecord = Record<string, unknown>;

export type ResultMetric = [label: string, value: string];

export type RunResultSummary = {
  title: string;
  status: string | null;
  runId: number | null;
  reportPath: string | null;
  outputUrl: string | null;
  metrics: ResultMetric[];
  outputPreview: string;
  rawJson: string;
};

export type RunEventLike = {
  type: string;
  workflowName?: string;
  version?: number;
  headed?: boolean;
  status?: string;
  stdout?: string;
  output?: unknown;
};

export type WorkflowRunLike = {
  id: number;
  status: string;
  output: unknown;
  reportPath: string | null;
};

const metricKeys = [
  "company_name",
  "ticker",
  "current_price",
  "current_price_formatted",
  "price",
  "market",
  "currency"
];

export function getRunEventResult(event: RunEventLike): RunResultSummary {
  const parsedOutput = asRecord(event.output) ?? parseJsonRecord(event.stdout);
  const nestedOutput = asRecord(parsedOutput?.output) ?? parsedOutput;
  const outputSummary = summarizeRunOutput(nestedOutput);

  return {
    title: event.version
      ? `${event.workflowName ?? "workflow"} v${event.version} ${event.headed ? "headed" : "headless"}`
      : event.type.replaceAll("-", " "),
    status: stringValue(parsedOutput?.status) ?? event.status ?? null,
    runId: numberValue(parsedOutput?.run_id),
    reportPath: stringValue(parsedOutput?.report_path) ?? stringValue(nestedOutput?.report_path),
    outputUrl: stringValue(parsedOutput?.url) ?? stringValue(nestedOutput?.url),
    metrics: outputSummary.metrics,
    outputPreview: outputSummary.outputPreview,
    rawJson: pretty(parsedOutput ?? event.stdout ?? "")
  };
}

export function getWorkflowRunResult(run: WorkflowRunLike): RunResultSummary {
  const outputSummary = summarizeRunOutput(run.output);
  return {
    title: `Run #${run.id}`,
    status: run.status,
    runId: run.id,
    reportPath: run.reportPath,
    outputUrl: stringValue(asRecord(run.output)?.url),
    metrics: outputSummary.metrics,
    outputPreview: outputSummary.outputPreview,
    rawJson: pretty(run.output)
  };
}

export function summarizeRunOutput(output: unknown): Pick<RunResultSummary, "metrics" | "outputPreview"> {
  const record = asRecord(output);
  if (!record) {
    return {
      metrics: [],
      outputPreview: pretty(output)
    };
  }

  const metrics = metricKeys.flatMap((key): ResultMetric[] => {
    const value = record[key];
    if (value === undefined || value === null || value === "") {
      return [];
    }
    return [[key, String(value)]];
  });

  return {
    metrics,
    outputPreview: stringValue(record.report_text) ?? pretty(record)
  };
}

function asRecord(value: unknown): UnknownRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as UnknownRecord;
}

function parseJsonRecord(value: unknown): UnknownRecord | null {
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }
  try {
    return asRecord(JSON.parse(value));
  } catch (_error) {
    return null;
  }
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pretty(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}
