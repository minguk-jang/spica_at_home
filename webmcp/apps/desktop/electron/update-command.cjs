const DEFAULT_CODEX_MODEL = "gpt-5.5";
const CREATE_WORKFLOW_MAX_ATTEMPTS = 10;

function buildPythonProposeArgs(payload, defaultOutputDir) {
  const args = [
    "-m",
    "webworkflows.cli",
    "propose-update",
    "--db",
    payload.dbPath,
    "--output-dir",
    payload.outputDir || defaultOutputDir || "outputs/desktop_runs",
    "--workflow-name",
    payload.workflowName,
    "--base-version",
    String(payload.baseVersion),
    "--instruction",
    payload.instruction,
    "--discovery-provider",
    payload.discoveryProvider || "none",
    "--synthesizer",
    "codex",
    "--synthesizer-model",
    payload.synthesizerModel || DEFAULT_CODEX_MODEL
  ];
  if (payload.companyName) {
    args.push("--company-name", payload.companyName);
  }
  if (payload.ticker) {
    args.push("--ticker", payload.ticker);
  }
  if (payload.headed) {
    args.push("--headed");
  }
  return args;
}

function buildPythonRunArgs(payload, version, defaultOutputDir) {
  const args = [
    "-m",
    "webworkflows.cli",
    "run-version",
    "--db",
    payload.dbPath,
    "--output-dir",
    payload.outputDir || defaultOutputDir || "outputs/desktop_runs",
    "--workflow-name",
    payload.workflowName,
    "--version",
    String(version),
    "--request",
    payload.request || `${payload.workflowName} run`
  ];

  if (payload.companyName) {
    args.push("--company-name", payload.companyName, "--live-page-text");
  }
  if (payload.ticker) {
    args.push("--ticker", payload.ticker);
  }
  if (payload.newsLimit !== undefined && payload.newsLimit !== null) {
    args.push("--news-limit", String(payload.newsLimit));
  }
  appendGenericArguments(args, payload);
  if (payload.headed) {
    args.push("--headed");
  }
  appendEvalAndEvolveArgs(args, payload.headed ? { ...payload, evalAndEvolve: true, evalBrowser: payload.evalBrowser || "chromium" } : payload);
  return args;
}

function buildPythonEvolveArgs(payload, defaultOutputDir) {
  const args = [
    "-m",
    "webworkflows.cli",
    "evolve",
    "--db",
    payload.dbPath,
    "--output-dir",
    payload.outputDir || defaultOutputDir || "outputs/desktop_runs",
    "--workflow-name",
    payload.workflowName,
    "--base-version",
    String(payload.baseVersion),
    "--request",
    payload.request || `${payload.workflowName} evolve`,
    "--max-attempts",
    String(payload.maxAttempts || 3),
    "--repair-synthesizer",
    payload.repairSynthesizer || "codex"
  ];

  if (payload.companyName) {
    args.push("--company-name", payload.companyName);
  }
  if (payload.ticker) {
    args.push("--ticker", payload.ticker);
  }
  if (payload.newsLimit !== undefined && payload.newsLimit !== null) {
    args.push("--news-limit", String(payload.newsLimit));
  }
  appendGenericArguments(args, payload);
  if (payload.repairWorkflowJsonFile) {
    args.push("--repair-workflow-json-file", payload.repairWorkflowJsonFile);
  }
  if (payload.synthesizerModel) {
    args.push("--synthesizer-model", payload.synthesizerModel);
  }
  if (payload.headed) {
    args.push("--headed");
  }
  args.push("--eval-and-evolve");
  appendEvalAndEvolveArgs(args, { ...payload, evalAndEvolve: true });
  return args;
}

function buildPythonCreateWorkflowArgs(payload, defaultOutputDir) {
  const args = [
    "-m",
    "webworkflows.cli",
    "create-workflow",
    "--db",
    payload.dbPath,
    "--output-dir",
    payload.outputDir || defaultOutputDir || "outputs/desktop_runs",
    "--start-url",
    payload.startUrl,
    "--task",
    payload.task,
    "--final-state",
    payload.finalState,
    "--synthesizer",
    "codex",
    "--synthesizer-model",
    payload.synthesizerModel || DEFAULT_CODEX_MODEL,
    "--max-attempts",
    String(CREATE_WORKFLOW_MAX_ATTEMPTS),
    "--repair-synthesizer",
    "codex"
  ];

  if (payload.companyName) {
    args.push("--company-name", payload.companyName);
  }
  if (payload.ticker) {
    args.push("--ticker", payload.ticker);
  }
  if (payload.newsLimit !== undefined && payload.newsLimit !== null) {
    args.push("--news-limit", String(payload.newsLimit));
  }
  appendGenericArguments(args, payload);
  if (payload.headed) {
    args.push("--headed");
  }
  args.push("--eval-and-evolve");
  appendEvalAndEvolveArgs(args, { ...payload, evalAndEvolve: true });
  return args;
}

function buildPythonExportJsToolArgs(payload, defaultOutputDir) {
  return [
    "-m",
    "webworkflows.cli",
    "export-js-tool",
    "--db",
    payload.dbPath,
    "--workflow-name",
    payload.workflowName,
    "--version",
    String(payload.version),
    "--output-dir",
    payload.outputDir || defaultOutputDir || "outputs/js_tools"
  ];
}

function buildPythonRunJsToolArgs(payload) {
  const args = [
    "-m",
    "webworkflows.cli",
    "run-js-tool",
    "--tool-dir",
    payload.toolDir
  ];
  appendArgumentPairs(args, payload.arguments);
  return args;
}

function buildPythonEvalJsToolArgs(payload) {
  const args = [
    "-m",
    "webworkflows.cli",
    "eval-js-tool",
    "--tool-dir",
    payload.toolDir
  ];
  appendArgumentPairs(args, payload.arguments);
  for (const key of payload.requiredOutput || []) {
    if (key) {
      args.push("--required-output", key);
    }
  }
  return args;
}

function appendEvalAndEvolveArgs(args, payload) {
  if (!payload.evalAndEvolve) {
    return;
  }
  if (!args.includes("--eval-and-evolve")) {
    args.push("--eval-and-evolve");
  }
  args.push("--vlm-evaluator", "codex");
  if (payload.evalBrowser) {
    args.push("--eval-browser", payload.evalBrowser);
  }
}

function appendGenericArguments(args, payload) {
  const extraArguments = payload.extraArguments && typeof payload.extraArguments === "object" ? payload.extraArguments : {};
  appendArgumentPairs(args, extraArguments);
}

function appendArgumentPairs(args, values) {
  const source = values && typeof values === "object" ? values : {};
  for (const [key, value] of Object.entries(source)) {
    if (!key || value === undefined || value === null || value === "") {
      continue;
    }
    args.push("--argument", `${key}=${formatGenericArgumentValue(value)}`);
  }
}

function formatGenericArgumentValue(value) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

module.exports = {
  DEFAULT_CODEX_MODEL,
  CREATE_WORKFLOW_MAX_ATTEMPTS,
  buildPythonCreateWorkflowArgs,
  buildPythonEvolveArgs,
  buildPythonEvalJsToolArgs,
  buildPythonExportJsToolArgs,
  buildPythonProposeArgs,
  buildPythonRunArgs,
  buildPythonRunJsToolArgs
};
