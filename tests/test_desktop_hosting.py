"""Real hosted lifecycle plus repository execution and safe file editing."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService


class DesktopHostingTests(unittest.TestCase):
    def test_hosted_server_persists_projects_and_authenticates_every_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root/'repos'
            project = projects/'example'
            project.mkdir(parents=True)
            token = 'test-only-token-' * 4
            env = dict(os.environ, AGENTIC_CONTROL_TOKEN=token)
            command = [sys.executable, '-m', 'harness_manager.cli', 'serve', '--data-root', str(root/'data'),
                       '--project-root', str(projects)]

            def start():
                process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                import selectors
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    if not selector.select(10):
                        process.kill()
                        self.fail('Hosted server did not start')
                line = process.stdout.readline()
                self.assertNotIn(token, line)
                hello = json.loads(line)
                return process, f'http://127.0.0.1:{hello["port"]}/rpc'

            def rpc(url, method, params=None, credential=token, origin=None):
                headers = {'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = origin
                request = urllib.request.Request(url, data=json.dumps({'method': method, 'params': params or {}}).encode(), headers=headers)
                with urllib.request.urlopen(request, timeout=10) as response:
                    return json.load(response)['result']

            process, url = start()
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    rpc(url, 'snapshot', credential='wrong')
                self.assertEqual(denied.exception.code, 401)
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    rpc(url, 'snapshot', origin='https://untrusted.example')
                self.assertEqual(denied.exception.code, 403)
                workspace = rpc(url, 'project.open', {'path': str(project)})
                self.assertEqual(rpc(url, 'project.open', {'path': str(project)})['id'], workspace['id'])
                rpc(url, 'stack.initialize', {'workspaceId': workspace['id']})
                state = rpc(url, 'stack.snapshot', {'workspaceId': workspace['id']})
                self.assertTrue(state['initialized'])
                self.assertTrue(state['skills'])
                self.assertTrue(state['files'])
                profile = rpc(url, 'agentProfiles.save', {'name': 'Hosted reviewer', 'instructions': 'Review only.', 'model': 'test-model', 'effort': 'low'})
                self.assertTrue(rpc(url, 'agentProfiles.models')['models'])
                self.assertTrue(any(s.get('installed') for s in rpc(url, 'skills.catalog', {'workspaceId': workspace['id']})['skills']))
                # Seed a session record, then exercise its authenticated public configuration API.
                from harness_manager.workspaces.store import Store
                conversation = Store(root/'data').create('conversation', dict(workspaceId=workspace['id'], agent='codex', mode='read-only', model='old', effort='high'))
                updated = rpc(url, 'conversation.configure', {'workspaceId': workspace['id'], 'conversationId': conversation['id'], 'modelSelection': {'model': 'new', 'effort': 'low'}})
                self.assertEqual(updated['model'], 'new')
                with self.assertRaises(urllib.error.HTTPError):
                    rpc(url, 'project.open', {'path': tmp})
            finally:
                process.terminate()
                out, err = process.communicate(timeout=10)
                self.assertNotIn(token, out + err)
            process, url = start()
            try:
                self.assertEqual(rpc(url, 'snapshot')['workspaces'][0]['id'], workspace['id'])
                self.assertEqual(rpc(url, 'snapshot')['agentProfiles'][0]['id'], profile['id'])
                self.assertEqual(rpc(url, 'snapshot')['conversations'][0]['model'], 'new')
            finally:
                process.terminate()
                process.communicate(timeout=10)

    def test_network_binding_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-m', 'harness_manager.cli', 'serve', '--data-root', tmp,
                                     '--host', '0.0.0.0'], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--allow-network', result.stderr)

    def test_project_task_runs_in_real_repository_without_overwriting_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)/'repository'
            project.mkdir()
            (project/'AGENTS.md').write_text('Project-owned instructions')
            (project/'main.py').write_text('print("existing code")')
            service = WorkspaceService(Path(tmp)/'data')
            ws = service.open_project({'path': str(project)})
            with patch('harness_manager.workspaces.service.executable', return_value='/official/codex'), patch('threading.Thread.start'):
                run = service.start_run({'workspaceId': ws['id'], 'task': 'Inspect main.py', 'projectRun': True})
            result = ProcessResult('completed', 0, 'Inspected real code', '', 20, 1)
            with patch('harness_manager.workspaces.service.run_profile', return_value=result) as execute, patch('harness_manager.workspaces.service.executable', return_value='/official/codex'):
                service._execute(run, '', threading.Event())
            self.assertEqual(execute.call_args.args[2], project.resolve())
            self.assertEqual((project/'AGENTS.md').read_text(), 'Project-owned instructions')
            self.assertFalse((project/'HANDOVER.md').exists())
            self.assertEqual(service.store.get('run', run['id'])['status'], 'needs_review')
            service.close()

    def test_editor_detects_concurrent_change_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WorkspaceService(Path(tmp)/'data')
            ws = service.create_workspace({'name': 'Test', 'goal': 'Manage'})
            service.stack.initialize(ws['id'])
            params = {'workspaceId': ws['id'], 'path': '.agent/memory/personal/PREFERENCES.md'}
            original = service.dispatch('stack.file', params)
            service.dispatch('stack.file', dict(params, digest=original['digest'], content='Updated conventions'))
            with self.assertRaisesRegex(ValueError, 'changed'):
                service.dispatch('stack.file', dict(params, digest=original['digest'], content='Stale overwrite'))
            with self.assertRaises(ValueError):
                service.dispatch('stack.file', dict(params, path='.agent/../../outside'))
            external = Path(tmp)/'outside.md'
            external.write_text('outside')
            link = service.stack.root(ws['id'])/'.agent/external.md'
            link.symlink_to(external)
            with self.assertRaises(ValueError):
                service.dispatch('stack.file', dict(params, path='.agent/external.md'))
            service.close()


if __name__ == '__main__':
    unittest.main()
