class AgenticStack < Formula
  desc "One brain, many harnesses — portable .agent/ folder for AI coding agents"
  homepage "https://github.com/codejunkie99/agentic-stack"
  url "https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.18.0.tar.gz"
  sha256 "ef2d9d9209755e3dd1888064eae48a78add44b2140a78b7952664d7c4945ba85"
  license "Apache-2.0"

  def install
    # install the brain + adapters alongside install.sh so relative paths hold
    pkgshare.install ".agent", "adapters", "harness_manager", "scripts", "install.sh",
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
    agentic_stack = bin/"agentic-stack"
    output = shell_output("#{agentic_stack} 2>&1", 2)
    assert_match "usage", output
    assert_match "agentic-stack transfer", shell_output("#{agentic_stack} transfer --help")
    assert_match "brain CLI not found", shell_output("#{agentic_stack} brain install-help")
    # Wizard --yes must write PREFERENCES.md AND .features.json into a temp project dir
    (testpath/".agent/memory/personal").mkpath
    system agentic_stack, "claude-code", testpath.to_s, "--yes"
    assert_path_exists testpath/".agent/memory/personal/PREFERENCES.md"
    assert_path_exists testpath/".agent/memory/.features.json"
    assert_match "agentic-stack dashboard", shell_output("#{agentic_stack} dashboard #{testpath} --plain")
    system agentic_stack, "mission-control", testpath.to_s,
           "--snapshot", (testpath/"mission-control.html").to_s, "--no-open"
    assert_path_exists testpath/"mission-control.html"
  end
end
