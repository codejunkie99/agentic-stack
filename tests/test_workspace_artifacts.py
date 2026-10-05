"""Local artifact approval and exporter boundaries, using the real bundled tools."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from harness_manager.workspaces.artifacts import Artifacts, MAX_BYTES
from harness_manager.workspaces.stack import StackManager
from harness_manager.workspaces.store import Store


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'service')
        self.stack = StackManager(self.store)
        self.artifacts = Artifacts(self.stack)
        self.ws = self.store.create('workspace', dict(name='Test project', goal='Verify local exports', provider='local'))
        self.wid = self.ws['id']
        self.root = self.stack.root(self.wid)

    def tearDown(self):
        self.temp.cleanup()

    def run_record(self, **changes):
        return self.store.create('run', dict(workspaceId=self.wid, task='Summarize the reviewed evidence',
            output='Here is the reviewed answer', agent='codex', model='model-test', sourceRefs=[],
            reviewed=True, status='completed') | changes)

    def file(self, relative, value):
        path = self.root / '.agent' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def preview(self, kind, **values):
        return self.artifacts.preview(dict(workspaceId=self.wid, kind=kind, **values))

    def generate(self, preview):
        return self.artifacts.generate(dict(workspaceId=self.wid, previewId=preview['previewId'], approved=True))

    def read(self, generated, name):
        row = next(r for r in generated['artifacts'] if r['name'] == name)
        return self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))

    def test_empty_metrics_and_native_training_run_real_bundled_exporters(self):
        snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(snapshot['counts']['eligibleRuns'], 0)
        self.assertEqual(snapshot['counts']['artifacts'], 0)
        metrics = self.generate(self.preview('metrics'))
        summary = json.loads(self.read(metrics, 'dashboard-summary.json')['text'])
        self.assertEqual(summary['window'], '30d')
        self.assertEqual(summary['bucket'], 'day')
        self.assertEqual(summary['counts']['agent_events'], 0)
        self.assertIn('<!doctype html>', self.read(metrics, 'dashboard.html')['text'])
        run = self.run_record(task='Use these facts\napi_key=abcdefghijklmnop123456789', output='A reviewed answer')
        preview = self.preview('training', runIds=[run['id']])
        self.assertEqual(preview['recordCount'], 1)
        self.assertEqual(preview['redactions'], 1)
        self.assertNotIn('abcdefghijklmnop123456789', preview['text'])
        self.assertIn('[credential-like content omitted]', preview['text'])
        generated = self.generate(preview)
        training = json.loads(self.read(generated, 'training-examples.jsonl')['text'])
        self.assertEqual(training['output'], 'A reviewed answer')
        self.assertIn('[credential-like content omitted]', training['input'])
        self.assertEqual(training['metadata']['harness'], 'codex')
        self.assertEqual(len(self.read(generated, 'eval-cases.jsonl')['text'].splitlines()), 1)
        audit = json.loads(self.read(generated, 'export-audit.json')['text'])
        self.assertTrue(audit['approved'])
        self.assertEqual(audit['digest'], preview['digest'])
        self.assertEqual(self.store.get('run', run['id'])['task'], run['task'])
        self.assertGreater(self.artifacts.snapshot(self.wid)['counts']['artifacts'], 25)
        with self.assertRaisesRegex(ValueError, 'already been generated'):
            self.generate(preview)

    def test_approval_selected_workspace_and_review_are_required(self):
        run = self.run_record(reviewed=False, status='needs_review')
        with self.assertRaisesRegex(ValueError, 'Review the completed run'):
            self.preview('training', runIds=[run['id']])
        with self.assertRaisesRegex(ValueError, 'Explicitly select'):
            self.preview('training', runIds=[])
        with self.assertRaisesRegex(ValueError, 'No eligible training'):
            self.preview('training')
        other = self.store.create('workspace', dict(name='Other'))
        foreign = self.run_record(workspaceId=other['id'])
        with self.assertRaisesRegex(ValueError, 'must belong'):
            self.preview('training', runIds=[foreign['id']])
        preview = self.preview('metrics')
        with self.assertRaisesRegex(ValueError, 'Explicit approval'):
            self.artifacts.generate(dict(workspaceId=self.wid, previewId=preview['previewId']))
        with self.assertRaisesRegex(ValueError, 'different workspace'):
            self.artifacts.generate(dict(workspaceId=other['id'], previewId=preview['previewId'], approved=True))

    def test_changed_source_or_review_invalidates_frozen_preview(self):
        run = self.run_record()
        preview = self.preview('training', runIds=[run['id']])
        self.store.update('run', run['id'], output='Changed answer')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.generate(preview)
        preview = self.preview('training', runIds=[run['id']])
        self.store.update('run', run['id'], reviewed=False)
        with self.assertRaisesRegex(ValueError, 'Review the completed run'):
            self.generate(preview)
        path = self.file('data-layer/harness-events.jsonl', '{}\n')
        preview = self.preview('metrics')
        path.write_text('{}\n{}\n')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.generate(preview)

    def test_existing_file_gates_raw_input_and_preserves_sources(self):
        good = dict(id='approved', human_review_status='accepted', redaction_status='passed',
                    raw_input_stored=False, input_redacted='Approved input', output_approved='Approved output')
        records = [good, good | {'id': 'unreviewed', 'human_review_status': 'unknown'},
            good | {'id': 'raw', 'raw_input_stored': True}, good | {'id': 'not-redacted', 'redaction_status': 'needs_review'},
            good | {'id': 'disabled', 'trainable': False}, good | {'id': 'blank', 'input_redacted': ''}]
        raw = '\n'.join(json.dumps(row) for row in records) + '\n{broken\n'
        source = self.file('flywheel/approved-runs.jsonl', raw)
        preview = self.preview('training')
        self.assertEqual(preview['recordCount'], 1)
        self.assertIn('Excluded 5', '\n'.join(preview['warnings']))
        self.assertIn('malformed', '\n'.join(preview['warnings']))
        generated = self.generate(preview)
        self.assertEqual(len(self.read(generated, 'training-examples.jsonl')['text'].splitlines()), 1)
        self.assertEqual(source.read_text(), raw)
        self.assertFalse((source.parent / 'exports').exists())

    def test_existing_exports_are_listed_and_read_without_importing_or_generating(self):
        sources = {
            'data-layer/exports/2026-09-09/dashboard.html': '<!doctype html><p>Existing metrics</p>',
            'data-layer/exports/daily-report.md': '# Existing report',
            'flywheel/exports/2026-09-09/training-examples.jsonl': '{"input":"Reviewed input"}\n',
            'flywheel/exports/2026-09-09/context-cards/software/review.md': '# Existing context card',
            'flywheel/exports/context-cards/software/review.json': '{"goal":"Review"}',
        }
        for path, content in sources.items():
            self.file(path, content)
        self.file('data-layer/exports/2026-09-09/private.json', '{"not":"an export"}')
        self.file('flywheel/exports/2026-09-09/context-cards/software/secret.txt', 'not a supported output')
        snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(snapshot['counts']['existingArtifacts'], 5)
        self.assertEqual(snapshot['counts']['generatedArtifacts'], 0)
        self.assertEqual(snapshot['counts']['artifacts'], 5)
        self.assertEqual(snapshot['counts']['approvedFileRuns'], 0)
        self.assertEqual(self.store.all('artifact'), [])
        self.assertEqual(self.store.all('artifactPreview'), [])
        for row in snapshot['artifacts']:
            relative = str(Path(row['path']).relative_to(self.root / '.agent'))
            self.assertEqual(row['status'], 'existing')
            self.assertEqual(row['size'], len(sources[relative].encode()))
            result = self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
            self.assertEqual(result['text'], sources[relative])
            self.assertEqual(Path(row['path']).read_text(), sources[relative])

    def test_existing_exports_do_not_duplicate_desktop_generated_content(self):
        generated = self.generate(self.preview('metrics'))
        dashboard = next(r for r in generated['artifacts'] if r['name'] == 'dashboard.html')
        self.file('data-layer/exports/2026-09-09/dashboard.html', Path(dashboard['path']).read_text())
        self.file('data-layer/exports/2026-09-09/daily-report.md', 'A separate existing report')
        snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(snapshot['counts']['generatedArtifacts'], len(generated['artifacts']))
        self.assertEqual(snapshot['counts']['existingArtifacts'], 1)
        self.assertEqual(snapshot['counts']['artifacts'], len(generated['artifacts']) + 1)
        self.assertEqual([r['name'] for r in snapshot['artifacts'] if r['status'] == 'existing'],
                         ['2026-09-09/daily-report.md'])

    def test_existing_export_reads_bind_workspace_content_and_supported_paths(self):
        source = self.file('data-layer/exports/daily-report.md', 'Original report')
        row = self.artifacts.snapshot(self.wid)['artifacts'][0]
        other = self.store.create('workspace', dict(name='Other project'))
        other_root = self.stack.root(other['id'])
        other_source = other_root / '.agent/data-layer/exports/daily-report.md'
        other_source.parent.mkdir(parents=True)
        other_source.write_text('Other project report')
        with self.assertRaisesRegex(ValueError, 'different workspace'):
            self.artifacts.read(dict(workspaceId=other['id'], artifactId=row['id']))
        other_rows = self.artifacts.snapshot(other['id'])['artifacts']
        self.assertEqual(len(other_rows), 1)
        self.assertNotEqual(other_rows[0]['id'], row['id'])
        self.assertEqual(self.artifacts.read(dict(workspaceId=other['id'], artifactId=other_rows[0]['id']))['text'],
                         'Other project report')
        prefix = ':'.join(row['id'].split(':', 3)[:3]) + ':'
        for relative in ['.agent/data-layer/exports/../../../daily-report.md',
                         '.agent/data-layer/exports/secrets.json', '/etc/hosts',
                         '.agent/flywheel/exports/context-cards/../../daily-report.md']:
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'Invalid existing artifact path'):
                self.artifacts.read(dict(workspaceId=self.wid, artifactId=prefix + relative))
        source.write_text('Revised report')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        fresh = self.artifacts.snapshot(self.wid)['artifacts'][0]
        self.assertNotEqual(fresh['id'], row['id'])
        self.assertEqual(self.artifacts.read(dict(workspaceId=self.wid, artifactId=fresh['id']))['text'], 'Revised report')

    def test_existing_export_discovery_excludes_links_nonregular_and_large_files(self):
        source = self.file('data-layer/exports/daily-report.md', 'Safe report')
        row = self.artifacts.snapshot(self.wid)['artifacts'][0]
        outside = Path(self.temp.name) / 'outside-exports'
        outside.mkdir()
        (outside / 'daily-report.md').write_text('OUTSIDE-WORKSPACE')
        source.unlink()
        source.symlink_to(outside / 'daily-report.md')
        source.parent.joinpath('linked-date').symlink_to(outside, target_is_directory=True)
        self.file('data-layer/exports/dashboard.html', 'x' * (MAX_BYTES + 1))
        fifo = source.parent / 'dashboard-summary.json'
        os.mkfifo(fifo)
        snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(snapshot['artifacts'], [])
        self.assertIn('symbolic links', '\n'.join(snapshot['issues']))
        self.assertIn('regular file under 2 MB', '\n'.join(snapshot['issues']))
        self.assertNotIn('OUTSIDE-WORKSPACE', json.dumps(snapshot))
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        training = self.root / '.agent/flywheel'
        training.mkdir()
        (training / 'exports').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.artifacts.snapshot(self.wid)['artifacts'], [])

    def test_existing_export_read_keeps_descriptor_when_directory_is_swapped(self):
        source = self.file('data-layer/exports/daily-report.md', 'Selected project report')
        row = self.artifacts.snapshot(self.wid)['artifacts'][0]
        outside = Path(self.temp.name) / 'outside-exports'
        outside.mkdir()
        (outside / source.name).write_text('OUTSIDE-WORKSPACE')
        original_open = os.open
        swapped = False

        def swap_at_leaf(name, flags, *args, **kwargs):
            nonlocal swapped
            if str(name) == source.name and not flags & os.O_DIRECTORY and not swapped:
                source.parent.rename(source.parent.with_name('original-exports'))
                source.parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_open(name, flags, *args, **kwargs)

        with patch('harness_manager.workspaces.artifacts.os.open', side_effect=swap_at_leaf):
            result = self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        self.assertTrue(swapped)
        self.assertEqual(result['text'], 'Selected project report')
        self.assertEqual(self.artifacts.snapshot(self.wid)['artifacts'], [])

    def test_existing_export_discovery_has_entry_and_read_budgets(self):
        for date in range(5):
            self.file(f'data-layer/exports/date-{date}/daily-report.md', 'An existing report')
        with patch('harness_manager.workspaces.artifacts.MAX_EXPORT_SCAN_ENTRIES', 3):
            snapshot = self.artifacts.snapshot(self.wid)
        self.assertLess(len(snapshot['artifacts']), 5)
        self.assertIn('discovery reached', '\n'.join(snapshot['issues']))
        with patch('harness_manager.workspaces.artifacts.MAX_EXPORT_SCAN_BYTES', MAX_BYTES):
            snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(len(snapshot['artifacts']), 1)
        self.assertIn('discovery reached', '\n'.join(snapshot['issues']))

    def test_snapshot_training_readiness_counts_only_approved_file_rows(self):
        good = dict(human_review_status='accepted', redaction_status='passed',
                    input_redacted='Approved input', output_approved='Approved output')
        source = self.file('flywheel/approved-runs.jsonl', json.dumps(good) + '\n'
                           + json.dumps(good | {'human_review_status': 'unknown'}) + '\n')
        before = source.read_bytes()
        snapshot = self.artifacts.snapshot(self.wid)
        self.assertEqual(snapshot['counts']['approvedFileRuns'], 1)
        self.assertEqual(snapshot['counts']['eligibleRuns'], 0)
        self.assertEqual(snapshot['counts']['artifacts'], 0)
        self.assertFalse((source.parent / 'exports').exists())
        self.assertEqual(source.read_bytes(), before)

    def test_metrics_stage_only_whitelisted_data_and_never_project_code(self):
        sentinel = Path(self.temp.name) / 'executed'
        self.file('tools/data_layer_export.py', f'from pathlib import Path\nPath({str(sentinel)!r}).touch()')
        (self.root / 'sitecustomize.py').write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).touch()')
        self.file('data-layer/harness-events.jsonl', json.dumps(dict(timestamp='2026-09-09T01:00:00Z',
            skill='codex', action='verify', raw_prompt='DO NOT COPY RAW', source={'run_id': 'test', 'raw': 'DO NOT COPY RAW'})) + '\n')
        self.run_record(task='DO NOT COPY DESKTOP TASK', output='DO NOT COPY DESKTOP OUTPUT')
        preview = self.preview('metrics', window='all')
        self.assertNotIn('DO NOT COPY', preview['text'])
        original = subprocess.run
        with patch('harness_manager.workspaces.artifacts.subprocess.run', wraps=original) as invoke:
            generated = self.generate(preview)
        args = invoke.call_args.args[0]
        self.assertEqual(args[1], '-I')
        self.assertEqual(invoke.call_args.kwargs['timeout'], 30)
        self.assertEqual(invoke.call_args.kwargs['env'], {'NO_COLOR': '1'})
        self.assertNotEqual(Path(args[2]), self.root / '.agent/tools/data_layer_export.py')
        summary = json.loads(self.read(generated, 'dashboard-summary.json')['text'])
        self.assertEqual(summary['counts']['agent_events'], 2)
        self.assertFalse(sentinel.exists())

    def test_symlinks_and_changed_or_cross_workspace_artifact_reads_fail(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        agent = self.root / '.agent'
        agent.mkdir()
        (agent / 'data-layer').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            self.preview('metrics')
        (agent / 'data-layer').unlink()
        generated = self.generate(self.preview('metrics'))
        row = generated['artifacts'][0]
        with self.assertRaisesRegex(ValueError, 'different workspace'):
            self.artifacts.read(dict(workspaceId='wrong', artifactId=row['id']))
        path = Path(row['path'])
        path.write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'changed since generation'):
            self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        path.unlink()
        path.symlink_to('/etc/hosts')
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        second = self.store.create('workspace', dict(name='Linked output'))
        root = self.stack.root(second['id'])
        (root / 'artifacts').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            self.artifacts.preview(dict(workspaceId=second['id'], kind='metrics'))

    def test_preview_cannot_follow_ancestor_swapped_before_leaf_open(self):
        source = self.file('data-layer/category-rules.json', json.dumps({'default_category': 'selected-project', 'rules': []}))
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        outside_text = json.dumps({'default_category': 'OUTSIDE-WORKSPACE', 'rules': []})
        (outside / source.name).write_text(outside_text)
        original_open = os.open
        swapped = False

        def swap_at_leaf(path, flags, *args, **kwargs):
            nonlocal swapped
            if Path(path).name == source.name and not flags & os.O_DIRECTORY and not swapped:
                self.assertIsNotNone(kwargs.get('dir_fd'))
                source.parent.rename(source.parent.with_name('original-data-layer'))
                source.parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        with patch('harness_manager.workspaces.artifacts.os.open', side_effect=swap_at_leaf):
            preview = self.preview('metrics')
        self.assertTrue(swapped)
        self.assertIn('selected-project', preview['text'])
        for row in self.store.all('artifactPreview') + [preview]:
            self.assertNotIn('OUTSIDE-WORKSPACE', row['text'])
        self.assertEqual((outside / source.name).read_text(), outside_text)

    def test_preview_rejects_ancestor_swapped_before_directory_open(self):
        source = self.file('flywheel/approved-runs.jsonl', '{}\n')
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (outside / source.name).write_text(json.dumps(dict(human_review_status='accepted', redaction_status='passed',
            input_redacted='OUTSIDE-WORKSPACE', output_approved='outside answer')) + '\n')
        original_open = os.open
        swapped = False

        def swap_at_directory(path, flags, *args, **kwargs):
            nonlocal swapped
            if str(path) == 'flywheel' and flags & os.O_DIRECTORY and not swapped:
                self.assertTrue(flags & os.O_NOFOLLOW)
                source.parent.rename(source.parent.with_name('original-flywheel'))
                source.parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        with patch('harness_manager.workspaces.artifacts.os.open', side_effect=swap_at_directory):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                self.preview('training')
        self.assertTrue(swapped)
        self.assertEqual(self.store.all('artifactPreview'), [])

    def test_artifact_read_uses_open_parent_when_ancestor_is_swapped(self):
        generated = self.generate(self.preview('metrics'))
        row = next(row for row in generated['artifacts'] if row['name'] == 'daily-report.md')
        path = Path(row['path'])
        expected = path.read_text()
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (outside / path.name).write_text('OUTSIDE-WORKSPACE')
        original_open = os.open
        swapped = False

        def swap_at_leaf(name, flags, *args, **kwargs):
            nonlocal swapped
            if str(name) == path.name and not flags & os.O_DIRECTORY and not swapped:
                self.assertIsNotNone(kwargs.get('dir_fd'))
                path.parent.rename(path.parent.with_name('original-export'))
                path.parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_open(name, flags, *args, **kwargs)

        with patch('harness_manager.workspaces.artifacts.os.open', side_effect=swap_at_leaf):
            result = self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))
        self.assertTrue(swapped)
        self.assertEqual(result['text'], expected)
        self.assertNotIn('OUTSIDE-WORKSPACE', result['text'])

    def test_input_and_read_size_limits_and_timeout_do_not_leave_outputs(self):
        source = self.file('data-layer/harness-events.jsonl', ' ' * (MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'under 2 MB'):
            self.preview('metrics')
        source.unlink()
        preview = self.preview('metrics')
        with patch('harness_manager.workspaces.artifacts.subprocess.run', side_effect=subprocess.TimeoutExpired('export', 30)):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                self.generate(preview)
        self.assertFalse(list(self.artifacts._root(self.wid).glob('.staging-*')))
        self.assertEqual(self.artifacts.snapshot(self.wid)['artifacts'], [])
        generated = self.generate(preview)
        row = generated['artifacts'][0]
        Path(row['path']).write_text(' ' * (MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'under 2 MB'):
            self.artifacts.read(dict(workspaceId=self.wid, artifactId=row['id']))


if __name__ == '__main__':
    unittest.main()
