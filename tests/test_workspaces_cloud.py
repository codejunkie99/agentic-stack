"""Exercise Box lifecycle and result boundaries without creating billable machines."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from harness_manager.workspaces.box import BoxProvider, ProviderError
from harness_manager.workspaces.service import WorkspaceService


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = Mock()
        self.provider.path = BoxProvider.path
        self.service = WorkspaceService(Path(self.tmp.name), provider_factory=lambda _: self.provider)
        self.ws = self.service.create_workspace({'name': 'Cloud', 'goal': 'Review evidence', 'provider': 'box'})
        self.source = self.service.add_source({'workspaceId': self.ws['id'], 'name': 'Brief', 'text': '  Preserve this exact source.\n'})
        self.service.review_source({'id': self.source['id'], 'approved': True})

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def start_box(self):
        self.provider.create.return_value = {'id': 'bx_23456789', 'status': 'ready', 'box': None}
        return self.service.cloud_action({'workspaceId': self.ws['id'], 'action': 'start', 'credential': 'test'})

    def run_record(self, **overrides):
        return self.service.store.create('run', dict({'workspaceId': self.ws['id'], 'provider': 'box',
            'status': 'running', 'promptId': 'prompt_123', 'output': '', 'error': '', 'task': 'Summarize',
            'timeoutSeconds': 10, 'model': '', 'mode': 'read-only'}, **overrides))

    def test_preserves_original_source_bytes(self):
        self.assertEqual(self.source['text'], '  Preserve this exact source.\n')

    def test_nullable_box_response_and_existing_machine_guard(self):
        result = self.start_box()
        self.assertEqual(result['boxId'], 'bx_23456789')
        with self.assertRaisesRegex(ValueError, 'already has'):
            self.start_box()
        self.assertEqual(self.provider.create.call_count, 1)

    def test_fork_prepares_local_child_then_reuses_key_on_start(self):
        self.start_box()
        child = self.service.cloud_action({'workspaceId': self.ws['id'], 'action': 'fork', 'credential': 'test'})
        self.assertEqual(child['forkOf'], 'bx_23456789')
        self.assertEqual(child['state'], 'not_started')
        self.provider.action.assert_not_called()
        self.assertEqual(len(self.service.sources(child['id'], True)), 1)
        self.provider.action.side_effect = ProviderError('Connection lost')
        for _ in range(2):
            with self.assertRaises(ProviderError):
                self.service.cloud_action({'workspaceId': child['id'], 'action': 'start', 'credential': 'test'})
        self.assertEqual(self.provider.action.call_args_list[0], self.provider.action.call_args_list[1])

    def test_expired_create_key_is_not_retried(self):
        self.service.store.update('workspace', self.ws['id'], creationAttemptAt='2020-01-01T00:00:00Z')
        with self.assertRaisesRegex(ProviderError, 'expiry'):
            self.start_box()
        self.provider.create.assert_not_called()

    def test_queued_status_is_not_a_completed_result_and_events_are_scoped(self):
        self.start_box()
        run = self.run_record()
        self.provider.request.side_effect = [
            {'promptRun': {'status': 'queued', 'done': False}},
            {'events': [{'taskId': 'unrelated', 'data': {'content': 'wrong result'}},
                        {'taskId': 'prompt_123', 'data': {'content': 'obsolete', 'is_reverted': True}},
                        {'taskId': 'prompt_123', 'data': {'content': 'valid result'}}]}]
        refreshed = self.service.refresh_cloud_run({'id': run['id'], 'credential': 'test'})
        self.assertEqual(refreshed['status'], 'running')
        self.assertEqual(refreshed['output'], 'valid result')
        with self.assertRaisesRegex(ValueError, 'Only completed'):
            self.service.dispatch('run.review', {'id': run['id']})

    def test_finished_result_and_review_are_not_overwritten(self):
        self.start_box()
        run = self.run_record()
        self.provider.request.side_effect = lambda method, path: {'promptRun': {'status': 'finished', 'done': True}} if '/prompts/' in path else {'events': []}
        result = self.service.refresh_cloud_run({'id': run['id'], 'credential': 'test'})
        self.assertEqual(result['status'], 'needs_review')
        self.service.dispatch('run.review', {'id': run['id']})
        self.assertEqual(self.service.refresh_cloud_run({'id': run['id'], 'credential': 'test'})['status'], 'completed')

    def test_lost_prompt_response_stays_uncertain_and_blocks_duplicate(self):
        self.start_box()
        run = self.run_record(promptId=None)
        self.service.materialize(self.ws['id'], self.service.store.root / 'runs' / run['id'])
        def action(box, operation, payload=None, **kw):
            if operation == 'commands':
                self.assertNotIn('Preserve this', payload['command'])
                return {'success': True, 'exitCode': 0}
            raise ProviderError('Response lost')
        self.provider.action.side_effect = action
        self.provider.request.return_value = {'success': True}
        self.service._execute(run, 'test', threading.Event())
        saved = self.service.store.get('run', run['id'])
        self.assertEqual(saved['status'], 'uncertain')
        uploads = self.provider.request.call_args_list
        self.assertEqual(len(uploads), 4)
        self.assertTrue(all(call.args[0] == 'PUT' for call in uploads))
        self.assertTrue(all('/runs/' + run['id'] in call.args[2]['path'] for call in uploads))
        with self.assertRaisesRegex(ValueError, 'active run'):
            self.service.start_run({'workspaceId': self.ws['id'], 'task': 'Duplicate', 'credential': 'test'})

    def test_each_local_run_gets_only_currently_approved_context(self):
        local = self.service.create_workspace({'name': 'Local', 'goal': 'Review'})
        source = self.service.add_source({'workspaceId': local['id'], 'name': 'Current', 'text': 'new evidence'})
        self.service.review_source({'id': source['id'], 'approved': True})
        old = self.service.store.workspace_path(local['id']) / 'old-result.md'
        old.write_text('revoked evidence')
        with patch('harness_manager.workspaces.service.shutil.which', return_value='/codex'), patch('threading.Thread.start'):
            run = self.service.start_run({'workspaceId': local['id'], 'task': 'Summarize', 'contextOptions': {'mode': 'local'}})
        self.service.threads.clear()
        root = self.service.store.root / 'runs' / run['id']
        self.assertIn('new evidence', (root / 'HANDOVER.md').read_text())
        self.assertFalse((root / 'old-result.md').exists())
        self.assertEqual(run['sourceRefs'], [{'id': source['id'], 'digest': source['digest']}])


if __name__ == '__main__':
    unittest.main()
