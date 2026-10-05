"""Asynchronous desktop lifecycle over the repository's existing loop runner."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import threading
from pathlib import Path

from ..loops.runner import cancel_run, contract_digest, prepare_run, resume_run
from ..loops.schema import load_contracts
from ..loops.storage import load_checkpoint, save_checkpoint
from ..transfer_bundle import scan_text_for_secrets
from ..loops.storage import _atomic_text
from .agents import executable, AGENTS


class LoopControl:
    def __init__(self, store, stack):
        self.store, self.stack = store, stack
        self.lock = threading.RLock()
        self.workers = {}
        for job in store.all('loop-job'):
            if job['status'] in {'queued', 'running', 'cancelling'}:
                store.update('loop-job', job['id'], status='interrupted', error='The service stopped during this loop. Inspect its worktree and any surviving agent processes. A run without a safe checkpoint cannot be resumed from the desktop.')

    def active(self, root):
        return any(job['root'] == str(root) and job['status'] in {'queued', 'running', 'cancelling'}
                   for job in self.store.all('loop-job'))

    def snapshot(self, wid):
        root = self.stack.root(wid)
        access_error = ''
        try:
            process = subprocess.run(
                [sys.executable, '-m', 'harness_manager.workspaces.loop_probe', str(root)],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if process.returncode:
                raise OSError(process.stderr.strip() or 'The project folder could not be read.')
            filesystem = json.loads(process.stdout)
        except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
            filesystem = {'contracts': [], 'runs': [], 'profileDigest': ''}
            access_error = 'Project files are unavailable. Reconnect this project folder to restore access.'
        jobs = {job['runId']: job for job in reversed(self.store.all('loop-job')) if job['root'] == str(root)}
        runs = []
        for run in reversed(filesystem['runs']):
            job = jobs.get(run['run_id'])
            status = job['status'] if job and job['status'] in {'queued', 'running', 'cancelling', 'interrupted', 'failed'} else run['status']
            runs.append({'id': run['run_id'], 'name': run['loop_name'], 'task': run['task'], 'status': status,
                         'phase': run.get('phase', ''), 'attempts': len(run.get('attempts', [])),
                         'detail': json.dumps(run, indent=2), 'error': job.get('error', '') if job else '',
                         'worktree': run.get('worktree', {}).get('path', ''),
                         'canResume': status in {'paused', 'awaiting_approval', 'created', 'interrupted'} and run['status'] in {'paused', 'awaiting_approval', 'created', 'interrupted'}})
        return {'contracts': filesystem['contracts'], 'runs': runs,
                'profileDigest': filesystem['profileDigest'], 'projectAccessError': access_error}

    def configure(self, p):
        root = self.stack.root(p['workspaceId'])
        if self.active(root):
            raise ValueError('Stop the current loop before changing its agents.')
        path = root/'.agent/loops/harnesses.json'
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('Initialize the loop contracts first.')
        raw = path.read_bytes()
        if p.get('digest') != hashlib.sha256(raw).hexdigest():
            raise ValueError('The agent profiles changed. Refresh before configuring them.')
        data = json.loads(raw)
        contracts = load_contracts(root, p.get('loop'))
        for key, role in [('makerAgent', contracts['loop']['executor']), ('checkerAgent', contracts['loop'].get('checker'))]:
            if not role:
                continue
            agent = p.get(key)
            binary = executable(agent) if agent in AGENTS else None
            if not binary:
                raise ValueError('Install the selected coding agent on this host first.')
            writing = key == 'makerAgent' and contracts['profiles']['profiles'][role]['mutates_workspace']
            if agent == 'codex':
                command = [binary, 'exec', '--skip-git-repo-check', '--sandbox', 'workspace-write' if writing else 'read-only', '--color', 'never', '{prompt}']
            else:
                command = [binary, '--print', '--permission-mode', 'acceptEdits' if writing else 'plan', '--permission-prompts', 'none', '{prompt}']
            if key == 'checkerAgent':
                command[-1] += '\nEnd with exactly one decision line: APPROVE, REJECT: reason, or ESCALATE: reason.'
            data['profiles'][role] = {'adapter': agent, 'command': command, 'timeout_seconds': 1200 if writing else 600,
                                      'mutates_workspace': writing, 'capabilities': ['workspace_write'] if writing else [], 'usage_source': 'none'}
        _atomic_text(path, json.dumps(data, indent=2) + '\n')
        return {'text': 'Loop agent profiles configured. Review the verifier command and limits before starting a loop.'}

    def launch(self, p, *, resume=False):
        root = self.stack.root(p['workspaceId'])
        with self.lock:
            if self.active(root):
                raise ValueError('This project already has an active loop. Stop it or wait for it to finish.')
            if p.get('approved') is not True:
                raise ValueError('Review the contract and approve this loop before starting it.')
            if resume:
                run = load_checkpoint(root, p.get('runId'))
                if run['status'] not in {'paused', 'awaiting_approval', 'created', 'interrupted'}:
                    raise ValueError('This loop has ended. Start a new loop instead.')
                name = run['loop_name']
            else:
                name = p.get('loop')
                task = p.get('task')
                if not isinstance(task, str) or not task.strip() or len(task) > 12000:
                    raise ValueError('Enter a loop task of 1–12,000 characters.')
                if scan_text_for_secrets(task):
                    raise ValueError('Remove credentials from the loop task.')
            current = load_contracts(root, name)
            if p.get('digest') != contract_digest(current):
                raise ValueError('The loop contract changed. Refresh and review it before starting.')
            if not resume:
                run = prepare_run(root, name, task.strip())
            if run['status'] == 'audit_failed':
                raise ValueError('The loop checkpoint or audit could not be written.')
            if resume and run['status'] == 'interrupted':
                # Resumption is explicit and checks the execution contract again.
                run['status'] = 'paused'
                save_checkpoint(root, run)
            job = self.store.create('loop-job', {'workspaceId': p['workspaceId'], 'root': str(root),
                'runId': run['run_id'], 'status': 'queued', 'error': ''})
            event = threading.Event()
            worker = threading.Thread(target=self._execute, args=(job, event), daemon=True)
            self.workers[job['id']] = (worker, event)
            worker.start()
            return {'text': 'Loop started. Its checkpoint and owned worktree remain in the project.', 'runId': run['run_id']}

    def _execute(self, job, event):
        try:
            self.store.update('loop-job', job['id'], status='running')
            result = resume_run(Path(job['root']), job['runId'], approved=True, cancel_event=event)
            self.store.update('loop-job', job['id'], status=result['status'])
        except Exception as exc:
            self.store.update('loop-job', job['id'], status='failed', error=str(exc)[:4000])
        finally:
            with self.lock:
                self.workers.pop(job['id'], None)

    def cancel(self, p):
        root = self.stack.root(p['workspaceId'])
        with self.lock:
            result = cancel_run(root, p.get('runId'))
            for job in self.store.all('loop-job'):
                if job['root'] == str(root) and job['runId'] == p.get('runId') and job['id'] in self.workers:
                    self.workers[job['id']][1].set()
                    self.store.update('loop-job', job['id'], status='cancelling')
            return {'text': 'Stop requested. The loop will confirm cancellation after its child process exits.', 'status': result['status']}

    def close(self):
        with self.lock:
            workers = list(self.workers.values())
            for _, event in workers:
                event.set()
        for worker, _ in workers:
            worker.join(timeout=3)
