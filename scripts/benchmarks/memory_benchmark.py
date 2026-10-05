"""Offline production ContextPacks benchmark. Labels never enter retrieval inputs."""
from __future__ import annotations
import hashlib
import json
import math
import os
import inspect
import subprocess
import platform
import sys
import tempfile
import time
from pathlib import Path

from harness_manager.workspaces.context_packs import ContextPacks
from harness_manager.workspaces.knowledge import KnowledgeGraph
from harness_manager.workspaces.memory_ledger import MemoryLedger
from harness_manager.workspaces.memory_sources import MemorySources
from harness_manager.workspaces.stack import StackManager
from harness_manager.workspaces.store import Store

SPLIT_VERSION = 'sha256-id-v1-dev20'


def split_for(identifier):
    return 'dev' if int(hashlib.sha256(identifier.encode()).hexdigest(), 16) % 5 == 0 else 'held-out'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def adapt_longmemeval(records):
    """Return physically separate retrieval inputs and scoring labels, with turn granularity.

    Schema: https://github.com/xiaowu0162/LongMemEval#-dataset-format
    Neither answer, answer_session_ids nor has_answer is copied to input records.
    """
    inputs, labels = [], {}
    for item in records:
        identifier = str(item['question_id'])
        ids, dates, sessions = item['haystack_session_ids'], item['haystack_dates'], item['haystack_sessions']
        if len(ids) != len(sessions) or len(dates) != len(sessions):
            raise ValueError('Session IDs, dates and histories must align uniquely')
        evidence, expected = [], []
        expected_sessions = set(item['answer_session_ids'])
        for session_index, (sid, date, turns) in enumerate(zip(ids, dates, sessions)):
            for index, turn in enumerate(turns):
                key = f'{sid}:{index}' if ids.count(sid) == 1 else f'{sid}:occurrence-{session_index}:{index}'
                body = f"Date: {date}\nRole: {turn['role']}\n{turn['content']}"
                evidence.append({'id': key, 'body': body, 'session_id': str(sid)})
                if turn.get('has_answer') is True:
                    expected.append(key)
        if not expected_sessions.issubset(set(ids)):
            raise ValueError('Answer sessions are outside history')
        inputs.append({'id': identifier, 'query': item['question'], 'question_date': item['question_date'],
                       'evidence': evidence, 'category': item['question_type']})
        abstention = identifier.endswith('_abs')
        # Official retrieval evaluation excludes abstention locations even when history carries labels.
        labels[identifier] = {'answer': item['answer'], 'evidence_ids': [] if abstention else expected,
                              'session_ids': [] if abstention else sorted(expected_sessions), 'abstention': abstention}
    validate(inputs, labels)
    return inputs, labels


def validate(inputs, labels):
    ids = [r['id'] for r in inputs]
    if not ids or set(ids) != set(labels):
        raise ValueError('Unique inputs and gold labels must match exactly')
    for row in inputs:
        if set(row) - {'id', 'query', 'question_date', 'category', 'evidence'}:
            raise ValueError('Unexpected retrieval input field; keep labels separate')
        if not isinstance(row['query'], str) or not row['query'].strip():
            raise ValueError('Query is required')
        evidence_ids = [e['id'] for e in row['evidence']]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError('Duplicate evidence ID')
        for evidence in row['evidence']:
            if set(evidence) - {'id', 'body', 'session_id', 'status'} or not isinstance(evidence['body'], str):
                raise ValueError('Unexpected evidence field; keep labels separate')
        if not set(labels[row['id']].get('evidence_ids', [])).issubset(evidence_ids):
            raise ValueError('Gold evidence is outside corpus')
        for span in labels[row['id']].get('evidence_spans', []):
            evidence = next((e for e in row['evidence'] if e['id'] == span['evidence_id']), None)
            if evidence is None or not span['text'] or span['text'] not in evidence['body']:
                raise ValueError('Gold span must exist verbatim in its evidence source')
        sessions = {e.get('session_id', e['id']) for e in row['evidence']}
        if not set(labels[row['id']].get('session_ids', [])).issubset(sessions):
            raise ValueError('Gold session is outside corpus')


def percentile(values, q):
    """Nearest rank; no fabricated latency when there are no successful samples."""
    return sorted(values)[max(0, math.ceil(q * len(values)) - 1)] if values else None


