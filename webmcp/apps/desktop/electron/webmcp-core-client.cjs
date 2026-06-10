const fs = require("fs");
const path = require("path");
const {
  buildPythonCreateWorkflowArgs,
  buildPythonEvolveArgs,
  buildPythonEvalJsToolArgs,
  buildPythonExportJsToolArgs,
  buildPythonProposeArgs,
  buildPythonRunArgs,
  buildPythonRunJsToolArgs,
  buildPythonSuggestStepGuideArgs
} = require("./update-command.cjs");
const {
  collectProcess: defaultCollectProcess,
  pauseCurrentProcess: defaultPauseCurrentProcess,
  resumeCurrentProcess: defaultResumeCurrentProcess
} = require("./process-runner.cjs");

function createWebmcpCoreClient(options) {
  const repoRoot = options.repoRoot;
  const defaultOutputDir = options.defaultOutputDir;
  const defaultPythonPath = options.defaultPythonPath;
  const collectProcess = options.collectProcess || defaultCollectProcess;
  const pauseProcess = options.pauseProcess || defaultPauseCurrentProcess;
  const resumeProcess = options.resumeProcess || defaultResumeCurrentProcess;
  const pythonExists = options.pythonExists || ((pythonPath) => fs.existsSync(pythonPath));
  const openExternal = options.openExternal || (async () => undefined);
  const now = options.now || (() => new Date().toISOString());
  const nowMs = options.nowMs || (() => Date.now());
  let nextJobId = options.nextJobId || 1;

  function pythonCommand(payload = {}) {
    if (payload.pythonPath) {
      return payload.pythonPath;
    }
    return pythonExists(defaultPythonPath) ? defaultPythonPath : "python3";
  }

  function emitRunEvent(sender, event) {
    if (sender && typeof sender.send === "function") {
      sender.send("webmcp:run-event", event);
    }
  }

  async function runPythonCli(args, cwd, pythonPath) {
    const startedAtMs = nowMs();
    const env = {
      ...process.env,
      PYTHONPATH: cwd
    };
    const result = await collectProcess(pythonCommand({ pythonPath }), args, { cwd, env });
    return { ...result, startedAtMs };
  }

  async function runVersion({ sender, payload, version, headed }) {
    if (!Number.isFinite(Number(version))) {
      throw new Error("version is required");
    }
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      workflowName: payload.workflowName,
      version,
      headed,
      startedAt
    };
    emitRunEvent(sender, { type: "job-started", ...jobBase });

    const args = buildPythonRunArgs({ ...payload, headed }, version, defaultOutputDir);
    const cwd = payload.repoRoot || repoRoot;
    const env = {
      ...process.env,
      PYTHONPATH: cwd,
      WEBWRIGHT_HEADLESS: headed ? "0" : "1"
    };
    const startedMs = nowMs();
    const result = await collectProcess(pythonCommand(payload), args, { cwd, env });
    const finishedAt = now();
    const durationMs = nowMs() - startedMs;
    const parsed = parseJson(result.stdout);
    const status = result.exitCode === 0 ? "succeeded" : "failed";
    if (headed && parsed && parsed.output && parsed.output.url) {
      await openExternal(parsed.output.url);
    }
    const job = {
      ...jobBase,
      status,
      finishedAt,
      durationMs,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
      output: parsed
    };
    emitRunEvent(sender, { type: "job-finished", ...job });
    return job;
  }

  async function runVersionQueue({ sender, payload, headed }) {
    const versions = Array.isArray(payload.versions) ? payload.versions : [];
    const results = [];
    emitRunEvent(sender, { type: "queue-started", total: versions.length });
    for (const version of versions) {
      const result = await runVersion({ sender, payload, version, headed });
      results.push(result);
    }
    emitRunEvent(sender, { type: "queue-finished", total: versions.length, results });
    return results;
  }

  async function proposeUpdate({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      workflowName: payload.workflowName,
      version: payload.baseVersion,
      startedAt
    };
    emitRunEvent(sender, { type: "update-proposal-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonProposeArgs(payload, defaultOutputDir),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "update-proposal-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function evolveWorkflow({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      workflowName: payload.workflowName,
      version: payload.baseVersion,
      startedAt
    };
    emitRunEvent(sender, { type: "evolution-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonEvolveArgs(payload, defaultOutputDir),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "evolution-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function createWorkflow({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      startUrl: payload.startUrl,
      startedAt
    };
    emitRunEvent(sender, { type: "creation-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonCreateWorkflowArgs(payload, defaultOutputDir),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "creation-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function suggestStepGuide({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      startUrl: payload.startUrl,
      startedAt
    };
    emitRunEvent(sender, { type: "step-guide-suggestion-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonSuggestStepGuideArgs(payload),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "step-guide-suggestion-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function exportJsTool({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      workflowName: payload.workflowName,
      version: payload.version,
      startedAt
    };
    emitRunEvent(sender, { type: "js-tool-export-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonExportJsToolArgs(payload, defaultJsToolOutputDir()),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "js-tool-export-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function runJsTool({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      toolDir: payload.toolDir,
      startedAt
    };
    emitRunEvent(sender, { type: "js-tool-run-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonRunJsToolArgs(payload),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "js-tool-run-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function evalJsTool({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      toolDir: payload.toolDir,
      startedAt
    };
    emitRunEvent(sender, { type: "js-tool-eval-started", ...jobBase });
    const result = await runPythonCli(
      buildPythonEvalJsToolArgs(payload),
      payload.repoRoot || repoRoot,
      payload.pythonPath
    );
    const job = buildCliJobResult({
      ...jobBase,
      type: "js-tool-eval-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  async function applyProposal({ sender, payload }) {
    const jobId = nextJobId++;
    const startedAt = now();
    const jobBase = {
      jobId,
      proposalId: payload.proposalId,
      startedAt
    };
    emitRunEvent(sender, { type: "update-apply-started", ...jobBase });
    const result = await runPythonCli(buildPythonApplyProposalArgs(payload), payload.repoRoot || repoRoot, payload.pythonPath);
    const job = buildCliJobResult({
      ...jobBase,
      type: "update-apply-finished",
      result,
      finishedAt: now(),
      nowMs
    });
    emitRunEvent(sender, job);
    return job;
  }

  function pauseActiveJob({ sender } = {}) {
    const result = pauseProcess();
    emitRunEvent(sender, { type: "job-paused", ...result, at: now() });
    return result;
  }

  function resumeActiveJob({ sender } = {}) {
    const result = resumeProcess();
    emitRunEvent(sender, { type: "job-resumed", ...result, at: now() });
    return result;
  }

  return {
    applyProposal,
    createWorkflow,
    evalJsTool,
    evolveWorkflow,
    exportJsTool,
    pauseActiveJob,
    proposeUpdate,
    resumeActiveJob,
    runJsTool,
    runVersion,
    runVersionQueue,
    suggestStepGuide,
    pythonCommand
  };

  function defaultJsToolOutputDir() {
    return path.join(defaultOutputDir || "outputs/desktop_runs", "js_tools");
  }
}

function buildCliJobResult({ type, result, finishedAt, nowMs, ...jobBase }) {
  return {
    type,
    ...jobBase,
    status: result.exitCode === 0 ? "succeeded" : "failed",
    finishedAt,
    durationMs: nowMs() - result.startedAtMs,
    stdout: result.stdout,
    stderr: result.stderr,
    exitCode: result.exitCode,
    output: parseJson(result.stdout)
  };
}

function buildPythonApplyProposalArgs(payload) {
  return [
    "-m",
    "webworkflows.cli",
    "apply-proposal",
    "--db",
    payload.dbPath,
    "--proposal-id",
    String(payload.proposalId),
    "--approved-by",
    payload.approvedBy || "desktop"
  ];
}

function parseJson(stdout) {
  try {
    return stdout ? JSON.parse(stdout) : null;
  } catch (_error) {
    return null;
  }
}

module.exports = {
  buildCliJobResult,
  buildPythonApplyProposalArgs,
  createWebmcpCoreClient,
  parseJson
};
