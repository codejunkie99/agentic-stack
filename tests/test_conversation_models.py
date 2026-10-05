import json
import threading
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService
from test_conversations import wait_for_task


@pytest.mark.parametrize('runner', ['codex', 'claude-code'])
def test_model_switch_keeps_session_role_access_and_run_history(tmp_path, runner):
    svc = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    ws = svc.open_project({'path': str(project)})
    profile = svc.profiles.save(dict(name='Reviewer', instructions='Review only.', runner=runner, model='first-model', effort='high'))
    calls = []
    hold, entered = threading.Event(), threading.Event()

    def execute(spec, values, *args, **kwargs):
        calls.append((spec['command'], values))
        if len(calls) == 2:
            entered.set()
            assert hold.wait(4)
        events = ([{'type': 'thread.started', 'thread_id': 'same-session'},
                   {'type': 'item.completed', 'item': {'id': 'm', 'type': 'agent_message', 'text': 'Remembered'}}]
                  if runner == 'codex' else [{'type': 'result', 'session_id': 'same-session', 'result': 'Remembered', 'is_error': False}])
        for event in events: kwargs['on_output']('stdout', json.dumps(event)+'\n')
        return ProcessResult('completed', 0, '', '', 0, .01)

    try:
        with patch('harness_manager.workspaces.service.executable', return_value='/agent'), patch('harness_manager.workspaces.service.run_profile', side_effect=execute):
            first = wait_for_task(svc, svc.send_conversation(dict(workspaceId=ws['id'], profileId=profile['id'], task='Remember this')))
            cid = first['conversationId']
            config = dict(workspaceId=ws['id'], conversationId=cid, modelSelection={'model': 'second-model', 'effort': 'low'})
            updated = svc.dispatch('conversation.configure', config)
            assert updated['agentSessionID'] == 'same-session'
            second = svc.send_conversation(dict(workspaceId=ws['id'], conversationId=cid, task='Recall it'))
            assert entered.wait(4)
            svc.dispatch('conversation.configure', dict(config, modelSelection={'model': '', 'effort': ''}))
            assert svc.store.get('run', second['id'])['model'] == 'second-model'
            hold.set(); second = wait_for_task(svc, second)
            third = wait_for_task(svc, svc.send_conversation(dict(workspaceId=ws['id'], conversationId=cid, task='Continue')))
        assert svc.store.get('run', first['id']) == first
        assert [first['model'], second['model'], third['model']] == ['first-model', 'second-model', '']
        assert [first['effort'], second['effort'], third['effort']] == ['high', 'low', '']
        assert all(r['mode'] == 'read-only' and r['agentInstructions'] == 'Review only.' for r in [first, second, third])
        assert second['resumeSessionID'] == third['resumeSessionID'] == 'same-session'
        assert calls[1][1]['model'] == 'second-model'
        assert '--model' in calls[1][0]
        assert ('model_reasoning_effort="low"' if runner == 'codex' else '--effort') in calls[1][0]
        if runner == 'claude-code':
            assert calls[2][0][calls[2][0].index('--model')+1] == 'default'
            for argv, values in calls:
                assert argv[argv.index('--add-dir')+1] == str(__import__('pathlib').Path(values['prompt_file']).parent)
        assert svc.store.get('agentProfile', profile['id']) == profile
        svc.close(); svc = WorkspaceService(tmp_path/'data')
        assert svc.store.get('conversation', cid)['model'] == ''
        assert len(svc.store.all('conversation')) == 1
    finally:
        hold.set(); svc.close()


