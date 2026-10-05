import copy
import json
import threading
import time

import pytest

from harness_manager.workspaces.jev_provider import JevProvider, JevError, validate_response

QUESTIONS = {
    'route': {'type': 'choice', 'instructions': 'Choose source or abstain.', 'criteria': {'source': 'Verified source', 'abstain': 'Insufficient evidence'}},
    'keep': {'type': 'noul', 'instructions': 'Is this reusable?'},
    'utility': {'type': 'score', 'instructions': 'Rate evidence utility.', 'criteria': ['None', 'Useful', 'Essential']}}
RESPONSE = {'model': 'jev-test', 'usage': {'input_tokens': 10, 'output_tokens': 3}, 'answers': {
    'route': {'type': 'choice', 'choice': 'source', 'probabilities': {'source': .8, 'abstain': .2}, 'confidence': .6},
    'keep': {'type': 'noul', 'noul': .9},
    'utility': {'type': 'score', 'score': 1.5, 'legend': {'0': 'None', '1': 'Useful', '2': 'Essential'}, 'probabilities': {'0': 0, '1': .5, '2': .5}, 'confidence': .3}}}


def run(transport, **kwargs):
    return JevProvider(token='synthetic-test-only', enabled=True, transport=transport).evaluate(
        {'evidence': 'fixture'}, QUESTIONS, deadline=time.monotonic() + 3, **kwargs)


def test_exact_protocol_and_all_question_types():
    def transport(endpoint, token, body, deadline, event):
        assert endpoint == 'https://api.typesafe.ai/v1/systemone'
        assert token == 'synthetic-test-only'
        assert json.loads(body) == {'state': {'evidence': 'fixture'}, 'model': 'jev-latest', 'questions': QUESTIONS}
        return 200, {}, json.dumps(RESPONSE).encode()
    assert run(transport) == RESPONSE


@pytest.mark.parametrize('mutation', [
    lambda r: r['answers'].pop('keep'),
    lambda r: r['answers']['route'].update(choice='forged'),
    lambda r: r['answers']['route'].update(choice='abstain'),
    lambda r: r['answers']['route'].update(probabilities={'source': 1}),
    lambda r: r['answers']['keep'].update(noul=True),
    lambda r: r['answers']['keep'].update(noul=float('nan')),
    lambda r: r['answers']['utility'].update(score=0),
    lambda r: r['answers']['utility'].update(confidence=float('inf')),
    lambda r: r['usage'].update(input_tokens=True),
])
def test_rejects_invalid_decisions(mutation):
    value = copy.deepcopy(RESPONSE)
    mutation(value)
    with pytest.raises(JevError, match='invalid decision'):
        validate_response(value, QUESTIONS)


@pytest.mark.parametrize('status,code', [(401,'authentication'), (422,'request'), (302,'redirect')])
def test_no_retry_or_error_body_disclosure(status, code):
    calls = []
    def transport(*args):
        calls.append(1)
        return status, {}, b'private echoed data'
    with pytest.raises(JevError) as error:
        run(transport)
    assert error.value.code == code and 'private' not in str(error.value)
    assert len(calls) == 1


def test_retry_is_bounded_and_recovers():
    calls = []
    def transport(*args):
        calls.append(1)
        return (429, {}, b'') if len(calls) == 1 else (200, {}, json.dumps(RESPONSE).encode())
    assert run(transport)['model'] == 'jev-test'
    assert len(calls) == 2


def test_no_network_without_enablement_and_late_answer_cancelled():
    calls = []
    def transport(*args):
        calls.append(1)
        return 200, {}, json.dumps(RESPONSE).encode()
    provider = JevProvider(token='synthetic', transport=transport)
    with pytest.raises(JevError) as error:
        provider.evaluate({}, QUESTIONS, deadline=time.monotonic()+1)
    assert error.value.code == 'unavailable' and not calls
    cancelled = threading.Event()
    def late(*args):
        cancelled.set()
        return transport(*args)
    with pytest.raises(InterruptedError):
        run(late, cancelled=cancelled)


def test_size_bad_json_and_expired_deadline():
    for data, code in [(b'not json','response'), (b'x'*240001,'size')]:
        with pytest.raises(JevError) as error:
            run(lambda *args: (200, {}, data))
        assert error.value.code == code
    with pytest.raises(JevError) as error:
        JevProvider().evaluate({}, QUESTIONS, deadline=time.monotonic()-1)
    assert error.value.code == 'deadline'


def test_hosted_rounded_score_and_distribution_are_consistent():
    value = copy.deepcopy(RESPONSE)
    value['answers']['utility'].update(score=1.92,
        probabilities={'2': .93, '0': 0., '1': .07})
    assert validate_response(value, QUESTIONS)['answers']['utility']['score'] == 1.92
    value['answers']['utility'].update(score=.99,
        probabilities={'0': .33, '1': .33, '2': .33})
    assert validate_response(value, QUESTIONS)['answers']['utility']['score'] == .99


@pytest.mark.parametrize('probabilities,score', [
    ({'0': .1, '1': .1, '2': .1}, .3),
    ({'0': 0., '1': .07, '2': .93}, 1.8),
    ({'0': .001, '1': .001, '2': .998}, 1.9),
])
def test_rounding_does_not_accept_impossible_mass_or_inconsistent_score(probabilities, score):
    value = copy.deepcopy(RESPONSE)
    value['answers']['utility'].update(probabilities=probabilities, score=score)
    with pytest.raises(JevError, match='invalid decision'):
        validate_response(value, QUESTIONS)


@pytest.mark.parametrize('state', [
    {'operation': 'capture', 'spans': [{'text': 'password=ABCDEFGHIJKLMNOP12345678'}]},
    {'operation': 'reconcile', 'subject': {'body': 'access_token=ABCDEFGHIJKLMNOP12345678'}},
    {'operation': 'maintenance', 'evidence': [{'body': 'ghp_ABCDEFGHIJKLMNOP12345678'}]},
    {'sourceKey': 'synthetic:api_key=ABCDEFGHIJKLMNOP12345678'},
    {'metadata': {'password': 'ABCDEFGHIJKLMNOP12345678'}},
])
def test_hosted_boundary_rejects_credentials_in_every_operation(state):
    calls = []
    def transport(*args):
        calls.append(args)
        return 200, {}, json.dumps(RESPONSE).encode()
    provider = JevProvider(token='synthetic-provider-key', enabled=True, transport=transport)
    with pytest.raises(JevError) as error:
        provider.evaluate(state, QUESTIONS, deadline=time.monotonic() + 1)
    assert error.value.code == 'request'
    assert 'ABCDEFGHIJKLMNOP' not in str(error.value)
    assert not calls


def test_hosted_boundary_checks_questions_as_well_as_state():
    questions = copy.deepcopy(QUESTIONS)
    questions['keep']['instructions'] = 'secret=ABCDEFGHIJKLMNOP12345678'
    provider = JevProvider(token='synthetic-provider-key', enabled=True,
        transport=lambda *args: pytest.fail('Credential-bearing questions reached transport'))
    with pytest.raises(JevError):
        provider.evaluate({}, questions, deadline=time.monotonic() + 1)
