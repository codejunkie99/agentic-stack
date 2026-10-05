"""One scoped read interface for reviewed claims, imported notes and conversations."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter


def evidence_window(body, query, limit, *, check=None):
    """Return an exact contiguous source slice, favoring distinct query evidence.

    Rare terms outweigh repeated boilerplate. No match retains the old prefix;
    offsets always refer to the original Unicode string, never a normalized copy.
    """
    if check:
        check()
    if len(body) <= limit or limit <= 0:
        return body[:max(0, limit)], 0
    stop = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'your',
            'you', 'are', 'can', 'could', 'would', 'should', 'please', 'use',
            'using', 'task', 'make', 'add', 'fix', 'all', 'our', 'then', 'its',
            'not', 'but', 'about', 'what', 'which', 'when', 'where', 'how'}
    terms = list(dict.fromkeys(t.casefold() for t in re.findall(r'[\w-]{3,}', query)
                              if t.casefold() not in stop))[:18]
    if not terms:
        return body[:limit], 0
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(t) for t in terms) + r')(?!\w)', re.I)
    matches = []
    for index, match in enumerate(pattern.finditer(body)):
        if check and index % 1024 == 0:
            check()
        matches.append((match.start(), match.end(), match.group().casefold()))
    if check:
        check()
    if not matches:
        return body[:limit], 0
    totals = Counter(term for _, _, term in matches)
    counts, right, score = Counter(), 0, 0.0
    best_score, best_start = -1.0, 0
    left = 0
    for index, (position, _, _) in enumerate(matches):
        if check and index % 1024 == 0:
            check()
        start = max(0, position - min(160, limit // 4))
        while right < len(matches) and matches[right][1] <= start + limit:
            term = matches[right][2]
            if not counts[term]:
                score += 1 / totals[term]
            counts[term] += 1
            right += 1
        while left < right and matches[left][0] < start:
            term = matches[left][2]
            counts[term] -= 1
            if not counts[term]:
                score -= 1 / totals[term]
            left += 1
        # Normalize by the amount of source text in the window. A short ending
        # passage should not lose to a long window filled with repeated filler.
        density = score / max(1, min(limit, len(body) - start)) ** .5
        if density > best_score + 1e-12:
            best_score, best_start = density, start
    # Prefer a complete nearby line when doing so keeps the anchor in the slice.
    line = body.rfind('\n', 0, best_start) + 1
    if best_start - line <= min(80, limit // 8):
        best_start = line
    return body[best_start:best_start + limit], best_start


class MemorySources:
    def __init__(self, graph, *, conversations=None, exclude_conversation='', topic=''):
        self.graph, self.conversations = graph, conversations
        self.exclude_conversation = exclude_conversation
        self.topic = topic

    @staticmethod
    def _claim_row(db, wid, row):
        identifier, body, kind, revision, evidence_ids = row
        origins = []
        for eid in json.loads(evidence_ids):
            evidence = db.execute('SELECT source_key,metadata FROM memory_evidence WHERE workspace_id=? AND id=?', (wid, eid)).fetchone()
            if evidence:
                origins.append({'path': evidence[0], 'line': 1, 'evidenceId': eid})
        return dict(id='claim:' + identifier, title=body.splitlines()[0][:160], body=body,
                    kind='memory', memoryKind=kind, status='accepted', review={'revision': revision},
                    digest=hashlib.sha256(body.encode()).hexdigest(), origins=origins)

    def _claims(self, wid, query, *, offset=0, limit=20, identifier=None, count=True):
        store = getattr(self.graph, 'store', None)
        if store is None:
            return [], 0
        # Validate workspace before opening any scoped claims.
        store.get('workspace', wid)
        with store.lock, store.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_claims'").fetchone():
                return [], 0
            where, values = "workspace_id=? AND status='accepted'", [wid]
            order, ranking_values = 'created_at,id', []
            if identifier is not None:
                where += ' AND id=?'; values.append(identifier)
            elif query:
                terms = list(dict.fromkeys(re.findall(r'[\w-]{3,}', query.casefold())))[:18]
                if terms:
                    where += ' AND (' + ' OR '.join('instr(lower(body),?)>0' for _ in terms) + ')'
                    values.extend(terms)
                    # Distinct term evidence, weighted by document frequency in
                    # the eligible workspace. Repeated boilerplate cannot boost
                    # its score. Rank before LIMIT, with stable pagination ties.
                    frequencies = db.execute('SELECT count(*),' + ','.join(
                        'coalesce(sum(instr(lower(body),?)>0),0)' for _ in terms) +
                        " FROM memory_claims WHERE workspace_id=? AND status='accepted'",
                        (*terms, wid)).fetchone()
                    weights = [math.log1p((frequencies[0] - frequency + .5) / (frequency + .5))
                               for frequency in frequencies[1:]]
                    relevance = ' + '.join('(instr(lower(body),?)>0)*?' for _ in terms)
                    ranking_values = [value for pair in zip(terms, weights) for value in pair]
                    order = '(' + relevance + ') DESC,created_at,id'
            total = db.execute('SELECT count(*) FROM memory_claims WHERE ' + where, values).fetchone()[0] if count else 0
            rows = db.execute('SELECT id,body,kind,revision,evidence_ids FROM memory_claims WHERE ' + where +
                              ' ORDER BY ' + order + ' LIMIT ? OFFSET ?',
                              (*values, *ranking_values, limit, offset)).fetchall()
            return [self._claim_row(db, wid, row) for row in rows], total

    def accepted_candidates(self, wid, query, *, limit=80):
        return self._claims(wid, query, limit=limit, count=False)[0]

    def _chats(self, wid, query):
        if self.conversations is None:
            return []
        from .context_packs import conversation_candidates
        return conversation_candidates(self.conversations, wid, query, self.exclude_conversation)

    def candidate_page(self, wid, query, *, offset=0, limit=20):
        # Three concatenated scoped streams; offsets count across stream boundaries.
        claims, claim_count = self._claims(wid, query, offset=offset, limit=limit)
        rows = list(claims)
        chats = self._chats(wid, query)
        chat_offset = max(0, offset - claim_count)
        if len(rows) < limit and offset + len(rows) >= claim_count:
            rows.extend(chats[chat_offset:chat_offset + limit - len(rows)])
        extras = claim_count + len(chats)
        more = offset + len(rows) < extras
        if len(rows) < limit and offset + len(rows) >= extras:
            page = self.graph.candidate_page(wid, query, offset=max(0, offset - extras), limit=limit - len(rows))
            rows.extend(page['rows']); more = page['hasMore']
        elif not more:
            # The page ended exactly on a stream boundary; inspect existence only.
            more = bool(self.graph.candidate_page(wid, query, offset=max(0, offset + len(rows) - extras), limit=1)['rows'])
        return {'rows': rows, 'nextOffset': offset + len(rows), 'hasMore': more}

    @staticmethod
    def _source_row(row):
        return dict(id='source:' + row['id'], title=row['name'], body=row['text'], kind='source',
                    status='reference', source=row.get('origin') or 'workspace source:' + row['id'],
                    digest=hashlib.sha256(row['text'].encode()).hexdigest(),
                    review={'approved': row['approved'], 'reviewedAt': row.get('reviewedAt')},
                    origins=[{'path': row.get('origin') or 'workspace source:' + row['id'], 'line': 1}])

    def approved_candidates(self, wid, query, *, limit=80):
        """Rank only approved documents in this workspace, before the shortlist.

        Filter in SQLite rather than loading every workspace's source bodies.
        Source text remains exact and source approval is checked again by note().
        """
        store = getattr(self.graph, 'store', None)
        if store is None:
            return []
        store.get('workspace', wid)
        terms = list(dict.fromkeys(re.findall(r'[\w-]{3,}', query.casefold())))[:18]
        fields = ("lower(json_extract(data,'$.name'))", "lower(json_extract(data,'$.text'))")
        score = ' + '.join(f'(instr({field},?)>0)*{weight}'
                           for field, weight in zip(fields, (2, 1)) for _ in terms) or '0'
        values = terms + terms
        with store.lock, store.connect() as db:
            rows = db.execute("SELECT data," + score + " AS relevance FROM records WHERE kind='source' "
                "AND json_extract(data,'$.workspaceId')=? AND json_extract(data,'$.approved')=1 " +
                ("AND relevance>0 " if terms else '') +
                "ORDER BY relevance DESC,id LIMIT ?", (*values, wid, min(limit, 200))).fetchall()
        return [self._source_row(row) for data, _ in rows
                if (row := json.loads(data)).get('approved') is True]

    def context_candidates(self, wid, query, *, streams, limit=16):
        """Represent each scoped stream before one bounded Jev batch.

        Lexical discovery is host work; broad imported rows give the model a
        chance to find a match outside the lexical shortlist. No source is
        claimed inspected beyond its supplied exact prefix.
        """
        groups = []
        store = getattr(self.graph, 'store', None)
        if store is not None:
            store.get('workspace', wid)
        if self.topic and 'memory' in streams:
            ranked = self.graph.query(dict(workspaceId=wid, query=query[:300], topic=self.topic))
            broad = self.graph.query(dict(workspaceId=wid, query='', topic=self.topic))
            groups.append(list({r['id']: r for r in ranked['notes'] + broad['notes']
                                if r.get('status', 'reference') in {'reference', 'accepted'}}.values()))
        elif 'memory' in streams:
            claims = self.accepted_candidates(wid, query, limit=limit + 1) + self.accepted_candidates(wid, '', limit=limit + 1)
            groups.append(list({r['id']: r for r in claims}.values()))
            candidates = self.graph.candidates(wid, query, limit=limit + 1)
            if hasattr(self.graph, 'candidate_page'):
                candidates += self.graph.candidate_page(wid, '', limit=limit + 1)['rows']
            groups.append(list({r['id']: r for r in candidates}.values()))
        if 'conversations' in streams:
            groups.append(self._chats(wid, query))
        if store is not None and ('memory' in streams or 'sources' in streams):
            ranked = self.approved_candidates(wid, query, limit=limit + 1)
            broad = self.approved_candidates(wid, '', limit=limit + 1)
            groups.append(list({r['id']: r for r in ranked + broad}.values()))
        rows = [group[index] for index in range(max((len(group) for group in groups), default=0))
                for group in groups if index < len(group)]
        rows = list({r['id']: r for r in rows}.values())
        if self.topic:
            rows = [r for r in rows if self.topic in r.get('topics', [])]
        return rows[:limit], len(rows) > limit

    def note(self, wid, identifier):
        if identifier.startswith('source:'):
            row = self.graph.store.get('source', identifier.removeprefix('source:'))
            if row.get('workspaceId') != wid or row.get('approved') is not True:
                raise ValueError('Reviewed source unavailable in this workspace.')
            return self._source_row(row)
        if identifier.startswith('claim:'):
            rows, _ = self._claims(wid, '', identifier=identifier.removeprefix('claim:'))
            if not rows:
                raise ValueError('Accepted memory claim unavailable in this workspace.')
            return rows[0]
        if identifier.startswith(('native:', 'live:')) and self.conversations is not None:
            from .context_packs import conversation_note
            if identifier == 'native:' + self.exclude_conversation:
                raise ValueError('Current conversation is excluded.')
            return conversation_note(self.conversations, wid, identifier)
        return self.graph.note(wid, identifier)
