"""Native facade over agentic-stack's existing project and skill machinery."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .. import install as installer, schema, skill_manifest, state
from ..mission_control_collectors import build_payloads
from ..transfer_bundle import scan_text_for_secrets
from .integrations import TOOLS


class StackManager:
    def __init__(self, store, project_root=None):
        self.store = store
        self.stack = Path(__file__).resolve().parents[2]
        self.project_root = project_root.resolve() if project_root else None

    def validate_project(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Choose a project folder.')
        path = Path(value).expanduser().resolve()
        if not path.is_dir() or path in {Path.home(), Path('/')}:
            raise ValueError('Choose a project folder, not your home folder or filesystem root.')
        if self.project_root and not path.is_relative_to(self.project_root):
            raise ValueError('Choose a project inside the configured server project root.')
        return path

    def root(self, wid):
        ws = self.store.get('workspace', wid)
        return self.validate_project(ws['projectPath']) if ws.get('projectPath') else self.store.workspace_path(wid)

    def attach(self, p):
        path = self.validate_project(p.get('path'))
        return self.store.update('workspace', p.get('workspaceId'), projectPath=str(path))

    def snapshot(self, wid):
        root = self.root(wid)
        payloads = build_payloads(root, self.stack)
        domains = []
        for key, value in payloads.items():
            if 'objects' in value:
                domains.append({'id': key, 'name': key.removeprefix('/api/').replace('-', ' ').replace('/', ' · ').title(),
                                'summary': value.get('domain_summary') or (value.get('summary', '') if isinstance(value.get('summary', ''), str) else ''), 'status': value.get('status', ''),
                                'items': [{'id': str(o.get('id', i)), 'label': o.get('label', ''), 'status': o.get('status', ''),
                                           'summary': o.get('summary', ''), 'detail': json.dumps(o.get('payload', {}), indent=2)}
                                          for i, o in enumerate(value['objects'])]})
        tracked = state.load(root) or {}
        return {'path': str(root), 'initialized': (root/'.agent/AGENTS.md').is_file(),
                'installed': sorted(tracked.get('adapters', {})),
                'adapters': [{'id': p.parent.name, 'name': p.parent.name, 'description': json.loads(p.read_text()).get('description', '')}
                             for p in sorted((self.stack/'adapters').glob('*/adapter.json'))],
                'domains': domains, 'skills': self.skills(wid),
                'files': [{'id': str(p.relative_to(root)), 'name': p.name, 'path': str(p.relative_to(root))}
                          for folder in ['memory/personal', 'memory/semantic', 'memory/working', 'protocols', 'loops']
                          for p in sorted((root/'.agent'/folder).rglob('*'))
                          if p.is_file() and p.suffix in {'.md', '.json', '.yaml', '.yml'}
                          and p.resolve().is_relative_to(root.resolve()) and p.stat().st_size <= 200_000][:300]}

    def initialize(self, wid):
        root = self.root(wid)
        target = root/'.agent'
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('The project .agent folder links outside the selected project.')
        existing_loop_profiles = (target/'loops/harnesses.json').is_file()
        # Merge missing skeleton files only. Existing project memory and skills remain authoritative.
        for source in (self.stack/'.agent').rglob('*'):
            rel = source.relative_to(self.stack/'.agent')
            if existing_loop_profiles and rel.parts[0] == 'loops':
                continue
            if any(part in {'.git', '__pycache__', '.index'} for part in rel.parts) or source.is_symlink():
                continue
            destination = target/rel
            if source.is_file() and not destination.exists():
                if not destination.resolve().is_relative_to(target.resolve()):
                    raise ValueError('Project contains a link outside its .agent folder.')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        skill_manifest.sync_manifest(root, log=lambda _: None)
        return {'text': 'Portable memory, skills, protocols and tools initialized. Existing files were preserved.'}

    def adapter(self, p):
        root = self.root(p['workspaceId'])
        name = p.get('adapter')
        manifests = {f.parent.name: f for f in (self.stack/'adapters').glob('*/adapter.json')}
        if name not in manifests:
            raise ValueError('Unknown harness adapter.')
        manifest = schema.validate(manifests[name])
        if any(not (root/f['dst']).resolve().is_relative_to(root.resolve()) for f in manifest['files']):
            raise ValueError('An adapter destination links outside the selected project.')
        tracked = state.load(root) or {}
        prior = (tracked.get('adapters') or {}).get(name, {})
        owned = set(prior.get('files_written', []))
        conflicts = [f['dst'] for f in manifest['files'] if f.get('merge_policy') == 'overwrite'
                     and (root/f['dst']).exists() and f['dst'] not in owned]
        if conflicts:
            raise ValueError('Existing files need a manual merge before this adapter can be installed: ' + ', '.join(conflicts))
        self.initialize(p['workspaceId'])
        log = []
        installer.install(manifest, root, manifests[name].parent, self.stack, log=log.append)
        # Claude's adapter references .agent skills in CLAUDE.md. Also expose the native skills path.
        if name == 'claude-code':
            link = root/'.claude/skills'
            if not link.exists() and not link.is_symlink():
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to('../.agent/skills', target_is_directory=True)
        return {'text': '\n'.join(log)}

    def catalog(self):
        roots = [('Bundled', self.stack/'.agent/skills'), ('Codex', Path.home()/'.codex/skills'),
                 ('Shared', Path.home()/'.agents/skills'), ('Claude Code', Path.home()/'.claude/skills')]
        roots.extend((name, Path.home()/folder) for name, _, _, _, _, folders in TOOLS.values() for folder in folders)
        rows = {}
        for origin, root in roots:
            if not root.is_dir():
                continue
            for path in sorted(root.glob('*/SKILL.md')):
                try:
                    actual = path.resolve()
                    if str(actual) in rows or path.stat().st_size > 200_000:
                        continue
                    content = path.read_text(encoding='utf-8')
                    identifier = hashlib.sha256(str(actual).encode()).hexdigest()[:24]
                    match = re.search(r'^description:\s*(.+)', content, re.M)
                    rows[str(actual)] = {'id': identifier, 'name': path.parent.name, 'origin': origin,
                        'description': match.group(1).strip('"\'')[:300] if match else '', 'path': str(actual.parent)}
                except (OSError, UnicodeError):
                    continue
        return list(rows.values())

    def skills(self, wid):
        root = self.root(wid)/'.agent/skills'
        return [{'id': p.parent.name, 'name': p.parent.name} for p in sorted(root.glob('*/SKILL.md'))]

    def project_file(self, p):
        root = self.root(p['workspaceId'])
        relative = p.get('path', '')
        if not isinstance(relative, str) or not relative.startswith('.agent/'):
            raise ValueError('Only project .agent files can be opened here.')
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_relative_to((root/'.agent').resolve()) or not path.is_file():
            raise ValueError('Choose an existing file inside the project .agent folder.')
        if path.stat().st_size > 200_000:
            raise ValueError('This file is too large for the desktop editor.')
        content = path.read_text(encoding='utf-8')
        digest = hashlib.sha256(content.encode()).hexdigest()
        if p.get('content') is not None:
            replacement = p['content']
            if p.get('digest') != digest:
                raise ValueError('The file changed since it was opened. Reload it before saving.')
            if not isinstance(replacement, str) or len(replacement.encode()) > 200_000:
                raise ValueError('The replacement text exceeds the file limit.')
            if scan_text_for_secrets(replacement):
                raise ValueError('Remove credentials before saving this file.')
            path.write_text(replacement)
            if path.name == 'SKILL.md':
                skill_manifest.sync_manifest(root, log=lambda _: None)
            content = replacement
            digest = hashlib.sha256(content.encode()).hexdigest()
        return {'text': content, 'digest': digest, 'path': relative}

    def skill_detail(self, identifier):
        match = next((x for x in self.catalog() if x['id'] == identifier), None)
        if not match:
            raise ValueError('Skill not found. Refresh the catalog.')
        content = (Path(match['path'])/'SKILL.md').read_text()
        if scan_text_for_secrets(content):
            raise ValueError('This skill appears to contain a credential. Remove it before importing.')
        return {'text': content, 'name': match['name']}

    def add_skill(self, p):
        match = next((x for x in self.catalog() if x['id'] == p.get('id')), None)
        if not match:
            raise ValueError('Skill not found.')
        source = Path(match['path'])
        target = self.root(p['workspaceId'])/'.agent/skills'/match['name']
        if not target.resolve().is_relative_to(self.root(p['workspaceId']).resolve()):
            raise ValueError('The project skill folder links outside the selected project.')
        if target.exists() or target.is_symlink():
            raise ValueError('This skill already exists in the project. Existing skills are never overwritten.')
        files, total = [], 0
        for path in source.rglob('*'):
            if any(part in {'.git', '__pycache__', 'node_modules'} for part in path.relative_to(source).parts):
                continue
            if path.is_symlink():
                raise ValueError('This skill contains symbolic links. Import a self-contained skill folder.')
            if path.is_file():
                total += path.stat().st_size
                if len(files) >= 500 or total > 10_000_000:
                    raise ValueError('This skill exceeds the import size limit.')
                if scan_text_for_secrets(path.read_text(errors='replace')):
                    raise ValueError('This skill appears to contain a credential. Remove it before importing.')
                files.append(path)
        for path in files:
            destination = target/path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        skill_manifest.sync_manifest(self.root(p['workspaceId']), log=lambda _: None)
        return {'text': 'Added ' + match['name'] + ' to the project skill library.'}

    def repair_skills(self, wid):
        """Repair only byte-for-byte legacy bundled skills, never customized content."""
        root = self.root(wid)
        repaired = 0
        for source in (self.stack/'.agent/skills').glob('*/SKILL.md'):
            target = root/'.agent/skills'/source.parent.name/'SKILL.md'
            if not target.is_file() or not target.resolve().is_relative_to(root.resolve()) or target.stat().st_size > 200_000:
                continue
            updated = source.read_text()
            description = next((line for line in updated.splitlines() if line.startswith('description:')), '')
            if description and target.read_text() == updated.replace(description+'\n', '', 1):
                target.write_text(updated)
                repaired += 1
        skill_manifest.sync_manifest(root, log=lambda _: None)
        return {'text': f'Updated {repaired} bundled skill descriptions. Customized skills were preserved.'}

    def command(self, p):
        root = self.root(p['workspaceId'])
        operation = p.get('operation')
        fixed = {
            'doctor': ['-m', 'harness_manager.cli', 'doctor', str(root)],
            'manifest': ['-m', 'harness_manager.cli', 'sync-manifest', str(root)],
            'upgrade-preview': ['-m', 'harness_manager.cli', 'upgrade', str(root), '--dry-run'],
            'upgrade': ['-m', 'harness_manager.cli', 'upgrade', str(root), '--yes'],
            'loop-init': ['-m', 'harness_manager.cli', 'loop', 'init', str(root)],
            'loop-validate': ['-m', 'harness_manager.cli', 'loop', 'validate', str(root)],
            'loop-status': ['-m', 'harness_manager.cli', 'loop', 'status', str(root)],
            'brain-status': ['-m', 'harness_manager.cli', 'brain', 'status'],
            'memory-candidates': [str(root/'.agent/tools/list_candidates.py'), '--format', 'json'],
            'memory-search': [str(root/'.agent/memory/memory_search.py'), str(p.get('query', ''))],
            'recall': [str(root/'.agent/tools/recall.py'), str(p.get('query', ''))],
        }
        if operation not in fixed:
            raise ValueError('Unsupported stack operation.')
        env = dict(os.environ, PYTHONPATH=str(self.stack), AGENTIC_STACK_ROOT=str(self.stack))
        result = subprocess.run([sys.executable, *fixed[operation]], cwd=root, env=env,
                                capture_output=True, text=True, timeout=60)
        output = (result.stdout + '\n' + result.stderr).strip()[-100000:]
        if result.returncode:
            raise ValueError(output[:4000] or 'The stack operation did not complete.')
        return {'text': output or 'Done.'}
