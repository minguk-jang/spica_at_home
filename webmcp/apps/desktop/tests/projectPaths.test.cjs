const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { createProjectPaths, ensureDefaultDbDirectory } = require("../electron/project-paths.cjs");

test("desktop resolves WebMCP core from inside the feature slice", () => {
  const appRoot = path.join("/repo", "webmcp", "apps", "desktop");
  const paths = createProjectPaths(appRoot, { homeDir: "/Users/alice", env: {} });

  assert.equal(paths.appRoot, appRoot);
  assert.equal(paths.coreRoot, path.join("/repo", "webmcp", "core"));
  assert.equal(
    paths.defaultDbPath,
    path.join("/Users/alice", ".webmcp-studio", "db", "workflows.sqlite")
  );
  assert.equal(paths.defaultOutputDir, path.join("/repo", "webmcp", "core", "outputs", "desktop_runs"));
  assert.equal(
    paths.defaultPythonPath,
    path.join("/repo", "webmcp", "core", "reference", "webwright", ".venv", "bin", "python")
  );
});

test("desktop allows overriding the default SQLite path", () => {
  const appRoot = path.join("/repo", "webmcp", "apps", "desktop");
  const paths = createProjectPaths(appRoot, {
    homeDir: "/Users/alice",
    env: { WEBMCP_STUDIO_DB_PATH: "/tmp/custom-workflows.sqlite" }
  });

  assert.equal(paths.defaultDbPath, "/tmp/custom-workflows.sqlite");
});

test("desktop creates the default SQLite directory before first use", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "webmcp-studio-db-"));
  const dbPath = path.join(tempRoot, ".webmcp-studio", "db", "workflows.sqlite");

  ensureDefaultDbDirectory(dbPath);

  assert.equal(fs.existsSync(path.dirname(dbPath)), true);
});
