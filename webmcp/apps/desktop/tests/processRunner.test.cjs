const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");

const { createProcessRunner } = require("../electron/process-runner.cjs");

test("process runner can pause and resume the active process group", async () => {
  const signals = [];
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.pid = 4321;
  child.kill = (signal) => {
    signals.push({ target: "child", signal });
    return true;
  };
  const runner = createProcessRunner({
    platform: "darwin",
    spawnImpl: (_command, _args, options) => {
      assert.equal(options.detached, true);
      return child;
    },
    killImpl: (pid, signal) => {
      signals.push({ target: pid, signal });
      return true;
    }
  });

  const pending = runner.collectProcess("python3", ["-m", "webworkflows.cli"], { cwd: "/repo" });
  assert.deepEqual(runner.pauseCurrentProcess(), { status: "paused", pid: 4321 });
  assert.deepEqual(runner.resumeCurrentProcess(), { status: "running", pid: 4321 });

  child.stdout.emit("data", Buffer.from("ok"));
  child.emit("close", 0);
  const result = await pending;

  assert.deepEqual(signals, [
    { target: -4321, signal: "SIGSTOP" },
    { target: -4321, signal: "SIGCONT" }
  ]);
  assert.deepEqual(result, { stdout: "ok", stderr: "", exitCode: 0 });
});

test("non-pausable helper processes do not replace a paused active job", async () => {
  const signals = [];
  const longJob = fakeChild(4321);
  const helper = fakeChild(6789);
  const children = [longJob, helper];
  const runner = createProcessRunner({
    platform: "darwin",
    spawnImpl: () => children.shift(),
    killImpl: (pid, signal) => {
      signals.push({ target: pid, signal });
      return true;
    }
  });

  const pendingLongJob = runner.collectProcess("python3", ["-m", "webworkflows.cli"], { cwd: "/repo" });
  assert.deepEqual(runner.pauseCurrentProcess(), { status: "paused", pid: 4321 });

  const pendingHelper = runner.collectProcess("sidecar", ["list-workflows"], { cwd: "/app", pausable: false });
  helper.stdout.emit("data", Buffer.from("{}"));
  helper.emit("close", 0);
  await pendingHelper;

  assert.deepEqual(runner.resumeCurrentProcess(), { status: "running", pid: 4321 });
  longJob.stdout.emit("data", Buffer.from("done"));
  longJob.emit("close", 0);
  await pendingLongJob;

  assert.deepEqual(signals, [
    { target: -4321, signal: "SIGSTOP" },
    { target: -4321, signal: "SIGCONT" }
  ]);
});

test("process runner can interrupt the active process group before app quit", () => {
  const signals = [];
  const child = fakeChild(9876);
  const runner = createProcessRunner({
    platform: "darwin",
    spawnImpl: () => child,
    killImpl: (pid, signal) => {
      signals.push({ target: pid, signal });
      return true;
    }
  });

  void runner.collectProcess("python3", ["-m", "webworkflows.cli"], { cwd: "/repo" });

  assert.deepEqual(runner.terminateCurrentProcess(), {
    status: "terminating",
    pid: 9876,
    signal: "SIGINT"
  });
  assert.deepEqual(runner.resumeCurrentProcess(), { status: "idle" });
  assert.deepEqual(signals, [{ target: -9876, signal: "SIGINT" }]);
});

test("process runner resumes a paused job before interrupting it", () => {
  const signals = [];
  const child = fakeChild(2468);
  const runner = createProcessRunner({
    platform: "darwin",
    spawnImpl: () => child,
    killImpl: (pid, signal) => {
      signals.push({ target: pid, signal });
      return true;
    }
  });

  void runner.collectProcess("python3", ["-m", "webworkflows.cli"], { cwd: "/repo" });
  runner.pauseCurrentProcess();

  assert.deepEqual(runner.terminateCurrentProcess(), {
    status: "terminating",
    pid: 2468,
    signal: "SIGINT"
  });
  assert.deepEqual(signals, [
    { target: -2468, signal: "SIGSTOP" },
    { target: -2468, signal: "SIGCONT" },
    { target: -2468, signal: "SIGINT" }
  ]);
});

function fakeChild(pid) {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.pid = pid;
  child.kill = () => true;
  return child;
}
