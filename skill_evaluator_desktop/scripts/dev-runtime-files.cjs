const path = require("path");

function isElectronRuntimeFile(filePath) {
  const normalized = filePath.split(path.sep).join("/");
  return /^electron\/[^/]+\.cjs$/.test(normalized);
}

module.exports = { isElectronRuntimeFile };
