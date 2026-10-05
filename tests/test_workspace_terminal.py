import base64
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

import pytest

from harness_manager.workspaces import terminal
from harness_manager.workspaces.server import make_server
from harness_manager.workspaces.service import WorkspaceService


@pytest.fixture
def service(tmp_path, monkeypatch):
    real_session = terminal.TerminalSession

    def clean_shell(wid, kind, root, command, cols, rows):
        if kind == 'shell':
            command = ['/bin/bash', '--noprofile', '--norc', '-i']
        return real_session(wid, kind, root, command, cols, rows)

    monkeypatch.setattr(terminal, 'TerminalSession', clean_shell)
    result = WorkspaceService(tmp_path/'data', project_root=tmp_path)
    yield result
    result.close()


def create(service):
    ws = service.create_workspace({'name': 'Terminal test', 'goal': 'Verify PTY'})
    params = {'workspaceId': ws['id'], 'requestId': uuid.uuid4().hex, 'kind': 'shell', 'cols': 111, 'rows': 37}
    session = service.dispatch('terminal.create', params)
    return params, session


def send(service, session, data, rid=None):
    return service.dispatch('terminal.write', {'workspaceId': session['workspaceId'], 'id': session['id'],
        'requestId': rid or uuid.uuid4().hex, 'data': base64.b64encode(data).decode()})


def until(service, session, marker, cursor=0):
    data = bytearray()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        output = service.dispatch('terminal.read', {'workspaceId': session['workspaceId'], 'id': session['id'], 'cursor': cursor})
        cursor = output['cursor']
        data.extend(base64.b64decode(output['data']))
        if marker in data:
            return bytes(data), cursor
        if output['session']['status'] == 'exited' and not output['data']:
            break
    raise AssertionError(f'Terminal did not produce marker; received {data[-2000:]!r}')


def python_command(code):
    return (shlex.quote(sys.executable) + ' -c ' + shlex.quote(code) + '\r').encode()


def test_real_tty_cwd_resize_unicode_and_control_token_not_inherited(service, monkeypatch):
    monkeypatch.setenv('AGENTIC_CONTROL_TOKEN', 'private-test-control-token')
    _, session = create(service)
    send(service, session, b'stty -echo\r')
    code = "import os,json; print('PROOF'+json.dumps([os.getcwd(),[os.isatty(i) for i in range(3)],os.getpgrp()==os.tcgetpgrp(0),os.get_terminal_size().columns,os.get_terminal_size().lines,'AGENTIC_CONTROL_TOKEN' in os.environ])); print(chr(27)+'[31m'+chr(955)+chr(27)+'[0m')"
    send(service, session, python_command(code))
    data, cursor = until(service, session, b'\x1b[31m\xce\xbb\x1b[0m')
    proof = data.split(b'PROOF')[-1].split(b'\r\n')[0]
    assert json.loads(proof) == [str(Path(session['path']).resolve()), [True]*3, True, 111, 37, False]
    service.dispatch('terminal.resize', dict(workspaceId=session['workspaceId'], id=session['id'], cols=88, rows=22))
    send(service, session, b'stty size\r')
    until(service, session, b'22 88', cursor)


