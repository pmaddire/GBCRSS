#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const { existsSync } = require("fs");
const { join, resolve, delimiter } = require("path");

function run(cmd, args, env, stdio = "inherit") {
  return spawnSync(cmd, args, { stdio, env });
}

function resolveVenvPython(gcieRoot) {
  const winVenv = join(gcieRoot, ".venv", "Scripts", "python.exe");
  const nixVenv = join(gcieRoot, ".venv", "bin", "python");
  if (existsSync(winVenv)) return winVenv;
  if (existsSync(nixVenv)) return nixVenv;
  return null;
}

function createVenv(gcieRoot, env) {
  const venvDir = join(gcieRoot, ".venv");

  let r = run("py", ["-3", "-m", "venv", venvDir], env, "pipe");
  if (r.status === 0) return true;

  r = run("python", ["-m", "venv", venvDir], env, "pipe");
  return r.status === 0;
}

function installDeps(venvPython, env) {
  const deps = ["typer", "networkx", "GitPython"];
  const r = run(venvPython, ["-m", "pip", "install", "--disable-pip-version-check", "--quiet", ...deps], env);
  return r.status === 0;
}

function runCli(pythonCmd, cliArgs, env) {
  return run(pythonCmd, ["-m", "cli.app", ...cliArgs], env);
}

function main() {
  const args = process.argv.slice(2);
  const cliArgs = args.length === 0 ? ["setup", "."] : args;

  const scriptDir = resolve(__dirname);
  const gcieRoot = process.env.GCIE_ROOT ? resolve(process.env.GCIE_ROOT) : resolve(scriptDir, "..");

  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH ? `${gcieRoot}${delimiter}${env.PYTHONPATH}` : gcieRoot;

  let venvPython = resolveVenvPython(gcieRoot);
  if (!venvPython) {
    console.error("[GCIE] No local venv found. Bootstrapping Python environment...");
    if (!createVenv(gcieRoot, env)) {
      console.error("No Python interpreter found. Install Python 3.11+ and retry.");
      process.exit(1);
    }
    venvPython = resolveVenvPython(gcieRoot);
    if (!venvPython) {
      console.error("[GCIE] Failed to create .venv.");
      process.exit(1);
    }
    if (!installDeps(venvPython, env)) {
      console.error("[GCIE] Failed to install Python dependencies (typer, networkx, GitPython).");
      process.exit(1);
    }
  }

  let result = runCli(venvPython, cliArgs, env);
  if (result.status === 0) {
    process.exit(0);
  }

  const stderr = (result.stderr || "").toString();
  if (stderr.includes("No module named") || stderr.includes("ModuleNotFoundError")) {
    console.error("[GCIE] Missing Python deps detected. Installing required dependencies...");
    if (installDeps(venvPython, env)) {
      result = runCli(venvPython, cliArgs, env);
      process.exit(result.status || 0);
    }
  }

  process.exit(result.status || 1);
}

main();
