const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const mainSource = fs.readFileSync(path.join(__dirname, "..", "electron", "main.cjs"), "utf8");

test("electron app interrupts active WebMCP jobs before quitting", () => {
  assert.match(mainSource, /terminateCurrentProcess/);
  assert.match(mainSource, /app\.on\("before-quit"/);
});
