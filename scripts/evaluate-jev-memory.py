#!/usr/bin/env python3
"""Evaluate production retrieval against synthetic records; offline unless explicitly opted in."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_manager.workspaces.context_packs import ContextPacks
from harness_manager.workspaces.jev_settings import ConfiguredJevProvider, JevSettings
from harness_manager.workspaces.knowledge import KnowledgeGraph
from harness_manager.workspaces.memory_ledger import MemoryLedger
from harness_manager.workspaces.memory_sources import MemorySources
from harness_manager.workspaces.stack import StackManager
from harness_manager.workspaces.store import Store


def evaluate(root, fixture, provider=None):
    store = Store(root)
    ledger = MemoryLedger(store)
    graph = KnowledgeGraph(store, StackManager(store), home=root)
    scopes = {key: store.create('workspace', {'name': 'Synthetic ' + key})['id']
              for key in ('main', 'foreign')}
    claims = {}
    for item in fixture['claims']:
        body = item['body']
        if item.get('padding'):
            body += '\n\n' + ('Archived experiment measured rendering durations without a retention decision.\n' * item['padding'])
            body += '\n' + item['tail']
        wid = scopes[item.get('scope', 'main')]
        evidence = ledger.observe(wid, source_key='synthetic:' + item['key'], body=body)
        claim = ledger.propose(wid, body=body, kind='decision', evidence_ids=[evidence['id']])
        if item['status'] != 'proposed':
            claim = ledger.review(wid, claim['id'], expected_revision=1, status=item['status'],
                rationale='Synthetic evaluation fixture',
                replacement_id=claims[item['replacement']]['id'] if item.get('replacement') else None)
        claims[item['key']] = dict(claim, scope=wid)
    modes = ['local'] + (['jev'] if provider is not None else [])
    reports = {}
    for mode in modes:
        packs = ContextPacks(provider)
        rows, safety_errors = [], []
        sources = MemorySources(graph)
        for case in fixture['queries']:
            pack = packs.prepare(graph, scopes['main'], case['query'],
                                 dict(mode=mode, tokenBudget=4000, timeoutSeconds=60))
            excerpts = {}
            for ref in pack['refs']:
                identifier = ref.get('sourceId', ref['id'])
                source = sources.note(scopes['main'], identifier)
                excerpt = ref['excerpt']
                start = ref.get('start', 0)
                if source['body'][start:start + len(excerpt)] != excerpt:
                    safety_errors.append(case['name'] + ': excerpt differs from source')
                if ref['digest'] != hashlib.sha256(source['body'].encode()).hexdigest():
                    safety_errors.append(case['name'] + ': digest differs from source')
                excerpts.setdefault(identifier, []).append(excerpt)
            expected = case['expected']
            hits = sum(any(phrase in excerpt for excerpt in excerpts.get('claim:' + claims[key]['id'], []))
                       for key, phrase in expected.items())
            rows.append(dict(name=case['name'], exactEvidenceHits=hits, expectedEvidence=len(expected),
                recall=hits / len(expected), selectedReferences=len(pack['refs']),
                selectionProvider=pack.get('selectionProvider', 'local'), status=pack['status'],
                elapsedMs=pack['elapsedMs'], coverage=pack.get('coverage')))
        # Pins exercise explicit cross-scope/stale/proposed/disputed eligibility, offline for both reports.
        invalid = ['claim:' + claims[key]['id'] for key in ('foreign', 'old-panels', 'disputed', 'unreviewed')]
        pinned = ContextPacks().prepare(graph, scopes['main'], 'Cache search overlays',
                    dict(mode='local', pinnedIds=invalid, tokenBudget=4000))
        excluded = not any(ref['id'] in invalid for ref in pinned['refs'])
        reports[mode] = dict(cases=rows, exactEvidenceRecall=sum(r['exactEvidenceHits'] for r in rows) /
            sum(r['expectedEvidence'] for r in rows), evidenceIntegrityErrors=safety_errors,
            invalidPinsExcluded=excluded,
            jevSelectedCases=sum(r['selectionProvider'] == 'jev' for r in rows))
    # Reuse one real cache instance before and after a durable review change.
    packs = ContextPacks()
    before = packs.prepare(graph, scopes['main'], 'Cache keys', dict(mode='local'))
    claim = claims['cache']
    ledger.review(scopes['main'], claim['id'], expected_revision=claim['revision'],
                  status='retracted', rationale='Synthetic stale-cache check')
    after = packs.prepare(graph, scopes['main'], 'Cache keys', dict(mode='local'))
    cache_check = ('claim:' + claim['id'] in {r['id'] for r in before['refs']} and
                   'claim:' + claim['id'] not in {r['id'] for r in after['refs']} and not after['cacheHit'])
    assert cache_check, 'Retracted evidence survived a warm context cache'
    assert all(not r['evidenceIntegrityErrors'] and r['invalidPinsExcluded'] for r in reports.values())
    return dict(dataset='synthetic-only-v1', networkEnabled=provider is not None,
                reports=reports, retractionInvalidatesWarmCache=cache_check,
                limits='Six synthetic queries; no production corpus, no model-quality claim for offline results. '
                       'Pin and warm-cache checks use local selection. Live fallbacks remain labeled local.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-jev', action='store_true', help='Permit hosted requests containing only synthetic fixture text')
    parser.add_argument('--provider-root', type=Path, help='Explicit root containing the configured Jev provider file; only read with --live-jev')
    args = parser.parse_args()
    if args.live_jev != (args.provider_root is not None):
        parser.error('--live-jev and --provider-root must be supplied together after user approval')
    provider = None
    if args.live_jev:
        provider = ConfiguredJevProvider(JevSettings(args.provider_root))
        if not provider.available:
            parser.error('Explicit provider is disabled or unavailable; configure it in the app first')
    fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('jev-memory-evaluation.json').read_text())
    with tempfile.TemporaryDirectory(prefix='jev-synthetic-evaluation-') as temporary:
        report = evaluate(Path(temporary), fixture, provider)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
