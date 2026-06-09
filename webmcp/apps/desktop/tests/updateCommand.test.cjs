const assert = require("node:assert/strict");
const test = require("node:test");

const updateCommand = require("../electron/update-command.cjs");

const { buildPythonProposeArgs, buildPythonRunArgs } = updateCommand;

test("proposal args always use codex synthesizer", () => {
  const args = buildPythonProposeArgs({
    dbPath: "/tmp/workflows.sqlite",
    outputDir: "/tmp/runs",
    workflowName: "naver_stock_report",
    baseVersion: 6,
    instruction: "뉴스 섹션을 더 자세히 작성",
    discoveryProvider: "webwright",
    synthesizerModel: "gpt-5.3-codex-spark"
  });

  assert.equal(args[0], "-m");
  assert.equal(args[2], "propose-update");
  assert.equal(args[args.indexOf("--synthesizer") + 1], "codex");
  assert.equal(args.includes("fake-copy"), false);
});

test("proposal helper no longer exposes visible terminal script generation", () => {
  assert.equal("buildVisibleTerminalScript" in updateCommand, false);
});

test("run args always collect live Naver page text instead of passing fixture text", () => {
  const args = buildPythonRunArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_stock_report",
      request: "네이버에서 삼성전자 주가 리포트",
      companyName: "삼성전자",
      ticker: "005930",
      pageTextFile: "/tmp/stale-fixture.txt",
      newsLimit: 1
    },
    7,
    "/tmp/default-runs"
  );

  assert.equal(args[2], "run-version");
  assert.equal(args.includes("--live-page-text"), true);
  assert.equal(args.includes("--page-text-file"), false);
  assert.equal(args.includes("/tmp/stale-fixture.txt"), false);
});
