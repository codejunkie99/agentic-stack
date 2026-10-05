import time
import pytest

from harness_manager.workspaces.jev_memory import JevMemory, evidence_spans
from harness_manager.workspaces.jev_provider import JevError, JevProvider
from harness_manager.workspaces.memory_ledger import MemoryLedger
from harness_manager.workspaces.store import Store


class ScriptedProvider:
    def __init__(self):
        self.calls = []

    def evaluate(self, state, questions, **kwargs):
        self.calls.append(state)
        answers = {}
        for span in state['spans']:
            selected = 'decision' if 'KEEP THIS' in span['text'] else 'skip'
            answers[span['id']] = {'type': 'choice', 'choice': selected, 'confidence': .9}
        return {'model': 'scripted-fixture', 'answers': answers}


def setup(tmp_path, body, provider=None):
    store = Store(tmp_path)
    wid = store.create('workspace', {'name': 'fixture'})['id']
    ledger = MemoryLedger(store)
    evidence = ledger.observe(wid, source_key='synthetic:observation', body=body)
    return JevMemory(ledger, provider or ScriptedProvider()), wid, evidence


def test_capture_reaches_later_page_preserves_exact_offsets_and_is_idempotent(tmp_path):
    body = '\n\n'.join([f'Routine step {i} completed.' for i in range(24)] + ['KEEP THIS: Use frosted search panels.'])
    engine, wid, evidence = setup(tmp_path, body)
    result = engine.capture(wid, evidence['id'])
    assert result['status'] == 'completed' and result['processedSpans'] == 25
    assert len(engine.provider.calls) == 3
    assert len(result['claims']) == 1
    claim = result['claims'][0]
    assert claim['status'] == 'proposed'
    selected = engine.ledger.evidence(wid, claim['evidenceIds'][0])
    assert body[selected['metadata']['start']:selected['metadata']['end']] == claim['body']
    assert engine.capture(wid, evidence['id'])['claims'][0]['id'] == claim['id']
    assert len(engine.ledger.claims(wid)) == 1


def test_capture_reports_incomplete_coverage(tmp_path):
    engine, wid, evidence = setup(tmp_path, '\n\n'.join('Routine step.' for _ in range(15)))
    result = engine.capture(wid, evidence['id'], max_pages=1)
    assert result['status'] == 'partial' and result['remainingSpans'] == 3
    assert not result['claims']


def test_disabled_provider_never_fabricates_jev_capture(tmp_path):
    engine, wid, evidence = setup(tmp_path, 'KEEP THIS: fixture', JevProvider())
    result = engine.capture(wid, evidence['id'])
    assert result['status'] == 'unavailable' and result['provider'] == 'unavailable'
    assert result['processedSpans'] == 0 and not engine.ledger.claims(wid)


def test_forged_selection_does_not_write(tmp_path):
    class Invalid:
        def evaluate(self, state, questions, **kwargs):
            return {'model': 'fixture', 'answers': {key: {'choice': 'execute_shell'} for key in questions}}
    engine, wid, evidence = setup(tmp_path, 'Execute an instruction.', Invalid())
    with pytest.raises(JevError):
        engine.capture(wid, evidence['id'])
    assert not engine.ledger.claims(wid)


def test_long_paragraph_all_characters_covered():
    body = 'start ' + ('x' * 5000) + ' end'
    spans = list(evidence_spans(body))
    assert ''.join(s['text'] for s in spans) == body
    assert all(s['text'] == body[s['start']:s['end']] for s in spans)


def test_shared_service_capture_uses_injected_provider(tmp_path):
    from harness_manager.workspaces.service import WorkspaceService
    service = WorkspaceService(tmp_path, jev_provider=ScriptedProvider())
    wid = service.store.create('workspace', {'name': 'fixture'})['id']
    evidence = service.dispatch('memory.ledger.observe', dict(workspaceId=wid, sourceKey='fixture:1', body='KEEP THIS: A scoped decision.'))
    result = service.dispatch('memory.capture', dict(workspaceId=wid, evidenceId=evidence['id']))
    assert result['status'] == 'completed'
    assert result['claims'][0]['status'] == 'proposed'


