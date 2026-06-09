import assert from "node:assert/strict";
import test from "node:test";

import {
  buildArgumentExamples,
  buildCreateWorkflowPayload,
  buildOperationControlState,
  buildStepCards,
  canCreateWorkflow,
  findLatestDraftProposal,
  storedRunDisplayStatus
} from "../src/workflowDashboard.ts";
import type { WorkflowExample, WorkflowStep, WorkflowUpdateProposal } from "../src/vite-env";

test("builds ordered user-facing step cards for the selected version", () => {
  const steps = [
    step({ id: 2, orderIndex: 1, name: "extract_stock_card", stepType: "run_handler" }),
    step({ id: 1, orderIndex: 0, name: "open_search", stepType: "goto" })
  ];

  const cards = buildStepCards(steps);

  assert.deepEqual(
    cards.map((card) => [card.label, card.name, card.type]),
    [
      ["Step 1", "open_search", "goto"],
      ["Step 2", "extract_stock_card", "run_handler"]
    ]
  );
});

test("builds argument examples from workflow metadata instead of hardcoded presets", () => {
  const examples = buildArgumentExamples([
    workflowExample({
      id: 10,
      userRequest: "네이버에서 삼성전자 주가 리포트",
      normalizedArguments: { company_name: "삼성전자", ticker: "005930", news_limit: 3 },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 11,
      userRequest: "Search flights from SEA to JFK",
      normalizedArguments: { origin: "SEA", destination: "JFK", passengers: 1 },
      expectedOutputSummary: "Flight result list"
    })
  ]);

  assert.equal(examples.length, 2);
  assert.deepEqual(examples[0].values, {
    request: "네이버에서 삼성전자 주가 리포트",
    companyName: "삼성전자",
    ticker: "005930",
    newsLimit: 3,
    extraArguments: {}
  });
  assert.equal(examples[0].description, "Markdown stock report");
  assert.deepEqual(examples[1].values.extraArguments, {
    origin: "SEA",
    destination: "JFK",
    passengers: 1
  });
});

test("omits internal page text argument from reusable run examples", () => {
  const examples = buildArgumentExamples([
    workflowExample({
      id: 10,
      userRequest: "네이버 지도 경로",
      normalizedArguments: {
        start_station: "양재역",
        end_station: "사당역",
        page_text: "large browser evidence"
      }
    })
  ]);

  assert.deepEqual(examples[0].values.extraArguments, {
    start_station: "양재역",
    end_station: "사당역"
  });
});

test("deduplicates repeated argument examples and keeps only three distinct choices", () => {
  const examples = buildArgumentExamples([
    workflowExample({
      id: 10,
      userRequest: "네이버에서 삼성전자 주가 리포트 iter 1",
      normalizedArguments: { company_name: "삼성전자", ticker: "005930", news_limit: 1 },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 11,
      userRequest: "네이버에서 삼성전자 주가 리포트 iter 2",
      normalizedArguments: { ticker: "005930", news_limit: 1, company_name: "삼성전자" },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 15,
      userRequest: "네이버에서 삼성전자 주가 리포트 뉴스 3개",
      normalizedArguments: { ticker: "005930", news_limit: 3, company_name: "삼성전자" },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 12,
      userRequest: "네이버에서 SK하이닉스 주가 리포트",
      normalizedArguments: { company_name: "SK하이닉스", ticker: "000660", news_limit: 3 },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 13,
      userRequest: "네이버에서 NAVER 주가 리포트",
      normalizedArguments: { company_name: "NAVER", ticker: "035420", news_limit: 2 },
      expectedOutputSummary: "Markdown stock report"
    }),
    workflowExample({
      id: 14,
      userRequest: "네이버에서 카카오 주가 리포트",
      normalizedArguments: { company_name: "카카오", ticker: "035720", news_limit: 2 },
      expectedOutputSummary: "Markdown stock report"
    })
  ]);

  assert.deepEqual(
    examples.map((example) => example.values.companyName),
    ["삼성전자", "SK하이닉스", "NAVER"]
  );
  assert.equal(examples[0].values.request, "네이버에서 삼성전자 주가 리포트 iter 1");
});

test("finds the newest draft proposal for approving eval and evolve results", () => {
  const proposals = [
    proposal({ id: 3, status: "applied", updatedAt: "2026-06-09T00:03:00.000Z" }),
    proposal({ id: 4, status: "draft", updatedAt: "2026-06-09T00:04:00.000Z" }),
    proposal({ id: 5, status: "draft", updatedAt: "2026-06-09T00:05:00.000Z" })
  ];

  assert.equal(findLatestDraftProposal(proposals)?.id, 5);
});

