#!/usr/bin/env python3
"""Claude Code session-memory hook: one script, four events.

    SessionStart       inject last session summary, recent episodes, valid foresight
    UserPromptSubmit   recall lessons + episodes relevant to the prompt (≥ 3 words)
    Stop               store the turn (prompt + last_assistant_message) as an episode
    SessionEnd         write a session summary row to memory/working/sessions.jsonl

Reads the hook payload on stdin, branches on `hook_event_name`, and always
exits 0 — a broken memory hook must never block a session. Context is sent
as `hookSpecificOutput.additionalContext`; Stop and SessionEnd print nothing.
Credentials are redacted before anything is persisted.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROJECT_ROOT = os.path.dirname(AGENT_ROOT)
sys.path.insert(0, os.path.join(AGENT_ROOT, "memory"))
sys.path.insert(0, os.path.join(AGENT_ROOT, "tools"))
sys.path.insert(0, os.path.join(AGENT_ROOT, "harness"))

SESSIONS = os.path.join(AGENT_ROOT, "memory", "working", "sessions.jsonl")
RUNTIME = os.path.join(AGENT_ROOT, "runtime", "sessions")
MIN_WORDS = 3
RECENT_EPISODES = 5
RECALL_K = 3
TURN_CHARS = 2000


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _session_file(session_id):
    return os.path.join(RUNTIME, f"{session_id or 'unknown'}.json")


def _load_session(session_id):
    try:
        with open(_session_file(session_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"session_id": session_id, "started_at": _now(), "turns": 0, "first_prompt": None, "last_prompt": None}


def _save_session(state):
    os.makedirs(RUNTIME, exist_ok=True)
    path = _session_file(state.get("session_id"))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def _last_session_summary():
    try:
        with open(SESSIONS, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        return json.loads(lines[-1]) if lines else None
    except (OSError, json.JSONDecodeError, IndexError):
        return None


def _emit(event, context):
    if context and context.strip():
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}) + "\n")
        sys.stdout.flush()


def on_session_start(payload):
    import tracks
    parts = []
    last = _last_session_summary()
    if last:
        parts.append(f"Last session ({last.get('ended_at', '')[:16]}, {last.get('turn_count', 0)} turns, "
                     f"ended: {last.get('end_reason')}): {last.get('summary')}")
    eps = tracks.recent("episode", k=RECENT_EPISODES)
    if eps:
        parts.append("Recent episodes:\n" + "\n".join(f"- [{e['id']}] {e['body'].splitlines()[0][:160]}" for e in eps))
    fs = tracks.active_foresights()
    if fs:
        parts.append("Foresight (valid now):\n" + "\n".join(f"- {e['body'].splitlines()[0][:160]}" for e in fs[-5:]))
    state = _load_session(payload.get("session_id"))
    state["source"] = payload.get("source")
    _save_session(state)
    if parts:
        _emit("SessionStart", "<session-context>\n" + "\n\n".join(parts) + "\n</session-context>")


def on_user_prompt(payload):
    prompt = (payload.get("prompt") or "").strip()
    state = _load_session(payload.get("session_id"))
    state["turns"] = int(state.get("turns") or 0) + 1
    if not state.get("first_prompt"):
        state["first_prompt"] = prompt[:200]
    state["last_prompt"] = prompt[:TURN_CHARS]
    _save_session(state)
    if len(prompt.split()) < MIN_WORDS:
        return
    import tracks
    lines = []
    try:
        import recall
        top, _meta = recall.recall(prompt, top_k=RECALL_K)
        for r in top:
            lines.append(f"- lesson ({r['lexical_overlap']:.2f}): {r['claim']}")
    except Exception:
        pass
    for e in tracks.search("episode", prompt, k=RECALL_K):
        lines.append(f"- episode ({e['score']:.2f}) [{e['id']}]: {e['body'].splitlines()[0][:160]}")
    for e in tracks.search("case", prompt, k=RECALL_K):
        lines.append(f"- case ({e['score']:.2f}) [{e['id']}]: {e['body'].replace(chr(10), ' / ')[:160]}")
    if lines:
        _emit("UserPromptSubmit", "<memory-recall>\n" + "\n".join(lines) + "\n</memory-recall>")


def on_stop(payload):
    if payload.get("stop_hook_active"):
        return
    import tracks
    from _cli import redact
    state = _load_session(payload.get("session_id"))
    user = redact((state.get("last_prompt") or "").strip())
    assistant = redact((payload.get("last_assistant_message") or "").strip())
    if not user and not assistant:
        return
    body = []
    if user:
        body.append(f"**User:** {user[:TURN_CHARS]}")
    if assistant:
        body.append(f"**Assistant:** {assistant[:TURN_CHARS]}")
    tracks.append_entry("episode", "\n".join(body), {
        "session_id": payload.get("session_id"), "source": "claude-code",
        "cwd": os.path.relpath(payload.get("cwd") or PROJECT_ROOT, PROJECT_ROOT) if payload.get("cwd") else None,
    })


def on_session_end(payload):
    state = _load_session(payload.get("session_id"))
    row = {"session_id": payload.get("session_id"), "summary": (state.get("first_prompt") or "")[:200],
           "turn_count": int(state.get("turns") or 0), "end_reason": payload.get("reason"),
           "started_at": state.get("started_at"), "ended_at": _now()}
    os.makedirs(os.path.dirname(SESSIONS), exist_ok=True)
    with open(SESSIONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    try:
        os.remove(_session_file(payload.get("session_id")))
    except OSError:
        pass


HANDLERS = {"SessionStart": on_session_start, "UserPromptSubmit": on_user_prompt,
            "Stop": on_stop, "SessionEnd": on_session_end}


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    event = payload.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")
    handler = HANDLERS.get(event)
    if handler:
        handler(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never block the session
        sys.stderr.write(f"claude_code_session hook error: {exc}\n")
    sys.exit(0)
