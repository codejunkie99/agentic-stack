class AgenticStack < Formula
  desc "One brain, many harnesses — portable .agent/ folder for AI coding agents"
  homepage "https://github.com/codejunkie99/agentic-stack"
  url "https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "02e31cdc861669089da6b290c24afcc64765f60a2a59f450c074c0f20e7a6b0a"
  version "0.3.0"
  license "MIT"

  def install
    # install the brain + adapters alongside install.sh so relative paths hold
    pkgshare.install ".agent", "adapters", "install.sh",
                     "onboard.py", "onboard_ui.py", "onboard_widgets.py",
                     "onboard_render.py", "onboard_write.py"

    # wrapper so `agentic-stack cursor` works from anywhere
    (bin/"agentic-stack").write <<~EOS
      #!/bin/bash
      exec "#{pkgshare}/install.sh" "$@"
    EOS
  end

  test do
    output = shell_output("#{bin}/agentic-stack 2>&1", 2)
    assert_match "usage", output
    # Wizard --yes must write PREFERENCES.md into a temp project dir
    (testpath/".agent/memory/personal").mkpath
    system "#{bin}/agentic-stack", "claude-code", testpath.to_s, "--yes"
    assert_predicate testpath/".agent/memory/personal/PREFERENCES.md", :exist?
  end
end
