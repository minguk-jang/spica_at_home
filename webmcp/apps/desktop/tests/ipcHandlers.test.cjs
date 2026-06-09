const assert = require("node:assert/strict");
const test = require("node:test");

const { createSidecarRunner, registerWebmcpIpcHandlers } = require("../electron/ipc-handlers.cjs");

test("registers stable WebMCP IPC channels", () => {
  const channels = [];
  const ipcMain = {
    handle: (channel, handler) => {
      channels.push(channel);
      assert.equal(typeof handler, "function");
    }
  };

  registerWebmcpIpcHandlers({
    ipcMain,
    paths: {
      repoRoot: "/repo/webmcp/core",
      defaultDbPath: "/repo/webmcp/core/outputs/workflows.sqlite",
      defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
      defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python"
    },
    sidecarPath: () => "/repo/webmcp/apps/desktop/rust/webmcp-sidecar/target/debug/webmcp-sidecar",
    sidecarExists: () => true,
    runSidecar: async () => ({}),
    coreClient: {
      runVersion: async () => ({}),
      runVersionQueue: async () => [],
      evolveWorkflow: async () => ({}),
      createWorkflow: async () => ({}),
      exportJsTool: async () => ({}),
      runJsTool: async () => ({}),
      evalJsTool: async () => ({}),
      proposeUpdate: async () => ({}),
      applyProposal: async () => ({}),
      pauseActiveJob: () => ({}),
      resumeActiveJob: () => ({})
    },
    openExternal: async () => undefined,
    openPath: async () => undefined,
    pythonExists: () => true
  });

  assert.deepEqual(channels, [
    "webmcp:get-default-paths",
    "webmcp:list-workflows",
    "webmcp:workflow-detail",
    "webmcp:memory-overview",
    "webmcp:run-versions",
    "webmcp:run-version",
    "webmcp:watch-version",
    "webmcp:evolve-workflow",
    "webmcp:create-workflow",
    "webmcp:export-js-tool",
    "webmcp:run-js-tool",
    "webmcp:eval-js-tool",
    "webmcp:pause-current-job",
    "webmcp:resume-current-job",
    "webmcp:propose-update",
    "webmcp:apply-proposal",
    "webmcp:open-path"
  ]);
});

test("watch-version is protected by the active job queue lock", async () => {
  const handlers = {};
  const ipcMain = {
    handle: (channel, handler) => {
      handlers[channel] = handler;
    }
  };
  let finishRun;
  const firstRun = new Promise((resolve) => {
    finishRun = resolve;
  });
  let runCount = 0;

  registerWebmcpIpcHandlers({
    ipcMain,
    paths: {
      repoRoot: "/repo/webmcp/core",
      defaultDbPath: "/repo/webmcp/core/outputs/workflows.sqlite",
      defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
      defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python"
    },
    sidecarPath: () => "/repo/webmcp/apps/desktop/rust/webmcp-sidecar/target/debug/webmcp-sidecar",
    sidecarExists: () => true,
    runSidecar: async () => ({}),
    coreClient: {
      runVersion: async () => {
        runCount += 1;
        return firstRun;
      },
      runVersionQueue: async () => [],
      evolveWorkflow: async () => ({}),
      createWorkflow: async () => ({}),
      exportJsTool: async () => ({}),
      runJsTool: async () => ({}),
      evalJsTool: async () => ({}),
      proposeUpdate: async () => ({}),
      applyProposal: async () => ({}),
      pauseActiveJob: () => ({}),
      resumeActiveJob: () => ({})
    },
    openExternal: async () => undefined,
    openPath: async () => undefined,
    pythonExists: () => true
  });

  const payload = { workflowName: "naver_stock_report", version: 1 };
  const first = handlers["webmcp:watch-version"]({ sender: {} }, payload);
  await assert.rejects(
    () => handlers["webmcp:watch-version"]({ sender: {} }, payload),
    /already active/
  );

  finishRun({});
  await first;
  assert.equal(runCount, 1);
});

test("sidecar runner does not replace the pausable active job process", async () => {
  const calls = [];
  const runSidecar = createSidecarRunner({
    appRoot: "/repo/webmcp/apps/desktop",
    sidecarPath: () => "/repo/webmcp/apps/desktop/rust/webmcp-sidecar/target/debug/webmcp-sidecar",
    sidecarExists: () => true,
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      return { stdout: "{}", stderr: "", exitCode: 0 };
    }
  });

  await runSidecar(["list-workflows", "--db", "/tmp/workflows.sqlite"]);

  assert.equal(calls[0].options.pausable, false);
});

test("memory-overview IPC calls the sidecar with the selected db path", async () => {
  const handlers = {};
  const ipcMain = {
    handle: (channel, handler) => {
      handlers[channel] = handler;
    }
  };
  const sidecarCalls = [];

  registerWebmcpIpcHandlers({
    ipcMain,
    paths: {
      repoRoot: "/repo/webmcp/core",
      defaultDbPath: "/home/user/.webmcp-studio/db/workflows.sqlite",
      defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
      defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python"
    },
    sidecarPath: () => "/repo/webmcp/apps/desktop/rust/webmcp-sidecar/target/debug/webmcp-sidecar",
    sidecarExists: () => true,
    runSidecar: async (args) => {
      sidecarCalls.push(args);
      return { pageAnalyses: [], knowledgeEntries: [], pageAnalysisCount: 0, knowledgeEntryCount: 0 };
    },
    coreClient: {
      runVersion: async () => ({}),
      runVersionQueue: async () => [],
      evolveWorkflow: async () => ({}),
      createWorkflow: async () => ({}),
      exportJsTool: async () => ({}),
      runJsTool: async () => ({}),
      evalJsTool: async () => ({}),
      proposeUpdate: async () => ({}),
      applyProposal: async () => ({}),
      pauseActiveJob: () => ({}),
      resumeActiveJob: () => ({})
    },
    openExternal: async () => undefined,
    openPath: async () => undefined,
    pythonExists: () => true
  });

  const overview = await handlers["webmcp:memory-overview"](
    {},
    { dbPath: "/home/user/.webmcp-studio/db/workflows.sqlite" }
  );

  assert.equal(overview.pageAnalysisCount, 0);
  assert.deepEqual(sidecarCalls, [
    ["memory-overview", "--db", "/home/user/.webmcp-studio/db/workflows.sqlite"]
  ]);
});
