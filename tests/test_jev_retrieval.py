import copy
import pytest

from harness_manager.workspaces.jev_retrieval import JevRetrieval
from harness_manager.workspaces.context_packs import ContextPacks


class Sources:
    def __init__(self):
        self.rows = [dict(id=str(i), title=f'Source {i}', body=f'Unrelated evidence {i}', status='accepted',
                         origins=[{'path': 'fixture', 'line': 1}]) for i in range(70)]
        self.rows[65]['body'] = 'irrelevant preamble ' * 150 + '\n\nThe target decision is here.'

    def candidate_page(self, wid, query, *, offset=0, limit=20):
        assert wid == 'project'
        rows = self.rows if not query else self.rows[:3]
        return {'rows': copy.deepcopy(rows[offset:offset+limit]), 'hasMore': len(rows) > offset+limit,
                'nextOffset': min(len(rows), offset+limit)}

    def note(self, wid, identifier):
        assert wid == 'project'
        return copy.deepcopy(next(r for r in self.rows if r['id'] == identifier))

    def candidates(self, wid, query, limit=80):
        return copy.deepcopy([r for r in self.rows[:3] if r['status']=='accepted'])


class Provider:
    available = True
    def __init__(self, on_select=None):
        self.on_select = on_select
        self.selected = False
        self.broad = False

    def evaluate(self, state, questions, **kwargs):
        if 'action' in questions:
            criteria = questions['action']['criteria']
            if self.selected:
                action = 'finish'
            elif 'inspect:65' in criteria:
                action = 'inspect:65'
            elif not self.broad:
                action = 'reseed'; self.broad = True
            else:
                action = 'next_page'
            return {'model': 'test-fixture', 'answers': {'action': {'choice': action, 'confidence': .9}}}
        if self.on_select:
            self.on_select()
        self.selected = True
        return {'model': 'test-fixture', 'answers': {s['id']: {'choice': 'include' if 'target decision' in s['text'] else 'omit',
            'confidence': .9} for s in state['spans']}}


def test_reseed_reaches_beyond_shortlist_and_selects_later_span():
    source = Sources()
    result = JevRetrieval(Provider()).retrieve(source, 'project', 'no lexical match')
    assert result['status'] == 'selected'
    assert result['coverage']['broadRouteVisited']
    assert result['rows'][0]['body'] == 'The target decision is here.'
    assert result['rows'][0]['start'] > 900
    assert result['rows'][0]['sourceId'] == '65'
    assert result['rows'][0]['origins'][0]['line'] == 3
    assert result['coverage']['exhaustive'] is False
    assert len(result['leads']) == 70


def test_changed_or_retracted_source_cannot_be_delivered():
    for change in [{'status': 'retracted'}, {'body': 'Different evidence'}]:
        source = Sources()
        provider = Provider(lambda: source.rows[65].update(change))
        result = JevRetrieval(provider).retrieve(source, 'project', 'task')
        assert not result['rows']
        assert any(t['action'] in {'source_changed','source_unavailable'} for t in result['trace'])


def test_budget_is_partial_not_false_negative():
    result = JevRetrieval(Provider()).retrieve(Sources(), 'project', 'task', max_steps=1)
    assert result['status'] == 'partial' and 'budget' in result['warning'].lower()
    assert not result['rows']


def test_context_pack_uses_single_batch_exact_prefix_and_source_identity():
    source = Sources()
    pack = ContextPacks(FirstSourceProvider()).prepare(source, 'project', 'task',
        {'mode': 'jev', 'pinnedIds': ['65']}, allow_agent=False)
    assert pack['selectionProvider'] == 'jev' and pack['refs'][0]['id'] == '65'
    assert source.note('project', '65')['body'].startswith(pack['refs'][0]['excerpt'])
    assert pack['retrievalTrace'] == [{'action': 'batch', 'providerCalls': 1}]
    assert pack['coverage']['exhaustive'] is False


def test_unconfigured_provider_reports_unavailable_without_substitute():
    pack = ContextPacks().prepare(Sources(), 'project', 'task', {'mode': 'jev'})
    assert pack['selectionProvider'] == 'jev' and pack['status'] == 'unavailable'
    assert pack['refs'] == [] and pack['text'] == ''


class FirstSourceProvider:
    available = True

    def evaluate(self, state, questions, **kwargs):
        answers = {}
        for key, question in questions.items():
            kind = question['type']
            if kind == 'noul':
                answer = dict(type=kind, noul=.95)
            elif kind == 'score':
                answer = dict(type=kind, score=3, confidence=.95,
                    probabilities={str(i): float(i == 3) for i in range(4)},
                    legend={str(i): text for i, text in enumerate(question['criteria'])})
            else:
                choice = 'include' if key.startswith('context:') else 'none'
                answer = dict(type=kind, choice=choice, confidence=.95,
                    probabilities={label: float(label == choice) for label in question['criteria']})
            answers[key] = answer
        return dict(model='fixture', answers=answers, usage={'input_tokens': 1, 'output_tokens': 1})


