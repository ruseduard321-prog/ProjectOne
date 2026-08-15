#!/usr/bin/env node
//
// Start the API development server through the project's own virtual
// environment, on any supported development OS.
//
// This exists because `.claude/launch.json` is tracked, shared configuration
// and its `runtimeExecutable` is a single literal string — it cannot express
// "Scripts/python.exe on Windows, bin/python everywhere else". Hardcoding
// either one encodes one contributor's machine into a file every contributor
// reads, and the other OS gets a config that cannot start.
//
// Why Node rather than a shell script: `bash` is not on PATH on a stock
// Windows machine, so a `.sh` launcher cannot be what `launch.json` invokes
// there. Node is already a hard dependency of this repository — the `web`
// entry in the same file runs `npm` — so this adds a launcher, not a
// prerequisite. `scripts/migrate.{sh,ps1}` solve the same problem with a
// per-platform pair; that shape works when a human types the command and
// chooses the right one, but `launch.json` names exactly one executable.
//
// The interpreter probe below is deliberately the same order `migrate.sh`
// already uses: Windows layout first, POSIX layout second, and a loud failure
// rather than a silent fallback to whatever `python` is on PATH. Starting the
// API against the wrong interpreter would fail later, further from the cause,
// with a missing-dependency error that says nothing about the venv.
//
// Usage: node scripts/run-api-dev.mjs [extra uvicorn args...]

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = join(repoRoot, "apps", "api");

// Windows puts the interpreter in Scripts/ and names it .exe; POSIX venvs use
// bin/. Both are checked because a repository can legitimately be developed on
// either, and neither location is a fallback for the other — they are the same
// interpreter under two layouts.
const candidates = [
  join(apiDir, ".venv", "Scripts", "python.exe"),
  join(apiDir, ".venv", "bin", "python"),
];

const python = candidates.find((candidate) => existsSync(candidate));

if (python === undefined) {
  console.error(
    [
      "error: no virtual environment found at apps/api/.venv",
      "",
      "Looked for:",
      ...candidates.map((candidate) => `  ${candidate}`),
      "",
      "Create it (see Environment Setup):",
      "  cd apps/api",
      "  py -m venv .venv                 # Windows",
      "  python3 -m venv .venv            # macOS/Linux",
      '  .venv/Scripts/python -m pip install -e ".[dev]"    # Windows',
      '  .venv/bin/python -m pip install -e ".[dev]"        # macOS/Linux',
    ].join("\n"),
  );
  process.exit(1);
}

// `-m uvicorn` rather than the uvicorn shim, matching what Environment Setup
// documents for running the API by hand. Two places describing the same
// startup should not describe it differently.
const args = [
  "-m",
  "uvicorn",
  "app.main:app",
  "--reload",
  "--port",
  "8000",
  ...process.argv.slice(2),
];

// `stdio: "inherit"` so uvicorn's output reaches the previewer's log stream
// unchanged — a wrapper that buffers or reformats its child's output makes
// startup failures harder to read than running the command directly.
const child = spawn(python, args, { cwd: apiDir, stdio: "inherit" });

child.on("error", (error) => {
  console.error(`error: failed to start ${python}: ${error.message}`);
  process.exit(1);
});

// Forward Ctrl-C and termination to the child rather than dying first and
// orphaning uvicorn holding port 8000 — the next start would then fail with an
// address-already-in-use error that looks unrelated to stopping the previous run.
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}

// Propagate the child's fate rather than always exiting 0: the previewer reads
// this process's exit code, and a wrapper that swallows a crash reports a
// healthy server that is not running. A signal death is reported as the
// conventional non-zero rather than mistaken for a clean exit.
child.on("exit", (code, signal) => {
  process.exit(signal !== null ? 1 : (code ?? 0));
});
