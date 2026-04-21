#!/usr/bin/env python3
"""Smart PostToolUse hook for Claude Code.

Claude Code calls this script after every matched tool use and passes a
JSON payload via stdin:

    {
      "session_id": "...",
      "tool_name": "Bash",
      "tool_input": {"command": "supabase db push"},
      "tool_response": {"output": "...", "exit_code": 0, "error": ""}
    }

The old hook called memory_reflect.py with hardcoded "post-tool ok" —
every entry looked identical so content_cluster() found nothing and the
dream cycle produced zero candidates. This version:

  - reads tool_name / tool_input / tool_response from stdin
  - falls back to CLAUDE_TOOL_NAME / CLAUDE_TOOL_INPUT env vars
  - detects failures from exit codes, error fields, and stderr content
  - scores importance by domain (deploy/migrate/schema = 8, edit = 5, etc.)
  - generates a non-empty reflection the dream cycle can actually cluster on
  - calls the same log_execution / on_failure path as the rest of the harness

Drop-in for the old command in settings.json:
    "command": "python3 .agent/harness/hooks/claude_code_post_tool.py"
"""
import json, os, re, sys

# Resolve .agent/ root from this file's location:
#   __file__  = .agent/harness/hooks/claude_code_post_tool.py
#   UP 1      = .agent/harness/hooks/
#   UP 2      = .agent/harness/
#   UP 3      = .agent/
HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

sys.path.insert(0, os.path.join(AGENT_ROOT, "harness"))
sys.path.insert(0, os.path.join(AGENT_ROOT, "tools"))

from hooks.post_execution import log_execution   # noqa: E402
from hooks.on_failure import on_failure          # noqa: E402


# ---------------------------------------------------------------------------
# Importance scoring
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Importance patterns — universal core + user-configurable extras
# ---------------------------------------------------------------------------

# Patterns that are high-stakes on ANY stack.
# Rule of thumb: if getting it wrong on a project you've never seen before
# would cause data loss, a production outage, or a security incident, it
# belongs here. Service names (supabase, stripe, vercel…) do NOT belong
# here — put those in .agent/protocols/hook_patterns.json.
_UNIVERSAL_HIGH = [
    r'deploy|deployment|release|rollback',
    r'migration|migrate',
    r'schema|alter\s+table|drop\s+table|create\s+table|truncate',
    r'production|prod\b|staging\b',
    r'force.?push|push\s+--force',
    r'secret|credential',
]

# Patterns that matter but are recoverable on any stack.
_UNIVERSAL_MEDIUM = [
    r'commit|push|merge|rebase',
    r'test|spec|build|bundle|compile',
    r'install|upgrade|uninstall',
    r'delete|remove|unlink',
    r'chmod|chown|cron|systemctl',
]


def _load_user_patterns() -> tuple[list[str], list[str]]:
    """Read extra high/medium patterns from .agent/protocols/hook_patterns.json.

    Returns (high_extras, medium_extras) — lists of raw regex fragments.
    Missing file or bad JSON is silently ignored so the hook never fails
    because a config file is absent or malformed.

    The config file lives at .agent/protocols/hook_patterns.json and is
    owned entirely by the user. Add your own service names, CLI tools, and
    domain terms there — not in this file.
    """
    config_path = os.path.join(AGENT_ROOT, "protocols", "hook_patterns.json")
    if not os.path.isfile(config_path):
        return [], []
    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], []
    raw_high   = [str(p) for p in cfg.get("high_stakes",   []) if p]
    raw_medium = [str(p) for p in cfg.get("medium_stakes", []) if p]
    # Drop fragments that aren't valid standalone regex — a single typo
    # (e.g. unbalanced paren) would otherwise kill every PostToolUse
    # invocation until the config file is hand-fixed.
    return _filter_valid(raw_high), _filter_valid(raw_medium)


def _filter_valid(fragments: list[str]) -> list[str]:
    good = []
    for frag in fragments:
        try:
            re.compile(frag)
        except re.error as e:
            import sys
            print(
                f"hook_patterns.json: skipping invalid regex {frag!r}: {e}",
                file=sys.stderr,
            )
            continue
        good.append(frag)
    return good


