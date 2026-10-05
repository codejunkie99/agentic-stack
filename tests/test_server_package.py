import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('domain', ['bad..example.com', '-bad.example.com', 'https://example.com', 'bad/example.com'])
def test_deployment_config_rejects_invalid_dns_names(tmp_path, domain):
    shutil.copy2(ROOT/'deploy/agentic-stack/configure.py', tmp_path/'configure.py')
    result = subprocess.run([sys.executable, str(tmp_path/'configure.py'), domain], capture_output=True, text=True)
    assert result.returncode != 0
    assert not (tmp_path/'.env').exists()


def test_deployment_config_does_not_print_or_replace_token(tmp_path):
    shutil.copy2(ROOT/'deploy/agentic-stack/configure.py', tmp_path/'configure.py')
    command = [sys.executable, str(tmp_path/'configure.py'), 'stack.example.com']
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0
    raw = (tmp_path/'.env').read_text()
    token = raw.split('AGENTIC_CONTROL_TOKEN=')[1].strip()
    assert len(token) >= 32 and token not in first.stdout+first.stderr
    assert (tmp_path/'.env').stat().st_mode & 0o777 == 0o600
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert (tmp_path/'.env').read_text() == raw


def test_server_package_is_self_contained_and_boots_without_checkout(tmp_path):
    package = tmp_path/'server.zip'
    subprocess.run([sys.executable, str(ROOT/'scripts/build-server-package.py'), str(package)], check=True, capture_output=True)
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert not any('/.env' in n or '/runtime/' in n or n.endswith(('.pyc', '.sqlite3')) for n in names)
        assert 'agentic-stack/onboard_widgets.py' in names
        assert 'agentic-stack/onboard_ui.py' in names
        assert 'agentic-stack/onboard.py' in names
        archive.extractall(tmp_path/'unpacked')
    extracted = tmp_path/'unpacked/agentic-stack'
    code = '''
from pathlib import Path
from harness_manager.workspaces.service import WorkspaceService
import onboard, onboard_widgets, onboard_ui
from harness_manager import manage_tui, transfer_tui
s=WorkspaceService(Path('../test-data'))
w=s.create_workspace({'name':'Packaged server','goal':'Verify standalone runtime'})
s.stack.initialize(w['id'])
assert s.stack.snapshot(w['id'])['initialized']
assert s.knowledge.query({'workspaceId':w['id']})['total']==0
assert s.dispatch('system.health',{})['status']=='ok'
s.close()
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=extracted,
                            env=dict(os.environ, PYTHONPATH=str(extracted)), capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def payload_checkout(tmp_path):
    checkout = tmp_path/'checkout'
    scripts = checkout/'scripts'
    scripts.mkdir(parents=True)
    for name in ['package_payload.py', 'build-server-package.py']:
        shutil.copy2(ROOT/'scripts'/name, scripts/name)
    code = {
        'harness_manager/__init__.py': '# Package code\n',
        'adapters/codex/adapter.json': '{}\n',
        '.agent/AGENTS.md': '# Agent protocol\n',
        '.agent/harness/context_budget.py': '# Context code\n',
        '.agent/memory/memory_search.py': '# Search code\n',
        '.agent/memory/archive.py': '# Archive code, not archived data\n',
        '.agent/memory/config.json': '{"limit": 20}\n',
        '.agent/memory/schemas/note.schema.json': '{"type": "object"}\n',
        '.agent/skills/data-layer/SKILL.md': '# Export skill\n',
        '.agent/skills/data-flywheel/SKILL.md': '# Flywheel skill\n',
        '.agent/skills/_manifest.jsonl': '{}\n',
        '.agent/protocols/permissions.md': '# Permissions\n',
        'deploy/agentic-stack/README.md': '# Hosting\n',
        'onboard.py': '# Onboarding code\n',
        'LICENSE': 'License\n',
        'NOTICE': 'Notice\n',
        '.dockerignore': '.git\n',
    }
    private = [
        '.agent/memory/personal/PREFERENCES.md', '.agent/memory/working/WORKSPACE.md',
        '.agent/memory/working/REVIEW_QUEUE.md', '.agent/memory/semantic/DECISIONS.md',
        '.agent/memory/semantic/DOMAIN_KNOWLEDGE.md', '.agent/memory/semantic/LESSONS.md',
        '.agent/memory/semantic/lessons.jsonl', '.agent/memory/semantic/private.md',
        '.agent/memory/episodic/AGENT_LEARNINGS.jsonl', '.agent/memory/candidates/graduated/note.json',
        '.agent/memory/archives/history.md', '.agent/memory/index/search.sqlite3',
        '.agent/memory/private-export.json', '.agent/runtime/run.json', '.agent/data-layer/export.json',
        '.agent/flywheel/export.jsonl', '.agent/index/index.json', '.agent/cache/cache.json',
        '.agent/archives/export.md', '.agent/private-export.md', 'adapters/codex/.env',
        'deploy/agentic-stack/.env.local', 'harness_manager/__pycache__/code.pyc',
        '.agent/tools/runner/.npmrc', '.agent/tools/id_ed25519', 'deploy/agentic-stack/tls/server.key',
        'adapters/codex/.pypirc', '.agent/tools/runner/.netrc', '.agent/tools/.git-credentials',
        'deploy/agentic-stack/tls/private.PEM', 'adapters/codex/signing.p12',
        '.agent/tools/runner/.npmrc.backup', '.agent/tools/id_rsa.pub',
        '.agent/tools/runner/.ssh/config', '.agent/tools/runner/.aws/config',
        '.agent/tools/runner/.config/gcloud/application_default_credentials.json',
        'adapters/codex/.ENV.PROD',
    ]
    for name, content in {**code, **{name: 'PRIVATE_PACKAGING_SENTINEL\n' for name in private}}.items():
        path = checkout/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (checkout/'onboard.py').chmod(0o755)
    return checkout, code


def test_app_payload_and_server_archive_share_sanitized_memory(payload_checkout, tmp_path):
    checkout, code = payload_checkout
    outside = tmp_path/'private'
    outside.mkdir()
    (outside/'secret.md').write_text('SYMLINK_PRIVATE_SENTINEL')
    (checkout/'.agent/skills/external').symlink_to(outside, target_is_directory=True)
    (checkout/'.agent/skills/internal-alias').symlink_to(checkout/'.agent/skills/data-layer', target_is_directory=True)
    (checkout/'.agent/memory/schemas/leak.schema.json').symlink_to(outside/'secret.md')
    before = {p.relative_to(checkout): p.read_bytes() for p in checkout.rglob('*') if p.is_file() and not p.is_symlink()}
    app_payload = tmp_path/'Agentic Stack.app/Contents/Resources/agentic-stack'
    package = checkout/'dist/server.zip'
    subprocess.run([sys.executable, str(checkout/'scripts/package_payload.py'), str(app_payload)], check=True, capture_output=True)
    command = [sys.executable, str(checkout/'scripts/build-server-package.py'), str(package)]
    subprocess.run(command, check=True, capture_output=True)
    subprocess.run(command, check=True, capture_output=True)  # Existing output must not become input.
    staged = {p.relative_to(app_payload).as_posix(): p.read_bytes() for p in app_payload.rglob('*') if p.is_file()}
    assert not any(p.is_symlink() for p in app_payload.rglob('*'))
    with zipfile.ZipFile(package) as archive:
        assert all(name.startswith('agentic-stack/') and '..' not in Path(name).parts for name in archive.namelist())
        archived = {name.removeprefix('agentic-stack/'): archive.read(name) for name in archive.namelist()}
    archived.pop('START-HERE.md')
    assert staged == archived
    assert not any(b'PRIVATE_PACKAGING_SENTINEL' in value or b'SYMLINK_PRIVATE_SENTINEL' in value for value in staged.values())
    assert {name: staged[name].decode() for name in code} == code
    assert staged['.agent/memory/episodic/AGENT_LEARNINGS.jsonl'] == b''
    assert staged['.agent/memory/semantic/lessons.jsonl'] == b''
    assert b'## Auto-promoted entries will be appended below' in staged['.agent/memory/semantic/LESSONS.md']
    assert os.access(app_payload/'onboard.py', os.X_OK)
    assert all((checkout/name).read_bytes() == value for name, value in before.items())
    assert not any('server.zip' in name or 'external/' in name or 'internal-alias/' in name for name in staged)


def test_distribution_license_boundary_is_explicit():
    project_notice = (ROOT/'NOTICE').read_text()
    normalized_notice = ' '.join(project_notice.split())
    desktop_notices = (ROOT/'apps/macos/THIRD-PARTY-NOTICES.md').read_text()
    assert 'Copyright 2026 Avidlive' in project_notice
    assert 'third-party software that remains under its own license' in normalized_notice
    assert 'SwiftTerm 1.19.0' in desktop_notices
    assert 'Sparkle 2.9.6' in desktop_notices
    assert 'bspatch.c and bsdiff.c' in desktop_notices


@pytest.mark.parametrize('destination', ['.agent/export', 'harness_manager/export', 'adapters/../.agent/export', '.', 'onboard-export.py'])
def test_packaging_rejects_outputs_overlapping_source(payload_checkout, destination):
    checkout, _ = payload_checkout
    for script in ['package_payload.py', 'build-server-package.py']:
        result = subprocess.run([sys.executable, str(checkout/'scripts'/script), str(checkout/destination)], capture_output=True, text=True)
        assert result.returncode != 0
        assert 'overlaps packaged source' in result.stderr
    assert not (checkout/'.agent/export').exists()
    assert not (checkout/'harness_manager/export').exists()
    assert not (checkout/'onboard-export.py').exists()


def test_packaging_refuses_symlink_outputs_and_existing_payloads(payload_checkout, tmp_path):
    checkout, _ = payload_checkout
    target = tmp_path/'keep.txt'
    target.write_text('Keep existing data')
    link = tmp_path/'output.zip'
    link.symlink_to(target)
    for script in ['package_payload.py', 'build-server-package.py']:
        result = subprocess.run([sys.executable, str(checkout/'scripts'/script), str(link)], capture_output=True, text=True)
        assert result.returncode != 0 and 'symbolic link' in result.stderr
    assert target.read_text() == 'Keep existing data'
    existing = tmp_path/'payload'
    existing.mkdir()
    (existing/'private.txt').write_text('Do not delete')
    result = subprocess.run([sys.executable, str(checkout/'scripts/package_payload.py'), str(existing)], capture_output=True)
    assert result.returncode != 0
    assert (existing/'private.txt').read_text() == 'Do not delete'
