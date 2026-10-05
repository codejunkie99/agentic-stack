"""Native onboarding using the stack's existing preference and feature formats."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile

from onboard_render import render
from onboard_write import is_customized, write_prefs
from ..transfer_bundle import scan_text_for_secrets

FEATURES = ('memory_search_fts', 'tldraw', 'mission_control')


class ProjectSetup:
    def __init__(self, stack):
        self.stack = stack

    def _paths(self, wid):
        root = self.stack.root(wid)
        prefs = root/'.agent/memory/personal/PREFERENCES.md'
        features = root/'.agent/memory/.features.json'
        for path in [prefs, features]:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('Setup files must stay inside the selected project.')
            if path.exists() and path.stat().st_size > 200_000:
                raise ValueError('A setup file is too large for the desktop editor.')
        return root, prefs, features

    def snapshot(self, wid):
        root, prefs, features = self._paths(wid)
        flags = json.loads(features.read_text()) if features.exists() else {}
        if not isinstance(flags, dict):
            raise ValueError('The project feature file must be a JSON object.')
        return {'customized': is_customized(str(root)), 'preferencesDigest': hashlib.sha256(prefs.read_bytes()).hexdigest() if prefs.exists() else '',
                'featuresDigest': hashlib.sha256(features.read_bytes()).hexdigest() if features.exists() else '',
                'features': {key: isinstance(flags.get(key), dict) and flags[key].get('enabled') is True for key in FEATURES}}

    def apply(self, p):
        wid = p['workspaceId']
        root, prefs, features = self._paths(wid)
        before = self.snapshot(wid)
        if p.get('preferencesDigest', '') != before['preferencesDigest']:
            raise ValueError('Preferences changed while setup was open. Reopen setup before applying it.')
        if p.get('featuresDigest', '') != before['featuresDigest']:
            raise ValueError('Feature settings changed while setup was open. Reopen setup before applying it.')
        answers = p.get('answers', {})
        if not isinstance(answers, dict) or set(answers) - {'name', 'languages', 'style', 'tests', 'commits', 'review'}:
            raise ValueError('Unsupported onboarding answers.')
        if any(not isinstance(v, str) or len(v) > 1000 or scan_text_for_secrets(v) for v in answers.values()):
            raise ValueError('Use short preference answers without credentials.')
        flags = p.get('features', {})
        if not isinstance(flags, dict) or set(flags) - set(FEATURES) or any(type(v) is not bool for v in flags.values()):
            raise ValueError('Choose supported optional features.')
        adapters = p.get('adapters', [])
        known = {f.parent.name for f in (self.stack.stack/'adapters').glob('*/adapter.json')}
        if not isinstance(adapters, list) or any(not isinstance(x, str) or x not in known for x in adapters):
            raise ValueError('Choose supported project adapters.')
        self.stack.initialize(wid)
        if not before['customized']:
            write_prefs(str(root), render(answers))
        current = json.loads(features.read_text()) if features.exists() else {}
        for key, enabled in flags.items():
            entry = current.get(key, {})
            current[key] = {**(entry if isinstance(entry, dict) else {}), 'enabled': enabled, 'beta': True}
        fd, temporary = tempfile.mkstemp(dir=features.parent, prefix='.features-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(current, stream, indent=2); stream.write('\n')
            os.replace(temporary, features)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        warnings = []
        for adapter in dict.fromkeys(adapters):
            try:
                self.stack.adapter({'workspaceId': wid, 'adapter': adapter})
            except (ValueError, OSError) as exc:
                warnings.append(adapter + ': ' + str(exc))
        return {'text': 'Project stack is ready. ' + ('Your existing preferences were preserved.' if before['customized'] else 'Your preferences were saved.'),
                'warnings': warnings}