def _build_pattern(fragments: list[str]) -> re.Pattern | None:
    """Compile fragments into a combined word-boundary pattern.
    Returns None on failure; caller decides on fallback behavior."""
    if not fragments:
        return None
    combined = r'\b(' + '|'.join(fragments) + r')\b'
    try:
        return re.compile(combined, re.IGNORECASE)
    except re.error:
        return None


def _build_with_fallback(universals: list[str],
                         user: list[str]) -> re.Pattern | None:
    """Try merging universal + user fragments. If the merged pattern fails
    to compile (one fragment like `(?i)foo` that is valid standalone, OR
    two fragments that only conflict together like duplicate named groups),
    rebuild INCREMENTALLY: add each user fragment only if it still compiles
    with everything we've kept so far. This way one bad entry doesn't
    disable every custom rule, and inter-fragment conflicts are resolved
    first-wins (deterministic)."""
    merged = _build_pattern(universals + user)
    if merged is not None or not user:
        return merged
    import sys
    surviving: list[str] = []
    for frag in user:
        if _build_pattern(universals + surviving + [frag]) is not None:
            surviving.append(frag)
        else:
            print(
                f"hook_patterns.json: fragment {frag!r} is incompatible "
                "with the rest of the pattern; dropping it.",
                file=sys.stderr,
            )
    return _build_pattern(universals + surviving)


# Build once at import time.  User patterns are merged in here so there's
# no per-call file I/O.
_user_high, _user_medium = _load_user_patterns()
_HIGH   = _build_with_fallback(_UNIVERSAL_HIGH,   _user_high)
_MEDIUM = _build_with_fallback(_UNIVERSAL_MEDIUM, _user_medium)


def _importance(tool_name: str, tool_input_str: str) -> int:
    if _HIGH and _HIGH.search(tool_input_str):
        return 9
    if tool_name in ("Edit", "MultiEdit", "Write"):
        if _MEDIUM and _MEDIUM.search(tool_input_str):
            return 6
        return 5
    if _MEDIUM and _MEDIUM.search(tool_input_str):
        return 6
    return 3


def _pain_score(importance: int, success: bool) -> int:
    """Pain score calibrated so high-importance recurring successes cross
    the dream-cycle promotion threshold (7.0).

    For a cluster of 3 high-importance successes:
      salience = recency(10) × pain(0.5) × importance(0.9) × recurrence(3) = 13.5
      → comfortably clears 7.0.

    Routine successes (importance ≤ 6) stay at pain=2 so they don't flood
    the candidate queue.
    """
    if not success:
        return 8 if importance < 9 else 10
    if importance >= 8:
        return 5  # significant success — recurring pattern should promote
    if importance >= 6:
        return 3
    return 2


# ---------------------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------------------

_ERROR_SIGNALS = re.compile(
    r'\b(error|exception|traceback|failed|failure|'
    r'denied|forbidden|unauthorized|'
    r'ENOENT|EACCES|EPERM|ECONNREFUSED|'
    r'cannot|could not|unable to|not found)\b',
    re.IGNORECASE,
)

# Patterns where the user has explicitly asked the shell to mask a non-zero
# exit PER-COMMAND. When a command uses these, exit_code=0 is NOT reliable,
# so we fall through to the generic stdout heuristic.
# Examples: `deploy || true`, `migrate || :`, `run; true`.
# Deliberately NOT matching `set +e`: it's often a temporary disable around
# `grep Error logfile; rc=$?; set -e`-style patterns where exit_code=0 IS
# still trustworthy for the actual command.
_EXIT_MASKED = re.compile(
    r'\|\|\s*(?:true|:|exit\s+0)'    # || true   ||  :   || exit 0
    r'|;\s*(?:true|:)\s*$',          # ; true    ; :  at end of command
    re.IGNORECASE,
)


_QUOTED_STRING = re.compile(
    r"'[^']*'"                      # single-quoted (no escapes in bash)
    r'|"(?:[^"\\]|\\.)*"',          # double-quoted, honoring backslash escapes
)


