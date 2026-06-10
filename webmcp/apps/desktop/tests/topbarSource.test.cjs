const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const appSource = fs.readFileSync(path.join(__dirname, "..", "src", "app", "App.tsx"), "utf8");

test("topbar does not expose the SQLite DB path setting", () => {
  assert.equal(appSource.includes('<PathField label="DB"'), false);
  assert.equal(appSource.includes("function PathField("), false);
});
