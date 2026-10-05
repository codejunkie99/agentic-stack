"""Explicit migration of imported notes into immutable Jev evidence snapshots."""
import hashlib
import json


def revision_token(note):
    return hashlib.sha256(json.dumps([note['id'], note.get('digest'), note['body'],
        note.get('status', 'reference'), note.get('review')], sort_keys=True).encode()).hexdigest()


class MemoryMigration:
    def __init__(self, graph, ledger):
        self.graph, self.ledger = graph, ledger

    def preview(self, wid, *, offset=0):
        page = self.graph.candidate_page(wid, '', offset=offset, limit=20)
        return dict(rows=[dict(id=row['id'], title=row['title'], body=row['body'],
                              status=row.get('status', 'reference'), revisionToken=revision_token(row))
                          for row in page['rows']], nextOffset=page['nextOffset'], hasMore=page['hasMore'])

    def migrate(self, wid, identifier, expected_revision):
        note = self.graph.note(wid, identifier)
        if note.get('status', 'reference') not in {'reference', 'accepted'}:
            raise ValueError('Only current imported memory can be migrated.')
        if not isinstance(expected_revision, str) or revision_token(note) != expected_revision:
            raise ValueError('Imported memory changed; refresh before migrating.')
        evidence = self.ledger.observe(wid, source_key='imported-note:' + identifier + ':revision:' + expected_revision,
            body=note['body'], metadata={'importedNoteId': identifier, 'originalDigest': note.get('digest'),
                'originalStatus': note.get('status', 'reference'), 'originalReview': note.get('review'),
                'origins': note.get('origins', [])[:20], 'migrationRevision': expected_revision})
        # Preserve source acceptance as provenance, not automatic approval of new derived claims.
        receipt_id = self.ledger.record_decision(wid, evidence['id'], 'migration',
            dict(noteId=identifier, revisionToken=expected_revision, evidenceId=evidence['id'],
                 originalStatus=note.get('status', 'reference')))
        return dict(evidenceId=evidence['id'], digest=evidence['digest'], receiptId=receipt_id,
                    status='observed', warning='')
