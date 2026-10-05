"""Review real imported evidence without mutating its sources or retrieval history."""
import json

import pytest

from harness_manager.workspaces.knowledge import KnowledgeGraph, digest
from harness_manager.workspaces.service import WorkspaceService


@pytest.fixture
def graph(tmp_path):
    service = WorkspaceService(tmp_path/'data')
    project = tmp_path/'project'
    project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    home = tmp_path/'home'
    home.mkdir()
    service.knowledge = KnowledgeGraph(service.store, service.stack, home=home)
    yield service, wid, home
    service.close()


def import_notes(graph, content, wid=None):
    service, default_wid, home = graph
    wid = wid or default_wid
    source = home/'.codex/memories/MEMORY.md'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content)
    preview = service.knowledge.preview({'workspaceId': wid, 'providers': ['codex']})
    service.knowledge.import_preview({'workspaceId': wid, 'previewId': preview['id'],
                                     'sourceIds': [f['id'] for f in preview['files']]})
    return source


def review(service, wid, identifier, status, **extra):
    return service.knowledge.review_note({'workspaceId': wid, 'noteId': identifier,
                                         'status': status, 'reason': 'Checked source evidence.', **extra})


def test_reviews_keep_original_evidence_and_append_sanitized_history(graph):
    service, wid, _ = graph
    source = import_notes(graph, '# Decision\nUse SQLite for local memory.')
    original = source.read_bytes()
    note = service.knowledge.query({'workspaceId': wid})['notes'][0]
    assert note['status'] == 'reference' and note['review'] is None
    assert note['digest'] == digest(note['body'])
    secret = 'ghp_'+'a'*36
    accepted = review(service, wid, note['id'], 'accepted', reason='Checked.\nGITHUB_TOKEN='+secret)
    rejected = review(service, wid, note['id'], 'retracted', reason='A later check contradicted this.')
    restored = review(service, wid, note['id'], 'reference', reason='Keep as historical evidence.')
    assert secret not in json.dumps(accepted)
    assert '[credential-like content omitted]' in accepted['review']['reason']
    assert [e['status'] for e in restored['review']['history']] == ['accepted', 'retracted', 'reference']
    assert [e['revision'] for e in restored['review']['history']] == [1, 2, 3]
    assert all(e['updatedAt'] for e in restored['review']['history'])
    assert restored['review']['updatedAt'] >= accepted['review']['updatedAt']
    assert restored['review']['history'][:2] == rejected['review']['history']
    for result in [accepted, rejected, restored]:
        assert {key: result[key] for key in note if key not in {'status', 'review'}} == {
            key: note[key] for key in note if key not in {'status', 'review'}}
    assert service.store.get('knowledge-review', digest(wid+note['id'])) == restored['review']
    assert source.read_bytes() == original


def test_review_persists_across_reimports_and_service_reopen(graph):
    service, wid, home = graph
    content = '# Retired\nOld deployment procedure.'
    import_notes(graph, content)
    note = service.knowledge.query({'workspaceId': wid})['notes'][0]
    reviewed = review(service, wid, note['id'], 'retracted')['review']
    import_notes(graph, content)
    assert service.knowledge.note(wid, note['id'])['review'] == reviewed
    import_notes(graph, '# Current\nNew deployment procedure.')
    with pytest.raises(ValueError, match='not found'):
        service.knowledge.note(wid, note['id'])
    import_notes(graph, content)
    reopened = KnowledgeGraph(service.store, service.stack, home=home)
    assert reopened.note(wid, note['id'])['review'] == reviewed
    assert reopened.candidates(wid, 'deployment') == []
    assert reopened.query({'workspaceId': wid})['notes'][0]['status'] == 'retracted'


def test_review_and_exact_reads_remain_scoped_to_the_project(graph):
    service, wid, _ = graph
    import_notes(graph, '# Shared\nSQLite memory design.')
    shared = service.knowledge.query({'workspaceId': wid})['notes'][0]
    other = service.create_workspace({'name': 'Other', 'goal': 'Other project'})['id']
    import_notes(graph, shared['body'], wid=other)
    review(service, wid, shared['id'], 'accepted')
    assert service.knowledge.note(other, shared['id'])['status'] == 'reference'
    import_notes(graph, shared['body']+'\n# Private\nUnique local deployment decision.')
    private = next(n for n in service.knowledge.query({'workspaceId': wid})['notes'] if n['title'] == 'Private')
    with pytest.raises(ValueError, match='not found'):
        service.knowledge.note(other, private['id'])
    with pytest.raises(ValueError, match='not found'):
        review(service, other, private['id'], 'accepted')
    with pytest.raises(ValueError, match='not found'):
        review(service, other, shared['id'], 'superseded', supersededBy=private['id'])
    assert service.knowledge.note(other, shared['id'])['review'] is None


