/**
 * memory-hook.ts — agentic-stack episodic logger for Pi Coding Agent
 *
 * Pi has no settings.json hook file like Claude Code, but it has a full
 * TypeScript extension system. This extension:
 *
 *   - Listens to `tool_result` and writes episodic entries to
 *     AGENT_LEARNINGS.jsonl after bash / edit / write calls (same signals
 *     Claude Code's PostToolUse hook captures — read/find/ls are noise and
 *     are intentionally skipped).
 *   - Runs `auto_dream.py` on session shutdown (quit / new session / resume)
 *     so the dream cycle fires at the natural end of a work session, exactly
 *     as Claude Code's `Stop` hook does.
 *
 * Place: .pi/extensions/memory-hook.ts  (project-local, auto-discovered)
 * Reload: /reload inside pi, or restart pi.
 *
 * Design decisions
 * ─────────────────
 * • process.cwd() for all paths — avoids import.meta.url which jiti can
 *   leave undefined in CJS-transform mode.
 * • All scoring / reflection logic is inline TypeScript — no Python
 *   subprocess per tool call, no spawn overhead, no timeout complexity.
 * • Direct fs.appendFileSync — single atomic write per entry; POSIX
 *   O_APPEND is atomic for payloads < PIPE_BUF (typically 4 KB). Entries
 *   are well under that limit.
 */

import type {
  ExtensionAPI,
  ToolResultEvent,
} from "@mariozechner/pi-coding-agent";
import {
  isBashToolResult,
  isEditToolResult,
  isWriteToolResult,
} from "@mariozechner/pi-coding-agent";
import * as fs from "node:fs";
import * as path from "node:path";
import { execSync } from "node:child_process";

// ── Paths ────────────────────────────────────────────────────────────────────

const CWD        = process.cwd();
const AGENT_ROOT = path.join(CWD, ".agent");
const EPISODIC   = path.join(AGENT_ROOT, "memory", "episodic", "AGENT_LEARNINGS.jsonl");
const DREAM_SCRIPT = path.join(AGENT_ROOT, "memory", "auto_dream.py");
const PATTERNS_CFG = path.join(AGENT_ROOT, "protocols", "hook_patterns.json");

// ── Importance patterns ───────────────────────────────────────────────────────
// Mirrors claude_code_post_tool.py's _UNIVERSAL_HIGH / _UNIVERSAL_MEDIUM so
// both harnesses score identically.

const HIGH_RE = /\b(deploy(?:ment)?|release|rollback|migrat(?:e|ion)|schema|alter\s+table|drop\s+table|create\s+table|truncate|prod(?:uction)?|staging|force.?push|push\s+--force|secret|credential)\b/i;
const MED_RE  = /\b(commit|push|merge|rebase|test|spec|build|bundle|compile|install|upgrade|uninstall|delete|remove|unlink|chmod|chown|cron|systemctl)\b/i;

function _loadUserPatterns(): { high: RegExp | null; medium: RegExp | null } {
  if (!fs.existsSync(PATTERNS_CFG)) return { high: null, medium: null };
  try {
    const cfg = JSON.parse(fs.readFileSync(PATTERNS_CFG, "utf8"));
    const toRe = (frags: string[]) =>
      frags.length ? new RegExp(`\\b(${frags.join("|")})\\b`, "i") : null;
    return {
      high:   toRe((cfg.high_stakes   ?? []).filter(Boolean)),
      medium: toRe((cfg.medium_stakes ?? []).filter(Boolean)),
    };
  } catch {
    return { high: null, medium: null };
  }
}

const { high: userHigh, medium: userMed } = _loadUserPatterns();

function _importance(toolName: string, subject: string): number {
  if (HIGH_RE.test(subject) || userHigh?.test(subject)) return 9;
  if (toolName === "edit" || toolName === "write") {
    return MED_RE.test(subject) || userMed?.test(subject) ? 6 : 5;
  }
  if (MED_RE.test(subject) || userMed?.test(subject)) return 6;
  return 3;
}

function _painScore(importance: number, success: boolean): number {
  if (!success) return importance >= 9 ? 10 : 8;
  if (importance >= 8) return 5;
  if (importance >= 6) return 3;
  return 2;
}

// ── Action label ─────────────────────────────────────────────────────────────

function _actionLabel(event: ToolResultEvent): string {
  if (isBashToolResult(event)) {
    const cmd = event.input.command.replace(/\s+/g, " ").slice(0, 80);
    return `bash: ${cmd}`;
  }
  if (isEditToolResult(event)) return `edit: ${event.input.path}`;
  if (isWriteToolResult(event)) return `write: ${event.input.path}`;
  return `tool:${event.toolName}`;
}

// ── Reflection (what the dream cycle clusters on) ────────────────────────────

