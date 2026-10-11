"""Knowledge module: source-backed topic pages, Markdown as the source of truth.

Turns a text document into a searchable topic library under
`memory/knowledge/<Category>/<doc_id>/`:

    index.md            document metadata + summary (frontmatter: type, id,
                        doc_id, category_id, title, schema_version,
                        source_name, source_type, topic_count)
    N_<Topic_Name>.md   one page per topic (type, id, node_id, doc_id,
                        category_id, topic_index, topic_name, topic_path,
                        summary, depth, parent_node_id, children_node_ids,
                        content_labels, schema_version)
    _original/<file>    the uploaded file, unchanged

Categories live in `memory/knowledge/.taxonomy.md`; `Others` is the fallback.
No model calls: topics come from Markdown headings (or ~1500-char chunks),
summaries from the first paragraph, labels from word frequency. Pages are
plain Markdown so you can edit them; `memory_search.py` indexes them with
the rest of memory.

    python3 .agent/tools/knowledge.py add notes/postgres.md --title "Postgres ops"
    python3 .agent/tools/knowledge.py list [--category Engineering]
    python3 .agent/tools/knowledge.py show <doc_id>
    python3 .agent/tools/knowledge.py topic <topic_id>
    python3 .agent/tools/knowledge.py search "connection pooling" --top-k 5
    python3 .agent/tools/knowledge.py patch <doc_id> --title ... --category ...
    python3 .agent/tools/knowledge.py remove <doc_id>
    python3 .agent/tools/knowledge.py categories
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text import word_set  # noqa: E402
from _cli import CliError, add_format_arg, run  # noqa: E402

KNOWLEDGE_ROOT = os.path.join(BASE, "memory", "knowledge")
SCHEMA_VERSION = 1
CHUNK_CHARS = 1500
DEFAULT_CATEGORIES = [
    ("Engineering", "software, code, architecture, infrastructure, deployment, testing, apis"),
    ("Product", "product requirements, roadmap, features, user stories, specs"),
    ("Research", "papers, experiments, findings, benchmarks, literature, analysis"),
    ("Operations", "runbooks, incidents, on-call, procedures, checklists, monitoring"),
    ("Data", "datasets, schemas, pipelines, analytics, sql, warehouses"),
    ("Security", "vulnerabilities, auth, secrets, compliance, threat models, audits"),
    ("Design", "ui, ux, visual design, typography, layout, brand"),
    ("Marketing", "content, campaigns, audience, growth, social, launches"),
    ("Finance", "budget, pricing, invoices, revenue, costs, accounting"),
    ("Legal", "contracts, licenses, terms, policy, privacy, regulation"),
    ("People", "hiring, onboarding, team, management, feedback, culture"),
    ("Personal", "notes, journal, habits, health, travel, home"),
    ("Others", "fallback category for anything else"),
]
_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml",
                  ".toml", ".py", ".js", ".ts", ".sh", ".html", ".xml", ".log", ".tex", ""}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _fm_render(fm):
    return "---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in fm.items()) + "\n---\n"


def _fm_parse(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            try:
                fm[k.strip()] = json.loads(v.strip())
            except json.JSONDecodeError:
                fm[k.strip()] = v.strip()
    return fm, text[end + 5:]


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _slug(s, limit=40):
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return (s or "topic")[:limit]


# --- taxonomy -------------------------------------------------------------

def taxonomy(root=None):
    root = root or KNOWLEDGE_ROOT
    path = os.path.join(root, ".taxonomy.md")
    if not os.path.exists(path):
        fm = {"kind": "knowledge_taxonomy", "schema_version": SCHEMA_VERSION,
              "categories": [{"id": c, "description": d} for c, d in DEFAULT_CATEGORIES]}
        _write(path, _fm_render(fm) + "\nEdit the `categories` list; it hot-reloads on the next command.\n")
    fm, _ = _fm_parse(open(path, encoding="utf-8").read())
    cats = fm.get("categories") or []
    if not any(c.get("id") == "Others" for c in cats):
        cats.append({"id": "Others", "description": "fallback"})
    return cats


def pick_category(text, cats):
    words = word_set(text)
    best, best_score = "Others", 0
    for c in cats:
        if c["id"] == "Others":
            continue
        score = len(words & word_set(c.get("description", "") + " " + c["id"]))
        if score > best_score:
            best, best_score = c["id"], score
    return best


# --- topic extraction -------------------------------------------------------

def split_topics(body):
    """[(name, depth, content)] from Markdown headings, else fixed chunks."""
    lines = body.splitlines()
    topics, current = [], None
    for line in lines:
        m = re.match(r"^(#{1,3})\s+(.+?)\s*#*\s*$", line)
        if m:
            if current:
                topics.append(current)
            current = {"name": m.group(2).strip(), "depth": len(m.group(1)), "lines": []}
        elif current is not None:
            current["lines"].append(line)
        else:
            current = {"name": "Introduction", "depth": 1, "lines": [line]}
    if current:
        topics.append(current)
    out = [(t["name"], t["depth"], "\n".join(t["lines"]).strip()) for t in topics if "\n".join(t["lines"]).strip()]
    if len(out) > 1:
        return out
    text = body.strip()
    if not text:
        return []
    chunks, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(buf) + len(para) > CHUNK_CHARS and buf:
            chunks.append(buf.strip())
            buf = ""
        buf += para + "\n\n"
    if buf.strip():
        chunks.append(buf.strip())
    return [(f"Part {i + 1}", 1, c) for i, c in enumerate(chunks)]


def _summary(text, limit=400):
    para = re.split(r"\n\s*\n", text.strip())[0] if text.strip() else ""
    para = re.sub(r"\s+", " ", para)
    return para[:limit]


def _labels(text, k=5):
    counts = collections.Counter(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))
    for w in list(counts):
        if w not in word_set(w):
            del counts[w]
    return [w for w, _ in counts.most_common(k)]


# --- documents ----------------------------------------------------------------

def _docs(root):
    root = root or KNOWLEDGE_ROOT
    if not os.path.isdir(root):
        return []
    out = []
    for cat in sorted(os.listdir(root)):
        cdir = os.path.join(root, cat)
        if cat.startswith(".") or not os.path.isdir(cdir):
            continue
        for doc in sorted(os.listdir(cdir)):
            idx = os.path.join(cdir, doc, "index.md")
            if os.path.exists(idx):
                fm, body = _fm_parse(open(idx, encoding="utf-8").read())
                out.append({"fm": fm, "summary": body.strip(), "dir": os.path.join(cdir, doc)})
    return out


def _find(doc_id, root):
    for d in _docs(root):
        if d["fm"].get("doc_id") == doc_id:
            return d
    raise CliError("not_found", f"document {doc_id} not found")


def _topics(doc_dir):
    out = []
    for name in sorted(os.listdir(doc_dir), key=lambda n: (len(n.split("_")[0]), n)):
        if re.match(r"^\d+_.*\.md$", name):
            fm, body = _fm_parse(open(os.path.join(doc_dir, name), encoding="utf-8").read())
            out.append({"fm": fm, "content": body.strip(), "path": os.path.join(doc_dir, name)})
    return out


def add_document(source_path, title, category=None, doc_id=None, root=None):
    root = root or KNOWLEDGE_ROOT
    if not os.path.isfile(source_path):
        raise CliError("not_found", f"no such file: {source_path}")
    suffix = os.path.splitext(source_path)[1].lower()
    try:
        with open(source_path, encoding="utf-8") as f:
            body = f.read()
    except UnicodeDecodeError:
        raise CliError("invalid_args", f"unsupported source type: {suffix or 'binary'}",
                       hint="convert to Markdown/text first (pdf, office files need a parser)")
    if suffix not in _TEXT_SUFFIXES:
        raise CliError("invalid_args", f"unsupported source type: {suffix}",
                       hint="convert to Markdown/text first")
    cats = taxonomy(root)
    if category and not any(c["id"] == category for c in cats):
        raise CliError("invalid_args", f"unknown category {category!r}",
                       hint="see `knowledge.py categories` or edit .taxonomy.md")
    category = category or pick_category(title + "\n" + body, cats)
    doc_id = doc_id or "doc_" + hashlib.sha1((title + os.path.basename(source_path)).encode()).hexdigest()[:10]
    if any(d["fm"].get("doc_id") == doc_id for d in _docs(root)):
        raise CliError("conflict", f"document {doc_id} already exists", hint="use `patch` or `remove` first")
    topics = split_topics(body)
    doc_dir = os.path.join(root, category, doc_id)
    os.makedirs(os.path.join(doc_dir, "_original"), exist_ok=True)
    shutil.copy2(source_path, os.path.join(doc_dir, "_original", os.path.basename(source_path)))

    stack = []  # (depth, node_id)
    children = collections.defaultdict(list)
    rows = []
    for i, (name, depth, content) in enumerate(topics, start=1):
        node_id = f"{doc_id}:{i}"
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1] if stack else None
        if parent:
            children[parent].append(node_id)
        path_names = [r["topic_name"] for r in rows if r["node_id"] in [s[1] for s in stack]]
        rows.append({"type": "knowledge_topic", "id": node_id, "node_id": node_id, "doc_id": doc_id,
                     "category_id": category, "topic_index": i, "topic_name": name,
                     "topic_path": " / ".join(path_names + [name]), "summary": _summary(content, 200),
                     "depth": depth, "parent_node_id": parent, "children_node_ids": [],
                     "content_labels": _labels(content), "schema_version": SCHEMA_VERSION, "_content": content})
        stack.append((depth, node_id))
    for r in rows:
        r["children_node_ids"] = children.get(r["node_id"], [])
        content = r.pop("_content")
        _write(os.path.join(doc_dir, f"{r['topic_index']}_{_slug(r['topic_name'])}.md"),
               _fm_render(r) + "\n" + content + "\n")
    fm = {"type": "knowledge_document", "id": doc_id, "doc_id": doc_id, "category_id": category,
          "title": title, "schema_version": SCHEMA_VERSION, "source_name": os.path.basename(source_path),
          "source_type": suffix.lstrip(".") or "text", "topic_count": len(rows), "created_at": _now()}
    _write(os.path.join(doc_dir, "index.md"), _fm_render(fm) + "\n" + _summary(body) + "\n")
    return {"doc_id": doc_id, "category_id": category, "title": title, "topic_count": len(rows),
            "path": doc_dir}


def search(query, top_k=5, include_content=False, score_threshold=0.0, root=None):
    q = word_set(query)
    if not q:
        raise CliError("invalid_args", "query must contain at least one content word")
    hits = []
    for d in _docs(root):
        for t in _topics(d["dir"]):
            fm = t["fm"]
            words = word_set(t["content"]) | set(fm.get("content_labels") or [])
            score = len(q & words) / len(q)
            if q & word_set(fm.get("topic_name", "")):
                score = min(1.0, score + 0.25)
            if score > score_threshold and score > 0:
                row = {"topic_id": fm.get("id"), "doc_id": fm.get("doc_id"), "title": d["fm"].get("title"),
                       "topic_name": fm.get("topic_name"), "topic_path": fm.get("topic_path"),
                       "category_id": fm.get("category_id"), "score": round(score, 3),
                       "summary": fm.get("summary")}
                if include_content:
                    row["content"] = t["content"]
                hits.append(row)
    hits.sort(key=lambda h: (-h["score"], h["topic_id"] or ""))
    return hits[:top_k]


def patch_document(doc_id, title=None, category=None, root=None):
    root = root or KNOWLEDGE_ROOT
    d = _find(doc_id, root)
    fm = d["fm"]
    if category and category != fm.get("category_id"):
        if not any(c["id"] == category for c in taxonomy(root)):
            raise CliError("invalid_args", f"unknown category {category!r}")
        new_dir = os.path.join(root, category, doc_id)
        if os.path.exists(new_dir):
            raise CliError("conflict", f"{new_dir} already exists")
        os.makedirs(os.path.dirname(new_dir), exist_ok=True)
        shutil.move(d["dir"], new_dir)
        d["dir"] = new_dir
        fm["category_id"] = category
        for t in _topics(new_dir):
            t["fm"]["category_id"] = category
            _write(t["path"], _fm_render(t["fm"]) + "\n" + t["content"] + "\n")
    if title:
        fm["title"] = title
    fm["updated_at"] = _now()
    _write(os.path.join(d["dir"], "index.md"), _fm_render(fm) + "\n" + d["summary"] + "\n")
    return {"doc_id": doc_id, "title": fm.get("title"), "category_id": fm.get("category_id")}


def remove_document(doc_id, root=None):
    d = _find(doc_id, root or KNOWLEDGE_ROOT)
    shutil.rmtree(d["dir"])
    return {"doc_id": doc_id, "removed": True}


# --- CLI --------------------------------------------------------------------------

def _cmd_add(ns):
    r = add_document(ns.file, ns.title, ns.category, ns.doc_id, root=ns.root)
    return r, None, f"{r['doc_id']}  [{r['category_id']}] {r['title']}  topics={r['topic_count']}"


def _cmd_list(ns):
    rows = [dict(d["fm"], summary=d["summary"][:160]) for d in _docs(ns.root)
            if not ns.category or d["fm"].get("category_id") == ns.category]
    text = "\n".join(f"{r['doc_id']}  [{r['category_id']}] {r['title']}  topics={r.get('topic_count')}" for r in rows) or "(empty)"
    return rows, {"count": len(rows)}, text


def _cmd_show(ns):
    d = _find(ns.doc_id, ns.root or KNOWLEDGE_ROOT)
    topics = [{"topic_id": t["fm"].get("id"), "topic_name": t["fm"].get("topic_name"),
               "topic_path": t["fm"].get("topic_path"), "summary": t["fm"].get("summary")} for t in _topics(d["dir"])]
    orig = os.path.join(d["dir"], "_original", d["fm"].get("source_name", ""))
    data = dict(d["fm"], summary=d["summary"], original_file_path=orig, topics=topics)
    text = f"{d['fm'].get('title')}\n{d['summary']}\n" + "\n".join(f"  {t['topic_id']}  {t['topic_path']}" for t in topics)
    return data, None, text


def _cmd_topic(ns):
    doc_id = ns.topic_id.split(":")[0]
    d = _find(doc_id, ns.root or KNOWLEDGE_ROOT)
    for t in _topics(d["dir"]):
        if t["fm"].get("id") == ns.topic_id:
            return dict(t["fm"], content=t["content"]), None, f"# {t['fm'].get('topic_path')}\n\n{t['content']}"
    raise CliError("not_found", f"topic {ns.topic_id} not found")


def _cmd_search(ns):
    hits = search(ns.query, ns.top_k, ns.include_content, ns.score_threshold, root=ns.root)
    text = "\n".join(f"{h['score']:.2f}  {h['topic_id']}  {h['title']} / {h['topic_name']}" for h in hits) or "(no hits)"
    return hits, {"count": len(hits)}, text


def _cmd_patch(ns):
    if not (ns.title or ns.category):
        raise CliError("invalid_args", "nothing to patch", hint="pass --title and/or --category")
    r = patch_document(ns.doc_id, ns.title, ns.category, root=ns.root)
    return r, None, f"{r['doc_id']}  [{r['category_id']}] {r['title']}"


def _cmd_remove(ns):
    r = remove_document(ns.doc_id, root=ns.root)
    return r, None, f"removed {ns.doc_id}"


def _cmd_categories(ns):
    docs = _docs(ns.root)
    rows = [dict(c, document_count=sum(1 for d in docs if d["fm"].get("category_id") == c["id"]))
            for c in taxonomy(ns.root)]
    return rows, {"count": len(rows)}, "\n".join(f"{r['id']:<14} {r['document_count']:>3}  {r.get('description','')}" for r in rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--root", default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", parents=[common]); a.add_argument("file"); a.add_argument("--title", required=True)
    a.add_argument("--category"); a.add_argument("--doc-id"); a.set_defaults(fn=_cmd_add)
    l = sub.add_parser("list", parents=[common]); l.add_argument("--category"); l.set_defaults(fn=_cmd_list)
    s = sub.add_parser("show", parents=[common]); s.add_argument("doc_id"); s.set_defaults(fn=_cmd_show)
    t = sub.add_parser("topic", parents=[common]); t.add_argument("topic_id"); t.set_defaults(fn=_cmd_topic)
    q = sub.add_parser("search", parents=[common]); q.add_argument("query"); q.add_argument("--top-k", type=int, default=5)
    q.add_argument("--include-content", action="store_true"); q.add_argument("--score-threshold", type=float, default=0.0)
    q.set_defaults(fn=_cmd_search)
    pa = sub.add_parser("patch", parents=[common]); pa.add_argument("doc_id"); pa.add_argument("--title"); pa.add_argument("--category")
    pa.set_defaults(fn=_cmd_patch)
    r = sub.add_parser("remove", parents=[common]); r.add_argument("doc_id"); r.set_defaults(fn=_cmd_remove)
    c = sub.add_parser("categories", parents=[common]); c.set_defaults(fn=_cmd_categories)
    ns = p.parse_args(argv)
    return run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
