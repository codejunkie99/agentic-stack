"""Agent state, terminal dashboard. One command, everything that matters.

    python3 .agent/tools/show.py

Designed to be screenshot-worthy: colored, boxed, spark-graphed, width-aware.
Zero deps (stdlib only). Respects NO_COLOR env var. Runs in any terminal
that understands ANSI.

Panels:
  - MEMORY      episodes, size, recent failures, last dream cycle
  - LESSONS     accepted + provisional, with claims
  - CANDIDATES  staged / graduated / rejected lifecycle
  - SKILLS      loaded + any flagged for rewrite
  - ACTIVITY    episodic entries per day, sparkline

Use --json for programmatic consumption, --plain to disable ANSI.
"""
import argparse, datetime, json, os, shutil, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

EPISODIC = os.path.join(BASE, "memory/episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(BASE, "memory/candidates")
LESSONS_JSONL = os.path.join(BASE, "memory/semantic/lessons.jsonl")
LESSONS_MD = os.path.join(BASE, "memory/semantic/LESSONS.md")
DREAM_LOG = os.path.join(BASE, "memory/dream.log")
MANIFEST = os.path.join(BASE, "skills/_manifest.jsonl")
VERSION_FILE = os.path.join(BASE, "..", "VERSION")


# ── ANSI color primitives ──────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_MAGENTA = "\033[95m"


_USE_COLOR = True


def _disable_color():
    global _USE_COLOR
    _USE_COLOR = False


def paint(text, *codes):
    if not _USE_COLOR or not codes:
        return text
    return "".join(codes) + text + C.RESET


def _visible_len(s):
    """Length of a string ignoring ANSI escapes."""
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            # skip to the next 'm'
            j = s.find("m", i)
            if j == -1:
                i += 1
            else:
                i = j + 1
        else:
            out += 1
            i += 1
    return out


# ── Data collection ────────────────────────────────────────────────────────

def _human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _human_age(ts_iso):
    try:
        t = datetime.datetime.fromisoformat(ts_iso)
    except (TypeError, ValueError):
        return "unknown"
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - t
    if delta.days >= 7:
        return f"{delta.days // 7}w ago"
    if delta.days >= 1:
        return f"{delta.days}d ago"
    h = delta.seconds // 3600
    if h >= 1:
        return f"{h}h ago"
    m = delta.seconds // 60
    if m >= 1:
        return f"{m}m ago"
    return "just now"


def _load_episodic():
    if not os.path.exists(EPISODIC):
        return []
    out = []
    for line in open(EPISODIC):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _daily_counts(entries, days=14):
    """Return list of (date_str, count) for the last `days` days, oldest first.

    Buckets on UTC dates so the activity graph aligns with the UTC
    timestamps every writer now emits.
    """
    today = datetime.datetime.now(datetime.timezone.utc).date()
    buckets = {today - datetime.timedelta(days=i): 0 for i in range(days)}
    for e in entries:
        ts = e.get("timestamp", "")
        try:
            parsed = datetime.datetime.fromisoformat(ts)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        d = parsed.astimezone(datetime.timezone.utc).date()
        if d in buckets:
            buckets[d] += 1
    return [(d, buckets[d]) for d in sorted(buckets)]


def _sparkline(counts):
    """Render a unicode-block sparkline from a list of ints."""
    if not counts:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    m = max(counts)
    if m == 0:
        return blocks[0] * len(counts)
    out = []
    for v in counts:
        idx = int(round((v / m) * (len(blocks) - 1)))
        out.append(blocks[idx])
    return "".join(out)


def _bar(n, total, width=20):
    """Filled/empty bar using block glyphs."""
    if total <= 0:
        return " " * width
    filled = max(0, min(width, int(round((n / total) * width))))
    return "█" * filled + "░" * (width - filled)


def episodic_stats():
    entries = _load_episodic()
    failures_14d = 0
    latest = None
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)
    for e in entries:
        ts = e.get("timestamp", "")
        if ts > (latest or ""):
            latest = ts
        if e.get("result") == "failure":
            try:
                parsed = datetime.datetime.fromisoformat(ts)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                if parsed > cutoff:
                    failures_14d += 1
            except ValueError:
                pass
    daily = _daily_counts(entries, days=14)
    return {
        "count": len(entries),
        "size": os.path.getsize(EPISODIC) if os.path.exists(EPISODIC) else 0,
        "failures_14d": failures_14d,
        "latest": latest,
        "daily": daily,
    }


