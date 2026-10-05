"""Interactive, project-scoped PTYs over the authenticated control connection.

Output and keystrokes stay in bounded RAM, never in project memory or task logs.
The same transport works for the local desktop and a hosted Linux service.
"""
from __future__ import annotations

import base64
import binascii
from collections import OrderedDict
import errno
import fcntl
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
import uuid

from .agents import executable

SCROLLBACK = 2 * 1024 * 1024
CHUNK = 64 * 1024
MAX_SESSIONS = 12
STACK_COMMANDS = {
    'stack-dashboard': ('Stack dashboard', ['dashboard']),
    'stack-manage': ('Manage adapters', ['manage']),
    'stack-transfer': ('Transfer memory', ['transfer']),
    'stack-status': ('Stack status', ['status']),
    'stack-doctor': ('Project health', ['doctor']),
    'stack-upgrade': ('Preview upgrade', ['upgrade', '--dry-run']),
    'stack-brain': ('Brain status', ['brain', 'status']),
    'stack-onboard': ('Stack setup', []),
    'stack-brain-onboard': ('Connect Brain', ['brain', 'onboard']),
    'stack-brain-tui': ('Brain explorer', ['brain', 'tui']),
    'stack-brain-log': ('Brain history', ['brain', 'log']),
    'stack-brain-doctor': ('Brain health', ['brain', 'doctor']),
    'stack-brain-mcp': ('Brain MCP command', ['brain', 'mcp-command']),
    'stack-loop-status': ('Loop status', ['loop', 'status']),
    'stack-loop-validate': ('Validate loops', ['loop', 'validate']),
    'stack-manifest': ('Rebuild skill manifest', ['sync-manifest']),
}


