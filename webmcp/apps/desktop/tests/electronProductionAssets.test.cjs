const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const appRoot = path.join(__dirname, "..");

test("Vite production assets are relative for Electron loadFile", () => {
  const viteConfig = fs.readFileSync(path.join(appRoot, "vite.config.ts"), "utf8");
  const electronMain = fs.readFileSync(path.join(appRoot, "electron", "main.cjs"), "utf8");

  assert.match(electronMain, /mainWindow\.loadFile\(path\.join\(appRoot,\s*"dist",\s*"index\.html"\)\)/);
  assert.match(viteConfig, /base:\s*["']\.\/["']/);
});
