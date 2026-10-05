"""Exercise actual loop workers and the portable memory lifecycle from desktop RPC."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from harness_manager.loops.runner import cancel_run, prepare_run, resume_run, start_run
from harness_manager.loops.storage import CheckpointError, execution_lock, load_checkpoint
from harness_manager.workspaces.service import WorkspaceService
from test_loop_runner import install_target, git, rewrite_json


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError('The expected live transition did not occur')


def setup_service(tmp_path):
    project = install_target(tmp_path)
    service = WorkspaceService(tmp_path/'data')
    ws = service.open_project({'path': str(project)})
    return service, ws, project


def parameters(service, ws, **extra):
    contract = service.dispatch('loops.snapshot', {'workspaceId': ws['id']})['contracts'][0]
    return {'workspaceId': ws['id'], 'loop': contract['id'], 'digest': contract['digest'],
            'task': 'make result equal green', 'approved': True, **extra}


def test_native_loop_start_requires_current_review_and_runs_in_owned_worktree(tmp_path):
    service, ws, project = setup_service(tmp_path)
    try:
        with pytest.raises(ValueError, match='approve'):
            service.dispatch('loops.start', parameters(service, ws, approved=False))
        with pytest.raises(ValueError, match='changed'):
            service.dispatch('loops.start', parameters(service, ws, digest='stale'))
        result = service.dispatch('loops.start', parameters(service, ws))
        run = wait_for(lambda: next((r for r in service.loops.snapshot(ws['id'])['runs'] if r['id'] == result['runId'] and r['status'] == 'completed'), None))
        assert run['attempts'] == 2
        assert Path(run['worktree'], 'result.txt').read_text() == 'green'
        assert not (project/'result.txt').exists()
        assert json.loads(run['detail'])['attempts'][-1]['checker']['decision'] == 'APPROVE'
    finally:
        service.close()


def test_native_resume_retains_approval_and_contract_checks(tmp_path):
    service, ws, project = setup_service(tmp_path)
    try:
        paused = start_run(project, 'ci-sweeper', 'make result equal green')
        assert paused['status'] == 'awaiting_approval'
        service.dispatch('loops.resume', parameters(service, ws, runId=paused['run_id']))
        wait_for(lambda: load_checkpoint(project, paused['run_id'])['status'] == 'completed')
    finally:
        service.close()


def test_initialize_keeps_existing_loop_contract_set_consistent(tmp_path):
    service, ws, project = setup_service(tmp_path)
    try:
        before = {p.name: p.read_bytes() for p in (project/'.agent/loops').glob('*.json')}
        service.stack.initialize(ws['id'])
        after = {p.name: p.read_bytes() for p in (project/'.agent/loops').glob('*.json')}
        assert before == after
        assert [c['id'] for c in service.loops.snapshot(ws['id'])['contracts']] == ['ci-sweeper']
    finally:
        service.close()


def test_loop_snapshot_returns_reconnect_state_when_project_scan_stalls(tmp_path, monkeypatch):
    service, ws, _ = setup_service(tmp_path)
    try:
        monkeypatch.setattr(
            'harness_manager.workspaces.loop_control.subprocess.run',
            lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired(args[0], 5)),
        )
        state = service.loops.snapshot(ws['id'])
        assert state['contracts'] == []
        assert state['runs'] == []
        assert state['projectAccessError'] == (
            'Project files are unavailable. Reconnect this project folder to restore access.'
        )
    finally:
        service.close()


def test_configuring_reporter_keeps_read_only_contract_and_detected_binary(tmp_path, monkeypatch):
    service = WorkspaceService(tmp_path/'data')
    ws = service.create_workspace({'name': 'Reporter', 'goal': 'Read-only reports'})
    service.stack.initialize(ws['id'])
    try:
        state = service.loops.snapshot(ws['id'])
        monkeypatch.setattr('harness_manager.workspaces.loop_control.executable', lambda _: '/custom/bin/codex')
        service.loops.configure({'workspaceId': ws['id'], 'loop': 'daily-triage', 'digest': state['profileDigest'], 'makerAgent': 'codex'})
        data = json.loads((service.stack.root(ws['id'])/'.agent/loops/harnesses.json').read_text())
        reporter = data['profiles']['reporter']
        assert reporter['command'][0] == '/custom/bin/codex'
        assert 'read-only' in reporter['command']
        assert not reporter['mutates_workspace'] and reporter['capabilities'] == []
        assert not next(c for c in service.loops.snapshot(ws['id'])['contracts'] if c['id'] == 'daily-triage')['error']
    finally:
        service.close()


def test_native_cancel_reaps_child_and_does_not_run_verifier(tmp_path):
    service, ws, project = setup_service(tmp_path)
    pid_file = tmp_path/'maker-pid'
    (project/'maker.py').write_text(f'import os,time,pathlib\npathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n')
    git(project, 'add', 'maker.py'); git(project, 'commit', '-m', 'sleeping maker')
    try:
        run = service.dispatch('loops.start', parameters(service, ws))
        wait_for(pid_file.exists)
        with pytest.raises(ValueError, match='active loop'):
            service.dispatch('loops.start', parameters(service, ws))
        with pytest.raises(ValueError, match='active loop'):
            service.dispatch('run.start', {'workspaceId': ws['id'], 'task': 'another task', 'projectRun': True})
        service.dispatch('loops.cancel', {'workspaceId': ws['id'], 'runId': run['runId']})
        wait_for(lambda: load_checkpoint(project, run['runId'])['status'] == 'cancelled', timeout=3)
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid_file.read_text()), 0)
        checkpoint = load_checkpoint(project, run['runId'])
        assert 'verifier' not in checkpoint['attempts'][0]
    finally:
        service.close()


def test_cli_stop_is_observed_during_child_and_second_coordinator_is_refused(tmp_path):
    project = install_target(tmp_path)
    pid_file = tmp_path/'pid'
    (project/'maker.py').write_text(f'import os,time,pathlib\npathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n')
    run = prepare_run(project, 'ci-sweeper', 'do it')
    worker = threading.Thread(target=resume_run, args=(project, run['run_id']), kwargs={'approved': True})
    worker.start()
    try:
        wait_for(pid_file.exists)
        with pytest.raises(CheckpointError, match='live coordinator'):
            resume_run(project, run['run_id'], approved=True)
        result = cancel_run(project, run['run_id'])
        assert result['status'] == 'cancelling'
        worker.join(timeout=3)
        assert not worker.is_alive()
        assert load_checkpoint(project, run['run_id'])['status'] == 'cancelled'
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid_file.read_text()), 0)
    finally:
        cancel_run(project, run['run_id'])
        worker.join(timeout=10)


def test_memory_review_round_trip_preserves_notes_and_retraction_history(tmp_path):
    service = WorkspaceService(tmp_path/'data')
    ws = service.create_workspace({'name': 'Memory test', 'goal': 'Review lessons'})
    service.stack.initialize(ws['id'])
    base = {'workspaceId': ws['id'], 'rationale': 'Observed in the repository integration test.'}
    claim = 'Retry transient network failures only after recording the previous request outcome.'
    try:
        service.dispatch('memory.action', dict(base, operation='teach', claim=claim))
        record = service.memory.snapshot(ws['id'])['candidates'][0]
        assert json.loads(record['detail'])['decisions'][-1]['notes'] == base['rationale']
        with pytest.raises(ValueError, match='already exists'):
            service.dispatch('memory.action', dict(base, operation='teach', claim=claim))
        with pytest.raises(ValueError, match='changed'):
            service.dispatch('memory.action', dict(base, operation='reject', id=record['id'], digest='stale'))
        for operation in ['reject', 'reopen', 'graduate']:
            record = service.memory.snapshot(ws['id'])['candidates'][0]
            service.dispatch('memory.action', dict(base, operation=operation, id=record['id'], digest=record['digest']))
        state = service.memory.snapshot(ws['id'])
        accepted = next(r for r in state['lessons'] if r['claim'] == claim)
        assert accepted['status'] == 'accepted'
        history = json.loads(next(r for r in state['candidates'] if r['claim'] == claim)['detail'])['decisions']
        assert [item['action'] for item in history] == ['staged', 'rejected', 'reopened', 'graduated']
        assert all(item.get('notes') == base['rationale'] for item in history)
        service.dispatch('memory.action', dict(base, operation='retract', id=accepted['id'], digest=accepted['digest']))
        assert next(r for r in service.memory.snapshot(ws['id'])['lessons'] if r['claim'] == claim)['status'] == 'retracted'
        assert 'retracted' in (service.stack.root(ws['id'])/'.agent/memory/semantic/lessons.jsonl').read_text()
    finally:
        service.close()


def test_completed_agent_output_stages_one_reusable_learning_candidate(tmp_path):
    service = WorkspaceService(tmp_path/'data')
    ws = service.create_workspace({'name': 'Learning test', 'goal': 'Keep useful findings'})
    service.stack.initialize(ws['id'])
    run = {
        'id': 'run-learning',
        'workspaceId': ws['id'],
        'status': 'needs_review',
        'agent': 'codex',
        'agentName': 'Cache investigator',
        'task': 'Diagnose cache invalidation',
        'output': 'The root cause was a stale cache key; include the workspace digest when constructing cache identities.',
    }
    try:
        learned = service.memory.learn_from_run(run)
        assert learned['status'] == 'staged'
        assert learned['claim'] == run['output']
        detail = json.loads(service.memory.snapshot(ws['id'])['candidates'][0]['detail'])
        assert 'Cache investigator run run-learning' in detail['decisions'][-1]['notes']
        assert service.memory.learn_from_run(run)['id'] == learned['id']
        assert service.memory._learning_claim('Done.') is None
    finally:
        service.close()
