const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const stylesPath = path.join(__dirname, "..", "src", "styles.css");

test("mobile layout keeps app section tabs compact and horizontal", () => {
  const css = fs.readFileSync(stylesPath, "utf8");
  const mobileBlock = css.match(/@media \(max-width: 860px\) \{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";

  assert.equal(/\.appNav,[\s\S]*grid-template-columns:\s*1fr/.test(mobileBlock), false);
  assert.match(mobileBlock, /\.appNav\s*\{[\s\S]*display:\s*inline-flex/);
  assert.match(mobileBlock, /\.appNav\s*\{[\s\S]*width:\s*max-content/);
});
