const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("webmcp", {
  getDefaultPaths: () => ipcRenderer.invoke("webmcp:get-default-paths"),
  listWorkflows: (dbPath) => ipcRenderer.invoke("webmcp:list-workflows", { dbPath }),
  getWorkflowDetail: (dbPath, workflowId, repoRoot) =>
    ipcRenderer.invoke("webmcp:workflow-detail", { dbPath, workflowId, repoRoot }),
  runVersion: (payload) => ipcRenderer.invoke("webmcp:run-version", payload),
  runVersions: (payload) => ipcRenderer.invoke("webmcp:run-versions", payload),
  watchVersion: (payload) => ipcRenderer.invoke("webmcp:watch-version", payload),
  proposeUpdate: (payload) => ipcRenderer.invoke("webmcp:propose-update", payload),
  applyProposal: (payload) => ipcRenderer.invoke("webmcp:apply-proposal", payload),
  openPath: (targetPath) => ipcRenderer.invoke("webmcp:open-path", targetPath),
  onRunEvent: (listener) => {
    const wrapped = (_event, payload) => listener(payload);
    ipcRenderer.on("webmcp:run-event", wrapped);
    return () => ipcRenderer.removeListener("webmcp:run-event", wrapped);
  }
});
