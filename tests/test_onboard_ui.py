from harness_manager import __version__
import onboard_ui
from pathlib import Path


def test_onboarding_banner_uses_package_version():
    assert f"v{__version__}" in onboard_ui._T
    assert "v0.8.0" not in onboard_ui._T


def test_v019_release_docs_describe_loops_and_safety():
    root = Path(__file__).resolve().parents[1]
    assert __version__ == "0.19.0"
    readme = (root / "README.md").read_text(encoding="utf-8")
    getting_started = (root / "docs" / "getting-started.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    release = (root / "docs" / "releases" / "v0.19.0.md").read_text(encoding="utf-8")
    for text in (readme, getting_started, release):
        assert "loop init" in text and "loop run" in text and "loop status" in text
        assert "not an operating-system sandbox" in text
    assert "## [0.19.0]" in changelog
    assert "### Added" in changelog and "### Safety" in changelog and "### Migration" in changelog
