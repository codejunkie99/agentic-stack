from harness_manager.workspaces.service import WorkspaceService


class NeverHosted:
    available = True

    def __getattr__(self, name):
        raise AssertionError(f'Demo invoked hosted provider: {name}')


def test_demo_uses_production_context_and_reset_is_scoped(tmp_path):
    service = WorkspaceService(tmp_path, jev_provider=NeverHosted())
    other = service.create_workspace(dict(name='Real project', goal='Preserve this project'))
    evidence = service.memory_ledger.observe(other['id'], source_key='selected-project.md', body='Private project evidence')
    claim = service.memory_ledger.propose(other['id'], body=evidence['body'], kind='fact', evidence_ids=[evidence['id']])
    service.memory_ledger.review(other['id'], claim['id'], expected_revision=1, status='accepted', rationale='Selected evidence')
    fixture = service.dispatch('memory.demo.prepare', {})
    again = service.dispatch('memory.demo.prepare', {})
    assert fixture['workspaceId'] == again['workspaceId']
    assert len(service.memory_ledger.claims(fixture['workspaceId'])) == 3
    params = dict(workspaceId=fixture['workspaceId'], prompt=fixture['cases'][0]['query'],
                  contextOptions=dict(mode='local', tokenBudget=2500))
    cold = service.dispatch('context.prepare', params)
    warm = service.dispatch('context.prepare', params)
    assert cold['refs'] and warm['cacheHit']
    assert all(origin['path'].startswith('fixture://') for ref in cold['refs'] for origin in ref['origins'])
    assert all('Private project' not in ref['excerpt'] for ref in cold['refs'])
    service.dispatch('memory.demo.reset', {})
    fresh = service.dispatch('context.prepare', params)
    assert not fresh['cacheHit']
    assert {r['id'] for r in cold['refs']}.isdisjoint(r['id'] for r in fresh['refs'])
    assert service.memory_ledger.claim(other['id'], claim['id'])['status'] == 'accepted'
    assert service.memory_ledger.evidence(other['id'], evidence['id'])['body'] == 'Private project evidence'
