import json
from pathlib import Path
from unittest.mock import patch

from harness_manager.loops.process import ProcessResult
from harness_manager.workspaces.service import WorkspaceService
from test_conversations import wait_for_task


def test_bundled_skills_have_runner_required_metadata_and_repair_preserves_edits(tmp_path):
    svc = WorkspaceService(tmp_path/'data')
    try:
        ws = svc.create_workspace({'name': 'Legacy skills', 'goal': 'Compatibility'})
        svc.stack.initialize(ws['id'])
        root = svc.stack.root(ws['id'])
        paths = list((svc.stack.stack/'.agent/skills').glob('*/SKILL.md'))
        assert len(paths) >= 14
        for source in paths:
            content = source.read_text()
            header = content.split('---', 2)[1]
            assert 'name: '+source.parent.name in header
            line = next(line for line in header.splitlines() if line.startswith('description:'))
            assert json.loads(line.split(':', 1)[1].strip())
            (root/'.agent/skills'/source.parent.name/'SKILL.md').write_text(content.replace(line+'\n', '', 1))
        custom = root/'.agent/skills/debug-investigator/SKILL.md'
        custom.write_text(custom.read_text()+'\nKeep this custom investigation rule.\n')
        original_custom = custom.read_bytes()
        result = svc.dispatch('skills.repair', {'workspaceId': ws['id']})
        assert f'Updated {len(paths)-1}' in result['text']
        assert custom.read_bytes() == original_custom
        repaired = root/'.agent/skills/brain/SKILL.md'
        assert repaired.read_bytes() == (svc.stack.stack/'.agent/skills/brain/SKILL.md').read_bytes()
        assert 'Updated 0' in svc.dispatch('skills.repair', {'workspaceId': ws['id']})['text']
    finally: svc.close()


def test_structured_runner_error_is_not_hidden_by_unrelated_startup_diagnostics(tmp_path):
    svc = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'; project.mkdir()
    ws = svc.open_project({'path': str(project)})
    def execute(spec, values, cwd, *args, **kwargs):
        kwargs['on_output']('stdout', json.dumps({'type': 'turn.failed', 'error': {'message': 'The requested model is unavailable.'}})+'\n')
        return ProcessResult('failed', 1, '', 'Unrelated startup diagnostics', 0, .01)
    try:
        with patch('harness_manager.workspaces.service.executable', return_value='/agent'), patch('harness_manager.workspaces.service.run_profile', side_effect=execute):
            run = wait_for_task(svc, svc.send_conversation({'workspaceId': ws['id'], 'task': 'Hello'}))
        assert run['status'] == 'failed'
        assert run['error'] == 'The requested model is unavailable.'
    finally: svc.close()
