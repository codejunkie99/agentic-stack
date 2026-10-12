"""The desktop orchestration page reads plan runs, campaigns, evolver state and tracks from project files."""
import json

from harness_manager.workspaces.service import WorkspaceService


def test_orchestration_snapshot_reads_project_runtime(tmp_path):
    app = WorkspaceService(tmp_path / 'data')
    try:
        folder = tmp_path / 'project'
        agent = folder / '.agent'
        (agent / 'runtime' / 'plans' / 'run-1').mkdir(parents=True)
        (agent / 'runtime' / 'plans' / 'run-1' / 'run.json').write_text(json.dumps({
            'run_id': 'run-1', 'name': 'demo', 'status': 'completed',
            'nodes': {'a': {'status': 'completed'}}}))
        (agent / 'proactive').mkdir()
        (agent / 'proactive' / 'campaigns.jsonl').write_text(
            json.dumps({'type': 'campaign', 'campaign_id': 'c1', 'target': 'green'}) + '\n')
        (agent / 'evolve' / 'candidates' / 'h1').mkdir(parents=True)
        (agent / 'evolve' / 'candidates' / 'h1' / 'descriptor.json').write_text(
            json.dumps({'id': 'h1', 'where': 'prompt', 'pathology': 'loops', 'symptom': 'retries'}))
        (agent / 'memory' / 'cases').mkdir(parents=True)
        (agent / 'memory' / 'cases' / 'agent_case-2026-10-12.md').write_text(
            '---\nid: x\n---\n\n<!-- entry:case_20261012_00000001 -->\nbody\n<!-- /entry:case_20261012_00000001 -->\n')
        wid = app.open_project({'path': str(folder)})['id']

        result = app.dispatch('orchestration.snapshot', {'workspaceId': wid})

        assert result['projectAccessError'] == ''
        assert [(r['label'], r['status']) for r in result['plans']] == [('run-1', 'pass')]
        assert result['campaigns'][0]['id'] == 'campaign-c1'
        assert result['evolutionStats']['candidates'] == 1
        assert result['evolution'][1]['command'] == 'python3 .agent/tools/evolve.py screen h1'
        assert result['tracks'][0]['summary'].startswith('1 entries')
        assert all(isinstance(item['command'], str) for group in ('plans', 'campaigns', 'evolution', 'tracks') for item in result[group])
    finally:
        app.close()