def candidate_stats():
    def _count(d):
        if not os.path.isdir(d):
            return 0
        return sum(1 for f in os.listdir(d) if f.endswith(".json"))
    return {
        "staged": _count(CANDIDATES),
        "graduated": _count(os.path.join(CANDIDATES, "graduated")),
        "rejected": _count(os.path.join(CANDIDATES, "rejected")),
    }


def lesson_stats():
    out = {"count": 0, "provisional": 0, "accepted": [],
           "from_md_fallback": False}
    if os.path.exists(LESSONS_JSONL):
        for line in open(LESSONS_JSONL):
            line = line.strip()
            if not line:
                continue
            try:
                l = json.loads(line)
            except json.JSONDecodeError:
                continue
            out["count"] += 1
            if l.get("status") == "provisional":
                out["provisional"] += 1
            elif l.get("status") == "accepted":
                out["accepted"].append(l)
    elif os.path.exists(LESSONS_MD):
        out["from_md_fallback"] = True
        for line in open(LESSONS_MD):
            s = line.strip()
            if s.startswith("- ") and len(s) > 2 and not s.startswith("- #"):
                out["count"] += 1
    return out


def skill_stats():
    if not os.path.exists(MANIFEST):
        return {"count": 0, "names": []}
    names = []
    for line in open(MANIFEST):
        line = line.strip()
        if not line:
            continue
        try:
            names.append(json.loads(line).get("name", "?"))
        except json.JSONDecodeError:
            continue
    return {"count": len(names), "names": names}


def last_dream_cycle():
    if not os.path.exists(DREAM_LOG):
        return None
    # UTC so _human_age (which now compares against UTC) reads it correctly.
    return datetime.datetime.fromtimestamp(
        os.path.getmtime(DREAM_LOG), tz=datetime.timezone.utc).isoformat()


def failing_skills(threshold=3, window_days=14):
    if not os.path.exists(EPISODIC):
        return []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=window_days)
    by_skill = {}
    for e in _load_episodic():
        if e.get("result") != "failure":
            continue
        try:
            parsed = datetime.datetime.fromisoformat(e.get("timestamp", ""))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            if parsed <= cutoff:
                continue
        except ValueError:
            continue
        s = e.get("skill", "?")
        by_skill[s] = by_skill.get(s, 0) + 1
    return sorted([(s, n) for s, n in by_skill.items() if n >= threshold],
                  key=lambda x: -x[1])


def _version():
    if not os.path.exists(VERSION_FILE):
        return ""
    try:
        return open(VERSION_FILE).read().strip()
    except OSError:
        return ""


# ── Rendering ──────────────────────────────────────────────────────────────

def _boxed(title, lines, width, accent=C.CYAN):
    """Wrap content in a rounded box with a titled top edge."""
    title_str = f" {title} " if title else ""
    top_fill = "─" * max(0, width - 2 - len(title_str))
    top = paint("╭─", accent) + paint(title_str, accent, C.BOLD) + paint(top_fill + "╮", accent)
    bottom = paint("╰" + "─" * (width - 2) + "╯", accent)
    inner_w = width - 2
    body = []
    for ln in lines:
        pad = inner_w - _visible_len(ln)
        if pad < 0:
            pad = 0
        body.append(paint("│", accent) + ln + " " * pad + paint("│", accent))
    return "\n".join([top] + body + [bottom])


def _metric_row(label, value, width, icon=None, icon_color=C.GREEN,
                value_color=C.BOLD, suffix=""):
    icon_str = paint(icon, icon_color) + " " if icon else "  "
    label_str = paint(label.ljust(14), C.DIM)
    value_str = paint(f"{value}".rjust(6), value_color)
    suffix_str = paint(f"  {suffix}", C.DIM) if suffix else ""
    return "  " + icon_str + label_str + value_str + suffix_str


def _health_icon(value, *, zero_is_good=True, low_is_good=True):
    if zero_is_good:
        if value == 0:
            return "✓", C.BRIGHT_GREEN
        return "⚠", C.BRIGHT_YELLOW
    if low_is_good:
        return "●", C.BRIGHT_CYAN
    return "●", C.BRIGHT_MAGENTA


