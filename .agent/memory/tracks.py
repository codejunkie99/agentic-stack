"""Markdown-native memory tracks: daily-log files that are the source of truth.

Two tracks, same file shape, kept apart on disk so user memory and agent
experience never blur:

    memory/episodes/episode-YYYY-MM-DD.md      user track   (what happened)
    memory/foresights/foresight-YYYY-MM-DD.md  user track   (what will matter, with a validity window)
    memory/cases/agent_case-YYYY-MM-DD.md      agent track  (intent → outcome → quality)

Every file carries YAML-compatible frontmatter (values are JSON, which is a
YAML subset) and one block per entry:

    <!-- entry:ep_20261011_00000001 -->
    <!-- meta: {"session_id": "abc", "source": "claude-code"} -->
    body...
    <!-- /entry:ep_20261011_00000001 -->

Entry ids are `<prefix>_<YYYYMMDD>_<NNNNNNNN>`; the sequence restarts each
day per file, so ids are unique per file and the join key is (file, id).
Scoping: `user_id` / `agent_id` in frontmatter,
`app_id` / `project_id` derived from the project directory and recorded in
entry meta. Nothing here calls a model; anything that needs an index
(`memory_search.py`) rebuilds it from these files.

Writes are atomic (temp file + os.replace) under an exclusive flock, so a
hook and a CLI appending at the same moment cannot interleave.
"""
import datetime
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from text import word_set  # noqa: E402

try:
    import fcntl  # POSIX
except ImportError:  # pragma: no cover
    fcntl = None

MEMORY_ROOT = os.path.abspath(os.path.dirname(__file__))
SCHEMA_VERSION = 1

# kind -> (directory, file type, id prefix, track)
KINDS = {
    "episode": ("episodes", "episode", "ep", "user"),
    "foresight": ("foresights", "foresight", "fs", "user"),
    "case": ("cases", "agent_case", "case", "agent"),
}

_ENTRY_RE = re.compile(
    r"<!-- entry:(?P<id>[A-Za-z0-9_]+) -->\n"
    r"(?:<!-- meta: (?P<meta>\{.*?\}) -->\n)?"
    r"(?P<body>.*?)\n?<!-- /entry:(?P=id) -->",
    re.DOTALL,
)


def _now(now=None):
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=datetime.timezone.utc)
    return now


def scope(root=None):
    """Scoping keys. One portable brain == one app/project pair."""
    root = root or MEMORY_ROOT
    project_dir = os.path.abspath(os.path.join(root, "..", ".."))
    return {
        "user_id": os.environ.get("AGENT_USER") or os.environ.get("USER") or "default",
        "agent_id": os.environ.get("AGENT_PROFILE") or "default",
        "app_id": os.environ.get("AGENT_APP_ID") or "agentic-stack",
        "project_id": os.environ.get("AGENT_PROJECT_ID") or os.path.basename(project_dir) or "default",
    }


def _file_for(kind, day, root):
    d, ftype, _, _ = KINDS[kind]
    return os.path.join(root or MEMORY_ROOT, d, f"{ftype}-{day}.md")


