const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const { enrichHandlersWithSource } = require("./handler-source.cjs");
const { createProjectPaths } = require("./project-paths.cjs");
const { buildPythonProposeArgs, buildPythonRunArgs } = require("./update-command.cjs");

const appRoot = path.resolve(__dirname, "..");
const projectPaths = createProjectPaths(appRoot);
const repoRoot = projectPaths.coreRoot;
const defaultDbPath = projectPaths.defaultDbPath;
const defaultOutputDir = projectPaths.defaultOutputDir;
const defaultPythonPath = projectPaths.defaultPythonPath;

let mainWindow = null;
let queueRunning = false;
let nextJobId = 1;

function sidecarPath() {
  if (process.env.WEBMCP_SIDECAR_BIN) {
    return process.env.WEBMCP_SIDECAR_BIN;
  }
  const binary = process.platform === "win32" ? "webmcp-sidecar.exe" : "webmcp-sidecar";
  return path.join(appRoot, "rust", "webmcp-sidecar", "target", "debug", binary);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1000,
    minHeight: 680,
    title: "WebMCP Desktop",
    backgroundColor: "#f5f6f8",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(appRoot, "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.handle("webmcp:get-default-paths", async () => ({
  repoRoot,
  dbPath: defaultDbPath,
  outputDir: defaultOutputDir,
  pythonPath: fs.existsSync(defaultPythonPath) ? defaultPythonPath : "python3",
  sidecarPath: sidecarPath()
}));

ipcMain.handle("webmcp:list-workflows", async (_event, payload) => {
  return runSidecar(["list-workflows", "--db", payload.dbPath]);
});

ipcMain.handle("webmcp:workflow-detail", async (_event, payload) => {
  const detail = await runSidecar([
    "workflow-detail",
    "--db",
    payload.dbPath,
    "--workflow-id",
    String(payload.workflowId)
  ]);
  return {
    ...detail,
    handlers: enrichHandlersWithSource(payload.repoRoot || repoRoot, detail.handlers)
  };
});

ipcMain.handle("webmcp:run-versions", async (event, payload) => {
  if (queueRunning) {
    throw new Error("A run queue is already active.");
  }
  queueRunning = true;
  try {
    return await runVersionQueue(event.sender, payload, false);
  } finally {
    queueRunning = false;
  }
});

ipcMain.handle("webmcp:run-version", async (event, payload) => {
  if (queueRunning) {
    throw new Error("A run is already active.");
  }
  queueRunning = true;
  try {
    return await runSingleVersion(event.sender, payload, payload.version, Boolean(payload.headed));
  } finally {
    queueRunning = false;
  }
});

ipcMain.handle("webmcp:watch-version", async (event, payload) => {
  const result = await runSingleVersion(event.sender, payload, payload.version, true);
  return result;
});

ipcMain.handle("webmcp:propose-update", async (event, payload) => {
  if (queueRunning) {
    throw new Error("A run or update job is already active.");
  }
  queueRunning = true;
  try {
    return await runProposalJob(event.sender, payload);
  } finally {
    queueRunning = false;
  }
});

ipcMain.handle("webmcp:apply-proposal", async (event, payload) => {
  if (queueRunning) {
    throw new Error("A run or update job is already active.");
  }
  queueRunning = true;
  try {
    return await runApplyProposalJob(event.sender, payload);
  } finally {
    queueRunning = false;
  }
});

ipcMain.handle("webmcp:open-path", async (_event, targetPath) => {
  if (!targetPath || typeof targetPath !== "string") {
    throw new Error("path is required");
  }
  if (/^https?:\/\//i.test(targetPath)) {
    return shell.openExternal(targetPath);
  }
  return shell.openPath(targetPath);
});

async function runSidecar(args) {
  const bin = sidecarPath();
  if (!fs.existsSync(bin)) {
    throw new Error(`Rust sidecar is missing. Run npm run sidecar:build. Expected: ${bin}`);
  }
  const result = await collectProcess(bin, args, { cwd: appRoot });
  if (result.exitCode !== 0) {
    throw new Error(result.stderr || `sidecar exited with ${result.exitCode}`);
  }
  return JSON.parse(result.stdout || "null");
}

async function runVersionQueue(sender, payload, headed) {
  const versions = Array.isArray(payload.versions) ? payload.versions : [];
  const results = [];
  emitRunEvent(sender, { type: "queue-started", total: versions.length });

  for (const version of versions) {
    const result = await runSingleVersion(sender, payload, version, headed);
    results.push(result);
  }

  emitRunEvent(sender, { type: "queue-finished", total: versions.length, results });
  return results;
}