def test_real_database_pagination_and_desktop_mcp_parity(tmp_path, monkeypatch):
    from harness_manager.workspaces.service import WorkspaceService
    from harness_manager.workspaces.knowledge import KnowledgeGraph
    from harness_manager.context_mcp import MCPServer
    service = WorkspaceService(tmp_path/'data', jev_provider=FirstSourceProvider())
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    home = tmp_path/'home'; home.mkdir()
    service.knowledge = KnowledgeGraph(service.store, service.stack, home=home)
    source = home/'.codex/memories/MEMORY.md'; source.parent.mkdir(parents=True)
    source.write_text('# Storage decision\nUse SQLite for local storage.')
    preview = service.knowledge.preview(dict(workspaceId=wid, providers=['codex']))
    service.knowledge.import_preview(dict(workspaceId=wid, previewId=preview['id'], sourceIds=[r['id'] for r in preview['files']]))
    monkeypatch.setenv('AGENTIC_WORKSPACES_DATA', str(service.store.root))
    monkeypatch.setattr(service.conversation_refs, '_live', lambda: [])
    try:
        first = service.knowledge.candidate_page(wid, '', limit=1)
        assert first['rows'] and first['nextOffset'] == 1
        assert not service.knowledge.candidate_page(wid, '', offset=100, limit=1)['rows']
        arguments = dict(workspaceId=wid, prompt='SQLite storage', contextOptions={'mode': 'jev'})
        desktop = service.dispatch('context.prepare', arguments)
        before = service.store.path.read_bytes()
        shared = MCPServer(home, jev_provider=FirstSourceProvider()).prepare_context(arguments)
        assert desktop['refs'] == shared['refs'] and desktop['selectionProvider'] == shared['selectionProvider'] == 'jev'
        assert service.store.path.read_bytes() == before
    finally:
        service.close()


def test_accepted_ledger_claims_join_same_search_without_cross_project_leak(tmp_path):
    from harness_manager.workspaces.service import WorkspaceService
    from harness_manager.workspaces.memory_sources import MemorySources
    service = WorkspaceService(tmp_path/'data', jev_provider=FirstSourceProvider())
    project = tmp_path/'project'; project.mkdir()
    other_project = tmp_path/'other'; other_project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    other = service.open_project({'path': str(other_project)})['id']
    try:
        for scope, body in [(wid, 'Use SQLite in this project.'), (other, 'Private unrelated preference.')]:
            evidence = service.memory_ledger.observe(scope, source_key='fixture', body=body)
            claim = service.memory_ledger.propose(scope, body=body, kind='decision', evidence_ids=[evidence['id']])
            service.memory_ledger.review(scope, claim['id'], expected_revision=1, status='accepted', rationale='Confirmed fixture')
        sources = MemorySources(service.knowledge)
        page = sources.candidate_page(wid, '')
        assert len(page['rows']) == 1 and page['rows'][0]['id'].startswith('claim:')
        assert sources.note(wid, page['rows'][0]['id'])['review']['revision'] == 2
        with pytest.raises(ValueError):
            sources.note(other, page['rows'][0]['id'])
    finally:
        service.close()


def test_explicit_local_keeps_accepted_claims_and_invalidates_after_retraction(tmp_path, monkeypatch):
    from harness_manager.workspaces.service import WorkspaceService
    service = WorkspaceService(tmp_path/'data')
    monkeypatch.setattr(service.conversation_refs, '_live', lambda: [])
    project = tmp_path/'project'; project.mkdir()
    wid = service.open_project({'path': str(project)})['id']
    try:
        evidence = service.memory_ledger.observe(wid, source_key='fixture', body='Use SQLite for storage.')
        claim = service.memory_ledger.propose(wid, body=evidence['body'], kind='decision', evidence_ids=[evidence['id']])
        service.memory_ledger.review(wid, claim['id'], expected_revision=1, status='accepted', rationale='Reviewed')
        args = dict(workspaceId=wid, prompt='SQLite storage', contextOptions={'mode': 'local', 'pinnedIds': ['claim:' + claim['id']]})
        pack = service.dispatch('context.prepare', args)
        assert pack['mode'] == 'local'
        assert any(ref['id'] == 'claim:' + claim['id'] for ref in pack['refs'])
        service.memory_ledger.review(wid, claim['id'], expected_revision=2, status='retracted', rationale='No longer applies')
        changed = service.dispatch('context.prepare', args)
        assert not changed['refs']
    finally:
        service.close()
