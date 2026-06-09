const assert = require("node:assert/strict");
const test = require("node:test");

const { registerWebmcpIpcHandlers } = require("../electron/ipc-handlers.cjs");

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
      proposeUpdate: async () => ({}),
      applyProposal: async () => ({})
    },
    openExternal: async () => undefined,
    openPath: async () => undefined,
    pythonExists: () => true
  });

  assert.deepEqual(channels, [
    "webmcp:get-default-paths",
    "webmcp:list-workflows",
    "webmcp:workflow-detail",
    "webmcp:run-versions",
    "webmcp:run-version",
    "webmcp:watch-version",
    "webmcp:propose-update",
    "webmcp:apply-proposal",
    "webmcp:open-path"
  ]);
});
