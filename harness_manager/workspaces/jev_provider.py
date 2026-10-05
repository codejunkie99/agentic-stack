"""Typed Jev decisions; no memory writes and no implicit provider enablement."""
from __future__ import annotations

import http.client
import hashlib
import json
import math
import socket
import threading
import time
from urllib.parse import urlsplit

from .knowledge import clean_text

MAX_REQUEST = 240000
MAX_RESPONSE = 240000


class JevError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__({'unavailable': 'Jev is not configured and enabled.',
            'deadline': 'Jev exceeded the decision deadline.',
            'transport': 'Jev could not be reached.',
            'authentication': 'Jev rejected the configured credential.',
            'request': 'Jev rejected the decision request.',
            'busy': 'Jev is temporarily unavailable.',
            'response': 'Jev returned an invalid decision.',
            'size': 'Jev decision exceeds the supported size.',
            'redirect': 'Jev endpoint redirects are not allowed.'}.get(code, 'Jev decision failed.'))


def _number(value, low, high):
    return type(value) in (float, int) and math.isfinite(value) and low <= value <= high


def _payload_has_secrets(value):
    """Apply the import sanitizer to every outbound field, including metadata.

    Inspect object key/value pairs together so structured credential fields get
    the same protection as a textual password=... assignment.
    """
    if isinstance(value, str):
        return bool(clean_text(value)[1])
    if isinstance(value, dict):
        return any(_payload_has_secrets(key) or _payload_has_secrets(item)
                   or isinstance(key, str) and isinstance(item, str)
                   and bool(clean_text(key + '=' + item)[1])
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_payload_has_secrets(item) for item in value)
    return False


def _check(deadline, cancelled):
    if cancelled.is_set():
        raise InterruptedError('Memory decision cancelled.')
    if time.monotonic() >= deadline:
        raise JevError('deadline')


def validate_questions(questions):
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 64:
        raise JevError('request')
    for key, question in questions.items():
        if not isinstance(key, str) or not key or len(key) > 200 or not isinstance(question, dict):
            raise JevError('request')
        if not isinstance(question.get('instructions'), (str, dict, list)) or not question['instructions']:
            raise JevError('request')
        kind, criteria = question.get('type'), question.get('criteria')
        if kind == 'choice':
            if (not isinstance(criteria, dict) or not 1 <= len(criteria) <= 255
                    or any(not isinstance(k, str) or not k for k in criteria)):
                raise JevError('request')
        elif kind == 'score':
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise JevError('request')
        elif kind == 'noul':
            if criteria is not None and (not isinstance(criteria, dict) or set(criteria) != {'true', 'false'}):
                raise JevError('request')
        else:
            raise JevError('request')


def _rounding_error(value):
    return .005 if abs(value - round(value, 2)) < 1e-10 else 1e-9


def _distribution_bounds(probabilities):
    """Bound underlying probabilities when hosted values are rounded to two decimals.

    Preserve returned values. Higher precision fixtures remain exact; a rounded
    distribution must still admit total mass one. Greedy extremes bound Score
    consistency instead of accepting an arbitrary difference from its expectation.
    """
    bounds = []
    for probability in probabilities.values():
        error = _rounding_error(probability)
        bounds.append((max(0., probability - error), min(1., probability + error)))
    if sum(low for low, _ in bounds) > 1 + 1e-9 or sum(high for _, high in bounds) < 1 - 1e-9:
        raise JevError('response')
    return bounds


def _score_extreme(bounds, *, highest):
    mass = [low for low, _ in bounds]
    remaining = max(0., 1 - sum(mass))
    for index in sorted(range(len(bounds)), reverse=highest):
        addition = min(remaining, bounds[index][1] - mass[index])
        mass[index] += addition
        remaining -= addition
    return sum(index * probability for index, probability in enumerate(mass))


def validate_response(value, questions):
    if (not isinstance(value, dict) or not isinstance(value.get('model'), str)
            or not value['model'] or len(value['model']) > 200
            or not isinstance(value.get('answers'), dict) or set(value['answers']) != set(questions)):
        raise JevError('response')
    usage = value.get('usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens', 'output_tokens')):
        raise JevError('response')
    answers = {}
    for key, question in questions.items():
        answer = value['answers'][key]
        kind = question['type']
        if not isinstance(answer, dict) or answer.get('type') != kind:
            raise JevError('response')
        if kind == 'noul':
            if not _number(answer.get('noul'), 0, 1):
                raise JevError('response')
            answers[key] = {'type': kind, 'noul': answer['noul']}
            continue
        keys = set(question['criteria']) if kind == 'choice' else {str(i) for i in range(len(question['criteria']))}
        probabilities = answer.get('probabilities')
        if (not isinstance(probabilities, dict) or set(probabilities) != keys
                or any(not _number(p, 0, 1) for p in probabilities.values())
                or not _number(answer.get('confidence'), 0, 1)):
            raise JevError('response')
        bounds = _distribution_bounds(probabilities)
        clean = dict(type=kind, probabilities=probabilities, confidence=answer['confidence'])
        if kind == 'choice':
            chosen = answer.get('choice')
            if not isinstance(chosen, str) or chosen not in keys or probabilities[chosen] + 1e-9 < max(probabilities.values()):
                raise JevError('response')
            clean['choice'] = chosen
        else:
            legend = answer.get('legend')
            # JSON map order is immaterial; rubric index defines the expectation.
            bounds = _distribution_bounds({str(index): probabilities[str(index)] for index in range(len(keys))})
            minimum = _score_extreme(bounds, highest=False)
            maximum = _score_extreme(bounds, highest=True)
            if (not _number(answer.get('score'), 0, len(keys) - 1)
                    or answer['score'] < minimum - _rounding_error(answer['score']) - 1e-9
                    or answer['score'] > maximum + _rounding_error(answer['score']) + 1e-9
                    or not isinstance(legend, dict) or set(legend) != keys
                    or any(not isinstance(v, str) for v in legend.values())):
                raise JevError('response')
            clean.update(score=answer['score'], legend=legend)
        answers[key] = clean
    return dict(model=value['model'], answers=answers,
                usage={k: usage[k] for k in ('input_tokens', 'output_tokens')})


