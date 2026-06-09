const fs = require("fs");
const path = require("path");

function moduleToSourcePath(repoRoot, moduleName) {
  const root = path.resolve(repoRoot);
  const moduleParts = String(moduleName || "").split(".");
  if (moduleParts.some((part) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(part))) {
    return "";
  }
  const sourcePath = path.resolve(root, ...moduleParts) + ".py";
  return isPathInside(sourcePath, root) ? sourcePath : "";
}

function enrichHandlersWithSource(repoRoot, handlers) {
  if (!Array.isArray(handlers)) {
    return [];
  }
  return handlers.map((handler) => {
    const sourcePath = moduleToSourcePath(repoRoot, handler.module);
    const sourceText = sourcePath && fs.existsSync(sourcePath)
      ? fs.readFileSync(sourcePath, "utf-8")
      : "";
    return {
      ...handler,
      sourcePath,
      sourceText
    };
  });
}

function isPathInside(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

module.exports = {
  enrichHandlersWithSource,
  moduleToSourcePath
};
