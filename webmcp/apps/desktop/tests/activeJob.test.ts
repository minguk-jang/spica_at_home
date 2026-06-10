import assert from "node:assert/strict";
import test from "node:test";

import {
  activeJobControlLabel,
  activeJobStatusText,
  activeJobTitle
} from "../src/features/active-job/model/activeJob.ts";

test("describes active Codex jobs with operation-specific labels", () => {
  assert.equal(
    activeJobTitle({ kind: "update", workflowName: "naver_stock_report", version: 2, paused: false }),
    "Codex draft for naver_stock_report v2"
  );
  assert.equal(
    activeJobTitle({ kind: "evolution", workflowName: "naver_stock_report", version: 2, paused: false }),
    "Eval & evolve for naver_stock_report v2"
  );
  assert.equal(
    activeJobTitle({ kind: "creation", startUrl: "https://www.google.com/flights", paused: false }),
    "Create workflow from browser task"
  );
});

test("uses pause and resume labels based on active job state", () => {
  assert.equal(activeJobControlLabel({ kind: "run", workflowName: "flight_search", version: 1, paused: false }), "Pause job");
  assert.equal(activeJobControlLabel({ kind: "run", workflowName: "flight_search", version: 1, paused: true }), "Resume job");
  assert.equal(activeJobStatusText({ kind: "run", workflowName: "flight_search", version: 1, paused: false }), "Running");
  assert.equal(activeJobStatusText({ kind: "run", workflowName: "flight_search", version: 1, paused: true }), "Paused");
});
