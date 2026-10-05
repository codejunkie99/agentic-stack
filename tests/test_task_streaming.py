import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_manager.workspaces.service import WorkspaceService
from harness_manager.workspaces.task_stream import TaskStream, MAX_EVENT, MAX_LIVE_TEXT, MAX_ACTIVITY


def emit(stream, *events):
    for event in events:
        stream.feed('stdout', json.dumps(event) + '\n')


def test_codex_updates_replace_messages_and_omit_private_payloads():
    saved = {}
    stream = TaskStream('codex', lambda **values: saved.update(values))
    emit(stream,
         {'type': 'item.completed', 'item': {'id': 'r', 'type': 'reasoning', 'text': 'PRIVATE-REASONING'}},
         {'type': 'item.updated', 'item': {'id': 'm', 'type': 'agent_message', 'text': 'Partial'}},
         {'type': 'item.completed', 'item': {'id': 'm', 'type': 'agent_message', 'text': 'Partial answer'}},
         {'type': 'item.started', 'item': {'id': 't', 'type': 'command_execution', 'command': 'SECRET-ARG'}},
         {'type': 'item.completed', 'item': {'id': 't', 'type': 'command_execution', 'aggregated_output': 'SECRET-RESULT', 'exit_code': 1}})
    stream.finish('completed')
    assert saved['liveOutput'] == 'Partial answer'
    assert stream.final == 'Partial answer'
    assert saved['activity'][-1]['status'] == 'failed'
    assert not any(value in json.dumps(saved) for value in ['PRIVATE-REASONING', 'SECRET-ARG', 'SECRET-RESULT'])


