import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultJsToolArgumentsJson,
  defaultRequiredOutputKeys
} from "../src/features/js-tool/model/jsToolDefaults.ts";
import type { WorkflowDetail } from "../src/vite-env";

test("adds page text seed for JS tools that validate page text markers", () => {
  const detail = workflowDetailWithPageTextSteps();

  const defaults = JSON.parse(defaultJsToolArgumentsJson(detail));

  assert.equal(defaults.start_url, "https://books.toscrape.com/");
  assert.match(defaults.page_text, /Mystery/);
  assert.match(defaults.page_text, /Page 1 of 2/);
  assert.match(defaults.page_text, /Page 2 of 2/);
  assert.match(defaults.page_text, /Product Information/);
});

test("infers required output keys from selected workflow version schema", () => {
  const detail = workflowDetailWithPageTextSteps();

  assert.deepEqual(defaultRequiredOutputKeys(detail, 1), [
    "final_url",
    "page_text",
    "report_text",
    "status"
  ]);
});

function workflowDetailWithPageTextSteps(): WorkflowDetail {
  return {
    workflow: {
      id: 1,
      name: "verified_books_mystery_page2_product_report",
      slug: "verified-books-mystery-page2-product-report",
      description: "Books workflow",
      domain: "books.toscrape.com",
      taskType: "catalog",
      status: "stable",
      latestVersion: 1,
      versionCount: 1,
      stepCount: 4,
      runCount: 0,
      updateCount: 0,
      lastRunStatus: null,
      lastRunDurationMs: null,
      lastRunAt: null,
      updatedAt: "2026-06-10"
    },
    versions: [{
      id: 1,
      version: 1,
      summary: "Books v1",
      bodyMd: "",
      inputSchema: { start_url: { type: "string", required: true } },
      outputSchema: {
        final_url: "string",
        page_text: "string",
        report_text: "string",
        status: "string"
      },
      status: "stable",
      createdFromRunId: null,
      createdAt: "2026-06-10"
    }],
    arguments: [{
      id: 1,
      versionId: 1,
      name: "start_url",
      description: "Start URL",
      valueType: "string",
      required: true,
      defaultValue: null,
      validation: {},
      examples: ["https://books.toscrape.com/"],
      isDynamic: true,
      orderIndex: 0
    }],
    steps: [
      waitStep(1, ["Mystery", "Page 1 of 2"]),
      waitStep(2, ["Page 2 of 2", "Mystery"]),
      waitStep(3, ["Product Information", "Availability", "Price"])
    ],
    resources: [],
    handlers: [],
    runs: [],
    stepRuns: [],
    updateEvents: [],
    examples: [],
    proposals: []
  };
}

function waitStep(id: number, containsAny: string[]) {
  return {
    id,
    versionId: 1,
    orderIndex: id,
    name: `wait_${id}`,
    description: "",
    stepType: "wait_for_text",
    handlerRef: null,
    action: { source: "page_text" },
    argumentBindings: {},
    assertions: { contains_any: containsAny },
    fallbackPolicy: {},
    updatePolicy: {}
  };
}