def _load(root, row):
    store = Store(root)
    ledger = MemoryLedger(store)
    wid = store.create('workspace', {'name': 'Isolated benchmark'})['id']
    graph = KnowledgeGraph(store, StackManager(store), home=root)
    mapping = {}
    with store.lock, store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        for evidence in row['evidence']:
            body = evidence['body']
            # Exact contiguous chunks cover every character; multiple chunks map to one original turn.
            for start in range(0, len(body), 10000):
                chunk = body[start:start + 10000]
                observed = ledger.observe(wid, source_key=f"benchmark:{evidence['id']}:{start}", body=chunk, _db=db)
                claim = ledger.propose(wid, body=chunk, kind='decision', evidence_ids=[observed['id']], _db=db)
                status = evidence.get('status', 'accepted')
                if status != 'proposed':
                    ledger.review(wid, claim['id'], expected_revision=1, status=status,
                                  rationale='Explicit isolated benchmark fixture ingestion', _db=db)
                mapping['claim:' + claim['id']] = evidence
    return graph, wid, mapping


def hardware():
    result = {'os': platform.system(), 'os_release': platform.release(), 'machine': platform.machine(),
              'processor': platform.processor(), 'logical_cpus': os.cpu_count(), 'python': sys.version.split()[0]}
    if platform.system() == 'Darwin':
        for key, label in [('hw.model', 'hardware_model'), ('hw.memsize', 'ram_bytes'), ('machdep.cpu.brand_string', 'cpu_model')]:
            try:
                value = subprocess.check_output(['sysctl', '-n', key], text=True, stderr=subprocess.DEVNULL).strip()
                result[label] = int(value) if label == 'ram_bytes' else value
            except (OSError, subprocess.SubprocessError, ValueError):
                result[label] = None
    return result


