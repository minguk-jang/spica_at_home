const assert = require("node:assert/strict");
const test = require("node:test");

const { isElectronRuntimeFile } = require("../scripts/dev-runtime-files.cjs");

test("detects Electron runtime files that require app restart", () => {
  assert.equal(isElectronRuntimeFile("electron/main.cjs"), true);
  assert.equal(isElectronRuntimeFile("electron/preload.cjs"), true);
  assert.equal(isElectronRuntimeFile("electron/update-command.cjs"), true);
  assert.equal(isElectronRuntimeFile("electron/handler-source.cjs"), true);
});

test("ignores renderer-only files handled by Vite", () => {
  assert.equal(isElectronRuntimeFile("src/main.tsx"), false);
  assert.equal(isElectronRuntimeFile("src/styles.css"), false);
  assert.equal(isElectronRuntimeFile("vite.config.ts"), false);
});
