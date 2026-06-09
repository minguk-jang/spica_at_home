const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("webmcp", {
  getDefaultPaths: () => ipcRenderer.invoke("webmcp:get-default-paths"),
  listWorkflows: (dbPath) => ipcRenderer.invoke("webmcp:list-workflows", { dbPath }),
  getWorkflowDetail: (dbPath, workflowId, repoRoot) =>
    ipcRenderer.invoke("webmcp:workflow-detail", { dbPath, workflowId, repoRoot }),
  getMemoryOverview: (dbPath) => ipcRenderer.invoke("webmcp:memory-overview", { dbPath }),
  runVersion: (payload) => ipcRenderer.invoke("webmcp:run-version", payload),
  runVersions: (payload) => ipcRenderer.invoke("webmcp:run-versions", payload),
  watchVersion: (payload) => ipcRenderer.invoke("webmcp:watch-version", payload),
  evolveWorkflow: (payload) => ipcRenderer.invoke("webmcp:evolve-workflow", payload),
  createWorkflow: (payload) => ipcRenderer.invoke("webmcp:create-workflow", payload),
  exportJsTool: (payload) => ipcRenderer.invoke("webmcp:export-js-tool", payload),
  runJsTool: (payload) => ipcRenderer.invoke("webmcp:run-js-tool", payload),
  evalJsTool: (payload) => ipcRenderer.invoke("webmcp:eval-js-tool", payload),
  pauseCurrentJob: () => ipcRenderer.invoke("webmcp:pause-current-job"),
  resumeCurrentJob: () => ipcRenderer.invoke("webmcp:resume-current-job"),
  proposeUpdate: (payload) => ipcRenderer.invoke("webmcp:propose-update", payload),
  applyProposal: (payload) => ipcRenderer.invoke("webmcp:apply-proposal", payload),
  openPath: (targetPath) => ipcRenderer.invoke("webmcp:open-path", targetPath),
  onRunEvent: (listener) => {
    const wrapped = (_event, payload) => listener(payload);
    ipcRenderer.on("webmcp:run-event", wrapped);
    return () => ipcRenderer.removeListener("webmcp:run-event", wrapped);
  }
});
