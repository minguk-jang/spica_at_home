const { spawn } = require("child_process");

function collectProcess(command, args, options) {
  return new Promise((resolve) => {
    const child = spawn(command, args, options);
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolve({ stdout, stderr: stderr || error.message, exitCode: 1 });
    });
    child.on("close", (exitCode) => {
      resolve({ stdout: stdout.trim(), stderr: stderr.trim(), exitCode });
    });
  });
}

module.exports = { collectProcess };
