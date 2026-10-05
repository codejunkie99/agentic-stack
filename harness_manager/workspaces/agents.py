"""Detect installed harnesses and delegate sign-in to their official CLIs."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AGENTS = {'codex': 'Codex', 'claude-code': 'Claude Code'}


def executable(agent):
    if agent not in AGENTS:
        raise ValueError('Choose Codex or Claude Code.')
    binary = 'claude' if agent == 'claude-code' else 'codex'
    path = shutil.which(binary)
    if path:
        return path
    for root in [Path.home()/'.local/bin', Path('/opt/homebrew/bin'), Path('/usr/local/bin')]:
        candidate = root / binary
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


class AgentAccounts:
    def __init__(self, root):
        self.root = root
        self.cached = []
        self.checked = 0
        self.lock = threading.Lock()

    def detect(self, agent):
        path = executable(agent)
        row = {'id': agent, 'name': AGENTS[agent], 'path': path or '', 'installed': bool(path),
               'signedIn': False, 'version': '', 'status': 'Not installed'}
        if not path:
            return row
        try:
            version = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5)
            row['version'] = version.stdout.strip()[:100]
            command = ['auth', 'status', '--json'] if agent == 'claude-code' else ['login', 'status']
            auth = subprocess.run([path, *command], capture_output=True, text=True, timeout=8)
            if agent == 'claude-code':
                # Never return account identifiers, token contents, or raw auth output.
                row['signedIn'] = json.loads(auth.stdout).get('loggedIn') is True
            else:
                row['signedIn'] = auth.returncode == 0
            row['status'] = 'Signed in' if row['signedIn'] else 'Sign in to continue'
        except (OSError, subprocess.TimeoutExpired, ValueError):
            row['status'] = 'Installed · sign-in status unavailable'
        return row

    def snapshot(self, force=False):
        with self.lock:
            if not force and self.cached and time.monotonic() - self.checked < 30:
                return self.cached
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.cached = list(pool.map(self.detect, AGENTS))
            self.checked = time.monotonic()
            return self.cached

    def login_script(self, agent):
        path = executable(agent)
        if not path:
            raise ValueError('Install the official CLI, then refresh detected agents.')
        root = self.root / 'sign-in'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        script = root / (agent + '-sign-in.command')
        arguments = ['auth', 'login'] if agent == 'claude-code' else ['login']
        script.write_text('#!/bin/zsh\n' + shlex.join([path, *arguments]) + '\n')
        script.chmod(0o700)
        self.checked = 0
        return {'path': str(script)}
