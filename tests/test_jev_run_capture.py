import threading
from harness_manager.workspaces.service import WorkspaceService


class Provider:
    available = True
    def evaluate(self, state, questions, **kwargs):
        return {'model': 'fixture', 'answers': {key: {'choice': 'lesson', 'confidence': .9} for key in questions}}


def make_run(service, wid, **updates):
    return service.store.create('run', dict(workspaceId=wid, status='needs_review',
        contextOptions={'mode': 'jev'}, output='Include the workspace digest in cache keys.', agent='codex', **updates))


def test_completed_run_captures_exact_output_once_without_accepting_it(tmp_path):
    service = WorkspaceService(tmp_path, jev_provider=Provider())
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    run = make_run(service, wid)
    result = service._capture_run_memory(run)
    assert result['status'] == 'completed'
    saved = service.store.get('run', run['id'])
    assert saved['status'] == 'needs_review' and saved['output'] == run['output']
    assert service.memory_ledger.evidence(wid, result['evidenceId'])['body'] == run['output']
    assert service.memory_ledger.claims(wid)[0]['status'] == 'proposed'
    assert service._capture_run_memory(saved)['receiptId'] == result['receiptId']


def test_capture_failure_does_not_fail_completed_run_or_echo_exception(tmp_path):
    class Broken:
        def evaluate(self, *args, **kwargs):
            raise RuntimeError('private source content')
    service = WorkspaceService(tmp_path, jev_provider=Broken())
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    run = make_run(service, wid)
    assert service._capture_run_memory(run) is None
    saved = service.store.get('run', run['id'])
    assert saved['status'] == 'needs_review'
    assert 'private source' not in saved['learningError']


def test_off_local_failed_and_cancelled_runs_do_not_capture(tmp_path):
    service = WorkspaceService(tmp_path, jev_provider=Provider())
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    run = make_run(service, wid)
    for mode in ['off', 'local']:
        assert service._capture_run_memory(dict(run, contextOptions={'mode': mode})) is None
    assert service._capture_run_memory(dict(run, status='failed')) is None
    cancelled = threading.Event(); cancelled.set()
    assert service._capture_run_memory(run, cancelled) is None
    assert service.memory_ledger.claims(wid) == []


def test_disabled_provider_retains_local_observation_and_reports_unavailable(tmp_path):
    service = WorkspaceService(tmp_path)
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    run = make_run(service, wid)
    result = service._capture_run_memory(run)
    assert result['status'] == 'unavailable'
    assert not service.memory_ledger.claims(wid)
    assert service.memory_ledger.evidence(wid, result['evidenceId'])['body'] == run['output']


def test_execute_routes_completed_output_through_jev_capture(tmp_path, monkeypatch):
    from pathlib import Path
    from unittest.mock import patch
    from harness_manager.loops.process import ProcessResult
    service = WorkspaceService(tmp_path/'data', jev_provider=Provider())
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    monkeypatch.setattr(service.conversation_refs, '_live', lambda: [])
    with patch('harness_manager.workspaces.service.executable', return_value='/fixture/codex'), patch('threading.Thread.start'):
        run = service.start_run(dict(workspaceId=wid, task='Inspect synthetic cache behavior', projectRun=True,
                                     contextOptions={'mode': 'jev'}))
    def finish(profile, values, *args, **kwargs):
        Path(values['output_file']).write_text('Include workspace digest in cache keys.')
        return ProcessResult('completed', 0, '', '', 20, 1)
    with patch('harness_manager.workspaces.service.run_profile', side_effect=finish), patch('harness_manager.workspaces.service.executable', return_value='/fixture/codex'):
        service._execute(run, '', threading.Event())
    saved = service.store.get('run', run['id'])
    assert saved['status'] == 'needs_review'
    assert saved['memoryCapture']['status'] == 'completed'
    assert service.memory_ledger.claims(wid)[0]['body'] == saved['output']
    service.close()


def test_late_cloud_completion_captures_without_original_execution_thread(tmp_path):
    class Cloud:
        def __init__(self, credential): pass
        def path(self, box, suffix): return suffix
        def request(self, method, path):
            if path.startswith('/prompts/'):
                return {'promptRun': {'done': True, 'status': 'finished'}}
            return {'events': [{'taskId': 'fixture-prompt', 'data': {'content': 'Cache keys need workspace identity.'}}], 'pageInfo': {}}
    service = WorkspaceService(tmp_path, provider_factory=Cloud, jev_provider=Provider())
    wid = service.store.create('workspace', {'name': 'fixture', 'boxId': 'synthetic-box'})['id']
    run = service.store.create('run', dict(workspaceId=wid, provider='box', promptId='fixture-prompt', status='running',
        contextOptions={'mode': 'jev'}, output='', task='Synthetic task'))
    result = service.refresh_cloud_run({'id': run['id']})
    assert result['status'] == 'needs_review'
    assert result['memoryCapture']['status'] == 'completed'
    again = service.refresh_cloud_run({'id': run['id']})
    assert again['memoryCapture']['receiptId'] == result['memoryCapture']['receiptId']
    assert len(service.memory_ledger.claims(wid)) == 1
    service.close()


def test_context_preview_records_exact_refs_without_query_text(tmp_path, monkeypatch):
    service = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    monkeypatch.setattr(service.conversation_refs, '_live', lambda: [])
    prompt = 'Synthetic private query words'
    result = service.dispatch('context.prepare', dict(workspaceId=wid, prompt=prompt, contextOptions={'mode': 'local'}))
    receipt = service.memory_ledger.history(wid, 'context')[-1]
    assert result['receiptId'] == receipt['id']
    assert receipt['operation'] == 'context'
    assert receipt['payload']['refs'] == []
    assert 'prompt' not in receipt['payload'] and prompt not in str(receipt)
    service.close()
