const { spawn } = require("child_process");

function createProcessRunner(options = {}) {
  const spawnImpl = options.spawnImpl || spawn;
  const killImpl = options.killImpl || process.kill;
  const platform = options.platform || process.platform;
  let activeChild = null;
  let paused = false;

  function collectProcess(command, args, spawnOptions = {}) {
    const { pausable = true, ...childSpawnOptions } = spawnOptions;
    return new Promise((resolve) => {
      const child = spawnImpl(command, args, {
        ...childSpawnOptions,
        detached: platform === "win32" ? childSpawnOptions.detached : true
      });
      if (pausable) {
        activeChild = child;
        paused = false;
      }
      let stdout = "";
      let stderr = "";

      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });
      child.on("error", (error) => {
        if (pausable && activeChild === child) {
          activeChild = null;
          paused = false;
        }
        resolve({ stdout, stderr: stderr || error.message, exitCode: 1 });
      });
      child.on("close", (exitCode) => {
        if (pausable && activeChild === child) {
          activeChild = null;
          paused = false;
        }
        resolve({ stdout: stdout.trim(), stderr: stderr.trim(), exitCode });
      });
    });
  }

  function pauseCurrentProcess() {
    if (!activeChild || !activeChild.pid) {
      return { status: "idle" };
    }
    if (paused) {
      return { status: "paused", pid: activeChild.pid };
    }
    if (platform === "win32") {
      return { status: "unsupported", reason: "pause is not supported on win32" };
    }
    signalProcess(activeChild, "SIGSTOP", killImpl);
    paused = true;
    return { status: "paused", pid: activeChild.pid };
  }

  function resumeCurrentProcess() {
    if (!activeChild || !activeChild.pid) {
      return { status: "idle" };
    }
    if (!paused) {
      return { status: "running", pid: activeChild.pid };
    }
    if (platform === "win32") {
      return { status: "unsupported", reason: "resume is not supported on win32" };
    }
    signalProcess(activeChild, "SIGCONT", killImpl);
    paused = false;
    return { status: "running", pid: activeChild.pid };
  }

  function terminateCurrentProcess(signal = "SIGINT") {
    if (!activeChild || !activeChild.pid) {
      return { status: "idle" };
    }
    const child = activeChild;
    const pid = child.pid;
    if (paused && platform !== "win32") {
      signalProcess(child, "SIGCONT", killImpl);
    }
    signalProcess(child, signal, killImpl);
    activeChild = null;
    paused = false;
    return { status: "terminating", pid, signal };
  }

  return {
    collectProcess,
    pauseCurrentProcess,
    resumeCurrentProcess,
    terminateCurrentProcess
  };
}

function signalProcess(child, signal, killImpl) {
  try {
    killImpl(-child.pid, signal);
  } catch (_error) {
    child.kill(signal);
  }
}

const defaultRunner = createProcessRunner();

function collectProcess(command, args, options) {
  return defaultRunner.collectProcess(command, args, options);
}

function pauseCurrentProcess() {
  return defaultRunner.pauseCurrentProcess();
}

function resumeCurrentProcess() {
  return defaultRunner.resumeCurrentProcess();
}

function terminateCurrentProcess(signal) {
  return defaultRunner.terminateCurrentProcess(signal);
}

module.exports = {
  collectProcess,
  createProcessRunner,
  pauseCurrentProcess,
  resumeCurrentProcess,
  terminateCurrentProcess
};
