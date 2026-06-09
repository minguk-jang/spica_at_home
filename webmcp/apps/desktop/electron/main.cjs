const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const { collectProcess } = require("./process-runner.cjs");
const { createSidecarRunner, registerWebmcpIpcHandlers } = require("./ipc-handlers.cjs");
const { createProjectPaths } = require("./project-paths.cjs");
const { createWebmcpCoreClient } = require("./webmcp-core-client.cjs");

const appRoot = path.resolve(__dirname, "..");
const projectPaths = createProjectPaths(appRoot);
const repoRoot = projectPaths.coreRoot;
const defaultDbPath = projectPaths.defaultDbPath;
const defaultOutputDir = projectPaths.defaultOutputDir;
const defaultPythonPath = projectPaths.defaultPythonPath;
const coreClient = createWebmcpCoreClient({
  repoRoot,
  defaultOutputDir,
  defaultPythonPath,
  openExternal: (url) => shell.openExternal(url)
});
const runSidecar = createSidecarRunner({
  appRoot,
  sidecarPath,
  sidecarExists: (targetPath) => fs.existsSync(targetPath),
  collectProcess
});

let mainWindow = null;

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

registerWebmcpIpcHandlers({
  ipcMain,
  paths: {
    repoRoot,
    defaultDbPath,
    defaultOutputDir,
    defaultPythonPath
  },
  sidecarPath,
  runSidecar,
  coreClient,
  openExternal: (targetUrl) => shell.openExternal(targetUrl),
  openPath: (targetPath) => shell.openPath(targetPath),
  pythonExists: (targetPath) => fs.existsSync(targetPath)
});
