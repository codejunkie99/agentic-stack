from harness_manager import __version__
import onboard_ui


def test_onboarding_banner_uses_package_version():
    assert f"v{__version__}" in onboard_ui._T
    assert "v0.8.0" not in onboard_ui._T
