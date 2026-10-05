import pytest

from harness_manager.workspaces.store import Store
from harness_manager.workspaces.memory_ledger import MemoryLedger, MemoryConflict


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    one = store.create('workspace', {'name': 'one'})['id']
    two = store.create('workspace', {'name': 'two'})['id']
    return store, MemoryLedger(store), one, two


def test_observations_are_immutable_idempotent_and_scoped(setup):
    store, ledger, one, two = setup
    original = ledger.observe(one, source_key='run:1/build', body='Build passed at revision A')
    again = ledger.observe(one, source_key='run:1/build', body='Build passed at revision A')
    changed = ledger.observe(one, source_key='run:1/build', body='Build failed at revision B')
    assert original == again and original['id'] != changed['id']
    assert ledger.evidence(one, original['id'])['body'] == 'Build passed at revision A'
    assert len(ledger.history(one, original['id'])) == 1
    with pytest.raises(ValueError):
        ledger.evidence(two, original['id'])
    reopened = MemoryLedger(Store(store.root))
    assert reopened.evidence(one, changed['id']) == changed


def test_claim_review_preserves_sources_and_uses_revision_guard(setup):
    _, ledger, one, two = setup
    source = ledger.observe(one, source_key='user:1', body='Use frosted search panels')
    claim = ledger.propose(one, body='Use frosted search panels', kind='decision', evidence_ids=[source['id']])
    with pytest.raises(ValueError):
        ledger.propose(two, body='Cross-project claim', kind='fact', evidence_ids=[source['id']])
    accepted = ledger.review(one, claim['id'], expected_revision=1, status='accepted', rationale='User confirmed')
    with pytest.raises(MemoryConflict):
        ledger.review(one, claim['id'], expected_revision=1, status='retracted', rationale='Stale client')
    assert accepted['revision'] == 2
    assert len(ledger.history(one, claim['id'])) == 2
    assert ledger.evidence(one, source['id']) == source


def test_supersession_requires_current_accepted_same_scope_replacement(setup):
    _, ledger, one, two = setup
    source = ledger.observe(one, source_key='user:1', body='Original and revised decisions')
    old = ledger.propose(one, body='Use solid panels', kind='decision', evidence_ids=[source['id']])
    new = ledger.propose(one, body='Use frosted panels', kind='decision', evidence_ids=[source['id']])
    with pytest.raises(ValueError):
        ledger.review(one, old['id'], expected_revision=1, status='superseded', rationale='Changed', replacement_id=new['id'])
    assert ledger.claim(one, old['id'])['revision'] == 1
    ledger.review(one, new['id'], expected_revision=1, status='accepted', rationale='Explicit decision')
    ledger.review(one, old['id'], expected_revision=1, status='superseded', rationale='Changed', replacement_id=new['id'])
    assert [c['id'] for c in ledger.claims(one)] == [new['id']]
    assert len(ledger.claims(one, include_history=True)) == 2
    with pytest.raises(ValueError):
        ledger.review(one, old['id'], expected_revision=2, status='accepted', rationale='Resurrect')


def test_event_failure_rolls_back_review(setup, monkeypatch):
    _, ledger, one, _ = setup
    source = ledger.observe(one, source_key='test:1', body='Supported statement')
    claim = ledger.propose(one, body='Supported statement', kind='fact', evidence_ids=[source['id']])
    def fail(*args):
        raise RuntimeError('disk write failed')
    monkeypatch.setattr(ledger, '_event', fail)
    with pytest.raises(RuntimeError):
        ledger.review(one, claim['id'], expected_revision=1, status='accepted', rationale='Reviewed')
    assert ledger.claim(one, claim['id'])['status'] == 'proposed'
    assert ledger.claim(one, claim['id'])['revision'] == 1


def test_shared_service_dispatch_uses_scoped_ledger(tmp_path):
    from harness_manager.workspaces.service import WorkspaceService
    service = WorkspaceService(tmp_path)
    wid = service.store.create('workspace', {'name': 'Test'})['id']
    evidence = service.dispatch('memory.ledger.observe', dict(workspaceId=wid, sourceKey='run:1', body='Build verified at revision A'))
    claim = service.dispatch('memory.ledger.propose', dict(workspaceId=wid, body='Build verified at revision A', kind='fact', evidenceIds=[evidence['id']]))
    service.dispatch('memory.ledger.review', dict(workspaceId=wid, id=claim['id'], expectedRevision=1, status='accepted', rationale='Checked receipt'))
    assert service.dispatch('memory.ledger.claims', {'workspaceId': wid})['claims'][0]['status'] == 'accepted'
    with pytest.raises(ValueError):
        service.dispatch('memory.ledger.claims', dict(workspaceId=wid, includeHistory='false'))
    assert len(service.dispatch('memory.ledger.history', dict(workspaceId=wid, id=claim['id']))['events']) == 2


def test_concurrent_observation_has_one_identity(setup):
    from concurrent.futures import ThreadPoolExecutor
    store, ledger, wid, _ = setup
    second = MemoryLedger(Store(store.root))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda x: x.observe(wid, source_key='run:repeat', body='Same verified observation'), [ledger, second]))
    assert results[0]['id'] == results[1]['id']
    assert len(ledger.history(wid, results[0]['id'])) == 1


