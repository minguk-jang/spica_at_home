const DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark";

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
    payload.request || `${payload.workflowName} run`,
    "--company-name",
    payload.companyName || "삼성전자",
    "--live-page-text"
  ];

  if (payload.ticker) {
    args.push("--ticker", payload.ticker);
  }
  if (payload.newsLimit !== undefined && payload.newsLimit !== null) {
    args.push("--news-limit", String(payload.newsLimit));
  }
  if (payload.headed) {
    args.push("--headed");
  }
  return args;
}

module.exports = {
  DEFAULT_CODEX_MODEL,
  buildPythonProposeArgs,
  buildPythonRunArgs
};
