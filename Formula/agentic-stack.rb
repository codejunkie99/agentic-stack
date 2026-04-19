class AgenticStack < Formula
  desc "One brain, many harnesses — portable .agent/ folder for AI coding agents"
  homepage "https://github.com/codejunkie99/agentic-stack"
  url "https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.7.1.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # TODO: regenerate after tag push
  version "0.7.1"
  license "Apache-2.0"

  def install
    # install the brain + adapters alongside install.sh so relative paths hold
    pkgshare.install ".agent", "adapters", "install.sh",
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