def render(width=None, json_out=False, plain=False):
    data = {
        "episodic": episodic_stats(),
        "candidates": candidate_stats(),
        "lessons": lesson_stats(),
        "skills": skill_stats(),
        "last_dream_cycle": last_dream_cycle(),
        "failing_skills": failing_skills(),
        "version": _version(),
    }
    if json_out:
        serializable = json.loads(json.dumps(data, default=str))
        return json.dumps(serializable, indent=2)

    if plain:
        _disable_color()
    if width is None:
        width = min(shutil.get_terminal_size((80, 20)).columns, 80)
    if width < 60:
        width = 60

    out = []

    # ── header ──
    ver = data["version"]
    title = paint(" agentic-stack", C.BRIGHT_MAGENTA, C.BOLD)
    subtitle = paint(" · brain state", C.DIM)
    right = paint(f"v{ver} " if ver else "", C.DIM)
    header_content = title + subtitle
    pad = width - _visible_len(header_content) - _visible_len(right)
    out.append(header_content + " " * max(0, pad) + right)
    out.append(paint("━" * width, C.DIM))
    out.append("")

    # ── MEMORY panel ──
    ep = data["episodic"]
    mem_lines = [""]
    icon, icol = _health_icon(ep["count"], zero_is_good=False, low_is_good=False)
    mem_lines.append(_metric_row("episodes", ep["count"], width,
                                 icon=icon, icon_color=icol,
                                 suffix=f"({_human_size(ep['size'])})"))
    fi, fc = _health_icon(ep["failures_14d"])
    mem_lines.append(_metric_row("failures 14d", ep["failures_14d"], width,
                                 icon=fi, icon_color=fc,
                                 value_color=C.BRIGHT_RED if ep["failures_14d"] > 0
                                             else C.BRIGHT_GREEN))
    ldc = data["last_dream_cycle"]
    age = _human_age(ldc) if ldc else "never"
    li = "✓" if ldc else "○"
    lc = C.BRIGHT_GREEN if ldc else C.DIM
    mem_lines.append(_metric_row("last dream", age, width, icon=li, icon_color=lc,
                                 value_color=C.BOLD if ldc else C.DIM))

    # sparkline — aligned with _metric_row's 2-space lead + 2-space icon slot
    counts = [c for _, c in ep["daily"]]
    spark = _sparkline(counts)
    spark_label = "  " + "  " + paint("activity 14d".ljust(14), C.DIM)
    spark_render = paint(spark, C.BRIGHT_CYAN)
    peak = max(counts) if counts else 0
    spark_line = spark_label + spark_render + paint(f"  max={peak}/day", C.DIM)
    mem_lines.append(spark_line)
    mem_lines.append("")
    out.append(_boxed("MEMORY", mem_lines, width, accent=C.CYAN))
    out.append("")

    # ── LESSONS panel ──
    le = data["lessons"]
    source = "lessons.jsonl" if not le["from_md_fallback"] else "LESSONS.md"
    le_lines = [""]
    ai, ac = _health_icon(len(le["accepted"]) if le["accepted"] else le["count"],
                          zero_is_good=False, low_is_good=False)
    le_lines.append(_metric_row(
        "accepted", len(le["accepted"]) if le["accepted"] else le["count"],
        width, icon=ai, icon_color=ac,
        suffix=f"(source: {source})"))
    pi = "○" if le["provisional"] == 0 else "◐"
    pc = C.DIM if le["provisional"] == 0 else C.BRIGHT_YELLOW
    le_lines.append(_metric_row("provisional", le["provisional"], width,
                                icon=pi, icon_color=pc,
                                value_color=C.BOLD if le["provisional"] > 0 else C.DIM))

    shown = 0
    if le["accepted"]:
        le_lines.append("")
        for l in le["accepted"][:5]:
            age = _human_age(l.get("accepted_at", "")) if l.get("accepted_at") else ""
            claim = l.get("claim", "")
            # Truncate to fit
            max_claim = width - 12 - len(age) - 2
            if len(claim) > max_claim:
                claim = claim[: max_claim - 1] + "…"
            bullet = paint("  • ", C.BRIGHT_CYAN)
            age_str = paint(f"  [{age}]", C.DIM) if age else ""
            le_lines.append("  " + bullet + paint(claim, C.WHITE) + age_str)
            shown += 1
        if len(le["accepted"]) > shown:
            le_lines.append("  " + paint(
                f"    …and {len(le['accepted']) - shown} more", C.DIM))
    elif le["count"] > 0 and le["from_md_fallback"]:
        le_lines.append("")
        le_lines.append("  " + paint(
            f"  {le['count']} seed lessons in LESSONS.md "
            f"(none graduated yet — run learn.py)", C.DIM))
    le_lines.append("")
    out.append(_boxed("LESSONS", le_lines, width, accent=C.BRIGHT_MAGENTA))
    out.append("")

    # ── CANDIDATES panel ──
    cs = data["candidates"]
    c_lines = [""]
    si = "●" if cs["staged"] > 0 else "○"
    sc = C.BRIGHT_YELLOW if cs["staged"] > 0 else C.DIM
    c_lines.append(_metric_row("staged", cs["staged"], width,
                               icon=si, icon_color=sc,
                               value_color=C.BOLD if cs["staged"] > 0 else C.DIM,
                               suffix="(awaiting review)" if cs["staged"] > 0 else ""))
    gi = "✓" if cs["graduated"] > 0 else "○"
    gc = C.BRIGHT_GREEN if cs["graduated"] > 0 else C.DIM
    c_lines.append(_metric_row("graduated", cs["graduated"], width,
                               icon=gi, icon_color=gc,
                               value_color=C.BOLD if cs["graduated"] > 0 else C.DIM))
    ri = "✗" if cs["rejected"] > 0 else "○"
    rc = C.BRIGHT_RED if cs["rejected"] > 0 else C.DIM
    c_lines.append(_metric_row("rejected", cs["rejected"], width,
                               icon=ri, icon_color=rc,
                               value_color=C.BOLD if cs["rejected"] > 0 else C.DIM))
    c_lines.append("")
    out.append(_boxed("CANDIDATES", c_lines, width, accent=C.BRIGHT_YELLOW))
    out.append("")

    # ── SKILLS panel ──
    sk = data["skills"]
    fs = data["failing_skills"]
    sk_lines = [""]
    sk_lines.append(_metric_row("loaded", sk["count"], width,
                                icon="●", icon_color=C.BRIGHT_CYAN))
    fi_icon, fi_color = _health_icon(len(fs))
    sk_lines.append(_metric_row("failing", len(fs), width,
                                icon=fi_icon, icon_color=fi_color,
                                value_color=C.BRIGHT_RED if fs else C.BRIGHT_GREEN))
    if sk["names"]:
        sk_lines.append("")
        prefix_indent = "      "
        max_plain = width - len(prefix_indent) - 4
        buffered = ""  # visible chars tracked separately
        buf_visible = 0
        rows = []
        for i, name in enumerate(sk["names"]):
            is_last = (i == len(sk["names"]) - 1)
            piece_visible = len(name) + (0 if is_last else 2)
            if buffered and buf_visible + piece_visible > max_plain:
                rows.append(buffered)
                buffered, buf_visible = "", 0
            buffered += paint(name, C.BRIGHT_CYAN)
            if not is_last:
                buffered += paint(", ", C.DIM)
            buf_visible += piece_visible
        if buffered:
            rows.append(buffered)
        for row in rows:
            sk_lines.append(prefix_indent + row)
    if fs:
        sk_lines.append("")
        for name, n in fs[:3]:
            sk_lines.append("  " + paint("  ⚠ ", C.BRIGHT_YELLOW) +
                            paint(name.ljust(20), C.BRIGHT_RED) +
                            paint(f"{n} failures", C.DIM))
    sk_lines.append("")
    out.append(_boxed("SKILLS", sk_lines, width, accent=C.GREEN))

    # ── footer hint ──
    out.append("")
    out.append(paint("  learn:  ", C.DIM) + paint("python3 .agent/tools/learn.py \"…\"", C.BRIGHT_CYAN))
    out.append(paint("  recall: ", C.DIM) + paint("python3 .agent/tools/recall.py \"…\"", C.BRIGHT_CYAN))
    out.append(paint("  dream:  ", C.DIM) + paint("python3 .agent/memory/auto_dream.py", C.BRIGHT_CYAN))

    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="Agent state dashboard.")
    p.add_argument("--json", action="store_true", help="Emit JSON.")
    p.add_argument("--plain", action="store_true",
                   help="Disable ANSI color. Also triggered by NO_COLOR env.")
    p.add_argument("--width", type=int, default=None,
                   help="Override terminal width (default: auto-detect, max 80).")
    args = p.parse_args()
    plain = args.plain or bool(os.environ.get("NO_COLOR"))
    print(render(width=args.width, json_out=args.json, plain=plain))


if __name__ == "__main__":
    main()
