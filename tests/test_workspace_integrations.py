"""Portable tool migration with real temporary files and SQLite round trips."""
import json
from pathlib import Path

import pytest

from harness_manager.workspaces.integrations import discover
from harness_manager.workspaces.knowledge import KnowledgeGraph
from harness_manager.workspaces.service import WorkspaceService


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def service(tmp_path):
    app = WorkspaceService(tmp_path/'data')
    home, project = tmp_path/'home', tmp_path/'project'
    home.mkdir(); project.mkdir()
    ws = app.open_project({'path': str(project)})
    app.knowledge = KnowledgeGraph(app.store, app.stack, home=home)
    yield app, ws['id'], home, project
    app.close()


def test_detection_reads_presence_not_credentials(service, monkeypatch):
    app, wid, home, project = service
    monkeypatch.setattr('harness_manager.workspaces.integrations.shutil.which', lambda _: None)
    put(home/'.cursor/rules/team.mdc', 'Use explicit return types.')
    put(home/'.codex/auth.json', '{"access_token":"private-account-secret"}')
    result = app.dispatch('integrations.discover', {'workspaceId': wid})
    cursor = next(t for t in result['tools'] if t['id'] == 'cursor')
    assert cursor['detected'] and str(home/'.cursor/rules') in cursor['locations']
    assert {tool['id'] for tool in result['tools']} == {'claude', 'codex', 'opencode', 'cursor'}
    assert 'private-account-secret' not in json.dumps(result)
    assert 'auth.json' not in json.dumps(result)


def test_multi_tool_migration_dedup_and_provenance(service):
    app, wid, home, project = service
    text = '# Release practice\nUse release checklist and Python verification.'
    files = [put(project/'.cursor/rules/release.mdc', text),
             put(project/'.github/instructions/release.instructions.md', text),
             put(home/'.gemini/GEMINI.md', text),
             put(home/'.config/opencode/skills/review/SKILL.md', '# Review\nCheck correctness before merge.')]
    before = {p: p.read_bytes() for p in files}
    params = {'workspaceId': wid, 'providers': ['cursor', 'copilot', 'gemini', 'opencode']}
    scan = app.dispatch('knowledge.preview', params)
    assert len(scan['files']) == 4
    app.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': scan['id'], 'sourceIds': [f['id'] for f in scan['files']]})
    graph = app.dispatch('knowledge.query', {'workspaceId': wid, 'query': 'release checklist'})
    assert graph['matched'] == 1
    assert {o['provider'] for o in graph['notes'][0]['origins']} == {'cursor', 'copilot', 'gemini'}
    scan = app.dispatch('knowledge.preview', params)
    result = app.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': scan['id'], 'sourceIds': [f['id'] for f in scan['files']]})
    assert '0 new or changed' in result['text']
    assert all(p.read_bytes() == data for p, data in before.items())
    context = app.dispatch('knowledge.context', {'workspaceId': wid, 'task': 'release checklist'})
    assert context


def test_migration_skips_credential_files_links_and_binaries(service):
    app, wid, home, project = service
    secret = 'ghp_' + 'x'*36
    put(project/'.cursor/rules/good.mdc', '# Rules\nUse SwiftUI.\nGITHUB_TOKEN='+secret)
    put(project/'.cursor/rules/auth.json', secret)
    put(project/'.cursor/rules/settings.json', secret)
    put(project/'.cursor/rules/blob.db', secret)
    outside = put(home/'outside.md', 'Never include linked files')
    (project/'.cursor/rules/linked.md').symlink_to(outside)
    scan = app.dispatch('knowledge.preview', {'workspaceId': wid, 'providers': ['cursor']})
    assert len(scan['files']) == 1
    assert scan['redactedLines'] == 1
    assert secret not in json.dumps(scan)
    put(project/'.cursor/rules/good.mdc', 'Changed after preview')
    with pytest.raises(ValueError, match='changed'):
        app.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': scan['id'], 'sourceIds': [f['id'] for f in scan['files']]})


def test_any_tool_export_folder_is_previewed_and_selective(service):
    app, wid, home, project = service
    folder = home/'Other Tool Export'
    put(folder/'notes.md', '# Architecture\nKeep the memory boundary explicit.')
    put(folder/'rules.toml', 'description = "Portable coding convention"')
    scan = app.dispatch('knowledge.preview', {'workspaceId': wid, 'providers': ['folder'], 'folder': str(folder)})
    chosen = next(f for f in scan['files'] if f['path'].endswith('notes.md'))
    app.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': scan['id'], 'sourceIds': [chosen['id']]})
    assert app.dispatch('knowledge.query', {'workspaceId': wid})['total'] == 1
    assert app.dispatch('knowledge.query', {'workspaceId': wid, 'query': 'Portable'})['matched'] == 0


def test_exported_jsonl_preserves_line_numbers_with_blank_lines():
    from harness_manager.workspaces.knowledge import exported_conversation
    raw = '\n' + json.dumps({'role': 'user', 'content': 'Remember the Cedar deployment.'}) + '\n\n' + json.dumps({'role': 'assistant', 'content': 'Use the reviewed migration plan.'})
    segments, _, _ = exported_conversation(raw, '.jsonl', 'session')
    assert [segment[2] for segment in segments] == [2, 4]


def test_exported_conversations_omit_reasoning_and_tool_payloads(service):
    app, wid, home, project = service
    folder = home/'Exports'
    put(folder/'opencode.json', json.dumps({'messages': [
        {'info': {'role': 'user'}, 'parts': [{'type': 'text', 'text': 'Explain the migration design'}]},
        {'info': {'role': 'assistant'}, 'parts': [{'type': 'reasoning', 'text': 'HIDDEN_REASONING'}, {'type': 'tool', 'text': 'PRIVATE_TOOL_DATA'}, {'type': 'text', 'text': 'Retain original source provenance.'}]},
        {'role': 'system', 'content': 'PRIVATE_SYSTEM_DATA'}]}))
    scan = app.dispatch('knowledge.preview', {'workspaceId': wid, 'providers': ['folder'], 'folder': str(folder)})
    assert len(scan['files']) == 1
    app.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': scan['id'], 'sourceIds': [f['id'] for f in scan['files']]})
    result = json.dumps(app.dispatch('knowledge.query', {'workspaceId': wid}))
    assert 'Retain original source provenance' in result
    assert 'Explain the migration design' in result
    assert 'HIDDEN_REASONING' not in result and 'PRIVATE_' not in result


def test_opencode_data_is_detected_without_standalone_cli(service, monkeypatch):
    app, wid, home, project = service
    monkeypatch.setattr('harness_manager.workspaces.integrations.shutil.which', lambda _: None)
    from harness_manager.workspaces.integrations import TOOLS
    name, _, _, homes, projects, skills = TOOLS['opencode']
    monkeypatch.setitem(TOOLS, 'opencode', (name, '', '', homes, projects, skills))
    (home/'.local/share/opencode').mkdir(parents=True)
    result = discover(home, project)
    opencode = next(t for t in result['tools'] if t['id'] == 'opencode')
    assert opencode['detected']
    assert opencode['executable'] == ''
