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