test("validates create workflow form only when start URL task and final state are present", () => {
  assert.equal(
    canCreateWorkflow({
      startUrl: "https://www.google.com/flights",
      task: "Search flights from SEA to JFK",
      finalState: "Flight results are visible"
    }),
    true
  );
  assert.equal(
    canCreateWorkflow({
      startUrl: "   ",
      task: "Search flights from SEA to JFK",
      finalState: "Flight results are visible"
    }),
    false
  );
});

test("builds create workflow payload without domain-specific arguments and hides max attempts", () => {
  const payload = buildCreateWorkflowPayload({
    dbPath: "/tmp/workflows.sqlite",
    repoRoot: "/repo/webmcp/core",
    outputDir: "/tmp/runs",
    pythonPath: "python3",
    startUrl: " https://www.google.com/flights ",
    task: " Search flights from SEA to JFK ",
    finalState: " Flight results are visible ",
    headed: true,
    synthesizerModel: "gpt-5.5"
  });

  assert.deepEqual(payload, {
    dbPath: "/tmp/workflows.sqlite",
    repoRoot: "/repo/webmcp/core",
    outputDir: "/tmp/runs",
    pythonPath: "python3",
    startUrl: "https://www.google.com/flights",
    task: "Search flights from SEA to JFK",
    finalState: "Flight results are visible",
    maxAttempts: 10,
    headed: true,
    synthesizerModel: "gpt-5.5",
    evalBrowser: "chromium"
  });
});

test("builds visible busy and pause controls for active Python jobs", () => {
  assert.deepEqual(buildOperationControlState({ running: false, paused: false }), {
    busy: false,
    pauseResumeVisible: false,
    pauseResumeAction: "pause",
    pauseResumeLabel: "Pause current job"
  });
  assert.deepEqual(buildOperationControlState({ running: true, paused: false }), {
    busy: true,
    pauseResumeVisible: true,
    pauseResumeAction: "pause",
    pauseResumeLabel: "Pause current job"
  });
  assert.deepEqual(buildOperationControlState({ running: true, paused: true }), {
    busy: false,
    pauseResumeVisible: true,
    pauseResumeAction: "resume",
    pauseResumeLabel: "Resume current job"
  });
});

test("marks stored unfinished runs as interrupted when no app job is active", () => {
  assert.equal(
    storedRunDisplayStatus(
      {
        status: "running",
        finishedAt: null
      },
      false
    ),
    "interrupted"
  );
  assert.equal(
    storedRunDisplayStatus(
      {
        status: "running",
        finishedAt: null
      },
      true
    ),
    "running"
  );
  assert.equal(
    storedRunDisplayStatus(
      {
        status: "succeeded",
        finishedAt: "2026-06-09T00:01:00.000Z"
      },
      false
    ),
    "succeeded"
  );
});

function step(overrides: Partial<WorkflowStep>): WorkflowStep {
  return {
    id: 1,
    versionId: 1,
    orderIndex: 0,
    name: "step",
    description: "Step description",
    stepType: "goto",
    handlerRef: null,
    action: {},
    argumentBindings: {},
    assertions: {},
    fallbackPolicy: {},
    updatePolicy: {},
    ...overrides
  };
}

function proposal(overrides: Partial<WorkflowUpdateProposal>): WorkflowUpdateProposal {
  return {
    id: 1,
    skillId: 1,
    baseVersionId: 1,
    proposedVersion: 2,
    instruction: "Improve workflow",
    discoveryProvider: "none",
    synthesizerProvider: "codex",
    synthesizerModel: "gpt-5.5",
    status: "draft",
    proposedWorkflow: {},
    diff: {},
    evidence: {},
    synthesisDurationMs: null,
    error: null,
    appliedVersionId: null,
    approvedBy: null,
    createdAt: "2026-06-09T00:00:00.000Z",
    updatedAt: "2026-06-09T00:00:00.000Z",
    ...overrides
  };
}

function workflowExample(overrides: Partial<WorkflowExample>): WorkflowExample {
  return {
    id: 1,
    skillId: 1,
    userRequest: "Example request",
    normalizedArguments: {},
    expectedOutputSummary: "Expected output",
    successCount: 0,
    lastUsedAt: null,
    ...overrides
  };
}
