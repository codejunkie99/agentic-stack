"""Native setup preserves owned files and uses real stack formats/adapters."""
import json
from pathlib import Path

import pytest
from harness_manager.workspaces.service import WorkspaceService


@pytest.fixture
def project(tmp_path):
    app = WorkspaceService(tmp_path/'data')
    folder = tmp_path/'project'; folder.mkdir()
    workspace = app.open_project({'path': str(folder)})
    yield app, workspace['id'], folder
    app.close()


def params(app, wid, **values):
    return {'workspaceId': wid, 'preferencesDigest': app.setup.snapshot(wid)['preferencesDigest'], 'featuresDigest': app.setup.snapshot(wid)['featuresDigest'], **values}


def test_onboarding_saves_preferences_flags_and_real_adapters(project):
    app, wid, root = project
    result = app.dispatch('setup.apply', params(app, wid, answers={'name': 'Fixture', 'languages': 'Swift', 'tests': 'tdd'},
                                              features={'memory_search_fts': True, 'tldraw': False}, adapters=['codex']))
    prefs = (root/'.agent/memory/personal/PREFERENCES.md').read_text()
    assert 'Name: Fixture' in prefs and 'Language(s): Swift' in prefs and 'Test strategy: tdd' in prefs
    assert result['warnings'] == []
    assert app.stack.snapshot(wid)['installed'] == ['codex']
    assert app.setup.snapshot(wid)['features']['memory_search_fts'] is True
    assert (root/'.agents/skills/skillforge/SKILL.md').exists()


def test_onboarding_preserves_existing_preferences_and_unknown_feature_keys(project):
    app, wid, root = project
    app.stack.initialize(wid)
    prefs = root/'.agent/memory/personal/PREFERENCES.md'; prefs.write_text('Always retain my custom preferences.')
    features = root/'.agent/memory/.features.json'; features.write_text(json.dumps({'custom': {'value': 3}, 'tldraw': {'enabled': True, 'custom': 'keep'}}))
    app.dispatch('setup.apply', params(app, wid, answers={'name': 'Different'}, features={'memory_search_fts': True}))
    assert prefs.read_text() == 'Always retain my custom preferences.'
    saved = json.loads(features.read_text())
    assert saved['custom'] == {'value': 3} and saved['tldraw'] == {'enabled': True, 'custom': 'keep'}


def test_stale_and_invalid_setup_does_not_write(project):
    app, wid, root = project
    request = params(app, wid)
    prefs = root/'.agent/memory/personal/PREFERENCES.md'; prefs.parent.mkdir(parents=True); prefs.write_text('Changed outside setup')
    with pytest.raises(ValueError, match='changed'):
        app.dispatch('setup.apply', request)
    assert not (root/'.agent/skills').exists()
    with pytest.raises(ValueError, match='features'):
        app.dispatch('setup.apply', params(app, wid, features={'tldraw': 'true'}))
    assert not (root/'.agent/skills').exists()


def test_setup_reports_adapter_conflicts_and_preserves_files(project):
    app, wid, root = project
    settings = root/'.claude/settings.json'; settings.parent.mkdir(); settings.write_text('{"owned":true}')
    result = app.dispatch('setup.apply', params(app, wid, adapters=['claude-code']))
    assert result['warnings'] and 'manual merge' in result['warnings'][0]
    assert settings.read_text() == '{"owned":true}'


def test_setup_rejects_symlink_escape(project, tmp_path):
    app, wid, root = project
    outside = tmp_path/'outside'; outside.mkdir()
    (root/'.agent').symlink_to(outside)
    with pytest.raises(ValueError, match='inside'):
        app.dispatch('setup.apply', {'workspaceId': wid})
    assert not list(outside.iterdir())