def test_claude_deltas_do_not_duplicate_complete_message_and_result():
    saved = {}
    stream = TaskStream('claude-code', lambda **values: saved.update(values))
    emit(stream,
         {'type': 'system', 'subtype': 'init', 'api_key': 'PRIVATE-ACCOUNT'},
         {'type': 'stream_event', 'event': {'type': 'message_start', 'message': {'id': 'm1'}}},
         {'type': 'stream_event', 'event': {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': 'PRIVATE-THINKING'}}},
         {'type': 'stream_event', 'event': {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'text_delta', 'text': 'Hello '}}},
         {'type': 'stream_event', 'event': {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'text_delta', 'text': 'world'}}},
         {'type': 'assistant', 'message': {'id': 'm1', 'content': [{'type': 'text', 'text': 'Hello world'}, {'type': 'tool_use', 'id': 't1', 'name': 'Read', 'input': {'path': 'PRIVATE-PATH'}}]}},
         {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': 'PRIVATE-FILE'}]}},
         {'type': 'assistant', 'parent_tool_use_id': 't1', 'message': {'content': [{'type': 'text', 'text': 'PRIVATE-SUBTASK'}]}},
         {'type': 'result', 'result': 'Final answer', 'is_error': False})
    stream.finish('completed')
    assert saved['liveOutput'] == 'Hello world'
    assert stream.has_result and stream.final == 'Final answer'
    assert saved['activity'][-1]['status'] == 'completed'
    assert 'PRIVATE-' not in json.dumps(saved)


def test_partial_lines_and_unterminated_final_record():
    saved = {}
    stream = TaskStream('claude-code', lambda **values: saved.update(values))
    line = json.dumps({'type': 'result', 'result': 'Ready 🌲', 'is_error': False})
    for char in line:
        stream.feed('stdout', char)
    assert not stream.has_result
    stream.end_input()
    assert stream.final == 'Ready 🌲'


def test_malformed_and_oversized_events_recover_with_bounded_state():
    saved = {}
    stream = TaskStream('codex', lambda **values: saved.update(values))
    for line in ['not json', '[]', 'null', '{"type": []}', '{"type":"item.completed","item":null}']:
        stream.feed('stdout', line + '\n')
    stream.feed('stdout', 'x' * (MAX_EVENT + 1))
    assert not stream.buffer and stream.discarding
    stream.feed('stdout', 'more\n')
    for i in range(80):
        emit(stream, {'type': 'item.completed', 'item': {'id': str(i), 'type': 'agent_message', 'text': 'x' * 3000}},
             {'type': 'item.completed', 'item': {'id': 't' + str(i), 'type': 'file_change'}})
    stream.finish('cancelled')
    assert len(saved['liveOutput']) <= MAX_LIVE_TEXT
    assert len(saved['activity']) <= MAX_ACTIVITY
    assert stream.buffer == ''


@pytest.mark.parametrize('agent', ['codex', 'claude-code'])
@pytest.mark.parametrize('cancel', [False, True])
def test_service_publishes_before_exit_and_keeps_partial_on_cancel(tmp_path, agent, cancel):
    project = tmp_path / 'project'; project.mkdir()
    service = WorkspaceService(tmp_path / 'data')
    gate = tmp_path / 'finish'
    if agent == 'codex':
        first = {'type': 'item.completed', 'item': {'id': 'm1', 'type': 'agent_message', 'text': 'Progress before completion'}}
        last = {'type': 'item.completed', 'item': {'id': 'm2', 'type': 'agent_message', 'text': 'Final answer'}}
    else:
        first = {'type': 'assistant', 'message': {'id': 'm1', 'content': [{'type': 'text', 'text': 'Progress before completion'}]}}
        last = {'type': 'result', 'result': 'Final answer', 'is_error': False}
    executable = tmp_path / 'agent'
    executable.write_text(f'#!{sys.executable}\nimport pathlib,time,json,sys\n'
                          f'print({json.dumps(first)!r}, flush=True)\n'
                          f'while not pathlib.Path({str(gate)!r}).exists(): time.sleep(.02)\n'
                          f'print({json.dumps(last)!r}, flush=True)\n')
    executable.chmod(0o700)
    try:
        ws = service.open_project({'path': str(project)})
        with patch('harness_manager.workspaces.service.executable', return_value=str(executable)):
            run = service.start_run({'workspaceId': ws['id'], 'task': 'Test progress', 'agent': agent, 'projectRun': True})
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                current = next(row for row in service.snapshot()['runs'] if row['id'] == run['id'])
                if current.get('liveOutput'):
                    break
                time.sleep(.05)
            assert current['status'] == 'running'
            assert current['liveOutput'] == 'Progress before completion'
            assert current['output'] == ''
            if cancel:
                service.cancel_run({'id': run['id']})
            else:
                gate.touch()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                current = service.store.get('run', run['id'])
                if current['status'] not in {'running', 'queued', 'cancelling'}:
                    break
                time.sleep(.05)
            assert current['status'] == ('cancelled' if cancel else 'needs_review')
            assert current['output'] == ('' if cancel else 'Final answer')
            assert 'Progress before completion' in current['liveOutput']
    finally:
        service.close()


def test_claude_missing_result_does_not_approve_partial_text(tmp_path):
    from harness_manager.loops.process import ProcessResult
    service = WorkspaceService(tmp_path / 'data')
    ws = service.create_workspace({'name': 'Test', 'goal': 'Check'})
    with patch('harness_manager.workspaces.service.executable', return_value='/agent'), patch('threading.Thread.start'):
        run = service.start_run({'workspaceId': ws['id'], 'task': 'Test', 'projectRun': True, 'agent': 'claude-code'})
    def truncated(*args, **kwargs):
        kwargs['on_output']('stdout', json.dumps({'type': 'assistant', 'message': {'id': 'm', 'content': [{'type': 'text', 'text': 'Incomplete'}]}}) + '\n')
        return ProcessResult('completed', 0, '', '', 10, .1)
    try:
        with patch('harness_manager.workspaces.service.run_profile', side_effect=truncated), patch('harness_manager.workspaces.service.executable', return_value='/agent'):
            service._execute(run, '', threading.Event())
        saved = service.store.get('run', run['id'])
        assert saved['status'] == 'failed'
        assert saved['output'] == '' and saved['liveOutput'] == 'Incomplete'
        assert 'without a final result' in saved['error']
    finally:
        service.close()