def _is_exit_masked(command: str) -> bool:
    """Return True if the Bash command explicitly suppresses its exit code.
    Strips single/double-quoted regions before matching so that masked-exit
    tokens inside quoted strings (e.g. `echo '... || true ...'`) don't
    produce false positives. Heredocs are not parsed; that corner case
    (text between <<EOF ... EOF lines containing || true) can still slip
    through, but is rare enough in real Bash tool use to accept."""
    if not command:
        return False
    stripped = _QUOTED_STRING.sub("", command)
    return bool(_EXIT_MASKED.search(stripped))


def _extract_bash_command(tool_input: dict) -> str:
    """Pull the Bash command string from tool_input, supporting both the
    modern `{"command": "..."}` shape and the env-var fallback `{"raw": "..."}`
    shape that `main()` constructs from `CLAUDE_TOOL_INPUT`."""
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command")
    if isinstance(cmd, str) and cmd:
        return cmd
    raw = tool_input.get("raw")
    if isinstance(raw, str) and raw:
        return raw
    return ""


def _is_success(tool_name: str, tool_input_or_resp, resp=None) -> bool:
    """Signature:
        _is_success(tool_name, tool_input, resp)   — preferred, 3-arg form
        _is_success(tool_name, resp)               — legacy 2-arg form;
                                                     wrapper detection off
    Detects failure from the tool_response dict. Conservative — only fails
    on unambiguous signals so we don't discard genuine successes."""
    # Support the legacy 2-arg call (tool_name, resp).
    if resp is None:
        tool_input: dict = {}
        resp = tool_input_or_resp
    else:
        tool_input = tool_input_or_resp if isinstance(tool_input_or_resp, dict) else {}
    return _is_success_impl(tool_name, tool_input, resp)


def _is_success_impl(tool_name: str, tool_input: dict, resp: dict) -> bool:
    """Detect failure from the tool_response dict. Conservative — only fails
    on unambiguous signals so we don't discard genuine successes."""
    if not isinstance(resp, dict):
        return True

    # Explicit error flag
    if resp.get("is_error", False):
        return False

    # Bash-specific. Classification rules, in order:
    #  1. interrupted → failure
    #  2. stderr looks like an error (length threshold differs by wrapper):
    #     - wrapped (`|| true`, `|| :`): any non-empty error-looking stderr
    #       catches masked failures, since they often emit brief messages
    #       like "build failed" or "permission denied".
    #     - unwrapped: require >30 chars to avoid tripping on benign warnings
    #  3. if exit_code is present and no wrapper override fired → trust it.
    #     Trusting exit_code=0 matters for `grep Error log`, `cat log`,
    #     `grep X || true`, and other inspections that legitimately print
    #     error-looking stdout.
    #  4. otherwise → fall through to generic stdout heuristic (handles
    #     non-Bash tools and ancient response shapes without exit_code).
    if tool_name == "Bash":
        exit_code = resp.get("exit_code")
        if resp.get("interrupted", False):
            return False
        stderr = resp.get("error", "") or resp.get("stderr", "") or ""
        command = _extract_bash_command(tool_input)
        wrapped = _is_exit_masked(command)
        if wrapped:
            # Masked exit. stderr is the best available signal; catch even
            # short messages because masked failures are often terse.
            if stderr and _ERROR_SIGNALS.search(stderr):
                return False
            # No stderr signal → trust exit_code. Prevents false-failure
            # misclassification of `grep '^Error' log || true` (benign).
            if exit_code is not None:
                return exit_code == 0
        else:
            if len(stderr) > 30 and _ERROR_SIGNALS.search(stderr):
                return False
            if exit_code is not None:
                return exit_code == 0
        # No exit_code and no stderr signal — fall through to the generic
        # stdout heuristic below.

    # Generic output error heuristic (non-Bash, or Bash without exit_code)
    output = _extract_output(resp)
    if output and _ERROR_SIGNALS.search(output[:200]):
        # Only fail if the very start of output looks like an error,
        # not just because the word "error" appears mid-output.
        first_line = output.strip().splitlines()[0] if output.strip() else ""
        if _ERROR_SIGNALS.search(first_line):
            return False

    return True


# ---------------------------------------------------------------------------
# Output extraction (handles multiple Claude Code response shapes)
# ---------------------------------------------------------------------------