def _http(endpoint, token, payload, deadline, cancelled):
    """No redirects; recheck total deadline between bounded response reads."""
    url = urlsplit(endpoint)
    _check(deadline, cancelled)
    connection = http.client.HTTPSConnection(url.hostname, url.port or 443,
                                             timeout=min(10, deadline - time.monotonic()))
    try:
        connection.request('POST', url.path or '/', body=payload,
                           headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        _check(deadline, cancelled)
        if connection.sock:
            connection.sock.settimeout(min(10, deadline - time.monotonic()))
        response = connection.getresponse()
        # Error bodies can contain sensitive echoed input. Do not read or return them.
        if response.status != 200:
            return response.status, dict(response.getheaders()), b''
        chunks, size = [], 0
        while True:
            _check(deadline, cancelled)
            if connection.sock:
                connection.sock.settimeout(min(10, deadline - time.monotonic()))
            chunk = response.read1(min(16384, MAX_RESPONSE + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise JevError('size')
            chunks.append(chunk)
        return response.status, dict(response.getheaders()), b''.join(chunks)
    finally:
        connection.close()


class JevProvider:
    def __init__(self, *, token='', enabled=False, model='jev-latest',
                 endpoint='https://api.typesafe.ai/v1/systemone', transport=None):
        url = urlsplit(endpoint)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ValueError('Jev endpoint must be an HTTPS URL without credentials, query or fragment.')
        if not isinstance(model, str) or not model or len(model) > 200:
            raise ValueError('Invalid Jev model.')
        if not isinstance(token, str) or '\r' in token or '\n' in token:
            raise ValueError('Invalid Jev credential.')
        self._token, self.enabled, self.model, self.endpoint = token, enabled is True, model, endpoint
        self._transport = transport or _http

    @property
    def available(self):
        return self.enabled and bool(self._token)

    @property
    def cache_identity(self):
        return (self.endpoint, self.model, self.enabled, hashlib.sha256(self._token.encode()).hexdigest())

    def evaluate(self, state, questions, *, deadline, cancelled=None):
        cancelled = cancelled or threading.Event()
        _check(deadline, cancelled)
        if not self.available:
            raise JevError('unavailable')
        validate_questions(questions)
        try:
            payload = json.dumps(dict(state=state, model=self.model, questions=questions), allow_nan=False).encode()
        except (ValueError, TypeError):
            raise JevError('request') from None
        if len(payload) > MAX_REQUEST:
            raise JevError('size')
        # The provider owns the final hosted boundary. Capture, reconciliation,
        # and maintenance must receive the same protection as context planning.
        if _payload_has_secrets(json.loads(payload)):
            raise JevError('request')
        for attempt in range(3):
            _check(deadline, cancelled)
            try:
                status, headers, body = self._transport(self.endpoint, self._token, payload, deadline, cancelled)
            except (socket.timeout, TimeoutError):
                raise JevError('deadline') from None
            except (OSError, http.client.HTTPException):
                raise JevError('transport') from None
            _check(deadline, cancelled)
            if status == 200:
                if not isinstance(body, bytes) or len(body) > MAX_RESPONSE:
                    raise JevError('size')
                try:
                    value = json.loads(body)
                except (ValueError, UnicodeError):
                    raise JevError('response') from None
                return validate_response(value, questions)
            if 300 <= status < 400:
                raise JevError('redirect')
            if status == 401:
                raise JevError('authentication')
            if status not in {429, 529, 502, 503, 504}:
                raise JevError('request')
            if attempt == 2:
                raise JevError('busy')
            delay = 0.25 * 2 ** attempt
            retry = next((v for k, v in headers.items() if k.lower() == 'retry-after'), '')
            try:
                delay = max(delay, float(retry))
            except (ValueError, TypeError):
                pass
            if not math.isfinite(delay) or delay >= deadline - time.monotonic():
                raise JevError('deadline')
            if cancelled.wait(delay):
                raise InterruptedError('Memory decision cancelled.')
