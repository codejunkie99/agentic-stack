from harness_manager.workspaces.service import WorkspaceService


def test_desktop_personal_memory_profile_separates_stable_current_and_relevant(tmp_path):
    project = tmp_path / "project"
    personal = project / ".agent/memory/personal"
    working = project / ".agent/memory/working"
    personal.mkdir(parents=True)
    working.mkdir(parents=True)
    (personal / "PREFERENCES.md").write_text("# Preferences\n\nKeep source provenance visible in every answer.\n")
    (working / "WORKSPACE.md").write_text("# Current task\n\nRedesign the native model picker.\n")
    service = WorkspaceService(tmp_path / "data")
    try:
        workspace = service.open_project({"path": str(project)})
        result = service.dispatch("memory.profile", {
            "workspaceId": workspace["id"], "query": "source provenance", "limit": 4,
        })
        assert result["static"][0]["source"] == ".agent/memory/personal/PREFERENCES.md"
        assert result["dynamic"]["source"] == ".agent/memory/working/WORKSPACE.md"
        assert result["relevant"][0]["title"] == "Preferences"
        assert "source provenance" in result["relevant"][0]["content"]
    finally:
        service.close()
