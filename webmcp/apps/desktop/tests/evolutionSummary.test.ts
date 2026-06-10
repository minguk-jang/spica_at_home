import assert from "node:assert/strict";
import test from "node:test";

import {
  summarizeEvolutionJobStatus,
  summarizeEvolutionOutput
} from "../src/features/evolve-workflow/model/evolutionSummary.ts";

test("summarizes waiting-for-repair evolution output with visible artifacts", () => {
  const summary = summarizeEvolutionOutput({
    status: "waiting_for_repair",
    session_id: 12,
    workflow: "naver_stock_report",
    base_version: 3,
    current_version: 3,
    attempt_count: 1,
    repair_request_path: "/tmp/evolution/session_0012/attempt_01/repair_request.json",
    attempts: [
      {
        attempt_index: 1,
        version: 3,
        status: "failed",
        duration_ms: 1520,
        failed_step: { name: "wait_stock_card" },
        repair_request_path: "/tmp/evolution/session_0012/attempt_01/repair_request.json"
      }
    ]
  });

  assert.equal(summary.status, "waiting_for_repair");
  assert.equal(summary.sessionId, "12");
  assert.equal(summary.attemptCount, "1");
  assert.equal(summary.versionLabel, "기준 v3 -> 현재 v3");
  assert.equal(summary.latestAttemptStatus, "failed");
  assert.equal(summary.latestFailedStep, "wait_stock_card");
  assert.deepEqual(summary.artifacts, [
    {
      label: "수정 요청 파일",
      path: "/tmp/evolution/session_0012/attempt_01/repair_request.json"
    }
  ]);
});

test("summarizes successful evolution output with final report artifact", () => {
  const summary = summarizeEvolutionOutput({
    status: "succeeded",
    session_id: 15,
    workflow: "naver_stock_report",
    base_version: 2,
    final_version: 4,
    final_run_id: 99,
    attempt_count: 2,
    attempts: [
      {
        attempt_index: 1,
        version: 2,
        status: "repair_applied",
        repair_request_path: "/tmp/repair_request.json",
        repair_response_path: "/tmp/repair_response.json"
      },
      {
        attempt_index: 2,
        version: 4,
        status: "succeeded",
        duration_ms: 840,
        report_path: "/tmp/report.md"
      }
    ]
  });

  assert.equal(summary.status, "succeeded");
  assert.equal(summary.sessionId, "15");
  assert.equal(summary.versionLabel, "기준 v2 -> 최종 v4");
  assert.equal(summary.finalRunId, "99");
  assert.equal(summary.latestAttemptStatus, "succeeded");
  assert.deepEqual(summary.artifacts, [
    { label: "리포트", path: "/tmp/report.md" }
  ]);
});

test("summarizes attempt steps with evaluation text and step durations", () => {
  const summary = summarizeEvolutionOutput({
    status: "succeeded",
    session_id: 20,
    base_version: 7,
    final_version: 8,
    attempt_count: 2,
    attempts: [
      {
        attempt_index: 1,
        version: 7,
        status: "repair_applied",
        duration_ms: 1300,
        evaluation: {
          status: "failed",
          step_evaluations: [
            {
              step_name: "wait_stock_card",
              step_type: "wait_for_text",
              status: "failed",
              summary: "주가 카드가 보이지 않았습니다.",
              problems: ["현재가 텍스트 없음"],
              suggested_update: "주가 카드 대기 조건을 보강합니다.",
              failure_kind: "missing_expected_ui",
              expected_state: "네이버 증권정보 카드와 현재가 텍스트가 보여야 합니다.",
              observed_state: "검색 결과 본문에 현재가 텍스트가 없습니다.",
              repair_focus: "wait_stock_card 대기 조건",
              evidence_artifacts: ["/tmp/s1.png"]
            }
          ]
        },
        step_runs: [
          {
            step_name: "wait_stock_card",
            step_type: "wait_for_text",
            status: "failed",
            duration_ms: 0
          }
        ]
      },
      {
        attempt_index: 2,
        version: 8,
        status: "succeeded",
        duration_ms: 900,
        evaluation: {
          status: "passed",
          step_evaluations: [
            {
              step_name: "wait_stock_card",
              step_type: "wait_for_text",
              status: "passed",
              summary: "주가 카드가 확인되었습니다.",
              problems: [],
              suggested_update: ""
            }
          ]
        },
        step_runs: [
          {
            step_name: "wait_stock_card",
            step_type: "wait_for_text",
            status: "succeeded",
            duration_ms: 12
          },
          {
            step_name: "extract_stock_card",
            step_type: "run_handler",
            status: "succeeded",
            duration_ms: 24
          }
        ]
      }
    ]
  });

  assert.equal(summary.attempts.length, 2);
  assert.equal(summary.attempts[0].steps[0].name, "wait_stock_card");
  assert.equal(summary.attempts[0].steps[0].status, "failed");
  assert.equal(summary.attempts[0].steps[0].duration, "0 ms");
  assert.equal(summary.attempts[0].steps[0].summary, "주가 카드가 보이지 않았습니다.");
  assert.deepEqual(summary.attempts[0].steps[0].problems, ["현재가 텍스트 없음"]);
  assert.equal(summary.attempts[0].steps[0].failureKind, "missing_expected_ui");
  assert.equal(summary.attempts[0].steps[0].expectedState, "네이버 증권정보 카드와 현재가 텍스트가 보여야 합니다.");
  assert.equal(summary.attempts[0].steps[0].observedState, "검색 결과 본문에 현재가 텍스트가 없습니다.");
  assert.equal(summary.attempts[0].steps[0].repairFocus, "wait_stock_card 대기 조건");
  assert.equal(summary.attempts[1].steps[0].status, "passed");
  assert.equal(summary.attempts[1].steps[0].duration, "12 ms");
  assert.equal(summary.attempts[1].steps[1].name, "extract_stock_card");
  assert.equal(summary.attempts[1].steps[1].summary, "워크플로우 step 실행 완료.");
});

test("uses nested evolution status for desktop job status text", () => {
  assert.equal(
    summarizeEvolutionJobStatus({
      status: "succeeded",
      output: { status: "waiting_for_repair" }
    }),
    "waiting_for_repair"
  );

  assert.equal(
    summarizeEvolutionJobStatus({
      status: "failed",
      output: null
    }),
    "failed"
  );
});
