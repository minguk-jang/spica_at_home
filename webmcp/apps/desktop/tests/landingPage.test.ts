import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  coreLogicStages,
  desktopTabGuides,
  landingMetricItems
} from "../src/landingPage.ts";

const mainSource = fs.readFileSync(path.join(import.meta.dirname, "..", "src", "main.tsx"), "utf8");
const stylesSource = fs.readFileSync(path.join(import.meta.dirname, "..", "src", "styles.css"), "utf8");

test("desktop starts on the landing home tab", () => {
  assert.match(mainSource, /type AppView = "home" \| "workflows" \| "jsTool" \| "memory"/);
  assert.match(mainSource, /useState<AppView>\("home"\)/);
  assert.match(mainSource, /key: "home"/);
  assert.match(mainSource, /key: "jsTool", label: "JS 도구"/);
});

test("landing page explains the core workflow lifecycle", () => {
  assert.deepEqual(
    coreLogicStages.map((stage) => stage.title),
    ["요청", "생성", "저장", "실행", "JS 변환", "평가", "메모리"]
  );
  assert.ok(coreLogicStages.every((stage) => /[가-힣]/.test(stage.summary) && /[가-힣]/.test(stage.detail)));
  assert.equal(coreLogicStages.some((stage) => /스킬/.test(`${stage.summary} ${stage.detail}`)), false);
  assert.ok(coreLogicStages.some((stage) => stage.detail.includes("Codex VLM")));
  assert.match(mainSource, /브라우저 요청에서 재사용 가능한 워크플로우까지/);
  assert.match(mainSource, /생성, 실행, 평가, 메모리가 하나의 루프로 이어집니다/);
});

test("landing page flow grid stays responsive for all core stages", () => {
  const logicDiagramBlock = stylesSource.match(/\.logicDiagram\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? "";

  assert.equal(coreLogicStages.length, 7);
  assert.match(logicDiagramBlock, /grid-template-columns:\s*repeat\(auto-fit,/);
  assert.doesNotMatch(logicDiagramBlock, /22px|minmax\(150px,\s*1fr\)/);
  assert.doesNotMatch(mainSource, /className="logicConnector"/);
});

test("landing page documents desktop tabs and primary usage", () => {
  const guideTitles = desktopTabGuides.map((guide) => guide.title);

  assert.deepEqual(guideTitles, [
    "홈(Home)",
    "워크플로우(Workflows)",
    "스텝(Steps)",
    "스크립트(Script)",
    "JS 도구(JS Tool)",
    "버전(Versions)",
    "업데이트(Update)",
    "실행 기록(Runs)",
    "메모리(Memory)"
  ]);
  assert.ok(desktopTabGuides.every((guide) => /[가-힣]/.test(guide.role) && /[가-힣]/.test(guide.usage)));
  assert.equal(landingMetricItems.length, 4);
  assert.ok(landingMetricItems.every((item) => /[가-힣]/.test(item.label) && /[가-힣]/.test(item.description)));
  assert.equal(landingMetricItems.some((item) => item.label.includes("스킬")), false);
  assert.match(mainSource, /데스크톱 탭/);
});