function _reflection(event: ToolResultEvent, success: boolean): string {
  if (isBashToolResult(event)) {
    const cmd = event.input.command.replace(/\s+/g, " ").slice(0, 100);
    const m = HIGH_RE.exec(cmd) ?? userHigh?.exec(cmd);
    if (m) {
      const domain = m[0].toLowerCase().replace(/\s+/g, "-");
      return success
        ? `High-stakes bash completed (${domain}): ${cmd}`
        : `High-stakes bash FAILED (${domain}): ${cmd}`;
    }
    return success ? `Ran: ${cmd}` : `Command failed: ${cmd}`;
  }

  if (isEditToolResult(event)) {
    const p = event.input.path;
    if (!success) return `Edit failed on ${p}`;
    const first = event.input.edits?.[0];
    if (first) {
      const old = first.oldText.slice(0, 40).replace(/\n/g, "↵");
      const neu = first.newText.slice(0, 40).replace(/\n/g, "↵");
      return `Edited ${p}: replaced '${old}' with '${neu}'`;
    }
    return `Edited ${p}`;
  }

  if (isWriteToolResult(event)) {
    const p = event.input.path;
    return success ? `Wrote ${p}` : `Write failed on ${p}`;
  }

  return `Tool ${event.toolName} ${success ? "completed" : "failed"}`;
}

// ── Commit SHA (module-level cache) ──────────────────────────────────────────

let _cachedSha: string | undefined;

function _commitSha(): string {
  if (_cachedSha !== undefined) return _cachedSha;
  try {
    _cachedSha = execSync("git rev-parse HEAD", {
      cwd: CWD,
      timeout: 2000,
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
  } catch {
    _cachedSha = "";
  }
  return _cachedSha;
}

// ── Episodic write ───────────────────────────────────────────────────────────

function _appendEntry(entry: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(EPISODIC), { recursive: true });
  fs.appendFileSync(EPISODIC, JSON.stringify(entry) + "\n", "utf8");
}

// ── Auto-dream helpers ────────────────────────────────────────────────────────

// Reasons that represent an actual end-of-session (mirrors Claude Code Stop hook).
// "reload" = dev reloading extensions; "fork" = branch checkpoint mid-session.
// Neither should flush the dream cycle.
const DREAM_REASONS = new Set(["quit", "new", "resume"]);

async function _runDream(pi: ExtensionAPI, hasUI: boolean): Promise<void> {
  if (!fs.existsSync(DREAM_SCRIPT)) return;

  // Try python3 then python — mirrors the TypeScript hook's pythonCandidates()
  // from the old subprocess approach, kept here for Windows / pyenv compat.
  for (const py of ["python3", "python"]) {
    try {
      const { code, stderr } = await pi.exec(py, [DREAM_SCRIPT], {
        cwd: CWD,
        timeout: 30_000,
      });
      if (code === 0) return;
      // Non-zero exit from python (not a spawn error): surface once and bail.
      if (hasUI && code !== null) {
        const firstLine = (stderr ?? "").split(/\r?\n/)[0] || `exit ${code}`;
        pi.sendMessage({
          customType: "agentic-stack",
          content: `dream cycle failed: ${firstLine}`,
          display: true,
        });
      }
      return;
    } catch {
      // spawn error for this candidate → try next
    }
  }
  // Both candidates failed to spawn — python not on PATH, silently skip.
}

// ── Extension entry point ────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {

  // ── tool_result: episodic logging ────────────────────────────────────────

  pi.on("tool_result", (_event, _ctx) => {
    const event = _event;

    // Only log the three tool types that carry meaningful signal.
    // read / find / ls / grep are noise — same filter as Claude Code's
    // "^(Bash|Edit|Write)$" PostToolUse matcher.
    if (
      !isBashToolResult(event) &&
      !isEditToolResult(event) &&
      !isWriteToolResult(event)
    ) return;

    const success = !event.isError;

    // Subject string for pattern matching.
    const subject = isBashToolResult(event)
      ? event.input.command
      : (event as { input: { path: string } }).input.path;

    const imp = _importance(event.toolName, subject);

    // Skip routine low-importance bash successes (grep, ls, cat, echo, etc.)
    // to keep the episodic log signal-rich. Failures always get logged so
    // the failure-threshold rewrite flag fires correctly.
    if (event.toolName === "bash" && imp <= 3 && success) return;

    const entry: Record<string, unknown> = {
      timestamp:   new Date().toISOString(),
      skill:       "pi",
      action:      _actionLabel(event).slice(0, 200),
      result:      success ? "success" : "failure",
      detail:      subject.slice(0, 500),
      pain_score:  _painScore(imp, success),
      importance:  imp,
      reflection:  _reflection(event, success),
      confidence:  0.7,
      source: {
        skill:      "pi",
        run_id:     `pi-${process.pid}`,
        commit_sha: _commitSha(),
      },
      evidence_ids: [],
    };

    try {
      _appendEntry(entry);
    } catch {
      // Never let a memory write crash pi.
    }
  });

  // ── session_shutdown: dream cycle ────────────────────────────────────────

  pi.on("session_shutdown", async (event, ctx) => {
    if (!DREAM_REASONS.has(event.reason)) return;
    await _runDream(pi, ctx.hasUI);
  });
}
