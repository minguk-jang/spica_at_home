const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const mainSource = fs.readFileSync(path.join(__dirname, "..", "src", "main.tsx"), "utf8");

test("topbar does not expose the SQLite DB path setting", () => {
  assert.equal(mainSource.includes('<PathField label="DB"'), false);
  assert.equal(mainSource.includes("function PathField("), false);
});
