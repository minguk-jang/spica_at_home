import assert from "node:assert/strict";
import test from "node:test";

import { buildVisibleRunControlFields } from "../src/runControlFields.ts";
import type { WorkflowArgument } from "../src/vite-env";

test("run controls hide runtime path fields from users", () => {
  const labels = buildVisibleRunControlFields([
    workflowArgument({ name: "company_name" }),
    workflowArgument({ name: "ticker" }),
    workflowArgument({ name: "news_limit", valueType: "integer" })
  ]).map((field) => field.label);

  assert.deepEqual(labels, ["Request", "Company", "Ticker", "News"]);
  assert.equal(labels.includes("Repo"), false);
  assert.equal(labels.includes("Output"), false);
  assert.equal(labels.includes("Python"), false);
});

test("run controls use selected workflow arguments instead of always showing stock fields", () => {
  const labels = buildVisibleRunControlFields([
    workflowArgument({ id: 1, name: "start_station", orderIndex: 0 }),
    workflowArgument({ id: 2, name: "end_station", orderIndex: 1 }),
    workflowArgument({ id: 3, name: "start_url", orderIndex: 2 }),
    workflowArgument({ id: 4, name: "page_text", orderIndex: 3 })
  ]).map((field) => field.label);

  assert.deepEqual(labels, ["Request", "Start Station", "End Station", "Start URL"]);
  assert.equal(labels.includes("Ticker"), false);
  assert.equal(labels.includes("Company"), false);
  assert.equal(labels.includes("News"), false);
});

function workflowArgument(overrides: Partial<WorkflowArgument>): WorkflowArgument {
  return {
    id: 1,
    versionId: 1,
    name: "company_name",
    description: "Argument",
    valueType: "string",
    required: true,
    defaultValue: null,
    validation: {},
    examples: [],
    isDynamic: true,
    orderIndex: 0,
    ...overrides
  };
}
