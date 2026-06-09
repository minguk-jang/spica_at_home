const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");
const { isElectronRuntimeFile } = require("./dev-runtime-files.cjs");

const appRoot = path.resolve(__dirname, "..");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const requestedDevServerUrl = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5178";
const smokeOnly = process.env.WEBMCP_DEV_SMOKE === "1";

let viteProcess = null;
let electronProcess = null;
let electronRestarting = false;
let electronEnv = null;
let shuttingDown = false;

main().catch((error) => {
  console.error(error.message || String(error));
  cleanup();
  process.exit(1);
});

async function main() {
  await runForeground("sidecar build", ["run", "sidecar:build"]);

  const parsedDevUrl = new URL(requestedDevServerUrl);
  const devServerHost = parsedDevUrl.hostname || "127.0.0.1";
  const requestedPort = Number(parsedDevUrl.port || 5178);
  const devServerPort = await findAvailablePort(devServerHost, requestedPort);
  parsedDevUrl.port = String(devServerPort);
  const devServerUrl = parsedDevUrl.toString().replace(/\/$/, "");
  if (devServerPort !== requestedPort) {
    console.log(`port ${requestedPort} is busy; using ${devServerPort}`);
  }

  viteProcess = spawn(localBin("vite"), ["--host", devServerHost, "--port", String(devServerPort), "--strictPort"], {
    cwd: appRoot,
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"]
  });
  pipeWithPrefix(viteProcess, "vite");
  monitorExit(viteProcess, "vite");

  await waitForPort("127.0.0.1", devServerPort, 20_000);
  console.log(`dev server ready at ${devServerUrl}`);

  if (smokeOnly) {
    await sleep(1_500);
    cleanup();
    return;
  }

  electronEnv = {
    ...process.env,
    VITE_DEV_SERVER_URL: devServerUrl
  };
  startElectron();
  watchElectronRuntimeFiles();
}

function startElectron() {
  electronProcess = spawn(npmCommand, ["run", "electron:dev"], {
    cwd: appRoot,
    env: electronEnv || process.env,
    stdio: "inherit"
  });

  electronProcess.on("exit", (code) => {
    if (electronRestarting && !shuttingDown) {
      electronRestarting = false;
      startElectron();
      return;
    }
    cleanup();
    process.exit(code ?? 0);
  });
}

function watchElectronRuntimeFiles() {
  const electronDir = path.join(appRoot, "electron");
  let debounce = null;
  fs.watch(electronDir, (_eventType, filename) => {
    if (!filename || !isElectronRuntimeFile(path.join("electron", filename))) {
      return;
    }
    clearTimeout(debounce);
    debounce = setTimeout(() => restartElectron(`electron/${filename}`), 120);
  });
}

function restartElectron(changedPath) {
  if (smokeOnly || shuttingDown || !electronProcess || electronProcess.killed) {
    return;
  }
  console.log(`[electron] ${changedPath} changed; restarting Electron main process`);
  electronRestarting = true;
  electronProcess.kill();
}

function localBin(name) {
  const binary = process.platform === "win32" ? `${name}.cmd` : name;
  return path.join(appRoot, "node_modules", ".bin", binary);
}

function runForeground(label, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(npmCommand, args, {
      cwd: appRoot,
      env: process.env,
      stdio: "inherit"
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${label} failed with exit code ${code}`));
      }
    });
  });
}

function waitForPort(host, port, timeoutMs) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const socket = net.createConnection({ host, port });
      socket.once("connect", () => {
        socket.destroy();
        resolve();
      });
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() - started > timeoutMs) {
          reject(new Error(`Timed out waiting for ${host}:${port}`));
          return;
        }
        setTimeout(attempt, 250);
      });
    };
    attempt();
  });
}

async function findAvailablePort(host, startPort) {
  for (let port = startPort; port < startPort + 20; port += 1) {
    if (await canBindPort(host, port)) {
      return port;
    }
  }
  throw new Error(`No available dev server port found from ${startPort} to ${startPort + 19}`);
}

function canBindPort(host, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

function pipeWithPrefix(child, label) {
  child.stdout.on("data", (chunk) => process.stdout.write(`[${label}] ${chunk}`));
  child.stderr.on("data", (chunk) => process.stderr.write(`[${label}] ${chunk}`));
}

function monitorExit(child, label) {
  child.on("exit", (code) => {
    if (shuttingDown) {
      return;
    }
    if (electronProcess) {
      return;
    }
    if (code !== null && code !== 0) {
      console.error(`${label} exited with code ${code}`);
      cleanup();
      process.exit(code);
    }
  });
}

function cleanup() {
  shuttingDown = true;
  for (const child of [electronProcess, viteProcess]) {
    if (child && !child.killed) {
      child.kill();
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

process.on("SIGINT", () => {
  cleanup();
  process.exit(130);
});

process.on("SIGTERM", () => {
  cleanup();
  process.exit(143);
});
