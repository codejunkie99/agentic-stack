"""Imported library pagination keeps original evidence and project boundaries."""
import pytest

from harness_manager.workspaces.knowledge import digest, lesson_source
from harness_manager.workspaces.service import WorkspaceService


@pytest.fixture
def library(tmp_path):
    service = WorkspaceService(tmp_path/'data')
    wid = service.create_workspace({'name': 'Library', 'goal': 'Browse imported evidence'})['id']
    folder = tmp_path/'references'
    folder.mkdir()
    yield service, wid, folder
    service.close()


def import_folder(service, wid, folder):
    preview = service.dispatch('knowledge.preview', {'workspaceId': wid, 'providers': ['folder'], 'folder': str(folder)})
    service.dispatch('knowledge.import', {'workspaceId': wid, 'previewId': preview['id'],
                                        'sourceIds': [source['id'] for source in preview['files']]})


def test_library_search_and_pages_reach_every_source_and_preserve_project_scope(library):
    service, wid, folder = library
    for index in range(85):
        (folder/f'{index:03}.md').write_text(f'# Reference {index:03}\nEvidence item {index:03}.')
    (folder/'084.md').write_text('# Reference 084\nStraße has a literal 100%_marker.')
    (folder/'LESSONS.md').write_text('# Durable lesson\nKeep timestamps in UTC.')
    import_folder(service, wid, folder)
    request = {'workspaceId': wid}
    first = service.dispatch('knowledge.library', request)
    second = service.dispatch('knowledge.library', {**request, 'offset': first['nextOffset']})
    assert first['total'] == second['total'] == 86
    assert len(first['sources']) == 80 and first['hasMore'] and first['nextOffset'] == 80
    assert len(second['sources']) == 6 and not second['hasMore'] and second['nextOffset'] is None
    assert len({s['id'] for s in first['sources']+second['sources']}) == 86
    source = service.dispatch('knowledge.library', {**request, 'query': 'STRASSE'})['sources'][0]
    assert source['title'] == 'Reference 084' and source['noteCount'] == 1
    assert source['provider'] == 'folder' and source['path'].endswith('/084.md')
    assert source['digest'] and source['importedAt']
    assert service.dispatch('knowledge.library', {**request, 'query': '100%_marker'})['total'] == 1
    assert service.dispatch('knowledge.library', {**request, 'query': '084.md'})['total'] == 1
    assert service.dispatch('knowledge.library', {**request, 'provider': 'codex'})['total'] == 0
    lessons = service.dispatch('knowledge.library', {**request, 'kind': 'lessons'})
    assert lessons['total'] == 1 and lessons['sources'][0]['title'] == 'Durable lesson'
    assert service.dispatch('knowledge.library', {**request, 'offset': 100001})['sources'] == []
    other = service.create_workspace({'name': 'Other', 'goal': 'Separate project'})['id']
    assert service.dispatch('knowledge.library', {'workspaceId': other, 'query': 'UTC'})['total'] == 0
    with pytest.raises(ValueError, match='not found in this project'):
        service.dispatch('knowledge.source', {'workspaceId': other, 'sourceId': source['id']})
    assert service.dispatch('knowledge.library', {**request, 'query': '" OR * --'})['total'] == 0