def proposal_fixture(ledger, wid):
    source = ledger.observe(wid, source_key='fixture:revision', body='Use solid panels. Revised decision: use frosted panels.')
    old = ledger.propose(wid, body='Use solid panels.', kind='decision', evidence_ids=[source['id']])
    new = ledger.propose(wid, body='Use frosted panels.', kind='decision', evidence_ids=[source['id']])
    proposal = ledger.propose_action(wid, new['id'], action='supersedes', subject_revision=1,
                                    target=old['id'], target_revision=1, model='fixture')
    return source, old, new, proposal


def test_supersession_proposal_is_inert_until_review_and_preserves_evidence(setup):
    _, ledger, wid, _ = setup
    source, old, new, proposal = proposal_fixture(ledger, wid)
    assert ledger.claim(wid, old['id'])['status'] == 'proposed'
    assert ledger.claim(wid, new['id'])['status'] == 'proposed'
    assert not ledger.links(wid)
    applied = ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=True, rationale='Explicit replacement reviewed')
    assert applied['status'] == 'applied'
    assert ledger.claim(wid, old['id'])['replacementId'] == new['id']
    assert ledger.claim(wid, old['id'])['status'] == 'superseded'
    assert ledger.claim(wid, new['id'])['status'] == 'accepted'
    assert ledger.evidence(wid, source['id']) == source
    assert ledger.links(wid)[0]['relation'] == 'supersedes'
    with pytest.raises(MemoryConflict):
        ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=True, rationale='Repeat')


def test_stale_proposal_can_be_dismissed_but_not_applied(setup):
    _, ledger, wid, _ = setup
    _, old, new, proposal = proposal_fixture(ledger, wid)
    ledger.review(wid, old['id'], expected_revision=1, status='disputed', rationale='New evidence')
    with pytest.raises(MemoryConflict):
        ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=True, rationale='Stale review')
    assert ledger.claim(wid, new['id'])['revision'] == 1
    assert not ledger.links(wid)
    assert ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=False, rationale='Stale') ['status'] == 'dismissed'


def test_supersession_event_failure_rolls_back_both_claims_and_link(setup, monkeypatch):
    _, ledger, wid, _ = setup
    _, old, new, proposal = proposal_fixture(ledger, wid)
    original = ledger._event
    def fail_target(db, workspace, subject, operation, payload):
        if subject == old['id']:
            raise RuntimeError('receipt failure')
        return original(db, workspace, subject, operation, payload)
    monkeypatch.setattr(ledger, '_event', fail_target)
    with pytest.raises(RuntimeError):
        ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=True, rationale='Reviewed')
    assert ledger.claim(wid, old['id']) == old
    assert ledger.claim(wid, new['id']) == new
    assert not ledger.links(wid)
    assert ledger.proposals(wid)[0]['status'] == 'pending'


def test_proposal_scope_and_idempotence(setup):
    _, ledger, wid, other = setup
    _, old, new, proposal = proposal_fixture(ledger, wid)
    assert ledger.propose_action(wid, new['id'], action='supersedes', subject_revision=1,
        target=old['id'], target_revision=1, model='fixture')['id'] == proposal['id']
    with pytest.raises(ValueError):
        ledger.review_proposal(other, proposal['id'], expected_revision=1, accept=True, rationale='Wrong scope')
    assert ledger.proposals(other) == []


def test_native_snapshot_shows_history_and_pending_proposals_with_truthful_provider(tmp_path):
    from harness_manager.workspaces.service import WorkspaceService
    service = WorkspaceService(tmp_path)
    wid = service.store.create('workspace', {'name': 'Review'})['id']
    _, old, new, proposal = proposal_fixture(service.memory_ledger, wid)
    before = service.dispatch('memory.ledger.snapshot', {'workspaceId': wid})
    assert before['providerAvailable'] is False
    assert len(before['claims']) == 2 and before['proposals'][0]['id'] == proposal['id']
    service.dispatch('memory.proposals.review', dict(workspaceId=wid, id=proposal['id'], expectedRevision=1,
                     accept=True, rationale='Reviewed source evidence'))
    after = service.dispatch('memory.ledger.snapshot', {'workspaceId': wid})
    assert {c['status'] for c in after['claims']} == {'accepted', 'superseded'}
    assert after['proposals'] == []


def test_palette_search_is_local_scoped_and_only_returns_accepted_claims(tmp_path):
    from harness_manager.workspaces.service import WorkspaceService
    class NoHostedCalls:
        def evaluate(self, *args, **kwargs):
            raise AssertionError('Command palette must stay local')
    service = WorkspaceService(tmp_path, jev_provider=NoHostedCalls())
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    other = service.store.create('workspace', {'name': 'other'})['id']
    ledger = service.memory_ledger
    for workspace, status in [(wid, 'accepted'), (wid, 'proposed'), (wid, 'disputed'),
                              (wid, 'retracted'), (wid, 'superseded'), (other, 'accepted')]:
        evidence = ledger.observe(workspace, source_key=status, body='Use UI blur ' + status)
        claim = ledger.propose(workspace, body=evidence['body'], kind='decision', evidence_ids=[evidence['id']])
        if status != 'proposed':
            ledger.review(workspace, claim['id'], expected_revision=1, status=status,
                          rationale='Synthetic review', replacement_id=accepted if status == 'superseded' else None)
        if workspace == wid and status == 'accepted':
            accepted = claim['id']
    result = service.dispatch('memory.ledger.search', {'workspaceId': wid, 'query': 'ui BLUR'})
    assert [claim['id'] for claim in result['claims']] == [accepted]
    assert not service.dispatch('memory.ledger.search', {'workspaceId': wid, 'query': 'absent'})['claims']
    with pytest.raises(ValueError):
        service.dispatch('memory.ledger.search', {'workspaceId': wid, 'query': []})