def test_ctrl_c_returns_to_shell_and_close_kills_background_job(service, tmp_path):
    _, session = create(service)
    pidfile = tmp_path/'job.pid'
    send(service, session, b'stty -echo\r')
    send(service, session, f'sleep 120 & echo $! > {shlex.quote(str(pidfile))}; sleep 120\r'.encode())
    deadline = time.monotonic() + 5
    while not pidfile.exists() and time.monotonic() < deadline:
        time.sleep(.03)
    pid = int(pidfile.read_text())
    os.kill(pid, 0)
    send(service, session, b'\x03')
    time.sleep(.1)
    send(service, session, b"printf 'RETURN%s\\n' ED\r")
    until(service, session, b'RETURNED')
    service.dispatch('terminal.close', {'workspaceId': session['workspaceId'], 'id': session['id']})
    result = subprocess.run(['/bin/ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
    assert not result.stdout.strip() or result.stdout.lstrip().startswith('Z')


def test_create_and_input_deduplicate_without_cross_project_access(service, tmp_path):
    params, session = create(service)
    assert service.dispatch('terminal.create', params)['id'] == session['id']
    path = tmp_path/'once.txt'
    command = f'printf x >> {shlex.quote(str(path))}; printf "DONE%s\\n" ONCE\r'.encode()
    send(service, session, command, rid='same-request')
    send(service, session, command, rid='same-request')
    until(service, session, b'DONEONCE')
    assert path.read_text() == 'x'
    other = service.create_workspace({'name': 'Other', 'goal': 'Keep separate'})
    for method in ('read', 'write', 'resize', 'close'):
        with pytest.raises(ValueError, match='not found for this project'):
            service.dispatch('terminal.' + method, dict(workspaceId=other['id'], id=session['id']))
    service.dispatch('terminal.close', dict(workspaceId=session['workspaceId'], id=session['id']))
    with pytest.raises(ValueError, match='already closed'):
        service.dispatch('terminal.create', params)


def test_bounded_output_replays_in_chunks_and_reports_trim(service, monkeypatch):
    monkeypatch.setattr(terminal, 'SCROLLBACK', 100000)
    _, session = create(service)
    live = service.terminals.sessions[session['id']]
    send(service, session, b'stty -echo\r')
    time.sleep(.1)
    live._append(b'a'*150000)
    first = live.read(0)
    assert first['dropped'] is True
    assert len(base64.b64decode(first['data'])) == terminal.CHUNK
    second = live.read(first['cursor'])
    assert second['dropped'] is False
    assert len(base64.b64decode(second['data'])) == 100000-terminal.CHUNK
    assert len(live.output) <= 100000


def test_invalid_requests_and_missing_agents_fail_before_launch(service, monkeypatch):
    params, session = create(service)
    for extra in ({'cols': True}, {'rows': 0}, {'kind': 'arbitrary'}, {'requestId': ''}):
        with pytest.raises(ValueError):
            service.dispatch('terminal.create', dict(params, requestId=uuid.uuid4().hex, **extra) if 'requestId' not in extra else dict(params, **extra))
    monkeypatch.setattr(terminal, 'executable', lambda _: None)
    with pytest.raises(ValueError, match='not installed'):
        service.dispatch('terminal.create', dict(params, kind='codex', requestId=uuid.uuid4().hex))
    with pytest.raises(ValueError, match='base64'):
        service.dispatch('terminal.write', dict(workspaceId=session['workspaceId'], id=session['id'], requestId='bad', data='!!!'))


@pytest.mark.parametrize('kind,marker', [
    ('stack-manage', b'what do you want to do?'),
    ('stack-transfer', b'What do you want to transfer?'),
    ('stack-status', b'no install.json'),
])
def test_stack_commands_use_interactive_bundled_cli(service, kind, marker):
    ws = service.create_workspace({'name': 'Bundled commands', 'goal': 'Verify stack tools'})
    project = service.stack.root(ws['id'])
    # A project module must not replace the bundled CLI used by these buttons.
    shadow = project/'harness_manager'
    shadow.mkdir()
    (shadow/'__init__.py').write_text("raise RuntimeError('PROJECT MODULE SHADOWED THE BUNDLE')")
    session = service.dispatch('terminal.create', {'workspaceId': ws['id'], 'kind': kind, 'requestId': uuid.uuid4().hex})
    data, _ = until(service, session, marker)
    assert b'PROJECT MODULE SHADOWED' not in data
    assert b'not a TTY' not in data
    assert b'ModuleNotFoundError' not in data


def test_authenticated_remote_rpc_round_trip_and_no_terminal_output_in_snapshot(service):
    server = make_server(service, 'test-control-'*4)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def rpc(method, params, token='test-control-'*4):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/rpc',
            data=json.dumps({'method': method, 'params': params}).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)['result']

    try:
        ws = service.create_workspace({'name': 'Remote terminal', 'goal': 'Round trip'})
        p = {'workspaceId': ws['id'], 'requestId': uuid.uuid4().hex}
        with pytest.raises(urllib.error.HTTPError) as exc:
            rpc('terminal.create', p, token='wrong')
        assert exc.value.code == 401
        session = rpc('terminal.create', p)
        params = {'workspaceId': ws['id'], 'id': session['id']}
        rpc('terminal.write', dict(params, requestId=uuid.uuid4().hex,
            data=base64.b64encode(b"printf 'PRIVATE%s\\n' OUTPUT\r").decode()))
        output = b''
        cursor = 0
        for _ in range(10):
            chunk = rpc('terminal.read', dict(params, cursor=cursor))
            cursor = chunk['cursor']
            output += base64.b64decode(chunk['data'])
            if b'PRIVATEOUTPUT' in output:
                break
        assert b'PRIVATEOUTPUT' in output
        assert 'PRIVATEOUTPUT' not in json.dumps(service.snapshot())
        assert rpc('terminal.list', {'workspaceId': ws['id']})['sessions'][0]['id'] == session['id']
        assert rpc('terminal.close', params)['closed']
    finally:
        server.shutdown()
        server.server_close()
