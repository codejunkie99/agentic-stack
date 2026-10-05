"""User-owned agent profiles and non-secret model discovery."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from .model_router import enrich_choice
try:
    import tomllib
except ImportError:  # The legacy command-line harness also supports Python 3.10.
    tomllib = None

RUNNERS = {'codex', 'claude-code'}
EFFORTS = {'', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}


def model_id(value):
    if not isinstance(value, str) or len(value) > 120 or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid model identifier.')
    return value.strip()


def effort_value(value, runner):
    if not isinstance(value, str) or value not in EFFORTS:
        raise ValueError('Choose a supported reasoning effort.')
    if runner == 'claude-code' and value not in {'', 'low', 'medium', 'high', 'xhigh', 'max'}:
        raise ValueError('Claude Code supports default, low, medium, high, xhigh or max effort.')
    return value


class AgentProfiles:
    def __init__(self, store, validate_text, safe_content):
        self.store, self.text, self.safe = store, validate_text, safe_content

    def save(self, p):
        runner = p.get('runner', 'codex')
        if not isinstance(runner, str) or runner not in RUNNERS:
            raise ValueError('Choose Codex or Claude Code as the runner.')
        mode = p.get('mode', 'read-only')
        if not isinstance(mode, str) or mode not in {'read-only', 'workspace-write'}:
            raise ValueError('Choose read only or edit project files.')
        values = {
            'name': self.safe(self.text(p.get('name'), 'Agent name', 60)),
            'role': self.safe(self.text(p.get('role') or 'Custom agent', 'Role', 140)),
            'instructions': self.safe(self.text(p.get('instructions'), 'Instructions', 12000)),
            'runner': runner, 'model': model_id(p.get('model', '')),
            'effort': effort_value(p.get('effort', ''), runner), 'mode': mode,
        }
        if p.get('id'):
            return self.store.update('agentProfile', p['id'], **values)
        return self.store.create('agentProfile', dict(values, archived=False))

    def archive(self, p):
        if not isinstance(p.get('archived'), bool):
            raise ValueError('Choose archive or restore.')
        return self.store.update('agentProfile', p.get('id'), archived=p['archived'])

    def models(self, home=None):
        choices = []
        home = Path(home).expanduser().resolve() if home else Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
        paths, warning = [], ''
        try:
            config_path = home/'config.toml'
            if tomllib and config_path.stat().st_size <= 2_000_000:
                config = tomllib.loads(config_path.read_text())
                catalog = config.get('model_catalog_json')
                if isinstance(catalog, str) and catalog:
                    path = Path(catalog).expanduser()
                    paths.append((path if path.is_absolute() else home/path, 'Configured Codex catalog'))
        except (OSError, ValueError, TypeError):
            pass
        paths.append((home/'models_cache.json', 'Codex model cache'))
        source = 'Manual model IDs'
        for path, label in paths:
            found = []
            try:
                if path.stat().st_size > 8_000_000:
                    raise ValueError('Catalog too large')
                rows = json.loads(path.read_text()).get('models', [])
                if not isinstance(rows, list):
                    raise ValueError('Invalid model catalog')
                for row in rows[:200]:
                    if not isinstance(row, dict):
                        continue
                    slug = row.get('slug', '')
                    if row.get('visibility') != 'list' or not isinstance(slug, str) or not re.fullmatch(r'[\w./:\[\]-]{1,120}', slug):
                        continue
                    levels = row.get('supported_reasoning_levels', [])
                    efforts = [x['effort'] for x in (levels if isinstance(levels, list) else [])
                               if isinstance(x, dict) and x.get('effort') in EFFORTS and x['effort']]
                    if not any(x['id'] == slug for x in found):
                        found.append(enrich_choice({'id': slug, 'runner': 'codex',
                            'name': str(row.get('display_name') or slug)[:120],
                            'efforts': list(dict.fromkeys(efforts))}))
                if found:
                    choices, source = found, label
                    break
                raise ValueError('Empty catalog')
            except (OSError, ValueError, TypeError, AttributeError, KeyError):
                if label == 'Configured Codex catalog':
                    warning = 'Configured catalog unavailable. Using the cache or manual model IDs.'
        choices += [enrich_choice({'id': alias, 'runner': 'claude-code', 'name': label, 'efforts': efforts})
                    for alias, label, efforts in [('sonnet', 'Sonnet', ['low', 'medium', 'high']),
                                                  ('opus', 'Opus', ['low', 'medium', 'high', 'xhigh', 'max']),
                                                  ('haiku', 'Haiku', []),
                                                  ('fable', 'Fable', ['low', 'medium', 'high', 'xhigh', 'max'])]]
        return {'models': choices, 'codexSource': source, 'warning': warning}
