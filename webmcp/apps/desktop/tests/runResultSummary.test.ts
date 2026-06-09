import assert from "node:assert/strict";
import test from "node:test";

import {
  getRunEventResult,
  getWorkflowRunResult,
  summarizeRunOutput
} from "../src/runResultSummary.ts";

test("extracts visible result details from a finished run event", () => {
  const result = getRunEventResult({
    type: "job-finished",
    workflowName: "naver_stock_report",
    version: 3,
    headed: false,
    status: "succeeded",
    durationMs: 42,
    stdout: "{\"status\":\"succeeded\"}",
    stderr: "",
    exitCode: 0,
    output: {
      workflow: "naver_stock_report",
      workflow_version: 3,
      run_id: 19,
      status: "succeeded",
      report_path: "/tmp/run_삼성전자_report.md",
      output: {
        company_name: "삼성전자",
        ticker: "005930",
        current_price: 295500,
        report_text: "삼성전자 주가 리포트"
      }
    }
  });

  assert.equal(result.title, "naver_stock_report v3 headless");
  assert.equal(result.status, "succeeded");
  assert.equal(result.runId, 19);
  assert.equal(result.reportPath, "/tmp/run_삼성전자_report.md");
  assert.deepEqual(result.metrics, [
    ["company_name", "삼성전자"],
    ["ticker", "005930"],
    ["current_price", "295500"]
  ]);
  assert.match(result.outputPreview, /삼성전자 주가 리포트/);
});

test("extracts visible result details from a stored workflow run", () => {
  const result = getWorkflowRunResult({
    id: 7,
    versionId: 3,
    userRequest: "네이버에서 삼성전자 주가 리포트",
    input: {},
    status: "succeeded",
    llmUsed: false,
    startedAt: "2026-06-09T00:00:00Z",
    finishedAt: "2026-06-09T00:00:01Z",
    durationMs: 85,
    reportPath: "/tmp/report.md",
    output: {
      company_name: "삼성전자",
      ticker: "005930",
      current_price: 295500,
      report_text: "본문"
    }
  });

  assert.equal(result.title, "Run #7");
  assert.equal(result.reportPath, "/tmp/report.md");
  assert.deepEqual(result.metrics, [
    ["company_name", "삼성전자"],
    ["ticker", "005930"],
    ["current_price", "295500"]
  ]);
  assert.match(result.outputPreview, /본문/);
});

test("summarizes unknown output without hiding raw JSON", () => {
  const summary = summarizeRunOutput({ nested: { ok: true } });

  assert.deepEqual(summary.metrics, []);
  assert.match(summary.outputPreview, /"ok": true/);
});
