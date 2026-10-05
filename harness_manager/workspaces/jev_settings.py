"""Explicit host-owned provider setup shared by desktop and read-only MCP.

Only this dedicated owner-readable file is read. No ambient credential discovery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile

from .jev_provider import JevProvider


class JevSettings:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'jev-provider.json'

    def read(self):
        try:
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, 'r') as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    return {}
                value = json.loads(file.read(20000))
                if not isinstance(value, dict) or value.get('version') != 1:
                    return {}
                return value
        except (OSError, ValueError):
            return {}

    def status(self):
        value = self.read()
        return {'enabled': value.get('enabled') is True,
                'configured': bool(value.get('token')),
                'consent': value.get('consent') is True,
                'available': _configured_provider(value).available,
                'model': value.get('model', 'jev-latest'),
                'endpoint': 'https://api.typesafe.ai/v1/systemone'}

    def configure(self, *, token, enabled, consent, model='jev-latest'):
        if type(enabled) is not bool or type(consent) is not bool:
            raise ValueError('Provider enablement and consent must be boolean.')
        if enabled and not consent:
            raise ValueError('Enable hosted processing only after reviewing the data-sharing notice.')
        if not isinstance(token, str) or not 0 < len(token.strip()) <= 16000:
            raise ValueError('Enter a provider credential.')
        token = token.strip()
        JevProvider(token=token, model=model)
        value = dict(version=1, token=token, enabled=enabled, consent=consent, model=model)
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.jev-provider-', dir=self.root)
        try:
            with os.fdopen(descriptor, 'w') as file:
                os.fchmod(file.fileno(), 0o600)
                json.dump(value, file)
                file.flush(); os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return self.status()

    def disconnect(self):
        # The exact provider file only; evidence/history are never touched.
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        return self.status()


def _configured_provider(value, *, transport=None):
    try:
        return JevProvider(token=value.get('token', ''), model=value.get('model', 'jev-latest'),
            enabled=value.get('enabled') is True and value.get('consent') is True, transport=transport)
    except ValueError:
        return JevProvider()


class ConfiguredJevProvider:
    def __init__(self, settings, *, transport=None):
        self.settings, self.transport = settings, transport

    def _provider(self):
        return _configured_provider(self.settings.read(), transport=self.transport)

    @property
    def available(self):
        return self._provider().available

    @property
    def cache_identity(self):
        return self._provider().cache_identity

    def evaluate(self, *args, **kwargs):
        # Reload on each decision so disconnect affects subsequent desktop/MCP calls.
        return self._provider().evaluate(*args, **kwargs)
