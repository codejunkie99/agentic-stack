import copy
import hashlib
import json
from pathlib import Path
import threading

import pytest

from harness_manager.workspaces.jev_provider import JevError
from harness_manager.workspaces.jev_runtime import JevRuntime, _schema, _validate


class Provider:
    available = True
    model = 'fixture-jev'

    def __init__(self, *, choice=None, confidence=.95, support=.95, mutate=None, invalid=False, error=None):
        self.calls = []
        self.choice, self.confidence, self.support = choice, confidence, support
        self.mutate, self.invalid, self.error = mutate, invalid, error

    def evaluate(self, state, questions, *, deadline, cancelled):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        assert len(questions) <= 64
        assert len(json.dumps(dict(state=state, questions=questions, model=self.model)).encode()) <= 240000
        if self.error:
            raise self.error
        answers = {}
        for key, question in questions.items():
            kind = question['type']
            if kind == 'score':
                size = len(question['criteria'])
                answers[key] = dict(type=kind, score=size - 1, confidence=self.confidence,
                    probabilities={str(i): float(i == size - 1) for i in range(size)},
                    legend={str(i): text for i, text in enumerate(question['criteria'])})
            elif kind == 'noul':
                answers[key] = dict(type=kind, noul=self.support)
            else:
                criteria = question['criteria']
                choice = self.choice(state, key, question) if callable(self.choice) else self.choice
                if choice is None:
                    choice = 'include' if 'include' in criteria else 'supports' if 'supports' in criteria else 'candidate:0'
                answers[key] = dict(type=kind, choice=choice, confidence=self.confidence,
                    probabilities={label: float(label == choice) for label in criteria})
        if self.mutate:
            self.mutate()
        if self.invalid:
            answers[next(iter(answers))]['probabilities'] = {'invented': 1.0}
        return dict(model=self.model, answers=answers, usage=dict(input_tokens=100, output_tokens=20))


def dispatch(method, **params):
    provider = Provider()
    return JevRuntime(provider).dispatch(method, dict(task='Find useful behavior', **params)), provider


def test_trace_exact_unicode_offsets_source_order_digest_and_single_batch():
    body = '  α source exact spacing.\n\nSecond trace\nwith a newline.\n\nUnneeded tail.'
    provider = Provider(choice=lambda state, key, _: 'none' if state['items'][int(key.split(':')[1])]['start'] > 50 else 'include')
    result = JevRuntime(provider).dispatch('memory.trace.compact', dict(task='Preserve useful evidence', body=body))
    assert len(provider.calls) == 1
    assert result['originalPreserved']
    assert result['sourceDigest'] == hashlib.sha256(body.encode()).hexdigest()
    assert result['compactedText'] == body[result['spans'][0]['start']:result['spans'][-1]['end']]
    assert all(not separator['synthetic'] for separator in result['separators'])
    assert all(s['text'] == body[s['start']:s['end']] and s['digest'] == hashlib.sha256(s['text'].encode()).hexdigest() for s in result['spans'])
    assert [s['start'] for s in result['spans']] == sorted(s['start'] for s in result['spans'])
    assert all(f'index {index}' in q['instructions'] for index in range(len(provider.calls[0][0]['items'])) for q in [provider.calls[0][1][f'select:{index}']])


def test_trace_pagination_and_budget_do_not_claim_unread_source_lost():
    body = '\n\n'.join(f'Observation {i} is useful.' for i in range(30))
    runtime = JevRuntime(Provider())
    first = runtime.dispatch('memory.trace.compact', dict(task='Review trace', body=body, tokenBudget=128))
    assert first['status'] == 'partial' and first['usedTokens'] <= 128
    assert first['coverage']['evaluatedCount'] == 24 and first['coverage']['nextCursor'] == 24
    second = runtime.dispatch('memory.trace.compact', dict(task='Review trace', body=body, cursor=24))
    assert second['coverage']['evaluatedCount'] == 6
    assert second['coverage']['unprocessedBeforeCursor'] == 24 and second['coverage']['hasMore'] is False
    assert all(s['start'] >= body.index('Observation 24') for s in second['spans'])


