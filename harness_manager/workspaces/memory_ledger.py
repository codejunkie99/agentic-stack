"""Additive, provenance-preserving foundation for the Jev memory lifecycle.

This ledger never edits imported originals. All identifiers are resolved inside a
workspace, and claim changes use compare-and-swap plus an atomic event receipt.
"""
from __future__ import annotations

import hashlib
from contextlib import nullcontext
import json
import uuid

from ..transfer_bundle import now_iso, scan_text_for_secrets


class MemoryConflict(ValueError):
    """The caller reviewed an older claim revision."""


def _text(value, name, limit=200000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {name}.')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


class MemoryLedger:
    def __init__(self, store):
        self.store = store
        with store.lock, store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS memory_evidence (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    source_key TEXT NOT NULL, digest TEXT NOT NULL,
                    body TEXT NOT NULL, metadata TEXT NOT NULL, observed_at TEXT NOT NULL,
                    UNIQUE(workspace_id, source_key, digest));
                CREATE TABLE IF NOT EXISTS memory_claims (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    body TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL, revision INTEGER NOT NULL,
                    replacement_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_events (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL, operation TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_proposals (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, action TEXT NOT NULL,
                    subject_id TEXT NOT NULL, target_id TEXT, subject_revision INTEGER NOT NULL,
                    target_revision INTEGER, model TEXT NOT NULL, status TEXT NOT NULL,
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_links (
                    workspace_id TEXT NOT NULL, subject_id TEXT NOT NULL, target_id TEXT NOT NULL,
                    relation TEXT NOT NULL, proposal_id TEXT NOT NULL,
                    PRIMARY KEY(workspace_id,subject_id,target_id,relation));
                CREATE INDEX IF NOT EXISTS memory_claims_scope
                    ON memory_claims(workspace_id, status);
                CREATE INDEX IF NOT EXISTS memory_events_subject
                    ON memory_events(workspace_id, subject_id);
            ''')

    def _workspace(self, wid):
        self.store.get('workspace', _text(wid, 'workspace', 200))

    @staticmethod
    def _event(db, wid, subject, operation, payload):
        identifier = uuid.uuid4().hex
        db.execute('INSERT INTO memory_events VALUES(?,?,?,?,?,?)',
                   (identifier, wid, subject, operation, _json(payload), now_iso()))
        return identifier

    def observe(self, wid, *, source_key, body, metadata=None, _db=None):
        self._workspace(wid)
        _text(source_key, 'source key', 2000)
        _text(body, 'evidence')
        metadata = {} if metadata is None else metadata
        if not isinstance(metadata, dict) or len(_json(metadata)) > 16000:
            raise ValueError('Invalid evidence metadata.')
        if scan_text_for_secrets(body) or scan_text_for_secrets(source_key) or scan_text_for_secrets(_json(metadata)):
            raise ValueError('Remove credentials before recording evidence.')
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self.store.lock, (nullcontext(_db) if _db is not None else self.store.connect()) as db:
            if _db is None:
                db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id FROM memory_evidence WHERE workspace_id=? AND source_key=? AND digest=?',
                             (wid, source_key, digest)).fetchone()
            if row:
                return self._evidence(db, wid, row[0])
            identifier = uuid.uuid4().hex
            db.execute('INSERT INTO memory_evidence VALUES(?,?,?,?,?,?,?)',
                       (identifier, wid, source_key, digest, body, _json(metadata), now_iso()))
            self._event(db, wid, identifier, 'observed', {'digest': digest, 'sourceKey': source_key})
            return self._evidence(db, wid, identifier)

    @staticmethod
    def _evidence(db, wid, identifier):
        row = db.execute('SELECT id,source_key,digest,body,metadata,observed_at FROM memory_evidence WHERE workspace_id=? AND id=?',
                         (wid, identifier)).fetchone()
        if row is None:
            raise ValueError('Evidence unavailable in this workspace.')
        return dict(id=row[0], workspaceId=wid, sourceKey=row[1], digest=row[2], body=row[3],
                    metadata=json.loads(row[4]), observedAt=row[5])

    def evidence(self, wid, identifier):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            return self._evidence(db, wid, identifier)

    @staticmethod
    def _claim(db, wid, identifier):
        row = db.execute('SELECT id,body,kind,status,evidence_ids,revision,replacement_id,created_at,updated_at FROM memory_claims WHERE workspace_id=? AND id=?',
                         (wid, identifier)).fetchone()
        if row is None:
            raise ValueError('Claim unavailable in this workspace.')
        return dict(id=row[0], workspaceId=wid, body=row[1], kind=row[2], status=row[3],
                    evidenceIds=json.loads(row[4]), revision=row[5], replacementId=row[6],
                    createdAt=row[7], updatedAt=row[8])

    def claim(self, wid, identifier):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            return self._claim(db, wid, identifier)

    def propose(self, wid, *, body, kind, evidence_ids, _db=None):
        self._workspace(wid)
        _text(body, 'claim', 12000)
        if scan_text_for_secrets(body):
            raise ValueError('Remove credentials before proposing a claim.')
        if kind not in {'decision', 'preference', 'fact', 'procedure', 'failure', 'lesson'}:
            raise ValueError('Invalid claim kind.')
        if (not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= 40
                or any(not isinstance(i, str) for i in evidence_ids)
                or len(set(evidence_ids)) != len(evidence_ids)):
            raise ValueError('Provide distinct supporting evidence IDs.')
        with self.store.lock, (nullcontext(_db) if _db is not None else self.store.connect()) as db:
            if _db is None:
                db.execute('BEGIN IMMEDIATE')
            for identifier in evidence_ids:
                self._evidence(db, wid, identifier)
            existing = db.execute('SELECT id FROM memory_claims WHERE workspace_id=? AND body=? AND kind=? AND evidence_ids=?',
                                  (wid, body, kind, _json(evidence_ids))).fetchone()
            if existing:
                return self._claim(db, wid, existing[0])
            identifier, now = uuid.uuid4().hex, now_iso()
            db.execute('INSERT INTO memory_claims VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (identifier, wid, body, kind, 'proposed', _json(evidence_ids), 1, None, now, now))
            self._event(db, wid, identifier, 'proposed', {'body': body, 'kind': kind, 'evidenceIds': evidence_ids, 'revision': 1})
            return self._claim(db, wid, identifier)

    def review(self, wid, identifier, *, expected_revision, status, rationale, replacement_id=None, _db=None):
        """Host-authorized review only; a Jev score is not authorization."""
        self._workspace(wid)
        _text(rationale, 'review rationale', 4000)
        if scan_text_for_secrets(rationale):
            raise ValueError('Remove credentials from the review rationale.')
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('Invalid claim revision.')
        if status not in {'accepted', 'disputed', 'superseded', 'retracted'}:
            raise ValueError('Invalid review status.')
        if bool(replacement_id) != (status == 'superseded'):
            raise ValueError('Only supersession requires a replacement.')
        with self.store.lock, (nullcontext(_db) if _db is not None else self.store.connect()) as db:
            # Acquire SQLite's write lock before reading: separate service
            # instances must not both accept the same old revision.
            if _db is None:
                db.execute('BEGIN IMMEDIATE')
            old = self._claim(db, wid, identifier)
            if old['revision'] != expected_revision:
                raise MemoryConflict('Claim changed; reload before reviewing.')
            if old['status'] in {'superseded', 'retracted'}:
                raise ValueError('Historical claims cannot be reactivated; propose a new claim.')
            if replacement_id:
                replacement = self._claim(db, wid, replacement_id)
                if replacement_id == identifier or replacement['status'] != 'accepted':
                    raise ValueError('Replacement must be a distinct accepted claim in this workspace.')
            db.execute('UPDATE memory_claims SET status=?,revision=revision+1,replacement_id=?,updated_at=? WHERE workspace_id=? AND id=? AND revision=?',
                       (status, replacement_id, now_iso(), wid, identifier, expected_revision))
            self._event(db, wid, identifier, 'reviewed', dict(previousStatus=old['status'], status=status,
                        rationale=rationale, revision=expected_revision + 1, replacementId=replacement_id))
            return self._claim(db, wid, identifier)

    def claims(self, wid, *, include_history=False):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            sql = 'SELECT id FROM memory_claims WHERE workspace_id=?'
            if not include_history:
                sql += " AND status NOT IN ('superseded','retracted')"
            ids = db.execute(sql + ' ORDER BY created_at,id', (wid,)).fetchall()
            return [self._claim(db, wid, row[0]) for row in ids]

    def history(self, wid, subject):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            rows = db.execute('SELECT id,operation,payload,created_at FROM memory_events WHERE workspace_id=? AND subject_id=? ORDER BY rowid',
                              (wid, subject)).fetchall()
            return [dict(id=r[0], operation=r[1], payload=json.loads(r[2]), createdAt=r[3]) for r in rows]


    def record_decision(self, wid, subject, operation, payload):
        self._workspace(wid)
        if operation not in {'capture', 'reconcile', 'maintenance', 'context', 'migration', 'handoff'}:
            raise ValueError('Invalid memory decision operation.')
        if not isinstance(payload, dict) or len(_json(payload)) > 200000:
            raise ValueError('Invalid memory decision payload.')
        if scan_text_for_secrets(_json(payload)):
            raise ValueError('Remove credentials from the memory decision.')
        with self.store.lock, self.store.connect() as db:
            if subject != 'context':
                exists = db.execute('SELECT 1 FROM memory_evidence WHERE workspace_id=? AND id=? UNION ALL SELECT 1 FROM memory_claims WHERE workspace_id=? AND id=?',
                                    (wid, subject, wid, subject)).fetchone()
                if not exists:
                    raise ValueError('Decision subject unavailable in this workspace.')
            return self._event(db, wid, subject, operation, payload)

    @staticmethod
    def _proposal(db, wid, identifier):
        row = db.execute('SELECT id,action,subject_id,target_id,subject_revision,target_revision,model,status,revision,created_at,updated_at FROM memory_proposals WHERE workspace_id=? AND id=?',
                         (wid, identifier)).fetchone()
        if row is None:
            raise ValueError('Memory proposal unavailable in this workspace.')
        return dict(id=row[0], workspaceId=wid, action=row[1], subjectId=row[2], targetId=row[3],
                    subjectRevision=row[4], targetRevision=row[5], model=row[6], status=row[7],
                    revision=row[8], createdAt=row[9], updatedAt=row[10])

    def propose_action(self, wid, subject, *, action, subject_revision, model, target=None, target_revision=None):
        self._workspace(wid)
        _text(model, 'decision model', 200)
        relations = {'duplicate', 'supports', 'contradicts', 'supersedes'}
        if action not in relations | {'revalidate', 'archive'} or (action in relations) != bool(target):
            raise ValueError('Invalid memory proposal action or target.')
        if type(subject_revision) is not int or subject_revision < 1:
            raise ValueError('Invalid proposal source revision.')
        if target is not None and (type(target_revision) is not int or target_revision < 1):
            raise ValueError('Invalid proposal target revision.')
        with self.store.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self._claim(db, wid, subject)
            if current['revision'] != subject_revision or current['status'] in {'retracted', 'superseded'}:
                raise MemoryConflict('Memory changed during evaluation; evaluate again.')
            if target:
                other = self._claim(db, wid, target)
                if target == subject or other['revision'] != target_revision or other['status'] in {'retracted', 'superseded'}:
                    raise MemoryConflict('Related memory changed during evaluation; evaluate again.')
            old = db.execute('SELECT id FROM memory_proposals WHERE workspace_id=? AND action=? AND subject_id=? AND target_id IS ? AND subject_revision=? AND target_revision IS ?',
                             (wid, action, subject, target, subject_revision, target_revision)).fetchone()
            if old:
                return self._proposal(db, wid, old[0])
            identifier, now = uuid.uuid4().hex, now_iso()
            db.execute('INSERT INTO memory_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (identifier, wid, action, subject, target, subject_revision, target_revision, model, 'pending', 1, now, now))
            self._event(db, wid, subject, 'action_proposed', {'proposalId': identifier, 'action': action,
                        'subjectRevision': subject_revision, 'targetId': target, 'targetRevision': target_revision, 'model': model})
            return self._proposal(db, wid, identifier)

    def proposals(self, wid, *, include_history=False):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            sql = 'SELECT id FROM memory_proposals WHERE workspace_id=?'
            if not include_history:
                sql += " AND status='pending'"
            return [self._proposal(db, wid, row[0]) for row in db.execute(sql + ' ORDER BY created_at,id', (wid,)).fetchall()]

    def review_proposal(self, wid, identifier, *, expected_revision, accept, rationale):
        self._workspace(wid)
        _text(rationale, 'proposal review rationale', 4000)
        if type(accept) is not bool or type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('Invalid proposal review.')
        if scan_text_for_secrets(rationale):
            raise ValueError('Remove credentials from proposal review.')
        with self.store.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            proposal = self._proposal(db, wid, identifier)
            if proposal['revision'] != expected_revision or proposal['status'] != 'pending':
                raise MemoryConflict('Proposal changed; reload before reviewing.')
            subject = self._claim(db, wid, proposal['subjectId'])
            target = self._claim(db, wid, proposal['targetId']) if proposal['targetId'] else None
            if accept:
                for claim, revision in [(subject, proposal['subjectRevision']), (target, proposal['targetRevision'])]:
                    if claim and (claim['revision'] != revision or claim['status'] in {'superseded', 'retracted'}):
                        raise MemoryConflict('Memory changed after this proposal; evaluate again.')
                action = proposal['action']
                if target:
                    db.execute('INSERT OR IGNORE INTO memory_links VALUES(?,?,?,?,?)',
                               (wid, subject['id'], target['id'], action, identifier))
                def transition(claim, status, replacement=None):
                    db.execute('UPDATE memory_claims SET status=?,revision=revision+1,replacement_id=?,updated_at=? WHERE workspace_id=? AND id=?',
                               (status, replacement, now_iso(), wid, claim['id']))
                    self._event(db, wid, claim['id'], 'reviewed', {'previousStatus': claim['status'],
                        'status': status, 'revision': claim['revision'] + 1, 'replacementId': replacement,
                        'rationale': rationale, 'proposalId': identifier})
                if action == 'supersedes':
                    transition(subject, 'accepted')
                    transition(target, 'superseded', subject['id'])
                elif action == 'revalidate':
                    transition(subject, 'disputed')
                elif action == 'archive':
                    transition(subject, 'retracted')
            status = 'applied' if accept else 'dismissed'
            db.execute('UPDATE memory_proposals SET status=?,revision=revision+1,updated_at=? WHERE workspace_id=? AND id=?',
                       (status, now_iso(), wid, identifier))
            self._event(db, wid, subject['id'], 'proposal_reviewed',
                        {'proposalId': identifier, 'status': status, 'rationale': rationale})
            return self._proposal(db, wid, identifier)

    def links(self, wid):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            rows = db.execute('SELECT subject_id,target_id,relation,proposal_id FROM memory_links WHERE workspace_id=?', (wid,)).fetchall()
            return [dict(subjectId=r[0], targetId=r[1], relation=r[2], proposalId=r[3]) for r in rows]

    def capture_page(self, wid, evidence_id, spans, decisions, *, start_span):
        """Commit a bounded classified page and its derivation receipt together."""
        self._workspace(wid)
        if not isinstance(spans, list) or not 1 <= len(spans) <= 12 or len(spans) != len(decisions):
            raise ValueError('Invalid capture page.')
        if type(start_span) is not int or start_span < 0:
            raise ValueError('Invalid capture page offset.')
        payload = dict(evidenceId=evidence_id, startSpan=start_span,
                       nextSpan=start_span + len(spans), decisions=decisions)
        if scan_text_for_secrets(_json(payload)):
            raise ValueError('Remove credentials from capture decisions.')
        with self.store.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            evidence = self._evidence(db, wid, evidence_id)
            # First committed outcome owns an immutable span, including skip.
            # Read under the write lock so concurrent captures cannot disagree.
            committed = {}
            for row in db.execute("SELECT payload FROM memory_events WHERE workspace_id=? AND subject_id=? AND operation='capture_page' ORDER BY rowid", (wid, evidence_id)):
                for previous in json.loads(row[0])['decisions']:
                    committed.setdefault(previous['spanId'], previous)
            claims, effective = [], []
            for span, decision in zip(spans, decisions):
                start, end = span.get('start'), span.get('end')
                if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(evidence['body'])
                        or span.get('text') != evidence['body'][start:end]
                        or span.get('id') != f'{start}:{end}' or decision.get('spanId') != span['id']):
                    raise ValueError('Capture span does not match its original evidence.')
                decision = committed.get(span['id'], decision)
                effective.append(decision)
                if decision['choice'] == 'skip':
                    continue
                selected = self.observe(wid, source_key=f"evidence:{evidence_id}:span:{span['id']}",
                    body=span['text'], metadata={'parentEvidenceId': evidence_id, 'parentDigest': evidence['digest'],
                    'start': start, 'end': end, 'model': decision['model']}, _db=db)
                claims.append(self.propose(wid, body=span['text'], kind=decision['choice'], evidence_ids=[selected['id']], _db=db))
            payload.update(digest=evidence['digest'], decisions=effective, claimIds=[claim['id'] for claim in claims])
            receipt_id = self._event(db, wid, evidence_id, 'capture_page', payload)
            return dict(claims=claims, decisions=effective, receiptId=receipt_id)

    @staticmethod
    def _context_receipt(db, wid, plan_id):
        row = db.execute("SELECT payload FROM memory_events WHERE workspace_id=? AND subject_id=? AND operation='context_applied'", (wid, plan_id)).fetchone()
        return json.loads(row[0]) if row else None

    def context_receipt(self, wid, plan_id):
        self._workspace(wid)
        with self.store.lock, self.store.connect() as db:
            return self._context_receipt(db, wid, plan_id)

    def apply_context_plan(self, wid, plan_id, changes, *, model):
        """Apply an immutable host-reviewed plan, all changes and receipt atomic.

        Forget is retraction with history. Replaying a committed plan returns
        the original receipt even after server restart or later claim edits.
        """
        self._workspace(wid)
        _text(plan_id, 'context plan ID', 200)
        _text(model, 'decision model', 200)
        if not isinstance(changes, list) or not 1 <= len(changes) <= 16:
            raise ValueError('Invalid context memory changes.')
        with self.store.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            receipt = self._context_receipt(db, wid, plan_id)
            if receipt:
                if receipt['changeDigest'] != hashlib.sha256(_json(changes).encode()).hexdigest():
                    raise MemoryConflict('Plan ID was already applied with different reviewed changes.')
                return receipt
            remembered, forgotten = [], []
            for change in changes:
                if change['action'] == 'remember':
                    evidence = self.observe(wid, source_key='context-input:' + change['id'], body=change['body'],
                        metadata={'source': change['source'], 'planId': plan_id, 'model': model}, _db=db)
                    claim = self.propose(wid, body=change['body'], kind=change['kind'], evidence_ids=[evidence['id']], _db=db)
                    if claim['status'] == 'proposed':
                        claim = self.review(wid, claim['id'], expected_revision=claim['revision'], status='accepted',
                            rationale='User explicitly applied the reviewed exact-text context plan.', _db=db)
                    elif claim['status'] != 'accepted':
                        raise MemoryConflict('This incoming item already has a historical or disputed claim; plan a new item.')
                    remembered.append(claim['id'])
                elif change['action'] == 'forget':
                    identifier = change['id'].removeprefix('claim:')
                    current = self._claim(db, wid, identifier)
                    if current['status'] != 'accepted' or current['revision'] != change['expectedRevision'] or current['body'] != change['body']:
                        raise MemoryConflict('Forget target changed after planning; review a new plan.')
                    self.review(wid, identifier, expected_revision=change['expectedRevision'], status='retracted',
                        rationale='User explicitly applied the reviewed forget target; original evidence and history retained.', _db=db)
                    forgotten.append(identifier)
                else:
                    raise ValueError('Invalid context memory action.')
            receipt = dict(status='completed', workspaceId=wid, planId=plan_id, rememberedIds=remembered,
                           forgottenIds=forgotten, changeDigest=hashlib.sha256(_json(changes).encode()).hexdigest())
            self._event(db, wid, plan_id, 'context_applied', receipt)
            return receipt
