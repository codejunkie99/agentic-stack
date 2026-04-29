"""
Backward-compatible environment helpers built on capability-based detection.
"""

from __future__ import annotations

import sys

from runtime_capabilities import detect_runtime_capabilities


def detect_skill_root():
    """Find the skill root directory across runtimes."""
    return detect_runtime_capabilities(anchor=__file__).skill_root


def detect_environment():
    """Return a compatibility dict for legacy callers."""
    capabilities = detect_runtime_capabilities(anchor=__file__)
    payload = capabilities.as_dict()
    payload["runtime"] = capabilities.runtime_family
    return payload


def setup_python_path():
    """Add skill scripts to sys.path. Call before importing skill modules."""
    env = detect_environment()
    scripts_dir = env["scripts_dir"]
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return env


def check_visual_qa_deps():
    """Check rendering dependencies and print actionable status."""
    env = detect_environment()

    if env["visual_qa_ready"]:
        print("OK  Visual QA ready (LibreOffice + poppler available)")
        return True

    missing = []
    if not env["has_libreoffice"]:
        missing.append(
            "LibreOffice: brew install --cask libreoffice (macOS) "
            "/ apt install libreoffice (Linux)"
        )
    if not env["has_poppler"]:
        missing.append(
            "poppler: brew install poppler (macOS) "
            "/ apt install poppler-utils (Linux)"
        )

    print("WARN  Visual QA dependencies missing:")
    for item in missing:
        print(f"  - {item}")
    if env["workflow_mode"] == "orchestrated":
        print("WARN  Parent reducer must rely on programmatic QA until rendered-image review is available.")
    else:
        print("WARN  Sequential workflow will rely on check_deck() until rendered-image review is available.")
    return False