def run(inputs, labels, *, split='held-out', repeats=3, token_budget=4000, variant='local', provider=None):
    validate(inputs, labels)
    if split not in {'dev', 'held-out', 'all'} or repeats < 1:
        raise ValueError('Choose a valid split and positive repeat count')
    if variant not in {'local', 'jev', 'jev-fast'}:
        raise ValueError('Only offline production selectors are supported')
    source_hashes = {cls.__module__: hashlib.sha256(Path(inspect.getfile(cls)).read_bytes()).hexdigest() for cls in (ContextPacks, MemorySources, MemoryLedger)}
    selected = [r for r in inputs if split == 'all' or split_for(r['id']) == split]
    samples = []
    for row in selected:
        with tempfile.TemporaryDirectory(prefix='memory-benchmark-') as temporary:
            try:
                graph, wid, mapping = _load(Path(temporary), row)
            except Exception as exc:
                for repeat in range(repeats):
                    for phase in ('cold', 'warm'):
                        samples.append({'case_id': row['id'], 'repeat': repeat, 'phase': phase,
                            'status': 'error', 'error_type': type(exc).__name__, 'failure_stage': 'ingestion', 'latency_ms': None})
                continue
            sources = MemorySources(graph)
            for repeat in range(repeats):
                packs = ContextPacks(provider)  # CLI allows configured providers only with explicit public-data opt-in.
                for phase in ('cold', 'warm'):
                    start = time.perf_counter_ns()
                    result = {'case_id': row['id'], 'repeat': repeat, 'phase': phase}
                    try:
                        query = row['query'] + ('\nQuestion date: ' + row['question_date'] if row.get('question_date') else '')
                        pack = packs.prepare(graph, wid, query, {'mode': variant, 'tokenBudget': token_budget})
                        result['latency_ms'] = (time.perf_counter_ns() - start) / 1e6
                        returned, sessions, integrity, excerpts = set(), set(), 0, {}
                        for ref in pack['refs']:
                            source_id = ref.get('sourceId', ref['id'])
                            source = sources.note(wid, source_id)
                            offset = ref.get('start', 0)
                            if source['body'][offset:offset + len(ref['excerpt'])] != ref['excerpt'] or ref['digest'] != hashlib.sha256(source['body'].encode()).hexdigest():
                                integrity += 1
                            evidence = mapping.get(source_id)
                            if evidence:
                                returned.add(evidence['id'])
                                excerpts.setdefault(evidence['id'], []).append(ref['excerpt'])
                                sessions.add(evidence.get('session_id', evidence['id']))
                        gold = labels[row['id']]  # Accessed only after retrieval completes.
                        expected = set(gold.get('evidence_ids', []))
                        expected_sessions = set(gold.get('session_ids', []))
                        exact_spans = gold.get('evidence_spans', [])
                        span_hits = sum(any(span['text'] in excerpt for excerpt in excerpts.get(span['evidence_id'], [])) for span in exact_spans)
                        result.update(exact_span_hits=span_hits, exact_span_total=len(exact_spans), status=pack['status'], cache_hit=pack['cacheHit'],
                            selected_count=len(returned), turn_source_hits=len(returned & expected), turn_source_total=len(expected),
                            session_hits=len(sessions & expected_sessions), session_total=len(expected_sessions),
                            integrity_errors=integrity, abstention=bool(gold.get('abstention')),
                            provider_calls=sum(t.get('providerCalls', 0) for t in pack.get('retrievalTrace', [])), provider_cost_usd=None,
                            selection_provider=pack.get('selectionProvider', 'local'), warning_present=bool(pack.get('warning')))
                    except Exception as exc:
                        # Do not leak corpus text, secrets, or query labels through exception messages.
                        result.update(latency_ms=(time.perf_counter_ns() - start) / 1e6, status='error', error_type=type(exc).__name__)
                    samples.append(result)
    timing = {}
    for phase in ('cold', 'warm'):
        rows = [s for s in samples if s['phase'] == phase]
        elapsed = [s['latency_ms'] for s in rows if s['latency_ms'] is not None]  # Includes failure latency; no survivorship bias.
        timing[phase] = dict(samples=len(rows), timed_samples=len(elapsed), p50_ms=percentile(elapsed, .5), p95_ms=percentile(elapsed, .95),
                            failures=sum(s['status'] in {'error', 'unavailable', 'failed', 'partial'} for s in rows), status_counts={status: sum(s['status'] == status for s in rows) for status in sorted({s['status'] for s in rows})}, cache_hits=sum(s.get('cache_hit', False) for s in rows))
    # Quality scored once per case (first cold sample), not inflated by repeated cache runs.
    first = [s for s in samples if s['phase'] == 'cold' and s['repeat'] == 0]
    turn_source_total = sum(len(labels[s['case_id']].get('evidence_ids', [])) for s in first)
    session_total = sum(len(labels[s['case_id']].get('session_ids', [])) for s in first)
    return dict(schema_version=1, dataset_input_sha256=digest(inputs), gold_sha256=digest(labels),
        split_version=SPLIT_VERSION, split=split, split_ids=[r['id'] for r in selected], variant=variant,
        configuration={'token_budget': token_budget, 'repeats': repeats}, network_enabled=provider is not None,
        production_source_sha256=source_hashes,
        environment=hardware(),
        timing=timing, quality={'cases': len(first), 'failed_cases': sum(s['status'] in {'error', 'unavailable', 'failed', 'partial'} for s in first),
            'abstention_cases': sum(bool(labels[s['case_id']].get('abstention')) for s in first),
            'empty_reference_cases': sum(s.get('selected_count') == 0 for s in first),
            'turn_source_recall': sum(s.get('turn_source_hits', 0) for s in first) / turn_source_total if turn_source_total else None,
            'session_recall': sum(s.get('session_hits', 0) for s in first) / session_total if session_total else None,
            'turn_source_denominator': turn_source_total,
            'exact_span_recall': sum(s.get('exact_span_hits', 0) for s in first) / sum(len(labels[s['case_id']].get('evidence_spans', [])) for s in first) if sum(len(labels[s['case_id']].get('evidence_spans', [])) for s in first) else None, 'session_denominator': session_total,
            'integrity_errors': sum(s.get('integrity_errors', 0) for s in samples), 'answer_accuracy': None},
        samples=samples, limits=['Turn/source recall means selected source IDs; it does not prove the answer is present in a bounded excerpt.',
            'Exact-span recall is scored only when separate evidence_spans labels are supplied; LongMemEval turn labels do not supply answer spans.',
            'Retrieval recall is not answer accuracy; no answer model or judge was run.',
            'Cold means a fresh ContextPacks instance, not flushed OS/SQLite caches; ingestion excluded from timing.',
            'Warm is the next identical query against the same instance; actual cache hits are reported.',
            '99.9% is aspirational, not an established score. Offline Jev may report unavailable.',
            'Long turns are ingested as exact 10,000-character chunks; span labels crossing chunk boundaries can be missed.',
            'Duplicate public session IDs are disambiguated for turn IDs by session occurrence; session recall uses original IDs.',
            'Each case uses a separate isolated corpus; no private workspace/history discovery.'])


def compare(baseline, change):
    keys = ('dataset_input_sha256', 'gold_sha256', 'split_version', 'split', 'split_ids', 'configuration')
    if any(baseline[k] != change[k] for k in keys):
        raise ValueError('Baseline/change must use identical data, gold, fixed split and benchmark configuration')
    return {'baseline': baseline, 'change': change, 'turn_source_recall_delta':
            change['quality']['turn_source_recall'] - baseline['quality']['turn_source_recall']
            if baseline['quality']['turn_source_recall'] is not None and change['quality']['turn_source_recall'] is not None else None}
