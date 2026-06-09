const path = require("path");

function createProjectPaths(appRoot) {
  const coreRoot = path.resolve(appRoot, "..", "..", "core");
  return {
    appRoot,
    coreRoot,
    defaultDbPath: path.join(coreRoot, "outputs", "webmcp_plugin_cold_iter_check", "workflows.sqlite"),
    defaultOutputDir: path.join(coreRoot, "outputs", "desktop_runs"),
    defaultPythonPath: path.join(coreRoot, "reference", "webwright", ".venv", "bin", "python")
  };
}

module.exports = { createProjectPaths };