def _extract_output(resp: dict) -> str:
    """Pull plain text from whatever shape tool_response comes in."""
    if not isinstance(resp, dict):
        return str(resp)[:300]

    # Shape 1: direct string fields
    for key in ("output", "stdout", "result", "text"):
        if isinstance(resp.get(key), str):
            return resp[key][:500]

    # Shape 2: content array (newer Claude Code versions)
    content = resp.get("content")
    if isinstance(content, list):
        texts = [
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        return " ".join(texts)[:500]

    # Shape 3: raw string response
    if isinstance(resp, str):
        return resp[:500]

    return ""


def _extract_error(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    for key in ("error", "stderr", "error_message"):
        v = resp.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()[:300]
    return ""


# ---------------------------------------------------------------------------
# Action label (short, searchable)
# ---------------------------------------------------------------------------

def _action_label(tool_name: str, tool_input: dict) -> str:
    """First-word summary. Ends up in the `action` field of the episodic entry."""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").strip()
        # Take first logical line, strip shell boilerplate
        first = re.sub(r"\s+", " ", cmd.split("\n")[0].split(";")[0])[:80]
        return f"bash: {first}"

    if tool_name in ("Edit", "MultiEdit"):
        path = (tool_input.get("file_path")
                or tool_input.get("path")
                or tool_input.get("new_path")
                or "?")
        return f"edit: {path}"

    if tool_name == "Write":
        path = tool_input.get("file_path") or tool_input.get("path") or "?"
        return f"write: {path}"

    if tool_name == "Read":
        path = tool_input.get("file_path") or tool_input.get("path") or "?"
        return f"read: {path}"

    if tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        pending = [t for t in todos if isinstance(t, dict)
                   and t.get("status") == "in_progress"]
        if pending:
            desc = pending[0].get("content", "")[:60]
            return f"todo-update: {desc}"
        return "todo: updated task list"

    if tool_name == "Task":
        desc = (tool_input.get("description") or "")[:60]
        return f"task: {desc}"

    if tool_name == "WebFetch":
        url = (tool_input.get("url") or "")[:60]
        return f"fetch: {url}"

    return f"tool:{tool_name}"


# ---------------------------------------------------------------------------
# Reflection generation (this is what the dream cycle clusters on)
# ---------------------------------------------------------------------------

def _reflection(tool_name: str, tool_input: dict,
                tool_response: dict, success: bool) -> str:
    """
    Produce a non-empty, content-rich reflection string. This is the most
    important field for the dream cycle — content_cluster() calls word_set()
    on it. An empty reflection means zero clustering signal.

    Rules:
      1. Describe WHAT happened in domain terms.
      2. For failures: include the command and the first error line.
      3. For high-stakes ops: include the matched keyword (deploy, migration,
         or whatever the user configured in hook_patterns.json).
      4. Keep under ~200 chars so detail field carries the rest.
    """
    parts = []
    inp_str = json.dumps(tool_input)

    # --- Bash ---
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").strip()
        short_cmd = re.sub(r"\s+", " ", cmd.split("\n")[0])[:100]

        m = _HIGH.search(cmd)
        if m:
            domain = m.group(0).lower().replace(" ", "-")
            if success:
                parts.append(f"High-stakes op completed ({domain}): {short_cmd}")
            else:
                parts.append(f"High-stakes op FAILED ({domain}): {short_cmd}")
                err = _extract_error(tool_response)
                if err:
                    parts.append(f"Error: {err[:120]}")
        elif not success:
            parts.append(f"Command failed: {short_cmd}")
            err = _extract_error(tool_response)
            if err:
                parts.append(f"Error: {err[:120]}")
        else:
            parts.append(f"Ran: {short_cmd}")

    # --- Edit ---
    elif tool_name in ("Edit", "MultiEdit"):
        path = tool_input.get("file_path") or tool_input.get("path") or "?"
        old = (tool_input.get("old_string") or "")[:50]
        new = (tool_input.get("new_string") or "")[:50]
        if old and new:
            parts.append(
                f"Edited {path}: replaced {repr(old[:30])} "
                f"with {repr(new[:30])}"
            )
        else:
            parts.append(f"Edited {path}")
        if not success:
            parts.append("Edit failed")

    # --- Write ---
    elif tool_name == "Write":
        path = tool_input.get("file_path") or tool_input.get("path") or "?"
        content = tool_input.get("content") or ""
        lines = content.count("\n") + 1 if content else 0
        parts.append(f"Wrote {path} ({lines} lines)")
        if not success:
            parts.append("Write failed")

    # --- TodoWrite ---
    elif tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        done = [t for t in todos if isinstance(t, dict)
                and t.get("status") == "completed"]
        in_prog = [t for t in todos if isinstance(t, dict)
                   and t.get("status") == "in_progress"]
        if done:
            parts.append(
                f"Completed todo: {done[-1].get('content','')[:60]}"
            )
        if in_prog:
            parts.append(
                f"Now working on: {in_prog[0].get('content','')[:60]}"
            )
        if not parts:
            parts.append(f"Updated todo list ({len(todos)} items)")

    # --- fallback ---
    else:
        status = "successfully" if success else "with failure"
        parts.append(f"Tool {tool_name} completed {status}")
        if inp_str and len(inp_str) < 80:
            parts.append(inp_str)

    return ". ".join(parts) if parts else f"Tool {tool_name} ran"


# ---------------------------------------------------------------------------
# Detail field — what went in / what came out
# ---------------------------------------------------------------------------

def _detail(tool_name: str, tool_input: dict,
            tool_response: dict, success: bool) -> str:
    """
    Stored in `detail`. More verbose than reflection. Truncated to 500 chars
    by log_execution anyway.
    """
    output = _extract_output(tool_response)
    inp_str = json.dumps(tool_input, separators=(",", ":"))[:300]

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")[:120]
        if not success:
            err = _extract_error(tool_response)
            return f"cmd={cmd!r} | exit≠0 | err={err[:200]}"
        out_snip = output[:200] if output else ""
        return f"cmd={cmd!r}" + (f" | out={out_snip}" if out_snip else "")

    return inp_str + (f" | {output[:150]}" if output else "")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # --- read payload from stdin ---
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        payload = {}

    # Fallback to env vars (older Claude Code versions, or empty stdin)
    tool_name = (
        payload.get("tool_name")
        or os.environ.get("CLAUDE_TOOL_NAME")
        or "Unknown"
    )

    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (json.JSONDecodeError, ValueError):
            tool_input = {"raw": tool_input}

    # Env-var fallback for tool_input
    if not tool_input:
        raw_input_env = os.environ.get("CLAUDE_TOOL_INPUT", "")
        if raw_input_env:
            try:
                tool_input = json.loads(raw_input_env)
            except (json.JSONDecodeError, ValueError):
                tool_input = {"raw": raw_input_env}

    tool_response = payload.get("tool_response") or {}
    if isinstance(tool_response, str):
        try:
            tool_response = json.loads(tool_response)
        except (json.JSONDecodeError, ValueError):
            tool_response = {"raw": tool_response}

    # Env-var fallback for tool_response
    if not tool_response:
        raw_resp_env = os.environ.get("CLAUDE_TOOL_RESPONSE", "")
        if raw_resp_env:
            try:
                tool_response = json.loads(raw_resp_env)
            except (json.JSONDecodeError, ValueError):
                tool_response = {"raw": raw_resp_env}

    # --- derive everything ---
    success = _is_success(tool_name, tool_input, tool_response)
    importance = _importance(tool_name, json.dumps(tool_input))
    action = _action_label(tool_name, tool_input)
    reflection = _reflection(tool_name, tool_input, tool_response, success)
    detail = _detail(tool_name, tool_input, tool_response, success)

    # --- write episodic entry ---
    pscore = _pain_score(importance, success)
    if success:
        log_execution(
            skill_name="claude-code",
            action=action,
            result=detail,
            success=True,
            reflection=reflection,
            importance=importance,
            confidence=0.7,
            pain_score=pscore,
        )
    else:
        on_failure(
            skill_name="claude-code",
            action=action,
            error=reflection,
            context=detail,
            confidence=0.7,
            importance=importance,
            pain_score=pscore,
        )


if __name__ == "__main__":
    main()
