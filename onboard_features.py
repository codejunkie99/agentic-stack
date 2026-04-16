"""Optional feature toggles written by onboarding.

Stored at `.agent/memory/.features.json` as a simple JSON map. Keeps the
data separate from PREFERENCES.md so toggling a feature doesn't require
regenerating the whole preferences file, and so downstream code can read
it without parsing markdown.

All features default to OFF. Users opt in explicitly during onboarding
or by editing .features.json directly.
"""
import json
import os

FEATURES_REL = ".agent/memory/.features.json"


def features_path(target_dir: str) -> str:
    return os.path.join(target_dir, FEATURES_REL)


def load_features(target_dir: str) -> dict:
    try:
        with open(features_path(target_dir), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_features(target_dir: str, features: dict) -> str:
    path = features_path(target_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=2)
        f.write("\n")
    return path


def is_enabled(target_dir: str, key: str) -> bool:
    """True iff the feature is explicitly enabled. Off when file missing
    or key absent — opt-in model."""
    entry = load_features(target_dir).get(key) or {}
    return bool(entry.get("enabled"))
