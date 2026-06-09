const assert = require("node:assert/strict");
const test = require("node:test");

const updateCommand = require("../electron/update-command.cjs");

const {
  buildPythonCreateWorkflowArgs,
  buildPythonEvolveArgs,
  buildPythonProposeArgs,
  buildPythonRunArgs
} = updateCommand;

test("proposal args always use codex synthesizer", () => {
  const args = buildPythonProposeArgs({
    dbPath: "/tmp/workflows.sqlite",
    outputDir: "/tmp/runs",
    workflowName: "naver_stock_report",
    baseVersion: 6,
    instruction: "뉴스 섹션을 더 자세히 작성",
    discoveryProvider: "webwright",
    synthesizerModel: "gpt-5.5"
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

test("run args always use Codex VLM monitoring when eval-and-evolve is enabled", () => {
  const args = buildPythonRunArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_stock_report",
      request: "네이버에서 삼성전자 주가 리포트",
      companyName: "삼성전자",
      ticker: "005930",
      newsLimit: 1,
      evalAndEvolve: true,
      vlmEvaluationFile: "/tmp/vlm-evaluations.json",
      evalBrowser: "chromium"
    },
    7,
    "/tmp/default-runs"
  );

  assert.equal(args.includes("--eval-and-evolve"), true);
  assert.equal(args[args.indexOf("--vlm-evaluator") + 1], "codex");
  assert.equal(args.includes("--vlm-model"), false);
  assert.equal(args[args.indexOf("--eval-browser") + 1], "chromium");
});

test("headed run args enable browser evaluation for page-driven workflows", () => {
  const args = buildPythonRunArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_map_transit_route",
      request: "네이버 지도에서 양재역에서 사당역까지 지하철로 몇 분 걸리는지 검색한다.",
      headed: true,
      extraArguments: {
        start_station: "양재역",
        end_station: "사당역",
        start_url: "https://www.naver.com"
      }
    },
    1,
    "/tmp/default-runs"
  );

  assert.equal(args.includes("--headed"), true);
  assert.equal(args.includes("--eval-and-evolve"), true);
  assert.equal(args[args.indexOf("--vlm-evaluator") + 1], "codex");
  assert.equal(args[args.indexOf("--eval-browser") + 1], "chromium");
});

test("run args include saved generic argument examples", () => {
  const args = buildPythonRunArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_map_transit_route",
      request: "네이버 지도에서 양재역에서 사당역",
      companyName: "",
      newsLimit: 3,
      extraArguments: {
        start_station: "양재역",
        end_station: "사당역",
        start_url: "https://www.naver.com"
      }
    },
    1,
    "/tmp/default-runs"
  );

  assert.equal(args.includes("--argument"), true);
  assert.equal(args.includes("start_station=양재역"), true);
  assert.equal(args.includes("end_station=사당역"), true);
  assert.equal(args.includes("start_url=https://www.naver.com"), true);
});

test("evolve args run selected workflow through automatic repair loop", () => {
  const args = buildPythonEvolveArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_stock_report",
      baseVersion: 3,
      request: "네이버에서 삼성전자 주가 리포트",
      companyName: "삼성전자",
      ticker: "005930",
      newsLimit: 1,
      maxAttempts: 5,
      evalBrowser: "chromium"
    },
    "/tmp/default-runs"
  );

  assert.equal(args[0], "-m");
  assert.equal(args[2], "evolve");
  assert.equal(args[args.indexOf("--base-version") + 1], "3");
  assert.equal(args[args.indexOf("--max-attempts") + 1], "5");
  assert.equal(args[args.indexOf("--repair-synthesizer") + 1], "codex");
  assert.equal(args.includes("--repair-workflow-json-file"), false);
  assert.equal(args.includes("--eval-and-evolve"), true);
  assert.equal(args[args.indexOf("--vlm-evaluator") + 1], "codex");
  assert.equal(args.includes("--vlm-model"), false);
});

test("evolve args include saved generic argument examples", () => {
  const args = buildPythonEvolveArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      workflowName: "naver_map_transit_route",
      baseVersion: 1,
      request: "네이버 지도에서 양재역에서 사당역",
      companyName: "",
      newsLimit: 3,
      maxAttempts: 2,
      extraArguments: {
        start_station: "양재역",
        end_station: "사당역"
      }
    },
    "/tmp/default-runs"
  );

  assert.equal(args.includes("start_station=양재역"), true);
  assert.equal(args.includes("end_station=사당역"), true);
});

test("create workflow args pass start URL task final state and Codex VLM defaults", () => {
  const args = buildPythonCreateWorkflowArgs(
    {
      dbPath: "/tmp/workflows.sqlite",
      outputDir: "/tmp/runs",
      startUrl: "https://www.google.com/flights",
      task: "Search flights from SEA to JFK",
      finalState: "Flight result list is visible",
      companyName: "삼성전자",
      ticker: "005930",
      maxAttempts: 2,
      headed: true,
      synthesizerModel: "gpt-5.5",
      evalBrowser: "chromium"
    },
    "/tmp/default-runs"
  );

  assert.equal(args[0], "-m");
  assert.equal(args[2], "create-workflow");
  assert.equal(args[args.indexOf("--start-url") + 1], "https://www.google.com/flights");
  assert.equal(args[args.indexOf("--task") + 1], "Search flights from SEA to JFK");
  assert.equal(args[args.indexOf("--final-state") + 1], "Flight result list is visible");
  assert.equal(args[args.indexOf("--max-attempts") + 1], "10");
  assert.equal(args[args.indexOf("--synthesizer") + 1], "codex");
  assert.equal(args.includes("--headed"), true);
  assert.equal(args.includes("--eval-and-evolve"), true);
  assert.equal(args[args.indexOf("--vlm-evaluator") + 1], "codex");
});
