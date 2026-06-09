const path = require("path");
const os = require("os");
const fs = require("fs");

function createProjectPaths(appRoot, options = {}) {
  const env = options.env || process.env;
  const homeDir = options.homeDir || os.homedir();
  const coreRoot = path.resolve(appRoot, "..", "..", "core");
  return {
    appRoot,
    coreRoot,
    defaultDbPath: resolveDefaultDbPath({ env, homeDir }),
    defaultOutputDir: path.join(coreRoot, "outputs", "desktop_runs"),
    defaultPythonPath: path.join(coreRoot, "reference", "webwright", ".venv", "bin", "python")
  };
}

function resolveDefaultDbPath({ env = process.env, homeDir = os.homedir() } = {}) {
  if (env.WEBMCP_STUDIO_DB_PATH) {
    return expandHome(env.WEBMCP_STUDIO_DB_PATH, homeDir);
  }
  return path.join(homeDir, ".webmcp-studio", "db", "workflows.sqlite");
}

function expandHome(targetPath, homeDir) {
  if (targetPath === "~") {
    return homeDir;
  }
  if (targetPath.startsWith(`~${path.sep}`)) {
    return path.join(homeDir, targetPath.slice(2));
  }
  return targetPath;
}

function ensureDefaultDbDirectory(dbPath) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true, mode: 0o700 });
}

module.exports = { createProjectPaths, ensureDefaultDbDirectory, resolveDefaultDbPath };