async function runSingleVersion(sender, payload, version, headed) {
  if (!Number.isFinite(Number(version))) {
    throw new Error("version is required");
  }
  const jobId = nextJobId++;
  const startedAt = new Date().toISOString();
  const jobBase = {
    jobId,
    workflowName: payload.workflowName,
    version,
    headed,
    startedAt
  };
  emitRunEvent(sender, { type: "job-started", ...jobBase });

  const args = buildPythonRunArgs({ ...payload, headed }, version, defaultOutputDir);
  const env = {
    ...process.env,
    PYTHONPATH: payload.repoRoot || repoRoot,
    WEBWRIGHT_HEADLESS: headed ? "0" : "1"
  };
  const startedMs = Date.now();
  const result = await collectProcess(pythonCommand(payload), args, {
    cwd: payload.repoRoot || repoRoot,
    env
  });
  const finishedAt = new Date().toISOString();
  const durationMs = Date.now() - startedMs;

  let parsed = null;
  try {
    parsed = result.stdout ? JSON.parse(result.stdout) : null;
  } catch (_error) {
    parsed = null;
  }

  const status = result.exitCode === 0 ? "succeeded" : "failed";
  if (headed && parsed && parsed.output && parsed.output.url) {
    await shell.openExternal(parsed.output.url);
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

async function runProposalJob(sender, payload) {
  const jobId = nextJobId++;
  const startedAt = new Date().toISOString();
  const jobBase = {
    jobId,
    workflowName: payload.workflowName,
    version: payload.baseVersion,
    startedAt
  };
  emitRunEvent(sender, { type: "update-proposal-started", ...jobBase });
  const args = buildPythonProposeArgs(payload, defaultOutputDir);
  const result = await runPythonCli(args, payload.repoRoot || repoRoot, payload.pythonPath);
  const finishedAt = new Date().toISOString();
  const job = buildCliJobResult({
    ...jobBase,
    type: "update-proposal-finished",
    result,
    finishedAt,
    startedAtMs: result.startedAtMs
  });
  emitRunEvent(sender, job);
  return job;
}

async function runApplyProposalJob(sender, payload) {
  const jobId = nextJobId++;
  const startedAt = new Date().toISOString();
  const jobBase = {
    jobId,
    proposalId: payload.proposalId,
    startedAt
  };
  emitRunEvent(sender, { type: "update-apply-started", ...jobBase });
  const result = await runPythonCli(buildPythonApplyProposalArgs(payload), payload.repoRoot || repoRoot, payload.pythonPath);
  const finishedAt = new Date().toISOString();
  const job = buildCliJobResult({
    ...jobBase,
    type: "update-apply-finished",
    result,
    finishedAt,
    startedAtMs: result.startedAtMs
  });
  emitRunEvent(sender, job);
  return job;
}

async function runPythonCli(args, cwd, pythonPath) {
  const env = {
    ...process.env,
    PYTHONPATH: cwd
  };
  const startedAtMs = Date.now();
  const result = await collectProcess(pythonCommand({ pythonPath }), args, { cwd, env });
  return { ...result, startedAtMs };
}

function buildCliJobResult({ type, result, finishedAt, startedAtMs, ...jobBase }) {
  let parsed = null;
  try {
    parsed = result.stdout ? JSON.parse(result.stdout) : null;
  } catch (_error) {
    parsed = null;
  }
  return {
    type,
    ...jobBase,
    status: result.exitCode === 0 ? "succeeded" : "failed",
    finishedAt,
    durationMs: Date.now() - startedAtMs,
    stdout: result.stdout,
    stderr: result.stderr,
    exitCode: result.exitCode,
    output: parsed
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

function pythonCommand(payload = {}) {
  if (payload.pythonPath) {
    return payload.pythonPath;
  }
  return fs.existsSync(defaultPythonPath) ? defaultPythonPath : "python3";
}

function emitRunEvent(sender, event) {
  sender.send("webmcp:run-event", event);
}

function collectProcess(command, args, options) {
  return new Promise((resolve) => {
    const child = spawn(command, args, options);
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolve({ stdout, stderr: stderr || error.message, exitCode: 1 });
    });
    child.on("close", (exitCode) => {
      resolve({ stdout: stdout.trim(), stderr: stderr.trim(), exitCode });
    });
  });
}
