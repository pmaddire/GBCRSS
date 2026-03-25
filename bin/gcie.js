#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const { existsSync } = require("fs");
const { join, resolve } = require("path");

function resolvePython(gcieRoot) {
  const winVenv = join(gcieRoot, ".venv", "Scripts", "python.exe");
  const nixVenv = join(gcieRoot, ".venv", "bin", "python");

  if (existsSync(winVenv)) return winVenv;
  if (existsSync(nixVenv)) return nixVenv;

  return null;
}

function tryCommand(cmd, args, env) {
  const result = spawnSync(cmd, args, { stdio: "inherit", env });
  return result.status === 0;
}

function main() {
  const args = process.argv.slice(2);
  const scriptDir = resolve(__dirname);
  const gcieRoot = process.env.GCIE_ROOT ? resolve(process.env.GCIE_ROOT) : resolve(scriptDir, "..");

  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH ? `${gcieRoot};${env.PYTHONPATH}` : gcieRoot;

  const venvPython = resolvePython(gcieRoot);
  if (venvPython) {
    process.exit(spawnSync(venvPython, ["-m", "cli.app", ...args], { stdio: "inherit", env }).status || 0);
  }

  if (tryCommand("python", ["-m", "cli.app", ...args], env)) return;
  if (tryCommand("py", ["-3", "-m", "cli.app", ...args], env)) return;

  console.error("No Python interpreter found. Create a .venv in the GCIE repo or install Python 3.11+.");
  process.exit(1);
}

main();