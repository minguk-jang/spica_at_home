const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const srcRoot = path.join(__dirname, "..", "src");
const layerRank = {
  app: 6,
  pages: 5,
  widgets: 4,
  features: 3,
  entities: 2,
  shared: 1
};

test("renderer source is organized into Feature-Sliced Design layers", () => {
  for (const layer of Object.keys(layerRank)) {
    assert.equal(fs.existsSync(path.join(srcRoot, layer)), true, `${layer} layer is missing`);
  }

  const mainSource = readSource("main.tsx");
  assert.ok(mainSource.split(/\r?\n/).length < 60, "main.tsx should only bootstrap the renderer");
  assert.match(mainSource, /from "\.\/app"/);

  const appSource = readSource(path.join("app", "App.tsx"));
  assert.match(appSource, /export function App\(/);
});

test("legacy flat renderer modules are moved behind FSD public APIs", () => {
  const legacyFiles = [
    "activeJob.ts",
    "evolutionDisplay.ts",
    "evolutionSummary.ts",
    "jsToolDefaults.ts",
    "landingPage.ts",
    "runControlFields.ts",
    "runResultSummary.ts",
    "updateModeOptions.ts",
    "workflowDashboard.ts",
    "workflowDetailDefaults.ts"
  ];

  for (const legacyFile of legacyFiles) {
    assert.equal(fs.existsSync(path.join(srcRoot, legacyFile)), false, `${legacyFile} should not remain at src root`);
  }
});

test("FSD imports do not point from lower layers to higher layers", () => {
  const violations = [];
  for (const filePath of sourceFiles(srcRoot)) {
    const fromLayer = layerFor(filePath);
    if (!fromLayer) {
      continue;
    }
    const source = fs.readFileSync(filePath, "utf8");
    for (const specifier of relativeImports(source)) {
      const resolved = resolveImport(filePath, specifier);
      const toLayer = resolved ? layerFor(resolved) : null;
      if (!toLayer || fromLayer === toLayer) {
        continue;
      }
      if (layerRank[fromLayer] < layerRank[toLayer]) {
        violations.push(`${relative(filePath)} imports higher layer ${toLayer}: ${specifier}`);
      }
    }
  }

  assert.deepEqual(violations, []);
});

function readSource(relativePath) {
  return fs.readFileSync(path.join(srcRoot, relativePath), "utf8");
}

function sourceFiles(root) {
  const result = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      result.push(...sourceFiles(fullPath));
    } else if (/\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith(".d.ts")) {
      result.push(fullPath);
    }
  }
  return result;
}

function layerFor(filePath) {
  const relativePath = path.relative(srcRoot, filePath).split(path.sep);
  return layerRank[relativePath[0]] ? relativePath[0] : null;
}

function relative(filePath) {
  return path.relative(srcRoot, filePath).split(path.sep).join("/");
}

function relativeImports(source) {
  return [...source.matchAll(/from\s+["'](\.{1,2}\/[^"']+)["']/g)].map((match) => match[1]);
}

function resolveImport(fromFile, specifier) {
  const basePath = path.resolve(path.dirname(fromFile), specifier);
  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    path.join(basePath, "index.ts"),
    path.join(basePath, "index.tsx")
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}
