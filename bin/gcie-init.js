#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const { resolve } = require("path");

function runGcie(args) {
  const scriptDir = resolve(__dirname);
  const gcieBin = resolve(scriptDir, "gcie.js");
  const result = spawnSync(process.execPath, [gcieBin, ...args], { stdio: "inherit" });
  return result.status || 0;
}

function main() {
  const userArgs = process.argv.slice(2);
  const setupArgs = ["setup", ".", ...userArgs];
  process.exit(runGcie(setupArgs));
}

main();