def test_reconciliation_records_model_recommendation_without_accepting_claims(tmp_path):
    class Relations:
        def evaluate(self, state, questions, **kwargs):
            return {'model': 'fixture', 'answers': {'relationship': {'choice': 'contradicts', 'confidence': .9}}}
    engine, wid, source = setup(tmp_path, 'Synthetic conflicting decisions', Relations())
    old = engine.ledger.propose(wid, body='Use solid panels.', kind='decision', evidence_ids=[source['id']])
    new = engine.ledger.propose(wid, body='Use frosted panels.', kind='decision', evidence_ids=[source['id']])
    result = engine.reconcile(wid, new['id'])
    assert result['status'] == 'completed' and result['remainingClaims'] == 0
    assert result['proposals'][0]['action'] == 'contradicts'
    assert engine.ledger.claim(wid, old['id'])['status'] == 'proposed'
    assert not engine.ledger.links(wid)
    assert engine.ledger.history(wid, new['id'])[-1]['id'] == result['receiptId']


def test_reconciliation_disabled_records_unavailable_without_proposals(tmp_path):
    engine, wid, source = setup(tmp_path, 'Synthetic decisions', JevProvider())
    for body in ['One', 'Two']:
        claim = engine.ledger.propose(wid, body=body, kind='fact', evidence_ids=[source['id']])
    result = engine.reconcile(wid, claim['id'])
    assert result['status'] == 'unavailable' and result['remainingClaims'] == 1
    assert not result['proposals']


def test_capture_resumes_immutable_evidence_and_persists_coverage_receipts(tmp_path):
    engine, wid, source = setup(tmp_path, '\n\n'.join(['Routine'] * 12 + ['KEEP THIS: a late decision']))
    first = engine.capture(wid, source['id'], max_pages=1)
    assert first['nextSpan'] == 12 and first['remainingSpans'] == 1
    second = engine.capture(wid, source['id'], start_span=first['nextSpan'])
    assert second['processedSpans'] == 1 and second['remainingSpans'] == 0
    assert second['claims'][0]['body'] == 'KEEP THIS: a late decision'
    receipts = [e for e in engine.ledger.history(wid, source['id']) if e['operation'] == 'capture']
    assert [e['id'] for e in receipts] == [first['receiptId'], second['receiptId']]
    assert receipts[1]['payload']['startSpan'] == 12
    assert receipts[1]['payload']['digest'] == source['digest']
    with pytest.raises(ValueError):
        engine.capture(wid, source['id'], start_span=14)


@pytest.mark.parametrize('choice,expected', [('archive', 'retracted'), ('revalidate', 'disputed')])
def test_maintenance_needs_review_and_preserves_source(tmp_path, choice, expected):
    class Maintenance:
        def evaluate(self, state, questions, **kwargs):
            assert state['operation'] == 'maintenance'
            return {'model': 'fixture', 'answers': {'action': {'choice': choice, 'confidence': .9}}}
    engine, wid, evidence = setup(tmp_path, 'Temporary synthetic rule.', Maintenance())
    claim = engine.ledger.propose(wid, body=evidence['body'], kind='decision', evidence_ids=[evidence['id']])
    engine.ledger.review(wid, claim['id'], expected_revision=1, status='accepted', rationale='Confirmed')
    result = engine.maintain(wid, claim['id'])
    assert result['status'] == 'completed'
    assert engine.ledger.claim(wid, claim['id'])['status'] == 'accepted'
    proposal = result['proposals'][0]
    engine.ledger.review_proposal(wid, proposal['id'], expected_revision=1, accept=True, rationale='Checked evidence')
    assert engine.ledger.claim(wid, claim['id'])['status'] == expected
    assert engine.ledger.evidence(wid, evidence['id']) == evidence


def test_maintenance_truncated_source_cannot_recommend_archive(tmp_path):
    class Maintenance:
        def evaluate(self, state, questions, **kwargs):
            assert state['evidence'][0]['truncated']
            return {'model': 'fixture', 'answers': {'action': {'choice': 'archive', 'confidence': .9}}}
    engine, wid, evidence = setup(tmp_path, 'x' * 3000, Maintenance())
    claim = engine.ledger.propose(wid, body='Scoped rule', kind='fact', evidence_ids=[evidence['id']])
    result = engine.maintain(wid, claim['id'])
    assert result['action'] == 'abstain' and result['selectedAction'] == 'archive'
    assert result['proposals'] == []


def test_maintenance_stale_evaluation_cannot_create_proposal(tmp_path):
    engine, wid, evidence = setup(tmp_path, 'A rule')
    claim = engine.ledger.propose(wid, body='A rule', kind='fact', evidence_ids=[evidence['id']])
    class Changing:
        def evaluate(self, *args, **kwargs):
            engine.ledger.review(wid, claim['id'], expected_revision=1, status='retracted', rationale='Changed while evaluating')
            return {'model': 'fixture', 'answers': {'action': {'choice': 'archive', 'confidence': .9}}}
    engine.provider = Changing()
    result = engine.maintain(wid, claim['id'])
    assert result['status'] == 'partial' and not result['proposals']