def _parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        try:
            fm[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            fm[k.strip()] = v
    return fm, text[end + 5:]


def _render_frontmatter(fm):
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {json.dumps(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class _Locked:
    """Exclusive lock on a sidecar so concurrent appenders serialize."""

    def __init__(self, path):
        self.path = path + ".lock"
        self.fd = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        if fcntl:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if fcntl:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        return False


def read_file(path):
    """Return (frontmatter, [entry dict]) for one daily-log file."""
    if not os.path.exists(path):
        return {}, []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = _parse_frontmatter(text)
    deprecated = fm.get("deprecated_entries") or {}
    entries = []
    for m in _ENTRY_RE.finditer(body):
        meta = {}
        if m.group("meta"):
            try:
                meta = json.loads(m.group("meta"))
            except json.JSONDecodeError:
                meta = {}
        eid = m.group("id")
        entries.append({
            "id": eid,
            "body": m.group("body"),
            "meta": meta,
            "date": fm.get("date"),
            "path": path,
            "deprecated_by": deprecated.get(eid),
        })
    return fm, entries


def append_entry(kind, body, meta=None, root=None, now=None):
    """Append one entry to today's file for `kind`. Returns the entry dict."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    root = root or MEMORY_ROOT
    now = _now(now)
    day = now.strftime("%Y-%m-%d")
    path = _file_for(kind, day, root)
    d, ftype, prefix, track = KINDS[kind]
    sc = scope(root)
    meta = dict(meta or {})
    meta.setdefault("time", now.isoformat())
    meta.setdefault("app_id", sc["app_id"])
    meta.setdefault("project_id", sc["project_id"])
    if track == "agent":
        meta.setdefault("agent_id", sc["agent_id"])
    with _Locked(path):
        fm, entries = read_file(path)
        if not fm:
            fm = {
                "id": f"{ftype}-{day}",
                "type": f"{ftype}_daily",
                "file_type": "daily_log",
                "schema_version": SCHEMA_VERSION,
                "track": track,
                "date": day,
                "entry_count": 0,
            }
            fm["agent_id" if track == "agent" else "user_id"] = sc["agent_id" if track == "agent" else "user_id"]
        seq = len(entries) + 1
        eid = f"{prefix}_{now.strftime('%Y%m%d')}_{seq:08d}"
        while any(e["id"] == eid for e in entries):  # defensive: never collide
            seq += 1
            eid = f"{prefix}_{now.strftime('%Y%m%d')}_{seq:08d}"
        fm["entry_count"] = len(entries) + 1
        fm["last_appended_at"] = now.isoformat()
        block = (
            f"<!-- entry:{eid} -->\n"
            f"<!-- meta: {json.dumps(meta, sort_keys=True)} -->\n"
            f"{body.strip()}\n"
            f"<!-- /entry:{eid} -->\n"
        )
        existing = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _, existing = _parse_frontmatter(f.read())
        text = _render_frontmatter(fm) + "\n" + existing.rstrip("\n") + ("\n\n" if existing.strip() else "") + block
        _atomic_write(path, text)
    return {"id": eid, "path": path, "body": body.strip(), "meta": meta, "date": day, "deprecated_by": None}


def iter_entries(kind, root=None, include_deprecated=False, agent_id=None):
    """All entries of a kind, oldest file first, file order preserved."""
    root = root or MEMORY_ROOT
    d = os.path.join(root, KINDS[kind][0])
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md"):
            continue
        fm, entries = read_file(os.path.join(d, name))
        for e in entries:
            if e["deprecated_by"] and not include_deprecated:
                continue
            if agent_id and e["meta"].get("agent_id", fm.get("agent_id")) != agent_id:
                continue
            out.append(e)
    return out


def deprecate(kind, entry_id, by_id, root=None):
    """Mark `entry_id` superseded by `by_id`. Originals are never deleted."""
    root = root or MEMORY_ROOT
    d = os.path.join(root, KINDS[kind][0])
    if not os.path.isdir(d):
        return False
    for name in sorted(os.listdir(d)):
        path = os.path.join(d, name)
        if not name.endswith(".md"):
            continue
        with _Locked(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            fm, body = _parse_frontmatter(text)
            if not any(m.group("id") == entry_id for m in _ENTRY_RE.finditer(body)):
                continue
            dep = dict(fm.get("deprecated_entries") or {})
            dep[entry_id] = by_id
            fm["deprecated_entries"] = dep
            _atomic_write(path, _render_frontmatter(fm) + body)
            return True
    return False


def _bag(text):
    return word_set(text)


def search(kind, query, k=5, root=None, agent_id=None):
    """Lexical search: fraction of query words present, ties → newest first."""
    q = _bag(query)
    rows = []
    for e in iter_entries(kind, root=root, agent_id=agent_id):
        words = _bag(e["body"] + " " + json.dumps(e["meta"]))
        score = (len(q & words) / len(q)) if q else 0.0
        if score > 0:
            rows.append((score, e))
    rows.sort(key=lambda r: (r[0], r[1]["meta"].get("time", "")), reverse=True)
    return [dict(e, score=round(s, 3)) for s, e in rows[:k]]


def recent(kind, k=5, root=None, agent_id=None):
    rows = iter_entries(kind, root=root, agent_id=agent_id)
    return list(reversed(rows[-k:]))


def active_foresights(now=None, root=None):
    """Foresight items whose validity window contains `now` (Eq. 58 style)."""
    now = _now(now)
    out = []
    for e in iter_entries("foresight", root=root):
        t0 = e["meta"].get("valid_from")
        t1 = e["meta"].get("valid_until")
        try:
            if t0 and _now(datetime.datetime.fromisoformat(t0)) > now:
                continue
            if t1 and _now(datetime.datetime.fromisoformat(t1)) < now:
                continue
        except ValueError:
            continue
        out.append(e)
    return out


def cosine(a, b):
    """Cosine between two {word: weight} bags."""
    if not a or not b:
        return 0.0
    dot = sum(w * b.get(t, 0.0) for t, w in a.items())
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


if __name__ == "__main__":  # self-check in a temp root
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, ".agent", "memory")
        os.makedirs(root)
        a = append_entry("episode", "Deployed api with supabase migration", {"session_id": "s1"}, root=root)
        b = append_entry("episode", "Fixed flaky test in auth module", {"session_id": "s1"}, root=root)
        assert a["id"].endswith("_00000001") and b["id"].endswith("_00000002")
        fm, entries = read_file(a["path"])
        assert fm["entry_count"] == 2 and fm["track"] == "user"
        assert [e["id"] for e in entries] == [a["id"], b["id"]]
        assert search("episode", "supabase migration", root=root)[0]["id"] == a["id"]
        assert deprecate("episode", a["id"], b["id"], root=root)
        assert [e["id"] for e in iter_entries("episode", root=root)] == [b["id"]]
        assert len(iter_entries("episode", root=root, include_deprecated=True)) == 2
        c = append_entry("case", "intent: x\noutcome: y", {"quality": 0.9}, root=root)
        assert c["meta"]["agent_id"] and read_file(c["path"])[0]["track"] == "agent"
        f = append_entry("foresight", "renew cert", {"valid_until": "2099-01-01T00:00:00+00:00"}, root=root)
        assert active_foresights(root=root)[0]["id"] == f["id"]
        g = append_entry("foresight", "old", {"valid_until": "2000-01-01T00:00:00+00:00"}, root=root)
        assert all(e["id"] != g["id"] for e in active_foresights(root=root))
        assert abs(cosine({"a": 1.0}, {"a": 2.0}) - 1.0) < 1e-9
    print("ok")
