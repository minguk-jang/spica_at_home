const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const stylesPath = path.join(__dirname, "..", "src", "styles.css");

test("modal body remains scrollable when create workflow content exceeds viewport", () => {
  const css = readCssGraph(stylesPath);
  const modalPanelBlock = css.match(/\.modalPanel\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
  const modalBodyBlock = css.match(/\.modalBody\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";

  assert.match(modalPanelBlock, /grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)\s+auto/);
  assert.match(modalPanelBlock, /overflow:\s*hidden/);
  assert.match(modalBodyBlock, /min-height:\s*0/);
  assert.match(modalBodyBlock, /overflow:\s*auto/);
});

function readCssGraph(filePath, seen = new Set()) {
  if (seen.has(filePath)) {
    return "";
  }
  seen.add(filePath);
  const source = fs.readFileSync(filePath, "utf8");
  return source.replace(/@import\s+["'](?<specifier>[^"']+)["'];/g, (_match, specifier) => {
    return readCssGraph(path.resolve(path.dirname(filePath), specifier), seen);
  });
}
