import assert from "node:assert/strict";
import test from "node:test";

import { normalizeWorkflowDetail } from "../src/entities/workflow/model/detailDefaults.ts";

test("adds an empty proposal list to legacy workflow details", () => {
  const detail = normalizeWorkflowDetail({
    workflow: { id: 1, name: "naver_stock_report" },
    versions: [],
    arguments: [],
    steps: [],
    resources: [],
    runs: [],
    stepRuns: [],
    updateEvents: []
  });

  assert.deepEqual(detail.handlers, []);
  assert.deepEqual(detail.examples, []);
  assert.deepEqual(detail.proposals, []);
});
