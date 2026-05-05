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
 *   - Runs `auto_dream.py` once on `session_shutdown` (process exit) so the
 *     dream cycle fires at the natural end of a work session, exactly like
 *     Claude Code's `Stop` hook. Pi's SessionShutdownEvent has no `reason`
 *     payload — earlier versions of this hook tried to filter on
 *     event.reason and rejected every event; the dream cycle never ran.
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

// Validate each fragment individually so one bad regex doesn't disable every
// custom rule. Mirrors claude_code_post_tool.py's _filter_valid + incremental
// merge so the two harnesses behave identically on malformed user patterns.
function _validFragments(frags: unknown): string[] {
  if (!Array.isArray(frags)) return [];
  const out: string[] = [];
  for (const raw of frags) {
    if (typeof raw !== "string" || !raw) continue;
    try {
      new RegExp(raw);
      out.push(raw);
    } catch {
      // Bad fragment — skip it, keep the rest.
    }
  }
  return out;
}

function _mergePattern(frags: string[]): RegExp | null {
  if (!frags.length) return null;
  // Try the merged form first; fall back to first-wins if two fragments
  // conflict only when combined (e.g., duplicate named groups).
  try {
    return new RegExp(`\\b(${frags.join("|")})\\b`, "i");
  } catch {
    const surviving: string[] = [];
    for (const frag of frags) {
      try {
        new RegExp(`\\b(${[...surviving, frag].join("|")})\\b`, "i");
        surviving.push(frag);
      } catch {
        // Drop this fragment; keep what we have.
      }
    }
    return surviving.length
      ? new RegExp(`\\b(${surviving.join("|")})\\b`, "i")
      : null;
  }
}

function _loadUserPatterns(): { high: RegExp | null; medium: RegExp | null } {
  if (!fs.existsSync(PATTERNS_CFG)) return { high: null, medium: null };
  let cfg: { high_stakes?: unknown; medium_stakes?: unknown };
  try {
    cfg = JSON.parse(fs.readFileSync(PATTERNS_CFG, "utf8"));
  } catch {
    return { high: null, medium: null };
  }
  return {
    high:   _mergePattern(_validFragments(cfg.high_stakes)),
    medium: _mergePattern(_validFragments(cfg.medium_stakes)),
  };
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
    // Pi's EditToolInput is flat: { path, oldText, newText }. There is no
    // `edits` array — that's Claude Code's MultiEdit shape.
    const oldText = (event.input as { oldText?: unknown }).oldText;
    const newText = (event.input as { newText?: unknown }).newText;
    if (typeof oldText === "string" && typeof newText === "string") {
      const old = oldText.slice(0, 40).replace(/\n/g, "↵");
      const neu = newText.slice(0, 40).replace(/\n/g, "↵");
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

// ── Commit SHA (module-level cache, invalidated on HEAD-changing bash) ──────
// Caching avoids forking git on every tool call; invalidating on commit-style
// commands keeps the recorded SHA accurate across long pi sessions where the
// user commits / merges / rebases mid-flight.

let _cachedSha: string | undefined;

// Match `git <subcommand>` where subcommand is one we know moves HEAD.
// `[^|;&]*?` allows option flags or porcelain wrappers between `git` and
// the subcommand (e.g. `git -c advice.detachedHead=false checkout main`,
// `git -C path switch dev`). The lazy quantifier + the shell-separator
// negative class keep us inside a single command — we don't want
// `git status; git commit` to match if the subcommand never reaches us.
const _SHA_INVALIDATING = /\bgit\b[^|;&]*?\b(commit|reset|checkout|switch|merge|rebase|cherry-pick|revert|pull|fetch|clone)\b/;

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

function _maybeInvalidateSha(event: ToolResultEvent): void {
  if (!isBashToolResult(event)) return;
  const cmd = event.input.command;
  if (typeof cmd === "string" && _SHA_INVALIDATING.test(cmd)) {
    _cachedSha = undefined;
  }
}

// ── Episodic write ───────────────────────────────────────────────────────────

function _appendEntry(entry: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(EPISODIC), { recursive: true });
  fs.appendFileSync(EPISODIC, JSON.stringify(entry) + "\n", "utf8");
}

// ── Auto-dream helpers ────────────────────────────────────────────────────────

// session_shutdown is fired exactly once on process exit (see pi-coding-agent
// agent-session.ts: `emit({ type: "session_shutdown" })`). The event has no
// `reason` field — earlier versions of this hook filtered on event.reason and
// rejected every event, so the dream cycle never ran. Keep this handler simple.
let _dreamRunning = false;

async function _runDream(pi: ExtensionAPI, hasUI: boolean): Promise<void> {
  if (!fs.existsSync(DREAM_SCRIPT)) return;
  // Re-entrancy guard: if pi fires session_shutdown twice during teardown
  // (or if the user opens two pi sessions that exit at the same instant in
  // the same project), only run the dream cycle once. auto_dream.py rewrites
  // AGENT_LEARNINGS.jsonl whole-file, so concurrent runs would clobber each
  // other.
  if (_dreamRunning) return;
  _dreamRunning = true;

  try {
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
      if (hasUI) {
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
  } finally {
    _dreamRunning = false;
  }
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

    // Invalidate the cached commit SHA when bash mutates HEAD so subsequent
    // entries record the post-commit SHA, not the stale session-start one.
    _maybeInvalidateSha(event);

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
  // Pi's SessionShutdownEvent fires once on process exit and carries no
  // payload (see pi-coding-agent agent-session.ts:emit({type:"session_shutdown"})).
  // Earlier versions of this hook tried to filter on event.reason — that
  // field doesn't exist, so the filter rejected every event and the dream
  // cycle never ran. Just always run.

  pi.on("session_shutdown", async (_event, ctx) => {
    await _runDream(pi, ctx.hasUI);
  });
}
