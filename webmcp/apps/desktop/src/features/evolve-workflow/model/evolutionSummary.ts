type UnknownRecord = Record<string, unknown>;

export type EvolutionArtifact = {
  label: string;
  path: string;
};

export type EvolutionSummary = {
  status: string;
  sessionId: string;
  attemptCount: string;
  versionLabel: string;
  finalRunId: string;
  latestAttemptStatus: string;
  latestFailedStep: string;
  latestDuration: string;
  artifacts: EvolutionArtifact[];
  attempts: EvolutionAttemptSummary[];
};

export type EvolutionAttemptSummary = {
  key: string;
  attemptIndex: string;
  version: string;
  status: string;
  duration: string;
  runId: string;
  steps: EvolutionStepSummary[];
};

export type EvolutionStepSummary = {
  key: string;
  name: string;
  type: string;
  status: string;
  duration: string;
  summary: string;
  problems: string[];
  suggestedUpdate: string;
  failureKind: string;
  expectedState: string;
  observedState: string;
  repairFocus: string;
  evidenceArtifacts: string[];
  source: "evaluation" | "execution";
};

export function summarizeEvolutionOutput(output: unknown): EvolutionSummary {
  const record = asRecord(output) ?? {};
  const attempts = Array.isArray(record.attempts) ? record.attempts.flatMap(asRecordOrEmpty) : [];
  const latestAttempt = attempts.at(-1) ?? {};
  const status = text(record.status) || "unknown";
  const baseVersion = text(record.base_version);
  const finalVersion = text(record.final_version);
  const currentVersion = text(record.current_version);

  return {
    status,
    sessionId: text(record.session_id) || "-",
    attemptCount: text(record.attempt_count) || text(attempts.length) || "0",
    versionLabel: versionLabel(baseVersion, finalVersion, currentVersion),
    finalRunId: text(record.final_run_id) || text(latestAttempt.run_id) || "-",
    latestAttemptStatus: text(latestAttempt.status) || "-",
    latestFailedStep: failedStepName(latestAttempt.failed_step),
    latestDuration: duration(latestAttempt.duration_ms),
    artifacts: uniqueArtifacts([
      artifact("수정 요청 파일", record.repair_request_path),
      artifact("수정 요청 파일", latestAttempt.repair_request_path),
      artifact("수정 결과 파일", latestAttempt.repair_response_path),
      artifact("리포트", latestAttempt.report_path)
    ]),
    attempts: attempts.map(summarizeAttempt)
  };
}

export function summarizeEvolutionJobStatus(jobResult: unknown): string {
  const job = asRecord(jobResult);
  const nestedStatus = text(asRecord(job?.output)?.status);
  return nestedStatus || text(job?.status) || "finished";
}

function versionLabel(baseVersion: string, finalVersion: string, currentVersion: string): string {
  if (baseVersion && finalVersion) {
    return `기준 v${baseVersion} -> 최종 v${finalVersion}`;
  }
  if (baseVersion && currentVersion) {
    return `기준 v${baseVersion} -> 현재 v${currentVersion}`;
  }
  if (baseVersion) {
    return `기준 v${baseVersion}`;
  }
  return "-";
}

function failedStepName(value: unknown): string {
  const record = asRecord(value);
  if (!record) {
    return "-";
  }
  return text(record.name) || text(record.step_name) || text(record.id) || "-";
}

function artifact(label: string, value: unknown): EvolutionArtifact | null {
  const path = text(value);
  return path ? { label, path } : null;
}

function summarizeAttempt(attempt: UnknownRecord, index: number): EvolutionAttemptSummary {
  return {
    key: text(attempt.attempt_id) || `${text(attempt.attempt_index) || index + 1}-${text(attempt.version)}`,
    attemptIndex: text(attempt.attempt_index) || String(index + 1),
    version: text(attempt.version) || "-",
    status: text(attempt.status) || "-",
    duration: duration(attempt.duration_ms),
    runId: text(attempt.run_id) || "-",
    steps: summarizeAttemptSteps(attempt)
  };
}

function summarizeAttemptSteps(attempt: UnknownRecord): EvolutionStepSummary[] {
  const evaluation = asRecord(attempt.evaluation);
  const evaluations = [
    ...arrayRecords(evaluation?.step_evaluations),
    ...arrayRecords(evaluation?.final_evaluation ? [evaluation.final_evaluation] : [])
  ];
  const evaluationByStep = new Map<string, UnknownRecord>();
  evaluations.forEach((item) => {
    const name = text(item.step_name);
    if (name) {
      evaluationByStep.set(name, item);
    }
  });

  const stepRuns = arrayRecords(attempt.step_runs);
  const seen = new Set<string>();
  const fromRuns = stepRuns.map((run, index) => {
    const name = text(run.step_name) || `step_${index + 1}`;
    seen.add(name);
    return stepSummary(name, run, evaluationByStep.get(name));
  });
  const evaluationOnly = evaluations
    .filter((item) => {
      const name = text(item.step_name);
      return name && !seen.has(name);
    })
    .map((item) => stepSummary(text(item.step_name), null, item));
  return [...fromRuns, ...evaluationOnly];
}

function stepSummary(
  name: string,
  run: UnknownRecord | null,
  evaluation: UnknownRecord | undefined
): EvolutionStepSummary {
  const rawProblems = arrayValues(evaluation?.problems).map(String);
  const rawArtifacts = arrayValues(evaluation?.evidence_artifacts).map(String);
  return {
    key: `${name}-${text(run?.id) || text(run?.step_id) || text(evaluation?.step_type)}`,
    name,
    type: text(evaluation?.step_type) || text(run?.step_type) || "-",
    status: normalizeStepStatus(text(evaluation?.status) || text(run?.status) || "-"),
    duration: duration(run?.duration_ms),
    summary: text(evaluation?.summary) || "워크플로우 step 실행 완료.",
    problems: rawProblems,
    suggestedUpdate: text(evaluation?.suggested_update),
    failureKind: text(evaluation?.failure_kind),
    expectedState: text(evaluation?.expected_state),
    observedState: text(evaluation?.observed_state),
    repairFocus: text(evaluation?.repair_focus),
    evidenceArtifacts: rawArtifacts,
    source: evaluation ? "evaluation" : "execution"
  };
}

function normalizeStepStatus(status: string): string {
  if (status === "succeeded") {
    return "passed";
  }
  return status;
}

function uniqueArtifacts(items: Array<EvolutionArtifact | null>): EvolutionArtifact[] {
  const seen = new Set<string>();
  return items.filter((item): item is EvolutionArtifact => {
    if (!item || seen.has(`${item.label}:${item.path}`)) {
      return false;
    }
    seen.add(`${item.label}:${item.path}`);
    return true;
  });
}

function asRecord(value: unknown): UnknownRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as UnknownRecord;
}

function asRecordOrEmpty(value: unknown): UnknownRecord[] {
  const record = asRecord(value);
  return record ? [record] : [];
}

function arrayRecords(value: unknown): UnknownRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap(asRecordOrEmpty);
}

function arrayValues(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return value;
  }
  return "";
}

function duration(value: unknown): string {
  const numberValue = typeof value === "number" && Number.isFinite(value) ? value : null;
  return numberValue === null ? "-" : `${numberValue} ms`;
}
