import json
import threading
import time

import pytest

from test_jev_context import setup, accepted, Provider
from harness_manager.workspaces.context_packs import options
from harness_manager.workspaces.jev_provider import JevProvider
from harness_manager.workspaces.jev_settings import JevSettings, ConfiguredJevProvider
from harness_manager.workspaces.memory_sources import MemorySources
from harness_manager.workspaces.service import WorkspaceService


def search(service, wid, **values):
    return service.dispatch('search.context', dict(workspaceId=wid, query='SQLite storage', **values))


def test_fast_search_is_one_bounded_read_only_batch_and_repeat_skips_provider(setup):
    service, provider, wid = setup
    for index in range(12):
        accepted(service, wid, f'SQLite storage decision number {index}.')
    before = service.store.path.read_bytes()
    deadlines = []
    original = provider.evaluate
    def evaluate(*args, **kwargs):
        deadlines.append(kwargs['deadline'] - time.monotonic())
        return original(*args, **kwargs)
    provider.evaluate = evaluate
    first = search(service, wid, category='memory')
    assert len(first['matches']) == 8 and first['coverage']['candidateLimit'] == 8
    assert first['providerCalls'] == 1 and not first['cacheHit']
    assert first['status'] == 'partial' and first['coverage']['hasMore']
    assert len(provider.calls[0][1]) == 17 and 0 < deadlines[0] <= 5
    assert first['elapsedMs'] >= 0 and first['selectionProvider'] == 'jev'
    second = search(service, wid, category='memory')
    assert second['cacheHit'] and second['providerCalls'] == 0 and len(provider.calls) == 1
    assert second['matches'] == first['matches'] and second['coverage']['providerCalls'] == 0
    assert second['coverage']['questionCount'] == 0 and second['coverage']['cachedQuestionCount'] == 17
    assert service.store.path.read_bytes() == before
    assert all(match['body'].startswith('SQLite storage decision') for match in first['matches'])


def test_search_cache_invalidation_includes_review_retraction_sources_query_and_profile(setup):
    service, provider, wid = setup
    claim = accepted(service, wid)
    source = service.add_source(dict(workspaceId=wid, name='Approved source', text='SQLite approved source body.'))
    service.review_source(dict(id=source['id'], approved=True))
    first = search(service, wid)
    assert search(service, wid)['cacheHit']
    service.memory_ledger.review(wid, claim['id'], expected_revision=claim['revision'], status='accepted', rationale='Revalidated')
    assert not search(service, wid)['cacheHit']
    service.memory_ledger.review(wid, claim['id'], expected_revision=claim['revision'] + 1, status='retracted', rationale='Forgotten')
    retracted = search(service, wid)
    assert not retracted['cacheHit'] and all(row['id'] != 'claim:' + claim['id'] for row in retracted['matches'])
    service.store.update('source', source['id'], text='SQLite edited source body.')
    edited = search(service, wid)
    assert not edited['cacheHit'] and edited['matches'][0]['body'] == 'SQLite edited source body.'
    service.review_source(dict(id=source['id'], approved=False))
    assert not search(service, wid)['cacheHit']
    assert search(service, wid, topic='Storage')['cacheHit'] is False
    assert search(service, wid, profile='standard')['coverage']['candidateLimit'] == 16


def test_search_scopes_categories_and_rejects_unsupported_filters(setup):
    service, provider, wid = setup
    accepted(service, wid)
    other = service.store.create('workspace', {'name': 'Other'})['id']
    accepted(service, other, 'SQLite private foreign workspace fact.')
    chat = service.store.create('conversation', dict(workspaceId=wid, agent='codex', title='SQLite conversation', mode='read-only'))
    service.store.create('run', dict(workspaceId=wid, conversationId=chat['id'], task='SQLite storage?', output='SQLite project conversation answer.',
                                    status='completed', reviewed=True, provider='local'))
    memory = search(service, wid, category='memory')
    chats = search(service, wid, category='conversations')
    assert memory['matches'] and all(row['kind'] != 'conversation' for row in memory['matches'])
    assert chats['matches'] and all(row['kind'] == 'conversation' for row in chats['matches'])
    assert 'foreign' not in json.dumps(search(service, wid))
    for values in [dict(scope='global'), dict(agent='codex'), dict(role='subagent'), dict(model='luna')]:
        rejected = search(service, wid, **values)
        assert rejected['status'] == 'unavailable' and rejected['matches'] == []
        assert rejected['providerCalls'] == 0 and rejected['warning']
    with pytest.raises(ValueError):
        search(service, wid, unknown=True)


