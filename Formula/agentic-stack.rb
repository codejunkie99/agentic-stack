class AgenticStack < Formula
  desc "One brain, many harnesses — portable .agent/ folder for AI coding agents"
  homepage "https://github.com/codejunkie99/agentic-stack"
  # NOTE: sha256 must be updated after the v0.9.0 GitHub release is cut.
  # The url/sha256 chicken-and-egg is the same pattern as the v0.8.0 release
  # (commit abaa352 "chore: update Formula sha256 for v0.8.0 tarball" did the
  # post-release sha256 bump). Tag v0.9.0, then run:
  #   curl -L https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.9.0.tar.gz | shasum -a 256
  # and replace the placeholder below.
  url "https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.9.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"  # TODO: update post-tag
  version "0.9.0"
  license "Apache-2.0"

  def install
    # install the brain + adapters alongside install.sh so relative paths hold.
    # harness_manager/ is the v0.9.0 Python backend that install.sh dispatches
    # into; without it brewed users hit ModuleNotFoundError on first install.
    pkgshare.install ".agent", "adapters", "install.sh", "install.ps1",
                     "harness_manager",
                     "onboard.py", "onboard_ui.py", "onboard_widgets.py",
                     "onboard_render.py", "onboard_write.py",
                     "onboard_features.py"

    # wrapper so `agentic-stack cursor` works from anywhere
    (bin/"agentic-stack").write <<~EOS
      #!/bin/bash
      exec "#{pkgshare}/install.sh" "$@"
    EOS
  end

  test do
    output = shell_output("#{bin}/agentic-stack 2>&1", 2)
    assert_match "usage", output
    # Wizard --yes must write PREFERENCES.md AND .features.json into a temp project dir
    (testpath/".agent/memory/personal").mkpath
    system "#{bin}/agentic-stack", "claude-code", testpath.to_s, "--yes"
    assert_predicate testpath/".agent/memory/personal/PREFERENCES.md", :exist?
    assert_predicate testpath/".agent/memory/.features.json", :exist?
  end
end
