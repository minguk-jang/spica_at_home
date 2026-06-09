const assert = require("node:assert/strict");
const test = require("node:test");

const { createWebmcpCoreClient } = require("../electron/webmcp-core-client.cjs");

test("core client runs selected workflow version through Python CLI with headed env", async () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python",
    pythonExists: () => true,
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      return {
        stdout: JSON.stringify({ output: { url: "https://search.naver.com/search.naver?query=test" } }),
        stderr: "",
        exitCode: 0
      };
    },
    openExternal: async (url) => calls.push({ openExternal: url }),
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 1000;
      return () => {
        value += 25;
        return value;
      };
    })()
  });

  const events = [];
  const job = await client.runVersion({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      workflowName: "naver_stock_report",
      version: 3,
      request: "네이버에서 삼성전자 주가 리포트",
      companyName: "삼성전자",
      ticker: "005930"
    },
    version: 3,
    headed: true
  });

  assert.equal(calls[0].command, "/repo/webmcp/core/reference/webwright/.venv/bin/python");
  assert.deepEqual(calls[0].args.slice(0, 4), ["-m", "webworkflows.cli", "run-version", "--db"]);
  assert.equal(calls[0].args[calls[0].args.indexOf("--version") + 1], "3");
  assert.equal(calls[0].options.cwd, "/repo/webmcp/core");
  assert.equal(calls[0].options.env.PYTHONPATH, "/repo/webmcp/core");
  assert.equal(calls[0].options.env.WEBWRIGHT_HEADLESS, "0");
  assert.equal(calls[1].openExternal, "https://search.naver.com/search.naver?query=test");
  assert.equal(job.status, "succeeded");
  assert.equal(job.output.output.url, "https://search.naver.com/search.naver?query=test");
  assert.equal(events[0].type, "job-started");
  assert.equal(events[1].type, "job-finished");
});

test("core client falls back to python3 and sets headless env for headless runs", async () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python",
    pythonExists: () => false,
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      return { stdout: "{}", stderr: "", exitCode: 0 };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: () => 1000
  });

  await client.runVersion({
    sender: { send: () => undefined },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      repoRoot: "/custom/core",
      workflowName: "naver_stock_report",
      version: 1,
      companyName: "삼성전자"
    },
    version: 1,
    headed: false
  });

  assert.equal(calls[0].command, "python3");
  assert.equal(calls[0].options.cwd, "/custom/core");
  assert.equal(calls[0].options.env.PYTHONPATH, "/custom/core");
  assert.equal(calls[0].options.env.WEBWRIGHT_HEADLESS, "1");
});

test("core client runs evolve workflow through Python CLI", async () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python",
    pythonExists: () => true,
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      return {
        stdout: JSON.stringify({ status: "waiting_for_repair", repair_request_path: "/tmp/repair_request.json" }),
        stderr: "",
        exitCode: 0
      };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 2000;
      return () => {
        value += 10;
        return value;
      };
    })()
  });

  const events = [];
  const job = await client.evolveWorkflow({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      workflowName: "naver_stock_report",
      baseVersion: 1,
      request: "네이버에서 삼성전자 주가 리포트",
      companyName: "삼성전자",
      ticker: "005930",
      maxAttempts: 3
    }
  });

  assert.equal(calls[0].command, "/repo/webmcp/core/reference/webwright/.venv/bin/python");
  assert.deepEqual(calls[0].args.slice(0, 4), ["-m", "webworkflows.cli", "evolve", "--db"]);
  assert.equal(calls[0].args[calls[0].args.indexOf("--base-version") + 1], "1");
  assert.equal(calls[0].args[calls[0].args.indexOf("--repair-synthesizer") + 1], "codex");
  assert.equal(calls[0].args.includes("--eval-and-evolve"), true);
  assert.equal(calls[0].args[calls[0].args.indexOf("--vlm-evaluator") + 1], "codex");
  assert.equal(calls[0].options.cwd, "/repo/webmcp/core");
  assert.equal(job.output.status, "waiting_for_repair");
  assert.equal(events[0].type, "evolution-started");
  assert.equal(events[1].type, "evolution-finished");
});

test("core client creates workflow through Python CLI and emits creation events", async () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "/repo/webmcp/core/reference/webwright/.venv/bin/python",
    pythonExists: () => true,
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      return {
        stdout: JSON.stringify({
          status: "succeeded",
          workflow: "flight_search",
          workflow_version: 1,
          created_skill_id: 7
        }),
        stderr: "",
        exitCode: 0
      };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 3000;
      return () => {
        value += 11;
        return value;
      };
    })()
  });

  const events = [];
  const job = await client.createWorkflow({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      startUrl: "https://www.google.com/flights",
      task: "Search flights from SEA to JFK",
      finalState: "Flight result list is visible",
      maxAttempts: 2
    }
  });

  assert.equal(calls[0].command, "/repo/webmcp/core/reference/webwright/.venv/bin/python");
  assert.deepEqual(calls[0].args.slice(0, 4), ["-m", "webworkflows.cli", "create-workflow", "--db"]);
  assert.equal(calls[0].args[calls[0].args.indexOf("--start-url") + 1], "https://www.google.com/flights");
  assert.equal(calls[0].options.cwd, "/repo/webmcp/core");
  assert.equal(job.output.workflow, "flight_search");
  assert.equal(events[0].type, "creation-started");
  assert.equal(events[1].type, "creation-finished");
});

test("core client pauses and resumes the active job through process controls", () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "python3",
    pauseProcess: () => {
      calls.push("pause");
      return { status: "paused", pid: 1234 };
    },
    resumeProcess: () => {
      calls.push("resume");
      return { status: "running", pid: 1234 };
    },
    now: () => "2026-06-09T00:00:00.000Z"
  });
  const events = [];

  const paused = client.pauseActiveJob({ sender: { send: (_channel, event) => events.push(event) } });
  const resumed = client.resumeActiveJob({ sender: { send: (_channel, event) => events.push(event) } });

  assert.deepEqual(calls, ["pause", "resume"]);
  assert.deepEqual(paused, { status: "paused", pid: 1234 });
  assert.deepEqual(resumed, { status: "running", pid: 1234 });
  assert.equal(events[0].type, "job-paused");
  assert.equal(events[1].type, "job-resumed");
});