def test_fast_context_option_uses_same_cache_exact_pack_and_no_fallback(setup):
    service, provider, wid = setup
    accepted(service, wid)
    assert options({'mode': 'jev-fast'})['mode'] == 'jev-fast'
    args = dict(workspaceId=wid, prompt='SQLite storage', contextOptions={'mode': 'jev-fast'})
    first = service.dispatch('context.prepare', args)
    second = service.dispatch('context.prepare', args)
    assert first['mode'] == second['mode'] == 'jev-fast' and first['selectionProvider'] == 'jev'
    assert second['cacheHit'] and second['contextPlan']['providerCalls'] == 0
    assert first['refs'] == second['refs'] and first['text'] == second['text']
    provider.available = False
    failed = service.dispatch('context.prepare', args)
    assert not failed['refs'] and failed['status'] == 'unavailable' and not failed['cacheHit']


def test_cache_configuration_identity_and_provider_failure_do_not_reuse_results(setup):
    service, provider, wid = setup
    accepted(service, wid)
    provider.cache_identity = 'configured-model-1'
    search(service, wid)
    assert search(service, wid)['cacheHit']
    provider.cache_identity = 'configured-model-2'
    assert not search(service, wid)['cacheHit']
    provider.available = False
    disabled = search(service, wid)
    assert disabled['status'] == 'unavailable' and disabled['matches'] == [] and not disabled['cacheHit']
    provider.available = True
    provider.cache_identity = 'model-3'
    provider.evaluate = lambda *args, **kwargs: {'model': 'malformed', 'answers': {}}
    failed = search(service, wid)
    assert failed['status'] == 'unavailable' and failed['matches'] == [] and not failed['cacheHit']
    assert not search(service, wid)['cacheHit']


def test_configured_provider_credential_consent_model_changes_invalidate_cache(tmp_path, monkeypatch):
    settings = JevSettings(tmp_path/'data')
    fixture = Provider()
    transport_calls = []
    def transport(endpoint, token, payload, deadline, cancelled):
        transport_calls.append(token)
        payload = json.loads(payload)
        raw = fixture.evaluate(payload['state'], payload['questions'], deadline=deadline, cancelled=cancelled)
        return 200, {}, json.dumps(raw).encode()
    settings.configure(token='fixture-one', enabled=True, consent=True, model='jev-latest')
    configured = ConfiguredJevProvider(settings, transport=transport)
    service = WorkspaceService(tmp_path/'data', jev_provider=configured)
    service.knowledge.home = tmp_path/'home'
    monkeypatch.setattr(service.conversation_refs, '_live', lambda **_: [])
    wid = service.store.create('workspace', {'name': 'Project'})['id']
    try:
        accepted(service, wid)
        search(service, wid)
        assert search(service, wid)['cacheHit'] and len(transport_calls) == 1
        settings.configure(token='fixture-two', enabled=True, consent=True, model='jev-latest')
        assert not search(service, wid)['cacheHit'] and len(transport_calls) == 2
        settings.configure(token='fixture-two', enabled=True, consent=True, model='jev-other')
        assert not search(service, wid)['cacheHit'] and len(transport_calls) == 3
        settings.configure(token='fixture-two', enabled=False, consent=False, model='jev-other')
        disabled = search(service, wid)
        assert disabled['matches'] == [] and disabled['status'] == 'unavailable' and len(transport_calls) == 3
    finally:
        service.close()


def test_cached_delivery_rechecks_source_version_and_cancellation(setup, monkeypatch):
    service, provider, wid = setup
    claim = accepted(service, wid)
    search(service, wid)
    original = MemorySources.note
    changed = False
    def mutate(sources, scope, identifier):
        nonlocal changed
        if not changed:
            changed = True
            service.memory_ledger.review(wid, claim['id'], expected_revision=claim['revision'], status='retracted', rationale='Concurrent forget')
        return original(sources, scope, identifier)
    monkeypatch.setattr(MemorySources, 'note', mutate)
    result = search(service, wid)
    assert result['matches'] == [] and not result['cacheHit']
    event = threading.Event(); event.set()
    with pytest.raises(InterruptedError):
        service.jev_context.readonly(MemorySources(service.knowledge), dict(workspaceId=wid, task='SQLite storage'), cancelled=event, fast=True)


