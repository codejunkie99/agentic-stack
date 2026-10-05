import copy
import pytest
from harness_manager.workspaces.store import Store
from harness_manager.workspaces.memory_ledger import MemoryLedger
from harness_manager.workspaces.memory_migration import MemoryMigration


class Imported:
    def __init__(self, wid):
        self.wid = wid
        self.row = dict(id='fixture-note', title='Storage', body='Keep cache state scoped.', status='accepted',
                        digest='original-digest', origins=[{'path': 'fixture.md', 'line': 12}], review={'reason': 'Reviewed'})
    def note(self, wid, identifier):
        if wid != self.wid or identifier != self.row['id']:
            raise ValueError('Wrong scope')
        return copy.deepcopy(self.row)
    def candidate_page(self, wid, query, **kwargs):
        return dict(rows=[self.note(wid, 'fixture-note')], nextOffset=1, hasMore=False)


def test_migration_preserves_original_and_never_auto_accepts_derived_memory(tmp_path):
    store = Store(tmp_path)
    wid = store.create('workspace', {'name': 'fixture'})['id']
    ledger = MemoryLedger(store); graph = Imported(wid); migration = MemoryMigration(graph, ledger)
    original = copy.deepcopy(graph.row)
    row = migration.preview(wid)['rows'][0]
    result = migration.migrate(wid, row['id'], row['revisionToken'])
    evidence = ledger.evidence(wid, result['evidenceId'])
    assert evidence['body'] == original['body']
    assert evidence['metadata']['originalStatus'] == 'accepted'
    assert evidence['metadata']['origins'] == original['origins']
    assert graph.row == original and ledger.claims(wid) == []
    assert migration.migrate(wid, row['id'], row['revisionToken'])['evidenceId'] == evidence['id']
    with pytest.raises(ValueError):
        migration.migrate('another-project', row['id'], row['revisionToken'])


@pytest.mark.parametrize('change', [{'body': 'Changed'}, {'review': {'reason': 'New review'}}, {'status': 'retracted'}])
def test_stale_preview_or_retracted_note_cannot_migrate(tmp_path, change):
    store = Store(tmp_path); wid = store.create('workspace', {'name': 'fixture'})['id']
    ledger = MemoryLedger(store); graph = Imported(wid); migration = MemoryMigration(graph, ledger)
    row = migration.preview(wid)['rows'][0]
    graph.row.update(change)
    with pytest.raises(ValueError):
        migration.migrate(wid, row['id'], row['revisionToken'])
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM memory_evidence').fetchone()[0] == 0


def test_review_change_creates_new_provenance_snapshot_for_same_body(tmp_path):
    store = Store(tmp_path); wid = store.create('workspace', {'name': 'fixture'})['id']
    ledger = MemoryLedger(store); graph = Imported(wid); migration = MemoryMigration(graph, ledger)
    first = migration.migrate(wid, graph.row['id'], migration.preview(wid)['rows'][0]['revisionToken'])
    graph.row['review'] = {'reason': 'Reviewed again'}
    second = migration.migrate(wid, graph.row['id'], migration.preview(wid)['rows'][0]['revisionToken'])
    assert first['evidenceId'] != second['evidenceId']
    assert first['digest'] == second['digest']
    assert ledger.evidence(wid, first['evidenceId'])['metadata']['originalReview'] == {'reason': 'Reviewed'}