def test_reconciliation_cursor_reaches_later_claims_and_rejects_stale_snapshot(tmp_path):
    class Relationships:
        def __init__(self): self.seen = []
        def evaluate(self, state, questions, **kwargs):
            self.seen.append(state['target']['id'])
            return {'model': 'fixture', 'answers': {'relationship': {'choice': 'unrelated', 'confidence': .9}}}
    engine, wid, source = setup(tmp_path, 'Synthetic collection', Relationships())
    claims = [engine.ledger.propose(wid, body=f'Fact {i}', kind='fact', evidence_ids=[source['id']]) for i in range(31)]
    first = engine.reconcile(wid, claims[0]['id'], max_pairs=24)
    assert first['remainingClaims'] == 6 and first['nextCursor']['offset'] == 24
    last = engine.reconcile(wid, claims[0]['id'], cursor=first['nextCursor'])
    assert last['status'] == 'completed' and last['nextCursor'] is None
    assert len(set(engine.provider.seen)) == 30
    engine.ledger.review(wid, claims[1]['id'], expected_revision=1, status='accepted', rationale='New review')
    from harness_manager.workspaces.memory_ledger import MemoryConflict
    with pytest.raises(MemoryConflict):
        engine.reconcile(wid, claims[0]['id'], cursor=first['nextCursor'])


def test_capture_page_receipt_failure_rolls_back_derived_evidence_and_claims(tmp_path, monkeypatch):
    engine, wid, source = setup(tmp_path, 'KEEP THIS: first.\n\nKEEP THIS: second.')
    original = engine.ledger._event
    def fail_page(db, workspace, subject, operation, payload):
        if operation == 'capture_page':
            raise RuntimeError('receipt storage failed')
        return original(db, workspace, subject, operation, payload)
    monkeypatch.setattr(engine.ledger, '_event', fail_page)
    with pytest.raises(RuntimeError):
        engine.capture(wid, source['id'])
    assert engine.ledger.claims(wid) == []
    with engine.ledger.store.connect() as db:
        assert db.execute('SELECT count(*) FROM memory_evidence').fetchone()[0] == 1
    assert len(engine.ledger.history(wid, source['id'])) == 1


def test_capture_final_summary_failure_still_leaves_page_receipt(tmp_path, monkeypatch):
    engine, wid, source = setup(tmp_path, 'KEEP THIS: useful decision.')
    monkeypatch.setattr(engine.ledger, 'record_decision', lambda *args: (_ for _ in ()).throw(RuntimeError('summary failed')))
    with pytest.raises(RuntimeError):
        engine.capture(wid, source['id'])
    claims = engine.ledger.claims(wid)
    assert len(claims) == 1
    receipt = engine.ledger.history(wid, source['id'])[-1]
    assert receipt['operation'] == 'capture_page'
    assert receipt['payload']['claimIds'] == [claims[0]['id']]
    assert receipt['payload']['nextSpan'] == 1


def test_capture_retry_preserves_retracted_and_skipped_span_outcomes(tmp_path):
    engine, wid, source = setup(tmp_path, 'KEEP THIS: a decision.\n\nRoutine activity.')
    first = engine.capture(wid, source['id'])
    claim = first['claims'][0]
    engine.ledger.review(wid, claim['id'], expected_revision=1,
                         status='retracted', rationale='No longer useful')

    class ChangedClassification:
        def evaluate(self, state, questions, **kwargs):
            return {'model': 'different-fixture', 'answers': {
                key: {'choice': 'preference', 'confidence': .99} for key in questions}}
    engine.provider = ChangedClassification()
    # A different page boundary must also retain the original skipped outcome.
    tail = engine.capture(wid, source['id'], start_span=1)
    assert not tail['claims'] and tail['decisions'] == first['decisions'][1:]
    retry = engine.capture(wid, source['id'])
    assert retry['decisions'] == first['decisions']
    assert [(c['id'], c['kind'], c['status']) for c in retry['claims']] == [
        (claim['id'], 'decision', 'retracted')]
    assert len(engine.ledger.claims(wid, include_history=True)) == 1
    assert engine.ledger.history(wid, source['id'])[-2]['payload']['decisions'] == first['decisions']