def test_durable_and_active_plans_cannot_enter_readonly_cache(setup):
    service, _, wid = setup
    for values in [dict(intent='add', incoming=[dict(id='new', title='New', body='New fact')]),
                   dict(activeContext=[dict(id='active', title='Active', body='Current reference')])]:
        with pytest.raises(ValueError, match='read-only'):
            service.jev_context.readonly(MemorySources(service.knowledge), dict(workspaceId=wid, task='SQLite storage', **values), fast=True)


def test_provider_change_during_selection_suppresses_output_and_does_not_cache(setup):
    service, provider, wid = setup
    accepted(service, wid)
    provider.cache_identity = 'before'
    provider.mutate = lambda: setattr(provider, 'cache_identity', 'after')
    result = search(service, wid)
    assert result['status'] == 'unavailable' and result['matches'] == []
    assert result['providerCalls'] == 1 and not result['cacheHit']
    assert service.jev_context.read_cache == {}


def test_discovery_deadline_returns_unavailable_without_provider_or_local_results(setup, monkeypatch):
    service, provider, wid = setup
    accepted(service, wid)
    clock = [time.monotonic()]
    original = MemorySources.context_candidates
    def delayed(sources, *args, **kwargs):
        rows = original(sources, *args, **kwargs)
        clock[0] += 6
        return rows
    monkeypatch.setattr('harness_manager.workspaces.jev_context.time.monotonic', lambda: clock[0])
    monkeypatch.setattr(MemorySources, 'context_candidates', delayed)
    result = search(service, wid)
    assert result['status'] == 'unavailable' and result['matches'] == []
    assert result['providerCalls'] == 0 and result['elapsedMs'] == 6000
    assert provider.calls == [] and not result['cacheHit']


def test_cache_expiry_runs_a_new_decision(setup):
    service, provider, wid = setup
    accepted(service, wid)
    search(service, wid)
    for saved in service.jev_context.read_cache.values():
        saved['expires'] = time.monotonic() - 1
    result = search(service, wid)
    assert not result['cacheHit'] and result['providerCalls'] == 1 and len(provider.calls) == 2


def test_exact_topic_facet_excludes_unlabelled_rows_and_search_never_refreshes_labels(setup):
    service, provider, wid = setup
    home = service.knowledge.home
    folder = home/'.codex/memories'; folder.mkdir(parents=True)
    (folder/'MEMORY.md').write_text('# Storage decision\nUse SQLite for project storage.')
    preview = service.knowledge.preview(dict(workspaceId=wid, providers=['codex']))
    service.knowledge.import_preview(dict(workspaceId=wid, previewId=preview['id'], sourceIds=[r['id'] for r in preview['files']]))
    note = service.knowledge.candidates(wid, 'SQLite', limit=1)[0]
    accepted(service, wid, 'SQLite untagged ledger fact.')
    with service.store.connect() as db:
        db.execute('DELETE FROM knowledge_topics WHERE workspace=?', (wid,))
        db.execute('INSERT INTO knowledge_topics VALUES(?,?,?)', (wid, note['id'], 'Storage'))
        db.execute('DELETE FROM knowledge_labels WHERE workspace=?', (wid,))
    before = service.store.path.read_bytes()
    # Missing labels remain missing: read-only search must never maintain the index.
    absent = search(service, wid, topic='Storage')
    assert absent['matches'] == []
    assert service.store.path.read_bytes() == before
    # Host index maintenance restores labels; refresh also derives topics from text.
    service.knowledge.candidates(wid, 'SQLite', limit=1)
    with service.store.connect() as db:
        db.execute('DELETE FROM knowledge_topics WHERE workspace=?', (wid,))
        db.execute('INSERT INTO knowledge_topics VALUES(?,?,?)', (wid, note['id'], 'Storage'))
    before = service.store.path.read_bytes()
    exact = search(service, wid, topic='Storage')
    assert [row['id'] for row in exact['matches']] == [note['id']]
    assert not any(row['id'].startswith('claim:') for row in exact['matches'])
    assert service.store.path.read_bytes() == before
    assert search(service, wid, topic='Missing')['matches'] == []
