const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { createProjectPaths } = require("../electron/project-paths.cjs");

test("desktop resolves WebMCP core from inside the feature slice", () => {
  const appRoot = path.join("/repo", "webmcp", "apps", "desktop");
  const paths = createProjectPaths(appRoot);

  assert.equal(paths.appRoot, appRoot);
  assert.equal(paths.coreRoot, path.join("/repo", "webmcp", "core"));
  assert.equal(
    paths.defaultDbPath,
    path.join("/repo", "webmcp", "core", "outputs", "webmcp_plugin_cold_iter_check", "workflows.sqlite")
  );
  assert.equal(paths.defaultOutputDir, path.join("/repo", "webmcp", "core", "outputs", "desktop_runs"));
  assert.equal(
    paths.defaultPythonPath,
    path.join("/repo", "webmcp", "core", "reference", "webwright", ".venv", "bin", "python")
  );
});
