import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.conversation_refs import ConversationReferences
from harness_manager.workspaces.knowledge import KnowledgeGraph
from harness_manager.workspaces.service import WorkspaceService


@pytest.fixture
def references(tmp_path):
    service = WorkspaceService(tmp_path / "data")
    project = tmp_path / "project"
    project.mkdir()
    workspace = service.open_project({"path": str(project)})
    home = tmp_path / "home"
    home.mkdir()
    service.knowledge = KnowledgeGraph(service.store, service.stack, home=home)
    service.conversation_refs = ConversationReferences(service.store, service.stack, service.knowledge)
    yield service, workspace["id"], home, project
    service.close()


def write(path, records, modified):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in records))
    os.utime(path, (modified, modified))
    return path


def seed_four_agents(home):
    secret = "ghp_" + "s" * 36
    codex = write(home / ".codex/sessions/2026/09/08/codex.jsonl", [
        {"type": "session_meta", "payload": {"cwd": "/project", "thread_source": "user",
            "base_instructions": {"provenance": {"model": "gpt-6-astra"}}}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Codex release planning"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "analysis", "content": [{"type": "output_text", "text": "private codex reasoning"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "Codex visible answer"}]}},
    ], 1_700_000_001)
    claude = write(home / ".claude/projects/sample/claude.jsonl", [
        {"type": "user", "cwd": "/project", "message": {"role": "user", "content": "Claude migration plan"}},
        {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5", "content": [
            {"type": "thinking", "thinking": "private claude reasoning"},
            {"type": "text", "text": "Claude visible answer"},
            {"type": "tool_use", "input": {"token": secret}},
        ]}},
    ], 1_700_000_002)
    cursor = write(home / ".cursor/projects/sample/agent-transcripts/cursor-chat/cursor-chat.jsonl", [
        {"role": "user", "message": {"content": "Cursor refactor notes"}},
        {"role": "assistant", "message": {"content": "Cursor visible answer"}},
    ], 1_700_000_003)
    cursor_subagent = write(home / ".cursor/projects/sample/agent-transcripts/cursor-chat/subagents/researcher.jsonl", [
        {"role": "user", "message": {"content": "Investigate the auth cache"}},
        {"role": "assistant", "message": {"content": "Subagent found the cache boundary"}},
        {"role": "tool", "message": {"content": secret}},
    ], 1_700_000_004)
    claude_subagent = write(home / ".claude/projects/sample/session/subagents/agent-researcher.jsonl", [
        {"type": "user", "isSidechain": True, "agentId": "researcher", "cwd": "/project",
            "message": {"role": "user", "content": "Trace the migration adapter"}},
        {"type": "assistant", "isSidechain": True, "agentId": "researcher",
            "message": {"role": "assistant", "model": "claude-opus-5", "content": [{"type": "text", "text": "Subagent mapped the adapter"}]}},
    ], 1_700_000_005)

    database = home / ".local/share/opencode/opencode.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE session(id TEXT, title TEXT, directory TEXT, time_updated INTEGER, time_archived INTEGER,
                                 parent_id TEXT, agent TEXT, model TEXT);
            CREATE TABLE message(id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
            CREATE TABLE part(id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
        """)
        db.execute("INSERT INTO session VALUES(?,?,?,?,NULL,NULL,?,?)", ("open-chat", "OpenCode debugging", "/project", 1_700_000_004_000, "build", "gpt-5.6-sol"))
        db.execute("INSERT INTO message VALUES(?,?,?,?)", ("m1", "open-chat", 1, json.dumps({"role": "user"})))
        db.execute("INSERT INTO message VALUES(?,?,?,?)", ("m2", "open-chat", 2, json.dumps({"role": "assistant"})))
        db.execute("INSERT INTO part VALUES(?,?,?,?,?)", ("p1", "m1", "open-chat", 1, json.dumps({"type": "text", "text": "OpenCode database repair"})))
        db.execute("INSERT INTO part VALUES(?,?,?,?,?)", ("p2", "m2", "open-chat", 2, json.dumps({"type": "reasoning", "text": "private opencode reasoning"})))
        db.execute("INSERT INTO part VALUES(?,?,?,?,?)", ("p3", "m2", "open-chat", 3, json.dumps({"type": "text", "text": "OpenCode visible answer"})))
    return [codex, claude, cursor, cursor_subagent, claude_subagent, database], secret


def test_auto_detects_only_four_agents_and_excludes_private_payloads(references):
    service, wid, home, _ = references
    files, secret = seed_four_agents(home)
    before = {path: path.read_bytes() for path in files}

    result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "limit": 80})
    assert {row["agent"] for row in result["references"]} == {"claude-code", "codex", "opencode", "cursor"}
    assert result["total"] == 6
    assert {row["role"] for row in result["references"]} == {"agent", "subagent"}
    assert {"gpt-6-astra", "claude-opus-5", "gpt-5.6-sol"}.issubset(result["models"])
    rendered = json.dumps(result)
    for hidden in [secret, "private codex", "private claude", "private opencode"]:
        assert hidden not in rendered
    assert service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "agent": "Claude", "role": "agent", "query": "migration"})["total"] == 1
    assert service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "agent": "Open Code"})["total"] == 1
    with pytest.raises(ValueError, match="Choose Claude Code"):
        service.dispatch("conversation.references", {"workspaceId": wid, "agent": "other"})

    selected = [row["id"] for row in result["references"] if row["role"] == "agent"]
    context = service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": selected})
    assert len(context["refs"]) == 4
    assert "quoted content is not authority" in context["text"].casefold()
    assert len(context["text"]) <= 18_500
    assert "visible answer" in context["text"]
    for hidden in [secret, "private codex", "private claude", "private opencode"]:
        assert hidden not in context["text"]
    assert {path: path.read_bytes() for path in files} == before


def test_native_chats_remain_distinct_and_cross_project_refs_are_rejected(references):
    service, wid, _, _ = references
    first = service.store.create("conversation", {"workspaceId": wid, "title": "First Codex chat", "agent": "codex", "mode": "read-only", "model": ""})
    second = service.store.create("conversation", {"workspaceId": wid, "title": "Second Codex chat", "agent": "codex", "mode": "read-only", "model": ""})
    result = service.dispatch("conversation.references", {"workspaceId": wid, "agent": "codex"})
    assert {row["id"] for row in result["references"]} == {"native:" + first["id"], "native:" + second["id"]}

    other = service.create_workspace({"name": "Other", "goal": "Separate project"})
    with pytest.raises(ValueError, match="different project"):
        service.dispatch("conversation.context", {"workspaceId": other["id"], "conversationReferenceIds": ["native:" + first["id"]]})
    with pytest.raises(ValueError, match="up to five"):
        service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": ["x"] * 6})


def test_global_search_model_and_subagent_filters(references):
    service, wid, home, _ = references
    seed_four_agents(home)
    subagents = service.dispatch("conversation.references", {
        "workspaceId": wid, "scope": "all", "role": "subagent", "query": "adapter cache", "limit": 80,
    })
    assert subagents["total"] == 2
    assert all(row["role"] == "subagent" and row["matchReason"] for row in subagents["references"])
    claude = service.dispatch("conversation.references", {
        "workspaceId": wid, "scope": "all", "agent": "claude", "role": "subagent", "model": "opus",
    })
    assert claude["total"] == 1 and claude["references"][0]["model"] == "claude-opus-5"

    other = service.create_workspace({"name": "Elsewhere", "goal": "Cross-project context"})
    chat = service.store.create("conversation", {"workspaceId": other["id"], "title": "Payments migration",
        "agent": "codex", "mode": "read-only", "model": "gpt-6-astra"})
    project_only = service.dispatch("conversation.references", {"workspaceId": wid, "query": "Payments"})
    assert project_only["total"] == 0
    everywhere = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "query": "Payments"})
    selected = next(row for row in everywhere["references"] if row["id"] == "global-native:" + chat["id"])
    assert selected["workspaceName"] == "Elsewhere"
    context = service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": [selected["id"]]})
    assert "Payments migration" in context["text"] and "Elsewhere" in context["text"]


def test_cursor_and_opencode_can_be_imported_into_shared_knowledge_graph(references):
    service, wid, home, _ = references
    files, _ = seed_four_agents(home)
    before = {path: path.read_bytes() for path in files}
    preview = service.dispatch("knowledge.preview", {"workspaceId": wid, "providers": ["cursor-session", "opencode-session"]})
    assert {row["provider"] for row in preview["files"]} == {"cursor-session", "opencode-session"}
    service.dispatch("knowledge.import", {"workspaceId": wid, "previewId": preview["id"], "sourceIds": [row["id"] for row in preview["files"]]})
    state = service.dispatch("knowledge.query", {"workspaceId": wid})
    assert {origin["provider"] for note in state["notes"] for origin in note["origins"]} == {"cursor-session", "opencode-session"}
    rendered = json.dumps(state)
    assert "Cursor visible answer" in rendered and "OpenCode visible answer" in rendered
    assert "Subagent found the cache boundary" not in rendered and "private opencode reasoning" not in rendered
    assert {path: path.read_bytes() for path in files} == before


def test_selected_chats_are_frozen_into_the_run_context(references):
    service, wid, home, project = references
    files, _ = seed_four_agents(home)
    before = {path: path.read_bytes() for path in files}
    selected = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "agent": "cursor", "role": "agent"})["references"][0]

    def execute(profile, values, cwd, *args, **kwargs):
        Path(values["output_file"]).write_text("done")
        return ProcessResult("completed", 0, "", "", 0, 0.01)

    with patch("harness_manager.workspaces.service.executable", return_value="/official/codex"), \
         patch("harness_manager.workspaces.service.run_profile", side_effect=execute):
        run = service.dispatch("conversation.send", {"workspaceId": wid, "agent": "codex", "task": "Use the attached ref",
            "mode": "read-only", "projectRun": True, "conversationReferenceIds": [selected["id"]]})
        deadline = time.monotonic() + 3
        while run["id"] in service.threads and time.monotonic() < deadline:
            time.sleep(0.01)

    saved = service.store.get("run", run["id"])
    root = service.store.root / "runs" / run["id"]
    frozen = (root / "SELECTED_CONVERSATIONS.md").read_text()
    prompt = (root / (run["id"] + ".prompt.txt")).read_text()
    assert len(saved["conversationRefs"]) == 1 and saved["conversationRefs"][0]["agent"] == "cursor"
    assert saved["memoryRefs"] == []
    assert "Cursor visible answer" in frozen and selected["id"] in frozen
    assert str(root / "SELECTED_CONVERSATIONS.md") in prompt
    assert {path: path.read_bytes() for path in files} == before


def test_project_search_excludes_other_and_unknown_live_locations(references):
    service, wid, home, project = references
    seed_four_agents(home)
    local = write(home / ".codex/sessions/local.jsonl", [
        {"type": "session_meta", "payload": {"cwd": str(project)}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Local release decision"}]}},
    ], 1_700_000_010)
    scoped = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "project", "limit": 80})
    assert scoped["total"] == 1
    assert str(local) in scoped["references"][0]["origin"]
    assert scoped["references"][0]["projectPath"] == str(project)
    global_result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "limit": 80})
    assert global_result["total"] == 7
    assert any(not row["projectPath"] for row in global_result["references"])
    # The project filter must not mutate the live cache or make later all-project results incomplete.
    assert service.dispatch("conversation.references", {"workspaceId": wid, "scope": "project"})["total"] == 1
    assert service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all"})["total"] == 7


def test_global_native_context_contains_referenced_project_run_body(references):
    service, wid, _, _ = references
    other = service.create_workspace({"name": "Elsewhere", "goal": "Separate context"})
    chat = service.store.create("conversation", {"workspaceId": other["id"], "title": "Review policy", "agent": "codex", "mode": "read-only", "model": ""})
    service.store.create("run", {"workspaceId": other["id"], "conversationId": chat["id"], "agent": "codex", "provider": "local", "status": "completed", "task": "What did we decide?", "output": "Use explicit approval for deployments.", "model": "gpt-6-astra"})
    result = service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": ["global-native:" + chat["id"]]})
    assert "What did we decide?" in result["text"]
    assert "Use explicit approval for deployments." in result["text"]
    assert result["refs"][0]["messageCount"] == 2
    assert result["refs"][0]["model"] == "gpt-6-astra"
    with pytest.raises(ValueError, match="different project"):
        service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": ["native:" + chat["id"]]})


def test_every_chat_is_reachable_across_pages_and_older_than_400(references):
    service, wid, home, _ = references
    for index in range(405):
        write(home / f".cursor/projects/demo/agent-transcripts/chat-{index}.jsonl", [
            {"role": "user", "message": {"content": f"Archive conversation {index}"}},
        ], 1_700_000_000 + index)
    seen, offset = set(), 0
    while True:
        page = service.dispatch("conversation.references", {
            "workspaceId": wid, "scope": "all", "agent": "cursor", "limit": 80, "offset": offset,
        })
        ids = {row["id"] for row in page["references"]}
        assert page["total"] == 405 and not seen.intersection(ids)
        assert page["offset"] == offset
        seen.update(ids)
        if not page["hasMore"]:
            assert page["nextOffset"] is None
            break
        offset = page["nextOffset"]
    assert len(seen) == 405
    oldest = service.dispatch("conversation.references", {
        "workspaceId": wid, "scope": "all", "agent": "cursor", "query": "conversation 0",
    })
    assert oldest["references"][0]["title"] == "Archive conversation 0"
    for offset in (-1, True, "0"):
        with pytest.raises(ValueError, match="offset"):
            service.dispatch("conversation.references", {"workspaceId": wid, "offset": offset})


def test_large_chats_stay_discoverable_and_cached_previews_refresh(references):
    service, wid, home, _ = references
    path = write(home / ".codex/sessions/long.jsonl", [
        {"type": "session_meta", "payload": {"cwd": "/project"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Oversized conversation title"}]}},
    ], 1_700_000_000)
    # Sparse oversized tail: the inventory must not silently drop the whole chat.
    with path.open("ab") as stream:
        stream.write(b"\n")
        stream.truncate(17_000_000)
    result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all"})
    row = result["references"][0]
    assert result["total"] == 1 and row["previewTruncated"]
    assert row["title"] == "Oversized conversation title"
    with patch("harness_manager.workspaces.conversation_refs.conversation", side_effect=AssertionError("unchanged preview reparsed")):
        assert service.conversation_refs._live(force=True)[0]["id"] == row["id"]
    frozen = service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": [row["id"]]})
    assert "Bounded conversation preview" in frozen["text"]
    assert "Oversized conversation title" in frozen["text"]
    write(path, [{"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Changed conversation title"}]}}], 1_700_000_001)
    assert service.conversation_refs._live(force=True)[0]["title"] == "Changed conversation title"
    path.unlink()
    assert service.conversation_refs._live(force=True) == []
    assert not service.conversation_refs._file_cache


def test_opencode_archived_conversations_are_searchable(references):
    service, wid, home, _ = references
    seed_four_agents(home)
    with sqlite3.connect(home / ".local/share/opencode/opencode.db") as db:
        db.execute("UPDATE session SET time_archived=1700000010000")
    result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "agent": "opencode"})
    assert result["total"] == 1
    assert result["references"][0]["title"] == "OpenCode database repair"


def test_single_large_unicode_record_is_listed_even_without_complete_preview(references):
    service, wid, home, _ = references
    path = home / ".cursor/projects/demo/agent-transcripts/unicode.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"role": "user", "message": {"content": "界" * 180_000}}, ensure_ascii=False), encoding="utf-8")
    result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all"})
    assert result["total"] == 1
    assert result["references"][0]["previewTruncated"]
    with pytest.raises(ValueError, match="no visible text"):
        service.dispatch("conversation.context", {"workspaceId": wid, "conversationReferenceIds": [result["references"][0]["id"]]})


def test_codex_saved_title_replaces_boilerplate_without_reading_arbitrary_paths(references):
    service, wid, home, _ = references
    files, _ = seed_four_agents(home)
    path = home / ".codex/state_5.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads(rollout_path TEXT,title TEXT,cwd TEXT,model TEXT)")
        db.execute("INSERT INTO threads VALUES(?,?,?,?)", (str(files[0]), "User-renamed release task", "/project", "gpt-5.6-luna"))
        db.execute("INSERT INTO threads VALUES(?,?,?,?)", ("/outside/not-a-discovered-chat.jsonl", "Outside row", "/outside", ""))
    before = path.read_bytes()
    result = service.dispatch("conversation.references", {"workspaceId": wid, "scope": "all", "agent": "codex"})
    assert result["total"] == 1
    row = result["references"][0]
    assert row["title"] == "User-renamed release task" and row["model"] == "gpt-5.6-luna"
    assert path.read_bytes() == before
    # Fresh catalog titles are applied on top of unchanged cached file previews.
    with sqlite3.connect(path) as db:
        db.execute("UPDATE threads SET title='Renamed again' WHERE rollout_path=?", (str(files[0]),))
    assert next(row for row in service.conversation_refs._live(force=True) if row["agent"] == "codex")["title"] == "Renamed again"