def integer(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")
    return value


def request_id(p):
    value = p.get('requestId')
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise ValueError('A terminal request ID is required.')
    return value


class TerminalSession:
    def __init__(self, wid, kind, root, command, cols, rows):
        self.id = uuid.uuid4().hex
        self.wid, self.kind, self.root = wid, kind, str(root)
        self.condition = threading.Condition(threading.RLock())
        self.output = bytearray()
        self.offset = 0
        self.pending = bytearray()
        self.requests = OrderedDict()
        self.stopping = False
        self.finished = False
        self.exit_code = None
        self.cols, self.rows = cols, rows
        master, slave = os.openpty()
        self.master = master
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        env = os.environ.copy()
        for key in ('AGENTIC_CONTROL_TOKEN', 'AGENTIC_WORKSPACES_DATA', 'AGENTIC_STACK_ROOT',
                    'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT'):
            env.pop(key, None)
        env.update(TERM='xterm-256color', COLORTERM='truecolor', PYTHONDONTWRITEBYTECODE='1')
        env.setdefault('LANG', 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8')
        # Use an absolute helper path: the selected project is the child's cwd.
        helper = str(Path(__file__).with_name('terminal_child.py'))
        try:
            self.process = subprocess.Popen([sys.executable, helper, *command], cwd=root,
                stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
        except BaseException:
            os.close(master)
            raise
        finally:
            os.close(slave)
        os.set_blocking(master, False)
        self.thread = threading.Thread(target=self._pump, daemon=True, name='terminal-' + self.id[:8])
        self.thread.start()

    def summary(self):
        with self.condition:
            return {'id': self.id, 'workspaceId': self.wid, 'kind': self.kind, 'path': self.root,
                    'status': 'exited' if self.finished else 'closing' if self.stopping else 'running',
                    'exitCode': self.exit_code, 'cols': self.cols, 'rows': self.rows}

    def _append(self, data):
        with self.condition:
            self.output.extend(data)
            excess = max(0, len(self.output) - SCROLLBACK)
            if excess:
                del self.output[:excess]
                self.offset += excess
            self.condition.notify_all()

    def _pump(self):
        try:
            while not self.stopping:
                with self.condition:
                    writable = bool(self.pending)
                readable, ready, _ = select.select([self.master], [self.master] if writable else [], [], 0.03)
                if readable:
                    try:
                        data = os.read(self.master, CHUNK)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    self._append(data)
                if ready:
                    with self.condition:
                        try:
                            count = os.write(self.master, self.pending[:16384])
                            del self.pending[:count]
                        except BlockingIOError:
                            pass
                if not readable and self.process.poll() is not None:
                    break
        except OSError:
            pass  # A closed PTY is an ordinary session exit.
        finally:
            self._stop_processes()
            os.close(self.master)
            with self.condition:
                self.pending.clear()
                self.exit_code = self.process.poll()
                self.finished = True
                self.condition.notify_all()

    def _session_pids(self):
        """Include shell job-control groups, which differ from the leader's group."""
        try:
            if sys.platform.startswith('linux'):
                # Minimal hosted images need no optional procps package for cleanup.
                candidates = (entry.name for entry in Path('/proc').iterdir() if entry.name.isdecimal())
            else:
                result = subprocess.run(['/bin/ps', '-axo', 'pid='], capture_output=True, text=True, timeout=2)
                candidates = result.stdout.split()
            members = []
            for item in candidates:
                try:
                    pid = int(item)
                    if pid != os.getpid() and os.getsid(pid) == self.process.pid:
                        members.append(pid)
                except (OSError, ValueError):
                    continue
            return members
        except (OSError, subprocess.TimeoutExpired):
            return []

    def _stop_processes(self):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in self._session_pids():
                try:
                    # Recheck before signalling; do not act on a recycled unrelated PID.
                    if os.getsid(pid) == self.process.pid:
                        os.kill(pid, sig)
                except ProcessLookupError:
                    pass
            if self.process.poll() is None:
                try:
                    self.process.send_signal(sig)  # Also covers helper startup before setsid.
                except ProcessLookupError:
                    pass
            if sig == signal.SIGTERM:
                time.sleep(0.15)
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    def read(self, cursor):
        integer(cursor, 'Cursor', 0, 2**53 - 1)
        with self.condition:
            end = self.offset + len(self.output)
            if cursor > end:
                raise ValueError('Terminal cursor is ahead of the session.')
            self.condition.wait_for(lambda: cursor < self.offset + len(self.output) or self.finished, timeout=1)
            start = max(cursor, self.offset)
            data = self.output[start - self.offset:start - self.offset + CHUNK]
            return {'data': base64.b64encode(data).decode(), 'cursor': start + len(data),
                    'dropped': cursor < self.offset, 'session': self.summary()}

    def write(self, p):
        rid = request_id(p)
        encoded = p.get('data')
        if not isinstance(encoded, str) or len(encoded) > 24000:
            raise ValueError('Terminal input is too large.')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError('Terminal input must be base64 bytes.') from error
        with self.condition:
            if rid in self.requests:
                return {'accepted': True}
            if self.finished or self.stopping:
                raise ValueError('This terminal has exited. Open a new terminal.')
            if len(self.pending) + len(data) > CHUNK:
                raise ValueError('Terminal input is still draining. Wait before pasting more text.')
            self.pending.extend(data)
            self.requests[rid] = True
            if len(self.requests) > 2048:
                self.requests.popitem(last=False)
        return {'accepted': True}

    def resize(self, cols, rows):
        integer(cols, 'Columns', 2, 500)
        integer(rows, 'Rows', 2, 200)
        with self.condition:
            if not self.finished and not self.stopping:
                fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
                self.cols, self.rows = cols, rows
        return self.summary()

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        self.thread.join(timeout=6)


class TerminalManager:
    def __init__(self, store, stack):
        self.store, self.stack = store, stack
        self.sessions = {}
        self.creations = OrderedDict()
        self.lock = threading.RLock()
        self.closed = False

    def dispatch(self, method, p):
        wid = p.get('workspaceId')
        workspace = self.store.get('workspace', wid)
        if workspace['provider'] != 'local':
            raise ValueError('Terminals need a project on this Mac or a connected stack server.')
        root = self.stack.root(wid)  # Enforce the hosted project-root boundary on every call.
        if method == 'terminal.list':
            with self.lock:
                return {'sessions': [s.summary() for s in self.sessions.values() if s.wid == wid]}
        if method == 'terminal.create':
            rid = request_id(p)
            kind = p.get('kind', 'shell')
            if kind not in {'shell', 'codex', 'claude-code', *STACK_COMMANDS}:
                raise ValueError('Choose an agent, shell or supported stack command.')
            command = ['/bin/zsh' if sys.platform == 'darwin' else '/bin/bash', '-l']
            if kind in STACK_COMMANDS:
                command = [sys.executable, '-I', str(Path(__file__).with_name('terminal_cli.py')), *STACK_COMMANDS[kind][1]]
            elif kind != 'shell':
                binary = executable(kind)
                if not binary:
                    raise ValueError(f'{kind} is not installed on this host. Install it, then open a terminal again.')
                command = [binary]
            cols = integer(p.get('cols', 100), 'Columns', 2, 500)
            rows = integer(p.get('rows', 30), 'Rows', 2, 200)
            with self.lock:
                if self.closed:
                    raise ValueError('The terminal service is shutting down.')
                key = (wid, rid)
                if key in self.creations:
                    existing = self.sessions.get(self.creations[key])
                    if existing is None:
                        raise ValueError('This terminal was already closed. Start a new session.')
                    return existing.summary()
                if len(self.sessions) >= MAX_SESSIONS:
                    raise ValueError('Close a terminal before opening another (12 per host).')
                session = TerminalSession(wid, kind, root, command, cols, rows)
                self.sessions[session.id] = session
                self.creations[key] = session.id
                if len(self.creations) > 2048:
                    self.creations.popitem(last=False)
                return session.summary()
        with self.lock:
            session = self.sessions.get(p.get('id'))
            if session is None or session.wid != wid:
                raise ValueError('Terminal session not found for this project. Refresh the terminal list.')
        if method == 'terminal.read':
            return session.read(p.get('cursor', 0))
        if method == 'terminal.write':
            return session.write(p)
        if method == 'terminal.resize':
            return session.resize(p.get('cols'), p.get('rows'))
        if method == 'terminal.close':
            session.close()
            with self.lock:
                self.sessions.pop(session.id, None)
            return {'closed': True}
        raise ValueError('Unknown terminal operation.')

    def close(self):
        with self.lock:
            self.closed = True
            sessions = list(self.sessions.values())
        for session in sessions:
            session.close()
