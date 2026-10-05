#!/usr/bin/env python3
"""Verify Codex's actual container sandbox without login or model API requests."""
import errno
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile


def must_deny(operation, description):
    try:
        operation()
    except OSError as exc:
        if exc.errno in {errno.EPERM, errno.EACCES, errno.EROFS}:
            return
        raise RuntimeError(f'{description}: unexpected error {exc.errno}') from exc
    raise RuntimeError(f'{description}: unexpectedly allowed')


def probe(mode, root):
    project = root / 'project'
    assert (root / 'other/source.txt').read_text() == 'readable reference'
    if mode == 'workspace-write':
        (project / 'allowed.txt').write_text('project edit')
    else:
        must_deny(lambda: (project / 'allowed.txt').write_text('blocked'), 'read-only project write')
    for target in [root / 'other/blocked.txt', project / '.git/config', project / '.codex/config.toml']:
        must_deny(lambda: target.write_text('blocked'), f'protected write to {target.name}')
    def connect():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            channel.settimeout(2)
            channel.connect(('1.1.1.1', 443))
    must_deny(connect, 'direct network access')
    print(f'PASS {mode}: filesystem boundaries and network denial')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--probe':
        if sys.argv[2] not in {'read-only', 'workspace-write'}:
            raise ValueError('Unknown sandbox mode')
        probe(sys.argv[2], Path(sys.argv[3]))
        return
    if os.getuid() == 0:
        raise RuntimeError('The service must run as a non-root user')
    status = Path('/proc/self/status').read_text()
    fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    assert fields['NoNewPrivs'].strip() == '1', 'no-new-privileges is not enabled'
    assert fields['Seccomp'].strip() == '2', 'container seccomp filtering is not enabled'
    assert int(fields['CapEff'].strip(), 16) == 0, 'service has effective capabilities'
    label = Path('/proc/self/attr/current').read_text().strip()
    assert label == 'agentic-stack-bwrap (enforce)', 'named AppArmor profile is not enforced'
    print('PASS non-root service, no-new-privileges, seccomp and named AppArmor', flush=True)
    with tempfile.TemporaryDirectory(prefix='sandbox-check-', dir='/data/projects') as folder:
        root = Path(folder)
        project = root / 'project'
        for directory in [project / '.git', project / '.codex', root / 'other']:
            directory.mkdir(parents=True)
        (root / 'other/source.txt').write_text('readable reference')
        (project / '.git/config').write_text('# original')
        (project / '.codex/config.toml').write_text('# original')
        for mode in ['read-only', 'workspace-write']:
            result = subprocess.run(['codex', 'sandbox', '-c', f'sandbox_mode="{mode}"',
                                     '--', sys.executable, str(Path(__file__).resolve()), '--probe', mode, str(root)],
                                    cwd=project, capture_output=True, text=True, timeout=20)
            if result.returncode != 0:
                raise RuntimeError(f'{mode} sandbox failed: {result.stderr[-2000:]}')
            print(result.stdout.strip(), flush=True)
        assert (project / '.git/config').read_text() == '# original'
        assert (project / '.codex/config.toml').read_text() == '# original'
    print('Sandbox preflight passed. No account login or model request was made.')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f'Sandbox preflight failed: {exc}', file=sys.stderr)
        sys.exit(1)
