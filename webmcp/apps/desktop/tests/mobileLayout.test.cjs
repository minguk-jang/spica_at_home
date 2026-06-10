const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const stylesPath = path.join(__dirname, "..", "src", "styles.css");

test("mobile layout keeps app section tabs compact and horizontal", () => {
  const css = readCssGraph(stylesPath);
  const mobileBlock = css.match(/@media \(max-width: 860px\) \{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";

  assert.equal(/\.appNav,[\s\S]*grid-template-columns:\s*1fr/.test(mobileBlock), false);
  assert.match(mobileBlock, /\.appNav\s*\{[\s\S]*display:\s*inline-flex/);
  assert.match(mobileBlock, /\.appNav\s*\{[\s\S]*width:\s*max-content/);
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