def test_source_detail_pages_stored_bodies_origins_and_all_review_states_without_writes(library):
    service, wid, folder = library
    content = '\n'.join(f'# Lesson {index:02}\nOriginal evidence {index:02}. '+('Full detail. '*70) for index in range(43))
    (folder/'LESSONS.md').write_text(content)
    (folder/'copy.md').write_text(content)
    import_folder(service, wid, folder)
    source = service.dispatch('knowledge.library', {'workspaceId': wid, 'kind': 'lessons'})['sources'][0]
    request = {'workspaceId': wid, 'sourceId': source['id']}
    first = service.dispatch('knowledge.source', request)
    assert first['total'] == 43 and len(first['notes']) == 40 and first['nextOffset'] == 40
    notes = first['notes']+service.dispatch('knowledge.source', {**request, 'offset': 40})['notes']
    for index, status in enumerate(('accepted', 'retracted', 'superseded')):
        service.dispatch('knowledge.review', {'workspaceId': wid, 'noteId': notes[index]['id'], 'status': status,
                         'reason': 'Reviewed evidence.', **({'supersededBy': notes[-1]['id']} if status == 'superseded' else {})})
    # The original files can disappear; reads use the imported snapshot exclusively.
    for path in folder.iterdir():
        path.unlink()
    with service.store.connect() as db:
        db.execute('DELETE FROM knowledge_labels WHERE workspace=? AND note=?', (wid, notes[0]['id']))
    with service.store.connect() as db:
        before = '\n'.join(db.iterdump())
    first = service.dispatch('knowledge.source', request)
    second = service.dispatch('knowledge.source', {**request, 'offset': first['nextOffset']})
    assert [n['status'] for n in first['notes'][:4]] == ['accepted', 'retracted', 'superseded', 'reference']
    assert first['notes'][0]['review']['history'][0]['status'] == 'accepted'
    assert not second['hasMore'] and second['nextOffset'] is None
    assert [n['body'] for n in first['notes']+second['notes']] == [n['body'] for n in notes]
    for note in first['notes']+second['notes']:
        assert note['digest'] == digest(note['body']) and len(note['body']) > 800
        assert len(note['origins']) == 2
        assert all(origin['provider'] == 'folder' and origin['line'] > 0 and origin['importedAt'] for origin in note['origins'])
        assert source['id'] in {origin['sourceId'] for origin in note['origins']}
    assert service.dispatch('knowledge.library', {'workspaceId': wid})['total'] == 2
    with service.store.connect() as db:
        assert '\n'.join(db.iterdump()) == before


def test_lesson_detection_uses_explicit_stores_not_learning_tool_names():
    for path in ('/repo/.agent/memory/semantic/LESSONS.md', '/repo/.agent/memory/semantic/lessons.jsonl',
                 '/repo/.agent/memory/episodic/AGENT_LEARNINGS.jsonl', '/home/.codex/memories/lessons/routing.md',
                 '/archive/lessons-learned.md'):
        assert lesson_source(path), path
    for path in ('/repo/skills/caveman-learn/SKILL.md', '/repo/skills/gstack/retro/SKILL.md',
                 '/repo/skills/lessons/LESSONS.md', '/repo/commands/learn.md', '/repo/docs/learning-api.md',
                 '/home/.codex/memories/MEMORY.md', '/repo/lessons/routes.py',
                 '/home/.codex/memories/skills/tool/.agent/memory/semantic/LESSONS.md'):
        assert not lesson_source(path), path
    for ancestor in ('tools', 'agents', 'skills', 'commands'):
        for store in ('.agent/memory', '.codex/memories', '.claude/memory'):
            assert lesson_source(f'/workspace/{ancestor}/project/{store}/semantic/lessons.jsonl')
            assert lesson_source(f'/workspace/{ancestor}/project/{store}/episodic/AGENT_LEARNINGS.jsonl')
            assert not lesson_source(f'/workspace/{ancestor}/project/{store}/skills/learn/LESSONS.md')


def test_library_rejects_invalid_pagination_and_search(library):
    service, wid, _ = library
    for extra in ({'offset': -1}, {'offset': True}, {'limit': 0}, {'limit': 201}, {'limit': '80'},
                  {'kind': 'skills'}, {'query': []}, {'provider': 'x'*301}):
        with pytest.raises(ValueError):
            service.dispatch('knowledge.library', {'workspaceId': wid, **extra})
    with pytest.raises(ValueError, match='valid imported source'):
        service.dispatch('knowledge.source', {'workspaceId': wid, 'sourceId': '../escape'})
