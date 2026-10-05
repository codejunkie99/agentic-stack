"""Native harness integration uses official auth and real portable skills."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.agents import AgentAccounts
from harness_manager.workspaces.service import WorkspaceService


class AgentStackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = WorkspaceService(Path(self.tmp.name))
        self.ws = self.service.create_workspace({'name': 'Project', 'goal': 'Build'})

    def tearDown(self):
        self.service.threads.clear()
        self.service.close()
        self.tmp.cleanup()

    def test_auth_output_is_reduced_to_non_secret_status(self):
        from subprocess import CompletedProcess
        accounts = AgentAccounts(Path(self.tmp.name))
        with patch('harness_manager.workspaces.agents.executable', return_value='/official/claude'), patch('subprocess.run', side_effect=[
            CompletedProcess([], 0, '2.1 test', ''),
            CompletedProcess([], 0, json.dumps({'loggedIn': True, 'email': 'private@example.com', 'token': 'secret-token'}), '')]):
            status = accounts.detect('claude-code')
        self.assertTrue(status['signedIn'])
        self.assertNotIn('private@example.com', json.dumps(status))
        self.assertNotIn('secret-token', json.dumps(status))

    def test_login_uses_cli_not_copied_oauth_credentials(self):
        with patch('harness_manager.workspaces.agents.executable', return_value='/path with spaces/claude'):
            result = self.service.accounts.login_script('claude-code')
        content = Path(result['path']).read_text()
        self.assertIn("'/path with spaces/claude' auth login", content)
        self.assertNotIn('token', content)

    def test_selected_harness_executes_claude_and_parses_result(self):
        source = self.service.add_source({'workspaceId': self.ws['id'], 'name': 'Brief', 'text': 'Reviewed input'})
        self.service.review_source({'id': source['id'], 'approved': True})
        with patch('harness_manager.workspaces.service.executable', return_value='/official/claude'), patch('threading.Thread.start'):
            run = self.service.start_run({'workspaceId': self.ws['id'], 'task': 'Summarize', 'agent': 'claude-code'})
        result = ProcessResult('completed', 0, '', '', 30, 1)
        def emit(*args, **kwargs):
            kwargs['on_output']('stdout', json.dumps({'type': 'result', 'result': 'A cited answer', 'is_error': False}) + '\n')
            return result
        with patch('harness_manager.workspaces.service.run_profile', side_effect=emit) as execute, patch('harness_manager.workspaces.service.executable', return_value='/official/claude'):
            self.service._execute(run, '', threading.Event())
        command = execute.call_args.args[0]['command']
        self.assertIn('--print', command)
        self.assertIn('stream-json', command)
        self.assertIn('--include-partial-messages', command)
        self.assertIn('plan', command)
        self.assertNotIn('--dangerously-skip-permissions', command)
        saved = self.service.store.get('run', run['id'])
        self.assertEqual(saved['output'], 'A cited answer')
        self.assertEqual(saved['status'], 'needs_review')

    def test_initialize_preserves_memory_and_installs_real_adapters(self):
        root = self.service.stack.root(self.ws['id'])
        preferences = root/'.agent/memory/personal/PREFERENCES.md'
        preferences.parent.mkdir(parents=True)
        preferences.write_text('User conventions')
        self.service.stack.initialize(self.ws['id'])
        self.service.stack.adapter({'workspaceId': self.ws['id'], 'adapter': 'claude-code'})
        self.service.stack.adapter({'workspaceId': self.ws['id'], 'adapter': 'codex'})
        self.assertEqual(preferences.read_text(), 'User conventions')
        self.assertTrue((root/'.claude/settings.json').is_file())
        self.assertTrue((root/'.claude/skills/skillforge/SKILL.md').is_file())
        self.assertTrue((root/'.agents/skills/skillforge/SKILL.md').is_file())
        self.assertEqual(self.service.stack.snapshot(self.ws['id'])['installed'], ['claude-code', 'codex'])

    def test_existing_claude_settings_are_never_overwritten(self):
        root = self.service.stack.root(self.ws['id'])
        file = root/'.claude/settings.json'
        file.parent.mkdir(parents=True)
        file.write_text('{"userSetting":true}')
        with self.assertRaisesRegex(ValueError, 'manual merge'):
            self.service.stack.adapter({'workspaceId': self.ws['id'], 'adapter': 'claude-code'})
        self.assertEqual(file.read_text(), '{"userSetting":true}')

    def test_skill_import_copies_support_files_and_rejects_external_links(self):
        skill = Path(self.tmp.name)/'catalog/demo'
        skill.mkdir(parents=True)
        (skill/'SKILL.md').write_text('---\nname: demo\ndescription: Example\n---\nDo the task.')
        (skill/'helper.py').write_text('print("example")')
        catalog = [{'id': 'demo-id', 'name': 'demo', 'path': str(skill)}]
        with patch.object(self.service.stack, 'catalog', return_value=catalog):
            self.service.stack.add_skill({'workspaceId': self.ws['id'], 'id': 'demo-id'})
            with self.assertRaisesRegex(ValueError, 'already exists'):
                self.service.stack.add_skill({'workspaceId': self.ws['id'], 'id': 'demo-id'})
        self.assertTrue((self.service.stack.root(self.ws['id'])/'.agent/skills/demo/helper.py').is_file())
        (skill/'external').symlink_to('/etc/hosts')
        catalog[0]['name'] = 'linked'
        with patch.object(self.service.stack, 'catalog', return_value=catalog), self.assertRaisesRegex(ValueError, 'symbolic links'):
            self.service.stack.add_skill({'workspaceId': self.ws['id'], 'id': 'demo-id'})


if __name__ == '__main__':
    unittest.main()
