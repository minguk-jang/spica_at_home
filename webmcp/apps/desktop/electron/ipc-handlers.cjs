const { enrichHandlersWithSource } = require("./handler-source.cjs");

function registerWebmcpIpcHandlers({
  ipcMain,
  paths,
  sidecarPath,
  runSidecar,
  coreClient,
  openExternal,
  openPath,
  pythonExists
}) {
  const repoRoot = paths.repoRoot;
  const defaultDbPath = paths.defaultDbPath;
  const defaultOutputDir = paths.defaultOutputDir;
  const defaultPythonPath = paths.defaultPythonPath;
  let queueRunning = false;

  ipcMain.handle("webmcp:get-default-paths", async () => ({
    repoRoot,
    dbPath: defaultDbPath,
    outputDir: defaultOutputDir,
    pythonPath: pythonExists(defaultPythonPath) ? defaultPythonPath : "python3",
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

  ipcMain.handle("webmcp:memory-overview", async (_event, payload) => {
    return runSidecar(["memory-overview", "--db", payload.dbPath]);
  });

  ipcMain.handle("webmcp:run-versions", async (event, payload) => {
    return withQueueLock("A run queue is already active.", async () => {
      return coreClient.runVersionQueue({ sender: event.sender, payload, headed: false });
    });
  });

  ipcMain.handle("webmcp:run-version", async (event, payload) => {
    return withQueueLock("A run is already active.", async () => {
      return coreClient.runVersion({
        sender: event.sender,
        payload,
        version: payload.version,
        headed: Boolean(payload.headed)
      });
    });
  });

  ipcMain.handle("webmcp:watch-version", async (event, payload) => {
    return withQueueLock("A run is already active.", async () => {
      return coreClient.runVersion({
        sender: event.sender,
        payload,
        version: payload.version,
        headed: true
      });
    });
  });

  ipcMain.handle("webmcp:evolve-workflow", async (event, payload) => {
    return withQueueLock("A run or evolution job is already active.", async () => {
      return coreClient.evolveWorkflow({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:create-workflow", async (event, payload) => {
    return withQueueLock("A run, creation, or evolution job is already active.", async () => {
      return coreClient.createWorkflow({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:export-js-tool", async (event, payload) => {
    return withQueueLock("A run or JavaScript tool job is already active.", async () => {
      return coreClient.exportJsTool({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:run-js-tool", async (event, payload) => {
    return withQueueLock("A run or JavaScript tool job is already active.", async () => {
      return coreClient.runJsTool({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:eval-js-tool", async (event, payload) => {
    return withQueueLock("A run or JavaScript tool job is already active.", async () => {
      return coreClient.evalJsTool({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:pause-current-job", async (event) => {
    return coreClient.pauseActiveJob({ sender: event.sender });
  });

  ipcMain.handle("webmcp:resume-current-job", async (event) => {
    return coreClient.resumeActiveJob({ sender: event.sender });
  });

  ipcMain.handle("webmcp:propose-update", async (event, payload) => {
    return withQueueLock("A run or update job is already active.", async () => {
      return coreClient.proposeUpdate({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:apply-proposal", async (event, payload) => {
    return withQueueLock("A run or update job is already active.", async () => {
      return coreClient.applyProposal({ sender: event.sender, payload });
    });
  });

  ipcMain.handle("webmcp:open-path", async (_event, targetPath) => {
    if (!targetPath || typeof targetPath !== "string") {
      throw new Error("path is required");
    }
    if (/^https?:\/\//i.test(targetPath)) {
      return openExternal(targetPath);
    }
    return openPath(targetPath);
  });

  async function withQueueLock(message, callback) {
    if (queueRunning) {
      throw new Error(message);
    }
    queueRunning = true;
    try {
      return await callback();
    } finally {
      queueRunning = false;
    }
  }
}

function createSidecarRunner({ appRoot, sidecarPath, sidecarExists, collectProcess }) {
  return async function runSidecar(args) {
    const bin = sidecarPath();
    if (!sidecarExists(bin)) {
      throw new Error(`Rust sidecar is missing. Run npm run sidecar:build. Expected: ${bin}`);
    }
    const result = await collectProcess(bin, args, { cwd: appRoot, pausable: false });
    if (result.exitCode !== 0) {
      throw new Error(result.stderr || `sidecar exited with ${result.exitCode}`);
    }
    return JSON.parse(result.stdout || "null");
  };
}

module.exports = {
  createSidecarRunner,
  registerWebmcpIpcHandlers
};