@pytest.mark.parametrize('method,params', [
    ('memory.trace.compact', dict(body='Trace source')),
    ('memory.skills.select', dict(skills=[dict(id='unit', title='Unit', body='Entire source instruction.')])),
    ('memory.tools.plan', dict(candidates=[dict(id='call', function='lookup', arguments={'value': 1})])),
    ('memory.citations.verify', dict(claim='Claim', evidence=[dict(id='e', body='Evidence', source='Source')])),
    ('memory.code.search', dict(snippets=[dict(id='code', body='return value + 1', source='main.py:1')]))
])
def test_provider_none_unavailable_invalid_and_cancel_never_substitute(method, params):
    catalog = {'lookup': {'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value'], 'additionalProperties': False}}
    for provider, expected in [(Provider(choice='none'), 'abstained'), (Provider(confidence=.1), 'abstained'),
                               (Provider(invalid=True), 'unavailable'), (Provider(error=JevError('deadline')), 'unavailable')]:
        result = JevRuntime(provider).dispatch(method, dict(task='Choose source', **params), tool_catalog=catalog)
        assert result['status'] == expected and result['selectedIds'] == []
    provider = Provider(); provider.available = False
    result = JevRuntime(provider).dispatch(method, dict(task='Choose source', **params), tool_catalog=catalog)
    assert result['status'] == 'unavailable' and provider.calls == []
    event = threading.Event(); event.set(); provider = Provider()
    result = JevRuntime(provider).dispatch(method, dict(task='Choose source', **params), tool_catalog=catalog, cancelled=event)
    assert result['status'] == 'cancelled' and provider.calls == []


@pytest.mark.parametrize('field', ['task', 'id', 'title', 'body', 'requires'])
def test_final_skill_payload_scans_every_metadata_field_before_provider(field):
    secret = 'sk-' + 'a' * 20
    skill = dict(id='unit', title='Instructions', body='Follow these exact instructions.', requires=[])
    params = dict(task='Select an instruction', skills=[skill])
    if field == 'task':
        params[field] = secret
    else:
        skill[field] = [secret] if field == 'requires' else secret
    provider = Provider()
    with pytest.raises(ValueError, match='credentials'):
        JevRuntime(provider).dispatch('memory.skills.select', params)
    assert provider.calls == []


