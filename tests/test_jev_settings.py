import json
import os
import pytest
from harness_manager.workspaces.jev_settings import JevSettings, ConfiguredJevProvider


def test_explicit_consent_required_and_public_status_has_no_secret(tmp_path):
    settings = JevSettings(tmp_path)
    with pytest.raises(ValueError):
        settings.configure(token='synthetic-token', enabled=True, consent=False)
    assert not settings.path.exists()
    status = settings.configure(token='synthetic-token', enabled=True, consent=True)
    assert status['enabled'] and status['configured']
    assert 'synthetic-token' not in json.dumps(status)
    assert os.stat(settings.path).st_mode & 0o777 == 0o600


def test_instances_reload_and_disconnect_without_touching_evidence(tmp_path):
    settings = JevSettings(tmp_path)
    first = ConfiguredJevProvider(settings)
    second = ConfiguredJevProvider(JevSettings(tmp_path))
    assert not first.available and not second.available
    settings.configure(token='synthetic-token', enabled=True, consent=True)
    assert first.available and second.available
    evidence = tmp_path/'evidence.txt'; evidence.write_text('Preserve this')
    settings.disconnect()
    assert not first.available and not second.available
    assert evidence.read_text() == 'Preserve this'


def test_insecure_symlink_and_malformed_config_fail_closed(tmp_path):
    settings = JevSettings(tmp_path)
    settings.configure(token='synthetic-token', enabled=True, consent=True)
    settings.path.chmod(0o644)
    assert not ConfiguredJevProvider(settings).available
    settings.path.unlink()
    target = tmp_path/'unrelated'; target.write_text('{}')
    settings.path.symlink_to(target)
    assert settings.read() == {}
    settings.disconnect()
    assert target.read_text() == '{}'


def test_desktop_setup_is_seen_by_existing_read_only_mcp(tmp_path, monkeypatch):
    from harness_manager.workspaces.service import WorkspaceService
    from harness_manager.context_mcp import MCPServer
    root = tmp_path/'data'
    monkeypatch.setenv('AGENTIC_WORKSPACES_DATA', str(root))
    service = WorkspaceService(root)
    mcp = MCPServer(tmp_path/'home')
    assert not mcp.context_packs.jev_provider.available
    status = service.dispatch('memory.provider.configure', dict(token='synthetic-token', enabled=True, consent=True))
    assert status['configured'] and 'token' not in status
    assert service.jev_memory.provider.available
    assert mcp.context_packs.jev_provider.available
    before = service.jev_settings.path.read_bytes()
    assert service.dispatch('memory.provider.status', {}) == status
    assert service.jev_settings.path.read_bytes() == before
    service.dispatch('memory.provider.disconnect', {})
    assert not mcp.context_packs.jev_provider.available
    service.close()


def test_public_available_matches_actual_provider_and_reports_consent(tmp_path):
    settings = JevSettings(tmp_path)
    provider = ConfiguredJevProvider(settings)
    assert settings.status()['available'] is False
    assert settings.status()['consent'] is False
    settings.configure(token='synthetic-token', enabled=True, consent=True)
    assert settings.status()['available'] is provider.available is True
    assert settings.status()['consent'] is True
    for changes in [dict(enabled=False), dict(consent=False), dict(model=''), dict(token='')]:
        value = dict(version=1, token='synthetic-token', enabled=True, consent=True, model='jev-latest', **{})
        value.update(changes)
        settings.path.write_text(json.dumps(value))
        status = settings.status()
        assert status['available'] is provider.available is False
        assert 'synthetic-token' not in json.dumps(status)
    settings.disconnect()
    assert settings.status()['available'] is provider.available is False


def test_unconfigured_implicit_context_is_local_explicit_jev_remains_visible(tmp_path, monkeypatch):
    from unittest.mock import patch
    from harness_manager.workspaces.service import WorkspaceService
    service = WorkspaceService(tmp_path/'data')
    service.knowledge.home = tmp_path/'home'
    monkeypatch.setattr(service.conversation_refs, '_live', lambda **_: [])
    monkeypatch.setattr(service.profiles, 'models', lambda *a, **k: {'models': []})
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    source = service.add_source(dict(workspaceId=wid, name='Approved', text='SQLite exact approved source body.'))
    service.review_source(dict(id=source['id'], approved=True))
    try:
        with patch('harness_manager.workspaces.service.executable', return_value='/fixture/codex'), patch('threading.Thread.start'):
            implicit = service.start_run(dict(workspaceId=wid, task='Inspect SQLite', projectRun=True))
            service.store.update('run', implicit['id'], status='completed')
            service.threads.clear()
            explicit = service.start_run(dict(workspaceId=wid, task='Inspect SQLite', projectRun=True, contextOptions={'mode': 'jev-fast'}))
        assert implicit['contextOptions']['mode'] == 'local'
        implicit_handover = (service.store.root/'runs'/implicit['id']/'HANDOVER.md').read_text()
        explicit_handover = (service.store.root/'runs'/explicit['id']/'HANDOVER.md').read_text()
        assert source['text'] in implicit_handover and source['text'] not in explicit_handover
        assert explicit['contextOptions']['mode'] == 'jev-fast'
        assert service.dispatch('context.prepare', dict(workspaceId=wid, prompt='SQLite'))['mode'] == 'local'
        failed = service.dispatch('context.prepare', dict(workspaceId=wid, prompt='SQLite', contextOptions={'mode': 'jev-fast'}))
        assert failed['status'] == 'unavailable' and failed['refs'] == []
    finally:
        service.threads.clear()
        service.close()
