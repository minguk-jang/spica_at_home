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

test("core client suggests a guided step draft through Python CLI", async () => {
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
          provider: "heuristic",
          step_guide: [{ name: "open_start_url", description: "Open the page.", step_type: "goto" }]
        }),
        stderr: "",
        exitCode: 0
      };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 3500;
      return () => {
        value += 13;
        return value;
      };
    })()
  });

  const events = [];
  const job = await client.suggestStepGuide({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      repoRoot: "/repo/webmcp/core",
      startUrl: "https://www.google.com/flights",
      task: "Search flights from SEA to JFK",
      finalState: "Flight result list is visible",
      synthesizerModel: "gpt-5.5"
    }
  });

  assert.equal(calls[0].command, "/repo/webmcp/core/reference/webwright/.venv/bin/python");
  assert.deepEqual(calls[0].args.slice(0, 4), ["-m", "webworkflows.cli", "suggest-step-guide", "--db"]);
  assert.equal(calls[0].args[calls[0].args.indexOf("--suggester") + 1], "codex");
  assert.equal(calls[0].options.cwd, "/repo/webmcp/core");
  assert.equal(job.output.step_guide[0].name, "open_start_url");
  assert.equal(events[0].type, "step-guide-suggestion-started");
  assert.equal(events[1].type, "step-guide-suggestion-finished");
});

test("core client exports a workflow version as a JavaScript tool", async () => {
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
          tool_dir: "/tmp/js-tools/naver-stock-report-v2",
          files: { entrypoint: "/tmp/js-tools/naver-stock-report-v2/tool.cjs" }
        }),
        stderr: "",
        exitCode: 0
      };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 4000;
      return () => {
        value += 9;
        return value;
      };
    })()
  });

  const events = [];
  const job = await client.exportJsTool({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      dbPath: "/tmp/workflows.sqlite",
      workflowName: "naver_stock_report",
      version: 2,
      outputDir: "/tmp/js-tools"
    }
  });

  assert.equal(calls[0].command, "/repo/webmcp/core/reference/webwright/.venv/bin/python");
  assert.deepEqual(calls[0].args.slice(0, 4), ["-m", "webworkflows.cli", "export-js-tool", "--db"]);
  assert.equal(calls[0].args[calls[0].args.indexOf("--workflow-name") + 1], "naver_stock_report");
  assert.equal(calls[0].args[calls[0].args.indexOf("--version") + 1], "2");
  assert.equal(calls[0].options.cwd, "/repo/webmcp/core");
  assert.equal(job.output.tool_dir, "/tmp/js-tools/naver-stock-report-v2");
  assert.equal(events[0].type, "js-tool-export-started");
  assert.equal(events[1].type, "js-tool-export-finished");
});

test("core client runs and evaluates exported JavaScript tools", async () => {
  const calls = [];
  const client = createWebmcpCoreClient({
    repoRoot: "/repo/webmcp/core",
    defaultOutputDir: "/repo/webmcp/core/outputs/desktop_runs",
    defaultPythonPath: "python3",
    collectProcess: async (command, args, options) => {
      calls.push({ command, args, options });
      const commandName = args[2];
      return {
        stdout: JSON.stringify(commandName === "eval-js-tool" ? { passed: true } : { status: "succeeded" }),
        stderr: "",
        exitCode: 0
      };
    },
    now: () => "2026-06-09T00:00:00.000Z",
    nowMs: (() => {
      let value = 5000;
      return () => {
        value += 7;
        return value;
      };
    })()
  });

  const events = [];
  const runJob = await client.runJsTool({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      toolDir: "/tmp/js-tools/naver-stock-report-v2",
      arguments: { company_name: "삼성전자", ticker: "005930" }
    }
  });
  const evalJob = await client.evalJsTool({
    sender: { send: (_channel, event) => events.push(event) },
    payload: {
      toolDir: "/tmp/js-tools/naver-stock-report-v2",
      arguments: { company_name: "삼성전자", ticker: "005930" },
      requiredOutput: ["company_name", "ticker", "report_text"]
    }
  });

  assert.equal(calls[0].args[2], "run-js-tool");
  assert.equal(calls[0].args.includes("company_name=삼성전자"), true);
  assert.equal(calls[1].args[2], "eval-js-tool");
  assert.equal(calls[1].args.filter((item) => item === "--required-output").length, 3);
  assert.equal(runJob.output.status, "succeeded");
  assert.equal(evalJob.output.passed, true);
  assert.equal(events[0].type, "js-tool-run-started");
  assert.equal(events[1].type, "js-tool-run-finished");
  assert.equal(events[2].type, "js-tool-eval-started");
  assert.equal(events[3].type, "js-tool-eval-finished");
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
