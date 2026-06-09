const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  enrichHandlersWithSource,
  moduleToSourcePath
} = require("../electron/handler-source.cjs");

test("maps workflow handler modules to Python source files inside repo root", () => {
  assert.equal(
    moduleToSourcePath("/repo", "webworkflows.handlers.naver_stock"),
    path.join("/repo", "webworkflows", "handlers", "naver_stock.py")
  );
});

test("attaches handler source text from the repo", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "webmcp-handler-source-"));
  const handlerDir = path.join(tempRoot, "webworkflows", "handlers");
  fs.mkdirSync(handlerDir, { recursive: true });
  fs.writeFileSync(
    path.join(handlerDir, "naver_stock.py"),
    [
      "def extract_stock_card(*, page_text, company_name):",
      "    return {'company_name': company_name}",
      "",
      "def _helper():",
      "    return 'helper'"
    ].join("\n")
  );

  const handlers = enrichHandlersWithSource(tempRoot, [
    {
      id: 1,
      name: "naver_stock.extract_stock_card",
      module: "webworkflows.handlers.naver_stock",
      function: "extract_stock_card"
    }
  ]);

  assert.equal(handlers[0].sourcePath, path.join(handlerDir, "naver_stock.py"));
  assert.match(handlers[0].sourceText, /def extract_stock_card/);
  assert.match(handlers[0].sourceText, /def _helper/);
});