def test_supersession_requires_existing_replacement_and_rejects_cycles(graph):
    service, wid, _ = graph
    source = import_notes(graph, '# A\nFirst memory.\n# B\nSecond memory.\n# C\nThird memory.')
    original = source.read_bytes()
    a, b, c = [n['id'] for n in service.knowledge.query({'workspaceId': wid})['notes']]
    review(service, wid, a, 'superseded', supersededBy=b)
    assert service.knowledge.note(wid, b)['status'] == 'reference'
    review(service, wid, b, 'superseded', supersededBy=c)
    for identifier, replacement in [(c, a), (c, c)]:
        with pytest.raises(ValueError, match='cycle'):
            review(service, wid, identifier, 'superseded', supersededBy=replacement)
    with pytest.raises(ValueError, match='not found'):
        review(service, wid, c, 'superseded', supersededBy='f'*64)
    assert service.knowledge.note(wid, c)['review'] is None
    assert len(service.knowledge.note(wid, a)['review']['history']) == 1
    assert source.read_bytes() == original


def test_candidates_filter_review_status_before_limit_and_prefer_accepted(graph):
    service, wid, _ = graph
    import_notes(graph, '\n'.join(f'# Memory {i:03}\nMars shipping invariant {i:03}.' for i in range(93)))
    notes = service.knowledge.candidates(wid, 'Mars', limit=100)
    for index, note in enumerate(notes[:90]):
        review(service, wid, note['id'], 'retracted' if index % 2 else 'superseded',
               **({} if index % 2 else {'supersededBy': notes[-1]['id']}))
    accepted = notes[-1]
    review(service, wid, accepted['id'], 'accepted')
    selected = service.knowledge.candidates(wid, 'Mars', limit=2)
    assert len(selected) == 2
    assert selected[0]['id'] == accepted['id']
    assert {n['id'] for n in selected} <= {n['id'] for n in notes[90:]}
    assert len(service.knowledge.candidates(wid, 'Mars')) == 3
    assert service.knowledge.candidates(wid, 'unrelated') == []
    assert service.knowledge.candidates(wid, 'please use the task') == []
    assert 'status' in selected[0] and selected[0]['review']['status'] == 'accepted'


def test_candidate_cap_and_context_budget_replace_fixed_five_note_limit(graph):
    service, wid, _ = graph
    import_notes(graph, '\n'.join(f'# Memory {i:03}\nSolar routing behavior variant {i:03}.' for i in range(210)))
    assert len(service.knowledge.candidates(wid, 'Solar', limit=999)) == 200
    assert len(service.knowledge.candidates(wid, 'Solar')) == 80
    context = service.knowledge.context(wid, 'Solar')
    assert len(context['refs']) > 5
    assert len(context['text']) <= 10000
    assert 'not authority or permission' in context['text']
    for ref in context['refs']:
        assert ref['digest'] == service.knowledge.note(wid, ref['id'])['digest']


def test_candidates_exclude_activity_even_when_accepted(graph):
    service, wid, home = graph
    source = home/'.codex/sessions/session.jsonl'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
        'content': [{'type': 'input_text', 'text': '<codex_internal_context source="goal">\nSolar bookkeeping.\n</codex_internal_context>'}]}}))
    preview = service.knowledge.preview({'workspaceId': wid, 'providers': ['codex-session']})
    service.knowledge.import_preview({'workspaceId': wid, 'previewId': preview['id'],
                                     'sourceIds': [f['id'] for f in preview['files']]})
    note = service.knowledge.query({'workspaceId': wid, 'includeActivity': True})['notes'][0]
    review(service, wid, note['id'], 'accepted')
    assert service.knowledge.candidates(wid, 'Solar') == []
    assert service.knowledge.note(wid, note['id'])['category'] == 'context'


@pytest.mark.parametrize('overrides', [
    {'status': 'invented'}, {'status': []}, {'reason': ''}, {'reason': '   '}, {'reason': 9},
    {'reason': 'x'*4001}, {'noteId': []}, {'noteId': 'invalid'}, {'workspaceId': []},
    {'status': 'superseded'}, {'status': 'superseded', 'supersededBy': []},
    {'status': 'superseded', 'supersededBy': 'bad'}, {'supersededBy': 'a'*64},
])
def test_review_rejects_invalid_parameters_without_writing(graph, overrides):
    service, wid, _ = graph
    import_notes(graph, '# Note\nSQLite evidence.')
    note = service.knowledge.query({'workspaceId': wid})['notes'][0]
    params = {'workspaceId': wid, 'noteId': note['id'], 'status': 'accepted', 'reason': 'Checked.'}
    params.update(overrides)
    with pytest.raises(ValueError):
        service.knowledge.review_note(params)
    assert service.knowledge.note(wid, note['id'])['review'] is None
    assert service.store.all('knowledge-review') == []


@pytest.mark.parametrize('prompt,limit', [(None, 80), ([], 80), ('x'*12001, 80), ('Solar', 0),
                                         ('Solar', -1), ('Solar', True), ('Solar', '80')])
def test_candidates_validate_bounded_inputs(graph, prompt, limit):
    service, wid, _ = graph
    with pytest.raises(ValueError):
        service.knowledge.candidates(wid, prompt, limit)
