#!/usr/bin/env python3
"""Stage distributable code with fresh memory templates, never checkout memory."""
import argparse
import os
from pathlib import Path
import shutil


PAYLOAD_ROOTS = ('harness_manager', 'adapters', '.agent', 'deploy/agentic-stack',
                 'LICENSE', 'NOTICE', '.dockerignore')
AGENT_CODE = {'AGENTS.md', 'harness', 'tools', 'skills', 'protocols', 'loops', 'memory'}
BLOCKED = {'.git', '.hg', '.svn', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
           '.cache', 'cache', 'runtime', 'node_modules', '.ssh', '.aws', '.azure', '.kube', '.gnupg'}
CREDENTIAL_FILES = {'.npmrc', '.pypirc', '.netrc', '_netrc', '.git-credentials', '.boto', '.s3cfg',
                    '.pgpass', '.my.cnf', 'auth.json', 'credentials.json', 'secrets.json', 'tokens.json',
                    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', 'id_ecdsa_sk', 'id_ed25519_sk'}
KEY_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.jks', '.keystore', '.keychain', '.keychain-db'}
MEMORY_STATE = {'personal', 'working', 'semantic', 'episodic', 'candidates', 'archive', 'archives',
                'index', 'indexes', 'exports', 'data-layer', 'flywheel'}
TEMPLATES = {
    'personal/PREFERENCES.md': '# Preferences\n\nRecord explicit user preferences here.\n',
    'working/WORKSPACE.md': '# Workspace\n\n## Goal\n\n## Current state\n\n## Next steps\n',
    'working/REVIEW_QUEUE.md': '# Review Queue\n\n_No pending candidates._\n',
    'semantic/DECISIONS.md': '# Decisions\n\nRecord accepted decisions and their rationale here.\n',
    'semantic/DOMAIN_KNOWLEDGE.md': '# Domain Knowledge\n\nRecord verified project knowledge and sources here.\n',
    'semantic/LESSONS.md': '# Lessons\n\n## Auto-promoted entries will be appended below\n',
    'semantic/lessons.jsonl': '',
    'episodic/AGENT_LEARNINGS.jsonl': '',
}


def output_path(root, destination):
    """Outputs may live in dist, but never inside a packaged input tree."""
    path = Path(destination)
    if path.is_symlink():
        raise ValueError('The package destination cannot be a symbolic link.')
    path = path.resolve()
    if (path == root or root.is_relative_to(path) or any(path.is_relative_to(root/name) for name in PAYLOAD_ROOTS)
            or path.parent == root and path.name.startswith('onboard') and path.suffix == '.py'):
        raise ValueError('The package destination overlaps packaged source files.')
    return path


def include(relative, is_directory):
    parts = relative.parts
    lower_parts = tuple(part.casefold() for part in parts)
    if BLOCKED.intersection(lower_parts) or any(lower_parts[i:i+2] == ('.config', 'gcloud') for i in range(len(parts)-1)):
        return False
    if parts[0] == '.agent':
        if len(parts) > 1 and parts[1] not in AGENT_CODE:
            return False
        if len(parts) > 2 and parts[1] == 'memory':
            if MEMORY_STATE.intersection(parts[2:]):
                return False
            if not is_directory and relative.suffix != '.py':
                # Keep structural configuration and schemas; unknown memory files stay private.
                if not (relative.suffix in {'.json', '.toml', '.yaml', '.yml'} and
                        (relative.stem in {'config', 'schema'} or relative.name.endswith('.schema.json')
                         or parts[2] in {'config', 'schemas'})):
                    return False
    name = relative.name.casefold()
    if not is_directory and (name.startswith('.env') or name == '.ds_store' or
            any(name == credential or name.startswith(credential+'.') for credential in CREDENTIAL_FILES) or
            relative.suffix.casefold() in KEY_SUFFIXES | {'.pyc', '.pyo', '.sqlite', '.sqlite3', '.db', '.zip', '.tar', '.gz', '.dmg', '.log'}):
        return False
    return True


def build(root, destination):
    root = Path(root).resolve(strict=True)
    destination = output_path(root, destination)
    # A fresh output prevents stale private files or destination symlinks surviving a rebuild.
    destination.mkdir(parents=True, exist_ok=False)
    names = [*PAYLOAD_ROOTS, *(p.name for p in sorted(root.glob('onboard*.py')))]
    for name in names:
        source = root/name
        if any((root/Path(*source.relative_to(root).parts[:i])).is_symlink()
               for i in range(1, len(source.relative_to(root).parts)+1)):
            continue
        if source.is_dir():
            paths = []
            for directory, dirs, files in os.walk(source, followlinks=False):
                parent = Path(directory)
                dirs[:] = sorted(d for d in dirs if not (parent/d).is_symlink()
                                 and include((parent/d).relative_to(root), True))
                paths.extend(parent/f for f in sorted(files))
        else:
            paths = [source]
        for path in paths:
            relative = path.relative_to(root)
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root) or not include(relative, False):
                continue
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target, follow_symlinks=False)
    for name, content in TEMPLATES.items():
        path = destination/'.agent/memory'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    print(build(Path(__file__).resolve().parents[1], parser.parse_args().output))
