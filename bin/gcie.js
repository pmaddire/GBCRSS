#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const { existsSync } = require("fs");
const { join } = require("path");

function resolvePython() {
  const cwd = process.cwd();
  const winVenv = join(cwd, ".venv", "Scripts", "python.exe");
  const nixVenv = join(cwd, ".venv", "bin", "python");

  if (existsSync(winVenv)) return winVenv;
  if (existsSync(nixVenv)) return nixVenv;

  return null;
}

function tryCommand(cmd, args) {
  const result = spawnSync(cmd, args, { stdio: "inherit" });
  return result.status === 0;
}

function main() {
  const args = process.argv.slice(2);
  const venvPython = resolvePython();

  if (venvPython) {
    process.exit(spawnSync(venvPython, ["-m", "cli.app", ...args], { stdio: "inherit" }).status || 0);
  }

  // Fallbacks
  if (tryCommand("python", ["-m", "cli.app", ...args])) return;
  if (tryCommand("py", ["-3", "-m", "cli.app", ...args])) return;

  console.error("No Python interpreter found. Create a .venv or install Python 3.11+.");
  process.exit(1);
}

main();