def test_configuration_rejects_bad_input_atomically_and_allows_explicit_profile_override(tmp_path):
    svc = WorkspaceService(tmp_path/'data')
    try:
        ws = svc.create_workspace({'name': 'Test', 'goal': 'Test'})
        c = svc.store.create('conversation', dict(workspaceId=ws['id'], agent='claude-code', model='sonnet', effort='low', mode='read-only'))
        for selection in [None, [], {}, {'model': 'opus'}, {'model': [], 'effort': ''}, {'model': 'opus', 'effort': 'ultra'}, {'model': 'bad\nmodel', 'effort': ''}]:
            with pytest.raises(ValueError):
                svc.configure_conversation(dict(workspaceId=ws['id'], conversationId=c['id'], modelSelection=selection))
            assert svc.store.get('conversation', c['id']) == c
        with pytest.raises(ValueError, match='different project'):
            svc.configure_conversation(dict(workspaceId='other', conversationId=c['id'], modelSelection={'model': 'opus', 'effort': ''}))
        p = svc.profiles.save(dict(name='Builder', instructions='Be concise', model='original', effort='high'))
        with patch('harness_manager.workspaces.service.executable', return_value='/agent'), patch.object(svc, 'start_run', return_value={'id': 'r'}):
            svc.send_conversation(dict(workspaceId=ws['id'], profileId=p['id'], task='Hi', modelSelection={'model': 'override', 'effort': 'low'}))
        new = next(x for x in svc.store.all('conversation') if x['id'] != c['id'])
        assert new['model'] == 'override' and new['effort'] == 'low'
        assert svc.store.get('agentProfile', p['id']) == p
    finally: svc.close()


def test_configured_catalog_takes_precedence_and_recovers_from_malformed_rows(tmp_path, monkeypatch):
    home = tmp_path/'codex'; home.mkdir()
    monkeypatch.setenv('CODEX_HOME', str(home))
    (home/'config.toml').write_text('model_catalog_json = "router.json"\n')
    (home/'models_cache.json').write_text(json.dumps({'models': [{'slug': 'cached', 'visibility': 'list'}]}))
    catalog = home/'router.json'
    catalog.write_text(json.dumps({'models': [None, {'slug': 'routed', 'visibility': 'list', 'supported_reasoning_levels': None}, {'slug': 'routed', 'visibility': 'list'}]}))
    svc = WorkspaceService(tmp_path/'data')
    try:
        result = svc.profiles.models()
        assert [x['id'] for x in result['models'] if x['runner'] == 'codex'] == ['routed']
        assert result['codexSource'] == 'Configured Codex catalog'
        assert not result['warning']
        catalog.write_text('{broken')
        result = svc.profiles.models()
        assert result['models'][0]['id'] == 'cached' and result['warning']
    finally: svc.close()


def test_reported_model_is_public_bounded_and_excludes_subtasks():
    from harness_manager.workspaces.task_stream import TaskStream
    updates = []
    stream = TaskStream('claude-code', lambda **values: updates.append(values))
    for model, parent in [('claude-opus-5', None), ('child-model', 'child'), ('bad\nmodel', None)]:
        stream.feed('stdout', json.dumps({'type': 'assistant', 'parent_tool_use_id': parent,
            'account': 'private', 'message': {'model': model, 'id': 'm', 'content': []}})+'\n')
    stream.flush(force=True)
    assert updates[-1]['reportedModel'] == 'claude-opus-5'
    assert 'private' not in json.dumps(updates)


def test_skill_catalog_marks_existing_project_skills_without_overwriting(tmp_path):
    svc = WorkspaceService(tmp_path/'data')
    try:
        ws = svc.create_workspace({'name': 'Skills', 'goal': 'Test'})
        assert not any(s.get('installed') for s in svc.dispatch('skills.catalog', {'workspaceId': ws['id']})['skills'])
        svc.stack.initialize(ws['id'])
        catalog = svc.dispatch('skills.catalog', {'workspaceId': ws['id']})['skills']
        installed = next(row for row in catalog if row.get('installed'))
        path = svc.stack.root(ws['id'])/'.agent/skills'/installed['name']/'SKILL.md'
        original = path.read_bytes()
        with pytest.raises(ValueError, match='already exists'):
            svc.dispatch('skills.add', {'workspaceId': ws['id'], 'id': installed['id']})
        assert path.read_bytes() == original
    finally: svc.close()
