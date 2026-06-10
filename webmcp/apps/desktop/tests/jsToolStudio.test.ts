import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const desktopRoot = path.join(import.meta.dirname, "..");
const appSource = fs.readFileSync(path.join(desktopRoot, "src", "app", "App.tsx"), "utf8");
const preloadSource = fs.readFileSync(path.join(desktopRoot, "electron", "preload.cjs"), "utf8");
const typeSource = fs.readFileSync(path.join(desktopRoot, "src", "vite-env.d.ts"), "utf8");

test("workflow detail tabs expose a JavaScript tool conversion tab", () => {
  assert.match(appSource, /type TabKey = "steps" \| "script" \| "jsTool" \| "versions"/);
  assert.match(appSource, /key: "jsTool", label: "JS Tool"/);
  assert.match(appSource, /function JsToolStudio/);
  assert.match(appSource, /Workflow를 JS 도구로 변환하고 실제 입력으로 검증합니다/);
});

test("app navigation exposes JavaScript tool lab as a top-level tab", () => {
  assert.match(appSource, /type AppView = "home" \| "workflows" \| "jsTool" \| "memory"/);
  assert.match(appSource, /key: "jsTool", label: "JS 도구"/);
  assert.match(appSource, /appView === "jsTool"/);
  assert.match(appSource, /function JsToolAppView/);
});

test("create workflow sheet exposes a rough step guide editor", () => {
  assert.match(appSource, /Step guide/);
  assert.match(appSource, /Add Step/);
  assert.match(appSource, /Suggest Draft/);
  assert.match(appSource, /updateStepGuideItem/);
  assert.match(appSource, /removeStepGuideItem/);
  assert.match(appSource, /moveStepGuideItem/);
  assert.match(appSource, /duplicateStepGuideItem/);
  assert.match(appSource, /onDragStart/);
  assert.match(appSource, /onDrop/);
});

test("JavaScript tool studio presents a user-centered conversion and eval flow", () => {
  assert.match(appSource, /exportJsTool/);
  assert.match(appSource, /runJsTool/);
  assert.match(appSource, /evalJsTool/);
  assert.match(appSource, /JS 도구로 변환/);
  assert.match(appSource, /JS 도구 실행 검증/);
  assert.match(appSource, /JS 도구 Eval 분석/);
  assert.match(appSource, /Node\.js 실행 검증/);
  assert.match(appSource, /page_text/);
  assert.match(appSource, /Eval로 개선 포인트 확인/);
  assert.match(appSource, /테스트 입력 JSON/);
  assert.match(appSource, /검증할 출력 키/);
  assert.match(appSource, /변환 산출물/);
  assert.match(appSource, /원본 결과 JSON/);
  assert.match(appSource, /고급 설정/);
  assert.doesNotMatch(appSource, /Run \/ Eval/);
  assert.doesNotMatch(appSource, /Studio DB workflow version/);
  assert.doesNotMatch(appSource, /Output directory/);
  assert.doesNotMatch(appSource, /agent-browser eval/);
});

test("preload and window types expose JavaScript tool bridge methods", () => {
  assert.match(preloadSource, /suggestStepGuide: \(payload\) => ipcRenderer\.invoke\("webmcp:suggest-step-guide", payload\)/);
  assert.match(preloadSource, /exportJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:export-js-tool", payload\)/);
  assert.match(preloadSource, /runJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:run-js-tool", payload\)/);
  assert.match(preloadSource, /evalJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:eval-js-tool", payload\)/);
  assert.match(typeSource, /suggestStepGuide: \(payload: StepGuideSuggestionPayload\) => Promise<RunEvent>/);
  assert.match(typeSource, /exportJsTool: \(payload: JsToolExportPayload\) => Promise<RunEvent>/);
  assert.match(typeSource, /runJsTool: \(payload: JsToolRunPayload\) => Promise<RunEvent>/);
  assert.match(typeSource, /evalJsTool: \(payload: JsToolEvalPayload\) => Promise<RunEvent>/);
});
