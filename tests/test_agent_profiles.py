import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService
from test_conversations import wait_for_task


def profile(**values):
    return dict(name='Release reviewer', role='Review releases', instructions='End every reply with CHECKED.',
                runner='codex', model='chosen-model', effort='high', mode='read-only', **values)


def test_profiles_persist_archive_restore_and_validate(tmp_path):
    svc = WorkspaceService(tmp_path/'data')
    saved = svc.dispatch('agentProfiles.save', profile())
    svc.dispatch('agentProfiles.archive', {'id': saved['id'], 'archived': True})
    edited = svc.dispatch('agentProfiles.save', dict(profile(), id=saved['id'], name='Changed'))
    assert edited['archived'] and edited['name'] == 'Changed'
    svc.close()
    svc = WorkspaceService(tmp_path/'data')
    try:
        assert svc.snapshot()['agentProfiles'][0]['instructions'] == 'End every reply with CHECKED.'
        restored = svc.dispatch('agentProfiles.archive', {'id': saved['id'], 'archived': False})
        assert not restored['archived']
        for key, value in [('name', ''), ('instructions', ' '), ('model', []), ('mode', 'full-access'), ('runner', 'unknown'), ('effort', 'reckless')]:
            with pytest.raises(ValueError): svc.dispatch('agentProfiles.save', dict(profile(), **{key: value}))
        with pytest.raises(ValueError): svc.dispatch('agentProfiles.archive', {'id': saved['id'], 'archived': 'yes'})
        with pytest.raises(ValueError): svc.dispatch('agentProfiles.save', dict(profile(), runner='claude-code', effort='ultra'))
        assert len(svc.snapshot()['agentProfiles']) == 1
    finally: svc.close()


@pytest.mark.parametrize('runner', ['codex', 'claude-code'])
def test_profile_reaches_execution_and_conversation_freezes_configuration(tmp_path, runner):
    svc = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    ws = svc.open_project({'path': str(project)})
    agent = svc.dispatch('agentProfiles.save', dict(profile(), runner=runner))
    calls = []
    def execute(spec, values, cwd, *a, **kw):
        calls.append((spec['command'], values, Path(values['prompt_file']).read_text()))
        events = ([{'type': 'thread.started', 'thread_id': 'test-profile-session'}, {'type': 'item.completed', 'item': {'id': 'm', 'type': 'agent_message', 'text': 'CHECKED'}}]
                  if runner == 'codex' else [{'type': 'result', 'session_id': 'test-profile-session', 'result': 'CHECKED', 'is_error': False}])
        for event in events: kw['on_output']('stdout', json.dumps(event)+'\n')
        return ProcessResult('completed', 0, '', '', 0, .01)
    try:
        with patch('harness_manager.workspaces.service.executable', return_value='/agent'), patch('harness_manager.workspaces.service.run_profile', side_effect=execute):
            first = wait_for_task(svc, svc.send_conversation({'workspaceId': ws['id'], 'profileId': agent['id'], 'task': 'Review this', 'agent': 'codex', 'model': 'ignored', 'effort': 'low', 'mode': 'workspace-write'}))
            svc.dispatch('agentProfiles.save', dict(agent, instructions='REPLACEMENT', model='new-model', effort='low', mode='workspace-write'))
            svc.dispatch('agentProfiles.archive', {'id': agent['id'], 'archived': True})
            second = wait_for_task(svc, svc.send_conversation({'workspaceId': ws['id'], 'conversationId': first['conversationId'], 'task': 'Continue'}))
            with pytest.raises(ValueError, match='Restore'):
                svc.send_conversation({'workspaceId': ws['id'], 'profileId': agent['id'], 'task': 'New'})
        assert first['agent'] == second['agent'] == runner
        assert first['model'] == second['model'] == 'chosen-model'
        assert first['effort'] == second['effort'] == 'high'
        assert second['mode'] == 'read-only'
        assert second['resumeSessionID'] == 'test-profile-session'
        assert second['agentName'] == agent['name'] and second['profileId'] == agent['id']
        assert len(svc.store.all('conversation')) == 1
        for argv, values, prompt in calls:
            assert values['model'] == 'chosen-model' and '--model' in argv
            assert 'End every reply with CHECKED.' in prompt and 'REPLACEMENT' not in prompt
            assert ('model_reasoning_effort="high"' if runner == 'codex' else '--effort') in argv
            if runner == 'claude-code': assert argv[argv.index('--effort')+1] == 'high'
    finally: svc.close()


def test_model_catalog_uses_only_public_cache_fields_and_handles_missing_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path/'codex'))
    svc = WorkspaceService(tmp_path/'data')
    try:
        assert all(x['runner'] == 'claude-code' for x in svc.profiles.models()['models'])
        cache = tmp_path/'codex/models_cache.json'; cache.parent.mkdir()
        cache.write_text(json.dumps({'secret': 'PRIVATE', 'models': [
            {'slug': 'model-one', 'display_name': 'Model One', 'visibility': 'list', 'secret': 'PRIVATE', 'supported_reasoning_levels': [{'effort': 'high'}]},
            {'slug': 'hidden', 'visibility': 'hide'}, {'slug': '../bad\nmodel', 'visibility': 'list'}]}))
        data = svc.profiles.models()
        assert data['models'][0] == {
            'id': 'model-one', 'name': 'Model One', 'runner': 'codex', 'efforts': ['high'],
                'tier': 'balanced', 'capabilities': ['text', 'tools', 'files', 'image'],
            'summary': 'Balanced for everyday coding and tool use'}
        assert 'PRIVATE' not in json.dumps(data) and 'hidden' not in json.dumps(data)
        cache.write_text('broken')
        assert all(x['runner'] == 'claude-code' for x in svc.profiles.models()['models'])
    finally: svc.close()
