"""Progressive disclosure: manifest always, full SKILL.md only when triggered."""
import json
import os
import re
import sys
from pathlib import Path

ROOT = os.path.join(os.path.dirname(__file__), "..")
SKILLS_DIR = os.path.join(ROOT, "skills")
MANIFEST = os.path.join(SKILLS_DIR, "_manifest.jsonl")

# Skill names: alphanumerics, underscore, hyphen only. No path separators or dots.
_SAFE_NAME_RE = re.compile(r"[a-zA-Z0-9_-]+")


def _within(root, candidate):
    """Resolve both paths and assert candidate is contained within root.

    Returns the resolved Path on success. Raises ValueError otherwise.
    """
    root_p = Path(root).resolve()
    cand_p = Path(candidate).resolve()
    # Path.is_relative_to is available in Python 3.9+; project runs on 3.14.
    if not cand_p.is_relative_to(root_p):
        raise ValueError(f"path {cand_p} escapes root {root_p}")
    return cand_p


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    out = []
    for line in open(MANIFEST):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def match_triggers(user_input, manifest):
    matches = []
    text = user_input.lower()
    for skill in manifest:
        for trigger in skill.get("triggers", []):
            if trigger.lower() in text:
                matches.append(skill)
                break
    return matches


def check_preconditions(skill):
    # Preconditions are evaluated relative to the project root (one level above .agent).
    precond_root = os.path.join(ROOT, "..")
    for pre in skill.get("preconditions", []):
        if pre.endswith("exists"):
            path = pre.replace(" exists", "").strip()
            joined = os.path.join(precond_root, path)
            try:
                resolved = _within(precond_root, joined)
            except ValueError as e:
                print(
                    f"skill_loader: rejecting precondition {pre!r} for skill "
                    f"{skill.get('name')!r}: {e}",
                    file=sys.stderr,
                )
                return False
            if not resolved.exists():
                return False
    return True


def load_skill_full(name):
    # Validate the skill name BEFORE touching the filesystem so a malicious
    # name (e.g. "../../etc") cannot probe paths outside SKILLS_DIR.
    if not isinstance(name, str) or not _SAFE_NAME_RE.fullmatch(name):
        print(
            f"skill_loader: rejecting unsafe skill name {name!r}",
            file=sys.stderr,
        )
        return None

    base = os.path.join(SKILLS_DIR, name)
    try:
        base_resolved = _within(SKILLS_DIR, base)
    except ValueError as e:
        print(
            f"skill_loader: rejecting skill dir for {name!r}: {e}",
            file=sys.stderr,
        )
        return None

    skill_md = base_resolved / "SKILL.md"
    try:
        skill_md_resolved = _within(SKILLS_DIR, skill_md)
    except ValueError as e:
        print(
            f"skill_loader: rejecting SKILL.md for {name!r}: {e}",
            file=sys.stderr,
        )
        return None
    if not skill_md_resolved.exists():
        return None
    content = open(skill_md_resolved).read()

    knowledge = base_resolved / "KNOWLEDGE.md"
    try:
        knowledge_resolved = _within(SKILLS_DIR, knowledge)
    except ValueError as e:
        print(
            f"skill_loader: rejecting KNOWLEDGE.md for {name!r}: {e}",
            file=sys.stderr,
        )
        return content
    if knowledge_resolved.exists():
        content += "\n\n---\n## Accumulated knowledge\n" + open(knowledge_resolved).read()
    return content


def progressive_load(user_input):
    manifest = load_manifest()
    matches = match_triggers(user_input, manifest)
    loaded = []
    for skill in matches:
        name = skill.get("name")
        if not isinstance(name, str) or not _SAFE_NAME_RE.fullmatch(name):
            print(
                f"skill_loader: skipping manifest entry with unsafe name {name!r}",
                file=sys.stderr,
            )
            continue
        if not check_preconditions(skill):
            continue
        content = load_skill_full(name)
        if not content:
            continue
        loaded.append({
            "name": name,
            "constraints": skill.get("constraints", []),
            "content": content,
        })
    return loaded
