import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[1] / 'scripts/benchmarks/memory_benchmark.py'
spec = importlib.util.spec_from_file_location('memory_benchmark', path)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def public_shape():
    return [{'question_id': 'fixture-1', 'question_type': 'single-session-user', 'question': 'Which cache setting?',
             'answer': 'LABEL MUST NEVER LEAK', 'question_date': '2024-01-03',
             'haystack_session_ids': ['s1', 's2'], 'haystack_dates': ['2024-01-01', '2024-01-02'],
             'haystack_sessions': [[{'role': 'user', 'content': 'Cache setting is cedar.', 'has_answer': True}],
                                   [{'role': 'assistant', 'content': 'Routine unrelated note.'}]],
             'answer_session_ids': ['s1']}]


def test_adapter_removes_all_labels_and_keeps_exact_turns():
    inputs, labels = b.adapt_longmemeval(public_shape())
    assert 'LABEL MUST NEVER LEAK' not in str(inputs)
    assert 'has_answer' not in str(inputs) and 'answer_session_ids' not in str(inputs)
    assert labels['fixture-1']['evidence_ids'] == ['s1:0']
    assert labels['fixture-1']['session_ids'] == ['s1']
    assert inputs[0]['evidence'][0]['body'].endswith('Cache setting is cedar.')


def test_fixed_split_independent_of_order_and_labels():
    ids = ['case-' + str(i) for i in range(100)]
    forward = {i: b.split_for(i) for i in ids}
    assert forward == {i: b.split_for(i) for i in reversed(ids)}
    assert set(forward.values()) == {'dev', 'held-out'}
    assert b.SPLIT_VERSION == 'sha256-id-v1-dev20'


def test_rejects_label_injection_and_orphan_gold():
    inputs, gold = b.adapt_longmemeval(public_shape())
    inputs[0]['evidence'][0]['has_answer'] = True
    with pytest.raises(ValueError):
        b.validate(inputs, gold)
    del inputs[0]['evidence'][0]['has_answer']
    gold['fixture-1']['evidence_ids'] = ['missing']
    with pytest.raises(ValueError):
        b.validate(inputs, gold)


def test_runs_real_production_cold_warm_integrity_and_redacts_reports():
    inputs, gold = b.adapt_longmemeval(public_shape())
    report = b.run(inputs, gold, split='all', repeats=2)
    assert report['quality']['turn_source_recall'] == 1
    assert report['quality']['session_recall'] == 1
    assert report['quality']['answer_accuracy'] is None
    assert report['quality']['integrity_errors'] == 0
    assert report['timing']['cold']['samples'] == report['timing']['warm']['samples'] == 2
    assert report['timing']['warm']['cache_hits'] == 2
    assert report['timing']['cold']['cache_hits'] == 0
    assert 'Cache setting is cedar' not in str(report) and 'LABEL MUST NEVER LEAK' not in str(report)
    assert report['network_enabled'] is False


def test_compare_rejects_changed_corpus_and_gold():
    inputs, gold = b.adapt_longmemeval(public_shape())
    report = b.run(inputs, gold, split='all', repeats=1)
    assert b.compare(report, report)['turn_source_recall_delta'] == 0
    changed = dict(report, gold_sha256='different')
    with pytest.raises(ValueError):
        b.compare(report, changed)


def test_percentiles_and_empty_split_are_honest():
    assert b.percentile([9, 1, 5, 2], .5) == 2
    assert b.percentile([9, 1, 5, 2], .95) == 9
    assert b.percentile([], .95) is None
    inputs, gold = b.adapt_longmemeval(public_shape())
    other = 'dev' if b.split_for('fixture-1') == 'held-out' else 'held-out'
    report = b.run(inputs, gold, split=other)
    assert report['quality']['turn_source_recall'] is None and report['quality']['cases'] == 0
    assert report['timing']['cold']['p95_ms'] is None


