import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EXTENSION_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(EXTENSION_DIR, "..", "..");
const HOOK_SCRIPT = path.join(
  PROJECT_ROOT,
  ".agent",
  "harness",
  "hooks",
  "pi_post_tool.py",
);

let warnedMissingHook = false;
let warnedMissingPython = false;
let warnedHookFailure = false;

type PythonCandidate = {
  command: string;
  args: string[];
};

function pythonCandidates(): PythonCandidate[] {
  const envPy = process.env.AGENT_PYTHON?.trim();
  const out: PythonCandidate[] = [];
  if (envPy) out.push({ command: envPy, args: [] });
  out.push({ command: "python3", args: [] });
  out.push({ command: "python", args: [] });
  out.push({ command: "py", args: ["-3"] });
  return out;
}

function tryRun(
  candidate: PythonCandidate,
  payload: Record<string, unknown>,
): Promise<"ok" | "spawn-error" | "hook-failure"> {
  return new Promise((resolve) => {
    const child = spawn(
      candidate.command,
      [...candidate.args, HOOK_SCRIPT],
      {
        cwd: PROJECT_ROOT,
        stdio: ["pipe", "ignore", "ignore"],
      },
    );
    child.on("error", () => resolve("spawn-error"));
    child.on("spawn", () => {
      child.stdin.end(JSON.stringify(payload));
    });
    child.on("close", (code) => {
      resolve(code === 0 ? "ok" : "hook-failure");
    });
  });
}

async function runHook(payload: Record<string, unknown>) {
  if (!existsSync(HOOK_SCRIPT)) return "missing-hook";
  for (const candidate of pythonCandidates()) {
    const result = await tryRun(candidate, payload);
    if (result === "ok") return "ok";
    if (result === "hook-failure") return "hook-failure";
  }
  return "missing-python";
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_result", async (event, ctx) => {
    const payload = {
      tool_name: event.toolName,
      tool_input: event.input ?? {},
      content: event.content ?? [],
      details: event.details ?? {},
      isError: event.isError ?? false,
    };

    try {
      const result = await runHook(payload);
      if (result === "missing-hook" && !warnedMissingHook) {
        warnedMissingHook = true;
        ctx.ui.notify(
          "agentic-stack pi memory hook missing; automatic episodic logging disabled.",
          "warning",
        );
      } else if (result === "missing-python" && !warnedMissingPython) {
        warnedMissingPython = true;
        ctx.ui.notify(
          "agentic-stack pi memory hook: python3/python not found; automatic episodic logging disabled.",
          "warning",
        );
      } else if (result === "hook-failure" && !warnedHookFailure) {
        warnedHookFailure = true;
        ctx.ui.notify(
          "agentic-stack pi memory hook failed; continuing without automatic episodic logging.",
          "warning",
        );
      }
    } catch {
      if (!warnedHookFailure) {
        warnedHookFailure = true;
        ctx.ui.notify(
          "agentic-stack pi memory hook failed; continuing without automatic episodic logging.",
          "warning",
        );
      }
    }
  });
}
