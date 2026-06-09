import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const desktopRoot = path.join(import.meta.dirname, "..");
const mainSource = fs.readFileSync(path.join(desktopRoot, "src", "main.tsx"), "utf8");
const preloadSource = fs.readFileSync(path.join(desktopRoot, "electron", "preload.cjs"), "utf8");
const typeSource = fs.readFileSync(path.join(desktopRoot, "src", "vite-env.d.ts"), "utf8");

test("workflow detail tabs expose a JavaScript tool conversion tab", () => {
  assert.match(mainSource, /type TabKey = "steps" \| "script" \| "jsTool" \| "versions"/);
  assert.match(mainSource, /key: "jsTool", label: "JS Tool"/);
  assert.match(mainSource, /function JsToolStudio/);
  assert.match(mainSource, /도구를 JavaScript로 변환하고 테스트/);
});

test("app navigation exposes JavaScript tool lab as a top-level tab", () => {
  assert.match(mainSource, /type AppView = "home" \| "workflows" \| "jsTool" \| "memory"/);
  assert.match(mainSource, /key: "jsTool", label: "JS 도구"/);
  assert.match(mainSource, /appView === "jsTool"/);
  assert.match(mainSource, /function JsToolAppView/);
});

test("JavaScript tool studio includes export run and eval controls", () => {
  assert.match(mainSource, /exportJsTool/);
  assert.match(mainSource, /runJsTool/);
  assert.match(mainSource, /evalJsTool/);
  assert.match(mainSource, /Export JS tool/);
  assert.match(mainSource, /Run JS tool/);
  assert.match(mainSource, /Eval JS tool/);
  assert.match(mainSource, /required output/i);
});

test("preload and window types expose JavaScript tool bridge methods", () => {
  assert.match(preloadSource, /exportJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:export-js-tool", payload\)/);
  assert.match(preloadSource, /runJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:run-js-tool", payload\)/);
  assert.match(preloadSource, /evalJsTool: \(payload\) => ipcRenderer\.invoke\("webmcp:eval-js-tool", payload\)/);
  assert.match(typeSource, /exportJsTool: \(payload: JsToolExportPayload\) => Promise<RunEvent>/);
  assert.match(typeSource, /runJsTool: \(payload: JsToolRunPayload\) => Promise<RunEvent>/);
  assert.match(typeSource, /evalJsTool: \(payload: JsToolEvalPayload\) => Promise<RunEvent>/);
});