def test_escaped_secret_in_typed_arguments_is_caught_before_provider():
    provider = Provider()
    catalog = {'lookup': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text'], 'additionalProperties': False}}
    with pytest.raises(ValueError, match='credentials'):
        JevRuntime(provider).dispatch('memory.tools.plan', dict(task='Look up value', candidates=[dict(id='c', function='lookup', arguments={'text': 'OPENAI_API_KEY\n=hidden'})]), tool_catalog=catalog)
    assert provider.calls == []


def test_skill_dependency_closure_is_complete_exact_and_budget_atomic():
    skills = [dict(id='root', title='Root', body='Root unit\nsecond instruction.', requires=['dep']),
              dict(id='dep', title='Dependency', body='Dependency unit. Preserve every word.', requires=[])]
    provider = Provider(choice=lambda state, key, _: 'include' if key == 'select:0' else 'none')
    result = JevRuntime(provider).dispatch('memory.skills.select', dict(task='Use root instruction', skills=skills))
    assert result['selectedIds'] == ['dep', 'root']
    assert [s['body'] for s in result['skills']] == [skills[1]['body'], skills[0]['body']]
    assert result['coverage']['includedDependencies'] == 1
    huge = copy.deepcopy(skills); huge[1]['body'] = 'dependency' * 100
    result = JevRuntime(Provider()).dispatch('memory.skills.select', dict(task='Use root instruction', skills=huge, tokenBudget=128))
    assert result['skills'] == [] and result['status'] == 'partial'


@pytest.mark.parametrize('requires', [['missing'], ['root']])
def test_missing_or_cyclic_skill_dependency_withholds_unit(requires):
    result, _ = dispatch('memory.skills.select', skills=[dict(id='root', title='Unit', body='Exact complete unit.', requires=requires)])
    assert result['status'] == 'partial' and not result['skills'] and result['dependencyErrors']


SCHEMA = {'type': 'object', 'properties': {
    'count': {'type': 'integer', 'minimum': 1, 'maximum': 5},
    'enabled': {'type': 'boolean'},
    'labels': {'type': 'array', 'items': {'type': 'string', 'enum': ['a', 'b']}, 'maxItems': 2},
    'nested': {'type': 'object', 'properties': {'name': {'type': 'string', 'minLength': 1, 'maxLength': 10}}, 'required': ['name'], 'additionalProperties': False}},
    'required': ['count'], 'additionalProperties': False}


@pytest.mark.parametrize('arguments', [{'count': True}, {'count': 6}, {}, {'count': 1, 'extra': True},
                                       {'count': 1, 'enabled': 1}, {'count': 1, 'labels': ['c']},
                                       {'count': 1, 'nested': {'name': ''}}, {'count': 1, 'labels': ['a', 'a', 'a']}])
def test_typed_tool_arguments_fail_closed_without_any_network(arguments):
    provider = Provider()
    result = JevRuntime(provider).dispatch('memory.tools.plan', dict(task='Call lookup', candidates=[dict(id='c', function='lookup', arguments=arguments)]), tool_catalog={'lookup': SCHEMA})
    assert result['selectedCall'] is None and result['invalidCandidates'] and provider.calls == []


def test_tool_selection_returns_frozen_exact_allowlisted_args_never_executes():
    params = dict(task='Look up three values', candidates=[dict(id='bad', function='not_allowlisted', arguments={}),
        dict(id='good', function='lookup', arguments={'count': 3, 'enabled': True, 'labels': ['a']})])
    before = copy.deepcopy(params)
    provider = Provider()
    result = JevRuntime(provider).dispatch('memory.tools.plan', params, tool_catalog=[dict(name='lookup', inputSchema=SCHEMA)])
    assert result['selectedCall']['function'] == 'lookup' and result['selectedCall']['arguments'] == before['candidates'][1]['arguments']
    assert not result['executable'] and result['requiresHostAuthorization'] and params == before
    assert result['coverage']['invalidCount'] == 1 and len(provider.calls) == 1


@pytest.mark.parametrize('schema', [{'type': ['string', 'null']}, {'type': 'object', '$ref': 'file:///secret'},
                                   {'type': 'object', 'properties': {'x': {'type': 'string', 'pattern': '.*'}}}])
def test_unsupported_schema_constraints_never_get_ignored(schema):
    provider = Provider()
    result = JevRuntime(provider).dispatch('memory.tools.plan', dict(task='Call a function', candidates=[dict(id='c', function='lookup', arguments={})]), tool_catalog={'lookup': schema})
    assert result['selectedCall'] is None and result['invalidCandidates'] and provider.calls == []


def test_current_host_tool_catalog_revalidated_after_selection():
    catalog = {'lookup': copy.deepcopy(SCHEMA)}
    provider = Provider(mutate=lambda: catalog.clear())
    result = JevRuntime(provider).dispatch('memory.tools.plan', dict(task='Call a function', candidates=[dict(id='c', function='lookup', arguments={'count': 1})]), tool_catalog=catalog)
    assert result['selectedCall'] is None and result['status'] == 'partial'


@pytest.mark.parametrize('choice,support,confidence,expected', [('supports', .95, .95, 'supports'),
    ('contradicts', .05, .95, 'contradicts'), ('supports', .2, .95, 'insufficient'),
    ('contradicts', .9, .95, 'insufficient'), ('supports', .95, .2, 'insufficient'), ('none', .2, .95, 'none')])
def test_citation_support_is_source_pair_assessment_with_exact_quote(choice, support, confidence, expected):
    text = 'Exact citation text.\nWhitespace stays.'
    result = JevRuntime(Provider(choice=choice, support=support, confidence=confidence)).dispatch('memory.citations.verify', dict(claim='The claim is source supported.', evidence=[dict(id='e', body=text, source='Synthetic reference')]))
    assessment = result['assessments'][0]
    assert assessment['relation'] == expected and assessment['quote'] == text
    assert assessment['quoteDigest'] == hashlib.sha256(text.encode()).hexdigest()
    assert assessment['start'] == 0 and assessment['end'] == len(text) and not result['truthVerified']


def test_semantic_code_search_does_not_require_keyword_overlap():
    result, provider = dispatch('memory.code.search', snippets=[dict(id='increment', body='def next_value(x):\n    return x + 1', source='math.py:1')])
    assert result['matches'][0]['body'] == 'def next_value(x):\n    return x + 1'
    assert 'Judge code behavior semantically' in provider.calls[0][0]['policy']
    assert not result['jevgrep']['used'] and result['coverage']['exhaustive'] is False


def test_attached_project_code_walk_is_exact_paginated_and_excludes_private_symlink_files(tmp_path):
    project = tmp_path / 'project'; project.mkdir()
    body = '\n\n'.join(f'def step_{i}(x):\n    return x + {i}' for i in range(30))
    (project / 'math.py').write_text(body)
    for name in ['auth.py', 'config.swift', 'chat.ts', 'logs.js']:
        (project / name).write_text('PRIVATE FILE MUST NOT BE READ')
    hidden = project / '.hidden'; hidden.mkdir(); (hidden / 'hidden.py').write_text('PRIVATE HIDDEN')
    dependencies = project / 'node_modules'; dependencies.mkdir(); (dependencies / 'dep.js').write_text('PRIVATE DEPENDENCY')
    outside = tmp_path / 'outside.py'; outside.write_text('OUTSIDE FILE MUST NOT BE READ')
    (project / 'link.py').symlink_to(outside)
    provider = Provider(); runtime = JevRuntime(provider)
    first = runtime.dispatch('memory.code.search', dict(task='Compute a following value', tokenBudget=12000), project_root=project)
    assert first['status'] == 'partial' and len(first['matches']) == 24
    assert all(row['path'] == 'math.py' and row['body'] == body[row['start']:row['end']] for row in first['matches'])
    assert all('PRIVATE' not in row['body'] and 'OUTSIDE' not in row['body'] for row in provider.calls[0][0]['items'])
    second = runtime.dispatch('memory.code.search', dict(task='Compute a following value', cursor=first['coverage']['nextCursor']), project_root=project)
    assert len(second['matches']) == 6 and second['coverage']['hasMore'] is False
    assert len({row['id'] for row in first['matches'] + second['matches']}) == 30


def test_changed_project_code_is_withheld_after_provider_call(tmp_path):
    path = tmp_path / 'main.py'; path.write_text('return 1')
    provider = Provider(mutate=lambda: path.write_text('return 2'))
    result = JevRuntime(provider).dispatch('memory.code.search', dict(task='Find return value'), project_root=tmp_path)
    assert result['status'] == 'partial' and result['matches'] == []


@pytest.mark.parametrize('root', ['/', '/Users', '/tmp', str(Path.home())])
def test_code_scan_rejects_broad_or_home_roots_without_reading(root):
    with pytest.raises(ValueError, match='specific host-authorized'):
        JevRuntime(Provider()).dispatch('memory.code.search', dict(task='Find source'), project_root=root)


def test_caller_cannot_supply_project_root_or_function_catalog():
    for method, extra in [('memory.code.search', dict(project_root='/tmp')),
                          ('memory.tools.plan', dict(tool_catalog={}))]:
        with pytest.raises(ValueError, match='Unknown'):
            JevRuntime(Provider()).dispatch(method, dict(task='Choose', **extra))


def test_trace_omissions_use_declared_separators_instead_of_fusing_records():
    body = 'Keep first.\n\nDrop middle.\n\nKeep last.'
    provider = Provider(choice=lambda state, key, _: 'none' if key == 'select:1' else 'include')
    result = JevRuntime(provider).dispatch('memory.trace.compact', dict(task='Keep useful trace', body=body))
    assert result['compactedText'] == 'Keep first.\n\nKeep last.'
    assert result['separators'] == [dict(outputOffset=11, text='\n\n', synthetic=True, sourceStart=None, sourceEnd=None)]
    assert result['usedTokens'] <= result['tokenBudget']


def test_all_skipped_code_page_advances_to_safe_next_page(tmp_path):
    for index in range(24):
        (tmp_path / f'a{index:02}.py').write_bytes(b'\x00invalid source')
    (tmp_path / 'z.py').write_text('return value + 1')
    provider = Provider(); runtime = JevRuntime(provider)
    first = runtime.dispatch('memory.code.search', dict(task='Find addition'), project_root=tmp_path)
    assert first['matches'] == [] and first['status'] == 'partial' and not provider.calls
    assert first['coverage']['nextCursor']['file'] == 24 and first['coverage']['hasMore']
    second = runtime.dispatch('memory.code.search', dict(task='Find addition', cursor=first['coverage']['nextCursor']), project_root=tmp_path)
    assert second['matches'][0]['path'] == 'z.py' and not second['coverage']['hasMore']
    assert second['status'] == 'completed'


def test_unavailable_code_page_exposes_discovery_without_skipping_unreviewed_rows(tmp_path):
    (tmp_path / 'main.py').write_text('return value + 1')
    provider = Provider(); provider.available = False
    result = JevRuntime(provider).dispatch('memory.code.search', dict(task='Find addition'), project_root=tmp_path)
    assert result['status'] == 'unavailable' and result['matches'] == [] and not provider.calls
    coverage = result['coverage']
    assert coverage['filesRead'] == 1 and coverage['discoveredFiles'] == 1
    assert coverage['evaluatedCount'] == 0 and coverage['preparedCandidateCount'] == 1
    assert coverage['nextCursor'] == dict(file=0, span=0)
    assert coverage['preparedNextCursor']['file'] == 1


def test_code_discovery_ceiling_is_not_an_infinite_continuation_promise(tmp_path):
    for index in range(513):
        (tmp_path / f'unit_{index:03}.py').write_bytes(b'\x00excluded')
    result = JevRuntime(Provider()).dispatch('memory.code.search', dict(task='Find behavior', cursor=dict(file=512, span=0)), project_root=tmp_path)
    assert result['status'] == 'partial' and result['coverage']['discoveryIncomplete']
    assert result['coverage']['hasMore'] is False and result['coverage']['nextCursor']['file'] == 512
    assert 'ceiling' in result['warning']


def test_partial_file_cursor_rejects_changed_contents_even_when_paths_match(tmp_path):
    path = tmp_path / 'main.py'
    path.write_text('\n\n'.join(f'def f_{i}():\n    return {i}' for i in range(30)))
    runtime = JevRuntime(Provider())
    result = runtime.dispatch('memory.code.search', dict(task='Find returns'), project_root=tmp_path)
    cursor = result['coverage']['nextCursor']
    assert cursor['span'] == 24 and cursor['fileDigest']
    path.write_text(path.read_text().replace('return 29', 'return 99'))
    with pytest.raises(ValueError, match='changed'):
        runtime.dispatch('memory.code.search', dict(task='Find returns', cursor=cursor), project_root=tmp_path)


def test_snippets_accept_bound_object_cursor_and_keep_scalar_backward_compatibility():
    snippets = [dict(id=str(index), body=f'return {index}', source='fixture.py') for index in range(25)]
    runtime = JevRuntime(Provider())
    first = runtime.dispatch('memory.code.search', dict(task='Find behavior', snippets=snippets))
    cursor = first['coverage']['nextCursor']
    assert cursor['span'] == 24 and cursor['snapshot']
    second = runtime.dispatch('memory.code.search', dict(task='Find behavior', snippets=snippets, cursor=cursor))
    assert second['selectedIds'] == ['24'] and not second['coverage']['hasMore']
    legacy = runtime.dispatch('memory.code.search', dict(task='Find behavior', snippets=snippets, cursor=24))
    assert legacy['selectedIds'] == ['24']
    snippets[-1]['body'] = 'changed code'
    with pytest.raises(ValueError, match='changed'):
        runtime.dispatch('memory.code.search', dict(task='Find behavior', snippets=snippets, cursor=cursor))


def test_cancelled_project_walk_returns_cancelled_without_provider(tmp_path):
    event = threading.Event(); event.set(); provider = Provider()
    result = JevRuntime(provider).dispatch('memory.code.search', dict(task='Find behavior'), project_root=tmp_path, cancelled=event)
    assert result['status'] == 'cancelled' and result['matches'] == [] and not provider.calls


def test_integer_validation_does_not_overflow_into_float_coercion():
    schema = {'type': 'integer', 'minimum': 1, 'maximum': 10 ** 1000}
    _schema(schema)
    _validate(schema, 10 ** 999)
    with pytest.raises(ValueError, match='types'):
        _validate(schema, True)


def test_provider_numeric_overflow_is_invalid_response_and_never_selection():
    class Malformed(Provider):
        def evaluate(self, state, questions, **kwargs):
            result = super().evaluate(state, questions, **kwargs)
            result['answers']['support:0']['noul'] = 10 ** 1000
            return result
    result = JevRuntime(Malformed()).dispatch('memory.citations.verify', dict(claim='Claim', evidence=[dict(id='e', source='Evidence', body='Source body')]))
    assert result['status'] == 'unavailable' and not result['assessments'] and not result['selectedIds']


@pytest.mark.parametrize('body', ['ghp_' + 'a' * 36, 'password="' + 'a' * 20 + '"'])
def test_common_code_credentials_never_reach_hosted_provider(tmp_path, body):
    provider = Provider()
    runtime = JevRuntime(provider)
    with pytest.raises(ValueError, match='credential'):
        runtime.dispatch('memory.code.search', dict(task='Find behavior', snippets=[dict(id='code', body=body, source='sample.py')]))
    assert provider.calls == []
    (tmp_path / 'sample.py').write_text(body)
    outcome = runtime.dispatch('memory.code.search', dict(task='Find behavior'), project_root=tmp_path)
    assert outcome['matches'] == [] and provider.calls == []
