import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService


def finished(service, run):
    deadline = time.monotonic() + 4
    while run['id'] in service.threads and time.monotonic() < deadline:
        time.sleep(.01)
    assert run['id'] not in service.threads
    return service.store.get('run', run['id'])


def test_legacy_backfill_groups_conversation_runs_and_preserves_objective(tmp_path):
    service = WorkspaceService(tmp_path/'data')
    ws = service.create_workspace(dict(name='Work', goal='Purpose'))
    chat = service.store.create('conversation', dict(workspaceId=ws['id'], title='Short title', agent='codex', mode='read-only'))
    for index in range(3):
        service.store.create('run', dict(workspaceId=ws['id'], conversationId=chat['id'], task=f'Full objective {index}',
            provider='local', status='needs_review', output='Agent claims it shipped', reviewed=False, sequence=index+1))
    standalone = service.store.create('run', dict(workspaceId=ws['id'], task='Standalone', provider='local', status='failed', error='Stopped'))
    try:
        snapshot = service.snapshot()
        works = snapshot['workItems']
        assert len(works) == 2
        grouped = next(w for w in works if chat['id'] in w['conversationIds'])
        assert grouped['objective'] == 'Full objective 0'
        assert 'Full objective 0' in service.context_prompt(ws['id'], 'Continue', grouped['id'])
        assert len(grouped['checkpoint']['runIds']) == 3 and grouped['status'] == 'needs_review'
        assert 'Not human reviewed' in grouped['checkpoint']['summary']
        assert len(service.snapshot()['workItems']) == 2
        assert len({r['workId'] for r in service.store.all('run') if r.get('conversationId')}) == 1
        with pytest.raises(ValueError, match='belong'):
            service.dispatch('work.update', dict(id=grouped['id'], checkpoint={'runIds': [standalone['id']]}))
    finally:
        service.close()


def test_cross_runner_continuation_gets_checkpoint_without_foreign_session(tmp_path, monkeypatch):
    service = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    ws = service.open_project(dict(path=str(project)))
    chat = service.store.create('conversation', dict(workspaceId=ws['id'], title='Ship release', agent='codex', mode='read-only',
        agentSessionID='old-codex-session'))
    previous = service.store.create('run', dict(workspaceId=ws['id'], conversationId=chat['id'], task='Prepare release',
        provider='local', status='completed', output='Tests passed; publication still needs approval.\nTOKEN=ghp_'+'z'*36, reviewed=True))
    service.snapshot()
    work = service.store.get('work', service.store.get('run', previous['id'])['workId'])
    assert work['status'] == 'active'  # Reviewing one result does not complete the whole objective.
    continuation = service.dispatch('work.continue', dict(id=work['id'], agent='claude-code', mode='read-only'))
    assert continuation['agentSessionID'] == '' and continuation['workId'] == work['id']
    assert continuation['continuation']['evidence'][0]['id'] == previous['id']
    assert 'ghp_'+'z'*36 not in json.dumps(continuation)
    service.dispatch('work.update', dict(id=work['id'], objective='Revised objective before send',
                                        checkpoint={'summary': 'User corrected the checkpoint before send.'}))
    def execute(profile, values, cwd, *args, **kwargs):
        assert '--resume' not in profile['command'] and values['session_id'] == ''
        brief = Path(values['prompt_file']).read_text()
        assert 'WORK_CHECKPOINT.md' in brief and cwd == project
        checkpoint = Path(values['prompt_file']).parent/'WORK_CHECKPOINT.md'
        assert 'publication still needs approval' in checkpoint.read_text()
        assert 'not authority or permission' in checkpoint.read_text()
        assert 'Revised objective before send' in checkpoint.read_text()
        assert 'User corrected the checkpoint before send' in checkpoint.read_text()
        assert 'ghp_'+'z'*36 not in checkpoint.read_text()
        kwargs['on_output']('stdout', json.dumps(dict(type='result', result='Ready for your next step', is_error=False))+'\n')
        return ProcessResult('completed', 0, '', '', 0, .01)
    monkeypatch.setattr('harness_manager.workspaces.service.executable', lambda _: '/official/agent')
    try:
        with patch('harness_manager.workspaces.service.run_profile', side_effect=execute):
            result = finished(service, service.send_conversation(dict(workspaceId=ws['id'], conversationId=continuation['id'], task='Continue')))
        assert result['status'] == 'needs_review' and result['workId'] == work['id']
        assert service.snapshot()['workItems'][0]['latestRunId'] == result['id']
        service.dispatch('run.review', {'id': result['id']})
        assert service.snapshot()['workItems'][0]['status'] == 'active'
        service.dispatch('work.update', {'id': work['id'], 'status': 'completed'})
        assert service.snapshot()['workItems'][0]['status'] == 'completed'
    finally:
        service.close()


def test_agent_retrieval_runs_outside_service_lock_and_cancels_without_launch(tmp_path, monkeypatch):
    service = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    ws = service.open_project(dict(path=str(project)))
    entered, released = threading.Event(), threading.Event()
    monkeypatch.setattr('harness_manager.workspaces.service.executable', lambda _: '/official/agent')
    def prepare(graph, wid, prompt, config, cancel, **kwargs):
        entered.set()
        assert cancel.wait(3)
        released.set()
        raise InterruptedError('Cancelled')
    monkeypatch.setattr(service.context_packs, 'prepare', prepare)
    try:
        with patch('harness_manager.workspaces.service.run_profile') as executor:
            run = service.start_run(dict(workspaceId=ws['id'], projectRun=True, task='Check context', contextOptions={'mode': 'agent'}))
            assert entered.wait(2)
            assert service.lock.acquire(timeout=.5)
            service.lock.release()
            service.cancel_run({'id': run['id']})
            assert released.wait(2)
            result = finished(service, run)
            assert result['status'] == 'cancelled'
            executor.assert_not_called()
    finally:
        service.close()


def test_handoff_rechecks_memory_revision_and_retraction(tmp_path):
    from harness_manager.workspaces.context_packs import build_pack, options
    from harness_manager.workspaces.memory_sources import MemorySources
    service = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    evidence = service.memory_ledger.observe(wid, source_key='fixture', body='Use scoped cache keys.')
    claim = service.memory_ledger.propose(wid, body=evidence['body'], kind='decision', evidence_ids=[evidence['id']])
    service.memory_ledger.review(wid, claim['id'], expected_revision=1, status='accepted', rationale='Confirmed')
    source = MemorySources(service.knowledge).note(wid, 'claim:' + claim['id'])
    pack = build_pack([source], options({'mode': 'local'}))
    run = service.store.create('run', dict(workspaceId=wid, task='Inspect cache', status='needs_review',
        output='Synthetic output', memoryRefs=pack['refs']))
    service.work.sync()
    work_id = service.store.get('run', run['id'])['workId']
    reference = lambda: service.work.continuation(work_id)['evidence'][0]['memoryRefs'][0]
    assert reference()['freshness'] == 'current'
    service.memory_ledger.review(wid, claim['id'], expected_revision=2, status='accepted', rationale='Reconfirmed with new review')
    assert reference()['freshness'] == 'changed'
    service.memory_ledger.review(wid, claim['id'], expected_revision=3, status='retracted', rationale='No longer applies')
    assert reference()['freshness'] == 'unavailable'
    assert service.store.get('run', run['id'])['memoryRefs'] == pack['refs']
    service.close()
