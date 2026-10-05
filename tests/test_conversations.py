import json
import time
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService


def wait_for_task(service, run):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        row = service.store.get('run', run['id'])
        if row['id'] not in service.threads:
            return row
        time.sleep(.01)
    pytest.fail('Task did not finish')


@pytest.mark.parametrize('agent', ['codex', 'claude-code'])
def test_conversation_resumes_exact_cli_session_and_retains_access(tmp_path, agent):
    project = tmp_path / 'project'; project.mkdir()
    service = WorkspaceService(tmp_path / 'data')
    ws = service.open_project({'path': str(project)})
    calls = []
    session = 'f25f1191-630a-42e2-8eca-e9a65ae49fe6'
    def execute(profile, values, cwd, *args, **kwargs):
        calls.append((profile['command'], values, cwd))
        from pathlib import Path
        brief = Path(values['prompt_file']).read_text()
        assert 'User message:' in brief and 'Respond naturally to greetings' in brief
        assert 'conversation brief' in profile['command'][-1]
        events = ([{'type': 'thread.started', 'thread_id': session},
                   {'type': 'item.completed', 'item': {'id': 'm', 'type': 'agent_message', 'text': 'Remembered'}}]
                  if agent == 'codex' else [{'type': 'system', 'subtype': 'init', 'session_id': session},
                                            {'type': 'result', 'session_id': session, 'result': 'Remembered', 'is_error': False}])
        for event in events:
            kwargs['on_output']('stdout', json.dumps(event) + '\n')
        return ProcessResult('completed', 0, '', '', 0, .01)
    try:
        with patch('harness_manager.workspaces.service.executable', return_value='/official/agent'), patch('harness_manager.workspaces.service.run_profile', side_effect=execute):
            first = service.dispatch('conversation.send', {'workspaceId': ws['id'], 'agent': agent, 'task': 'Remember my release code', 'mode': 'read-only'})
            first = wait_for_task(service, first)
            cid = first['conversationId']
            assert first['status'] == 'needs_review'
            assert service.store.get('conversation', cid)['agentSessionID'] == session
            second = service.dispatch('conversation.send', {'workspaceId': ws['id'], 'conversationId': cid, 'task': 'What is the code?', 'mode': 'workspace-write', 'agent': 'codex'})
            second = wait_for_task(service, second)
        assert first['conversationId'] == second['conversationId']
        assert len(service.snapshot()['conversations']) == 1
        assert second['mode'] == 'read-only' and second['agent'] == agent
        assert second['output'] == 'Remembered'
        assert calls[0][1]['session_id'] == ''
        assert calls[1][1]['session_id'] == session
        assert ('resume' if agent == 'codex' else '--resume') in calls[1][0]
        assert ('read-only' if agent == 'codex' else 'plan') in calls[1][0]
        assert '--dangerously-bypass-approvals-and-sandbox' not in calls[1][0]
        assert '--dangerously-skip-permissions' not in calls[1][0]
        assert calls[1][2] == project.resolve()
        assert service.store.get('conversation', cid)['title'] == 'Remember my release code'
    finally:
        service.close()


def test_conversations_reject_other_projects_and_invalid_models(tmp_path):
    service = WorkspaceService(tmp_path / 'data')
    first = service.create_workspace({'name': 'First', 'goal': 'Test'})
    other = service.create_workspace({'name': 'Other', 'goal': 'Test'})
    conversation = service.store.create('conversation', {'workspaceId': first['id'], 'title': 'Private', 'agent': 'codex', 'mode': 'read-only', 'model': ''})
    try:
        with pytest.raises(ValueError, match='different project'):
            service.send_conversation({'workspaceId': other['id'], 'conversationId': conversation['id'], 'task': 'Continue'})
        with pytest.raises(ValueError, match='model'):
            service.send_conversation({'workspaceId': first['id'], 'task': 'Start', 'model': []})
        assert len(service.store.all('conversation')) == 1
        assert service.store.all('run') == []
    finally:
        service.close()
