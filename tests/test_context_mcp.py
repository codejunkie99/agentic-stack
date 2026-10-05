import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harness_manager.context_mcp import MCPServer, search_memory
from harness_manager.workspaces import context_integration


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows))
    return path


def seed(home):
    write(home / ".codex/sessions/2026/chat.jsonl", [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Ship the Atlas release"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "analysis", "content": [{"type": "output_text", "text": "HIDDEN"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "Atlas is ready"}]}},
    ])
    write(home / ".codex/sessions/2026/subagent.jsonl", [
        {"type": "session_meta", "payload": {"thread_source": "subagent",
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": "parent", "agent_nickname": "Scout"}}},
            "base_instructions": {"provenance": {"model": "gpt-5.6-luna"}}}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Inspect the Atlas cache"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "Cache boundary found"}]}},
    ])


def test_mcp_tools_resources_and_at_instructions_are_read_only(tmp_path):
    home = tmp_path / "home"; home.mkdir(); seed(home)
    source = next((home / ".codex/sessions").rglob("*.jsonl"))
    before = source.read_bytes()
    server = MCPServer(home)

    initialized = server.handle({"method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert initialized["protocolVersion"] == "2025-06-18"
    assert all(mention in initialized["instructions"] for mention in ["@Claude", "@Codex", "@OpenCode", "@Cursor"])
    tools = server.handle({"method": "tools/list"})["tools"]
    assert {tool["name"] for tool in tools} == {
        "recall_context", "search_conversations", "read_conversation", "search_shared_memory", "prepare_context",
        "recommend_model", "read_personal_memory", "plan_context",
        "compact_trace", "select_skills", "plan_tools", "verify_citations", "search_code"}
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)
    search_schema = next(tool for tool in tools if tool["name"] == "search_conversations")["inputSchema"]["properties"]
    assert {"model", "role", "context", "preferredAgent", "preferredModel"}.issubset(search_schema)

    searched = server.handle({"method": "tools/call", "params": {"name": "search_conversations",
        "arguments": {"agent": "codex", "query": "Atlas"}}})["structuredContent"]["conversations"]
    assert len(searched) == 2 and "HIDDEN" not in json.dumps(searched)
    subagents = server.handle({"method": "tools/call", "params": {"name": "search_conversations",
        "arguments": {"agent": "codex", "role": "subagent", "model": "luna", "query": "cache"}}})["structuredContent"]["conversations"]
    assert len(subagents) == 1 and subagents[0]["roleName"] == "Scout"
    recalled = server.handle({"method": "tools/call", "params": {"name": "recall_context", "arguments": {
        "query": "what did the cache subagent find", "agent": "codex", "role": "subagent",
        "model": "luna", "sources": ["conversations"], "limit": 2}}})["structuredContent"]
    assert recalled["coverage"] == {"conversationCount": 1, "memoryCount": 0,
        "personal": "not requested", "sources": ["conversations"]}
    assert recalled["conversations"][0]["roleName"] == "Scout"
    assert "Cache boundary found" in recalled["conversations"][0]["text"]
    assert "HIDDEN" not in json.dumps(recalled)
    searched = [row for row in searched if row["role"] == "agent"]
    result = server.handle({"method": "tools/call", "params": {"name": "read_conversation",
        "arguments": {"id": searched[0]["id"]}}})["structuredContent"]
    assert "Atlas is ready" in result["text"] and "HIDDEN" not in result["text"]
    resources = server.handle({"method": "resources/list"})["resources"]
    assert resources[0]["name"].startswith("@Codex")
    content = server.handle({"method": "resources/read", "params": {"uri": resources[0]["uri"]}})["contents"][0]["text"]
    assert "Historical chat reference" in content and source.read_bytes() == before


def test_agent_only_router_and_personal_memory_tools_are_bounded_and_read_only(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    project = tmp_path / "project"
    preferences = project / ".agent/memory/personal/PREFERENCES.md"
    preferences.parent.mkdir(parents=True)
    preferences.write_text("# Workflow\nPrefer small verified changes.\n")
    working = project / ".agent/memory/working/WORKSPACE.md"
    working.parent.mkdir(parents=True)
    working.write_text("# Current task\nBuild the router.\n")
    before = preferences.read_bytes()
    server = MCPServer(home)

    route = server.handle({"method": "tools/call", "params": {"name": "recommend_model", "arguments": {
        "runner": "claude-code", "task": "Audit and refactor the entire architecture",
        "policy": "auto:balanced", "attachmentKinds": ["image"]}}})["structuredContent"]
    assert route["model"] == "opus" and route["effort"] == "xhigh" and route["complexity"] == "deep"
    profile = server.handle({"method": "tools/call", "params": {"name": "read_personal_memory", "arguments": {
        "projectPath": str(project), "query": "verified workflow"}}})["structuredContent"]
    assert "Prefer small verified changes" in profile["static"][0]["content"]
    assert "Build the router" in profile["dynamic"]["content"]
    assert preferences.read_bytes() == before


def test_shared_memory_search_uses_read_only_desktop_index(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    root = home / "Library/Application Support/Agentic Workspaces"; root.mkdir(parents=True)
    database = root / "workspaces.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE knowledge_notes(workspace TEXT,id TEXT,title TEXT,body TEXT);
            CREATE TABLE knowledge_sources(workspace TEXT,id TEXT,provider TEXT,path TEXT,title TEXT,digest TEXT,imported TEXT,index_version INTEGER);
            CREATE TABLE knowledge_origins(workspace TEXT,note TEXT,source TEXT,line INTEGER);
            INSERT INTO knowledge_notes VALUES('w','n','Atlas note','Use the Atlas release checklist.');
            INSERT INTO knowledge_sources VALUES('w','s','cursor','/tmp/rule.mdc','Rule','d','now',1);
            INSERT INTO knowledge_origins VALUES('w','n','s',7);
        """)
    before = database.read_bytes()
    rows = search_memory("Atlas checklist", home=home)
    assert rows[0]["id"] == "n" and rows[0]["origins"][0]["line"] == 7
    assert database.read_bytes() == before


def test_install_and_remove_preserve_unrelated_tool_configuration(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    (home / ".cursor").mkdir()
    (home / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {"existing": {"command": "safe"}}, "other": True}))
    (home / ".config/opencode").mkdir(parents=True)
    (home / ".config/opencode/opencode.json").write_text(json.dumps({"mcp": {"existing": {"type": "remote"}}, "theme": "dark"}))
    (home / ".codex").mkdir()
    (home / ".codex/config.toml").write_text('model = "configured"\n')
    package = Path(__file__).resolve().parents[1] / "harness_manager"

    completed = SimpleNamespace(returncode=0, stderr="")
    with patch("harness_manager.workspaces.context_integration.shutil.which", return_value="/usr/bin/claude"), \
         patch("harness_manager.workspaces.context_integration.subprocess.run", return_value=completed) as run:
        result = context_integration.install(home, package)
    launcher = Path(result["launcher"])
    assert launcher.is_file() and launcher.stat().st_mode & stat.S_IXUSR
    assert (launcher.parent.parent / "share/agentic-stack/context-mcp").is_dir()
    assert "[mcp_servers.agentic-stack]" in (home / ".codex/config.toml").read_text()
    cursor = json.loads((home / ".cursor/mcp.json").read_text())
    opencode = json.loads((home / ".config/opencode/opencode.json").read_text())
    assert cursor["other"] is True and "existing" in cursor["mcpServers"] and "agentic-stack" in cursor["mcpServers"]
    assert opencode["theme"] == "dark" and "existing" in opencode["mcp"] and "agentic-stack" in opencode["mcp"]
    assert set(result["tagSkills"]) == {"Claude Code", "Codex", "OpenCode", "Cursor"}
    for relative in context_integration.SKILL_TARGETS.values():
        skill = home / relative
        assert skill.is_file() and "@Claude" in skill.read_text()
    assert any(call.args[0][1:4] == ["mcp", "add", "--scope"] for call in run.call_args_list)

    with patch("harness_manager.workspaces.context_integration.shutil.which", return_value="/usr/bin/claude"), \
         patch("harness_manager.workspaces.context_integration.subprocess.run", return_value=completed):
        context_integration.remove(home)
    assert "agentic-stack" not in (home / ".codex/config.toml").read_text()
    cursor = json.loads((home / ".cursor/mcp.json").read_text())
    opencode = json.loads((home / ".config/opencode/opencode.json").read_text())
    assert cursor["other"] is True and "existing" in cursor["mcpServers"]
    assert opencode["theme"] == "dark" and "existing" in opencode["mcp"]
    assert all(not (home / relative).exists() for relative in context_integration.SKILL_TARGETS.values())


def test_tag_skill_install_preserves_unmanaged_existing_skill(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    target = home / context_integration.SKILL_TARGETS["Cursor"]
    target.parent.mkdir(parents=True)
    target.write_text("user owned\n")
    package = Path(__file__).resolve().parents[1] / "harness_manager"

    result = context_integration._install_tag_skills(home, package)
    assert result["Cursor"] == "kept existing skill"
    assert target.read_text() == "user owned\n"
    context_integration._remove_tag_skills(home)
    assert target.read_text() == "user owned\n"


def test_opencode_v2_server_layout_is_supported_and_removed(tmp_path):
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps({"mcp": {"servers": {"existing": {"type": "remote"}}}}))
    context_integration._opencode_config(path, Path("/tmp/agentic-stack"), major=2)
    configured = json.loads(path.read_text())
    assert configured["mcp"]["servers"]["agentic-stack"]["disabled"] is False
    assert "existing" in configured["mcp"]["servers"]

    context_integration._remove_opencode(path)
    configured = json.loads(path.read_text())
    assert "agentic-stack" not in configured["mcp"]["servers"]
    assert "existing" in configured["mcp"]["servers"]


def test_stdio_protocol_emits_one_json_rpc_response_per_request(tmp_path):
    home = tmp_path / "home"; home.mkdir(); seed(home)
    requests = "\n".join(json.dumps(value) for value in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]) + "\n"
    env = dict(os.environ, HOME=str(home), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run([sys.executable, "-m", "harness_manager.context_mcp"], input=requests,
                            text=True, capture_output=True, env=env, timeout=10, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert [row["id"] for row in rows] == [1, 2]
    assert rows[1]["result"]["tools"][0]["name"] == "recall_context"