def test_exact_span_is_separate_from_source_id_hit(monkeypatch):
    inputs, gold = b.adapt_longmemeval(public_shape())
    gold['fixture-1']['evidence_spans'] = [{'evidence_id': 's1:0', 'text': 'cedar'}]
    original = b.ContextPacks.prepare
    def bounded(self, *args, **kwargs):
        pack = original(self, *args, **kwargs)
        for ref in pack['refs']:
            ref['excerpt'] = ref['excerpt'].split('Cache')[0]
        return pack
    monkeypatch.setattr(b.ContextPacks, 'prepare', bounded)
    report = b.run(inputs, gold, split='all', repeats=1)
    assert report['quality']['turn_source_recall'] == 1
    assert report['quality']['exact_span_recall'] == 0
    assert report['quality']['integrity_errors'] == 0


def test_duplicate_sessions_and_long_turns_are_preserved():
    raw = public_shape()
    raw[0]['haystack_session_ids'] = ['s1', 's1']
    raw[0]['haystack_sessions'][0][0]['content'] = 'Cache ' + 'padding ' * 2000 + 'cedar'
    inputs, gold = b.adapt_longmemeval(raw)
    assert inputs[0]['evidence'][0]['id'] != inputs[0]['evidence'][1]['id']
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        graph, wid, mapping = b._load(Path(root), inputs[0])
        bodies = [b.MemorySources(graph).note(wid, key)['body'] for key, evidence in mapping.items()
                  if evidence['id'] == inputs[0]['evidence'][0]['id']]
        assert ''.join(bodies) == inputs[0]['evidence'][0]['body']
        assert max(map(len, bodies)) <= 10000


def test_ingestion_failure_counts_against_quality_denominator(monkeypatch):
    inputs, gold = b.adapt_longmemeval(public_shape())
    def fail(*args):
        raise ValueError('sensitive text must not be reported')
    monkeypatch.setattr(b, '_load', fail)
    report = b.run(inputs, gold, split='all', repeats=2)
    assert report['quality']['failed_cases'] == 1
    assert report['quality']['turn_source_recall'] == 0
    assert report['timing']['cold']['failures'] == 2
    assert report['timing']['cold']['p95_ms'] is None
    assert 'sensitive text' not in str(report)


def test_abstention_history_labels_are_not_scored_as_retrieval_gold():
    raw = public_shape()
    raw[0]['question_id'] = 'fixture_abs'
    inputs, gold = b.adapt_longmemeval(raw)
    assert gold['fixture_abs']['evidence_ids'] == [] and gold['fixture_abs']['session_ids'] == []
    assert len(inputs[0]['evidence']) == 2
    report = b.run(inputs, gold, split='all', repeats=1)
    assert report['quality']['turn_source_recall'] is None
    assert report['quality']['session_recall'] is None
    assert report['quality']['answer_accuracy'] is None


def test_offline_jev_unavailability_is_not_a_success_score():
    inputs, gold = b.adapt_longmemeval(public_shape())
    report = b.run(inputs, gold, split='all', repeats=1, variant='jev')
    assert report['network_enabled'] is False
    assert report['quality']['failed_cases'] == 1
    assert report['quality']['turn_source_recall'] == 0
    assert report['timing']['cold']['failures'] == 1
    assert report['samples'][0]['provider_calls'] == 0


def test_exact_span_failure_retains_gold_denominator(monkeypatch):
    inputs, gold = b.adapt_longmemeval(public_shape())
    import copy
    other = copy.deepcopy(inputs[0])
    other['id'] = 'fixture-failure'
    inputs.append(other)
    gold['fixture-1']['evidence_spans'] = [{'evidence_id': 's1:0', 'text': 'cedar'}]
    gold[other['id']] = copy.deepcopy(gold['fixture-1'])
    original = b._load
    def partial(root, row):
        if row['id'] == 'fixture-failure':
            raise ValueError('ingestion failure')
        return original(root, row)
    monkeypatch.setattr(b, '_load', partial)
    report = b.run(inputs, gold, split='all', repeats=1)
    assert report['quality']['exact_span_recall'] == .5
    assert report['quality']['turn_source_recall'] == .5
