import assert from "node:assert/strict";
import test from "node:test";

import {
  browserModeLabel,
  evolutionStatusLabel
} from "../src/features/evolve-workflow/model/evolutionDisplay.ts";

test("presents browser mode in user-facing Korean labels", () => {
  assert.equal(browserModeLabel(false), "브라우저 숨김");
  assert.equal(browserModeLabel(true), "브라우저 보기");
});

test("presents evolution statuses in Korean", () => {
  assert.equal(evolutionStatusLabel("waiting_for_repair"), "수정 대기");
  assert.equal(evolutionStatusLabel("succeeded"), "성공");
  assert.equal(evolutionStatusLabel("passed"), "통과");
  assert.equal(evolutionStatusLabel("repair_applied"), "수정 적용");
  assert.equal(evolutionStatusLabel("failed"), "실패");
  assert.equal(evolutionStatusLabel("unknown_value"), "unknown_value");
});
