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

// Timeout for the Python child. If the hook hangs (bad import, stuck I/O),
// Pi's tool_result handler stays blocked because the extension awaits
// runHook(). Override via $AGENT_HOOK_TIMEOUT_MS for slow machines.
const HOOK_TIMEOUT_MS = (() => {
  const raw = process.env.AGENT_HOOK_TIMEOUT_MS?.trim();
  const n = raw ? Number.parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : 3000;
})();

let warnedMissingHook = false;
let warnedMissingPython = false;
let warnedHookFailure = false;
let warnedHookTimeout = false;

type PythonCandidate = {
  command: string;
  args: string[];
};

type HookResult =
  | { kind: "ok" }
  | { kind: "spawn-error" }
  | { kind: "hook-failure"; stderr: string; exitCode: number | null }
  | { kind: "timeout" };

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
): Promise<HookResult> {
  return new Promise((resolve) => {
    let settled = false;
    const settle = (r: HookResult) => {
      if (settled) return;
      settled = true;
      resolve(r);
    };

    let stderrBuf = "";
    const child = spawn(
      candidate.command,
      [...candidate.args, HOOK_SCRIPT],
      {
        cwd: PROJECT_ROOT,
        // Capture stderr so a "hook-failure" notification can include
        // the actual error instead of being undiagnosable.
        stdio: ["pipe", "ignore", "pipe"],
      },
    );

    const timer = setTimeout(() => {
      try { child.kill("SIGKILL"); } catch { /* already dead */ }
      settle({ kind: "timeout" });
    }, HOOK_TIMEOUT_MS);

    child.on("error", () => {
      clearTimeout(timer);
      settle({ kind: "spawn-error" });
    });
    child.on("spawn", () => {
      try {
        child.stdin.end(JSON.stringify(payload));
      } catch {
        // stdin closed before we could write — handled by close/error
      }
    });
    if (child.stderr) {
      child.stderr.setEncoding("utf8");
      child.stderr.on("data", (chunk: string) => {
        // bound stderr buffer to avoid memory blowup on a wedged hook
        if (stderrBuf.length < 4096) stderrBuf += chunk;
      });
    }
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) {
        settle({ kind: "ok" });
      } else {
        settle({ kind: "hook-failure", stderr: stderrBuf.trim(), exitCode: code });
      }
    });
  });
}

async function runHook(
  payload: Record<string, unknown>,
): Promise<
  | "ok"
  | "missing-hook"
  | "missing-python"
  | "timeout"
  | { kind: "hook-failure"; stderr: string; exitCode: number | null }
> {
  if (!existsSync(HOOK_SCRIPT)) return "missing-hook";
  for (const candidate of pythonCandidates()) {
    const result = await tryRun(candidate, payload);
    if (result.kind === "ok") return "ok";
    if (result.kind === "timeout") return "timeout";
    if (result.kind === "hook-failure") return result;
    // spawn-error → try the next python candidate
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
      } else if (result === "timeout" && !warnedHookTimeout) {
        warnedHookTimeout = true;
        ctx.ui.notify(
          `agentic-stack pi memory hook timed out (>${HOOK_TIMEOUT_MS}ms); subsequent calls may be skipped. Override with $AGENT_HOOK_TIMEOUT_MS.`,
          "warning",
        );
      } else if (
        typeof result === "object" &&
        result.kind === "hook-failure" &&
        !warnedHookFailure
      ) {
        warnedHookFailure = true;
        // Surface the first line of stderr so the failure is diagnosable.
        const firstLine = result.stderr.split(/\r?\n/, 1)[0] || `(exit ${result.exitCode})`;
        ctx.ui.notify(
          `agentic-stack pi memory hook failed: ${firstLine}`,
          "warning",
        );
      }
    } catch {
      if (!warnedHookFailure) {
        warnedHookFailure = true;
        ctx.ui.notify(
          "agentic-stack pi memory hook errored unexpectedly; continuing without automatic episodic logging.",
          "warning",
        );
      }
    }
  });
}
