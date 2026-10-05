#!/usr/bin/env python3
"""Compile the real Swift bridge and test it against a live private RPC server."""
import os
import secrets
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness_manager.workspaces.server import make_server
from harness_manager.workspaces.service import WorkspaceService


def main():
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp)/'connection-check'
        sources = ROOT/'apps/macos/Sources/AgenticWorkspaces'
        subprocess.run(['swiftc', '-parse-as-library', '-o', str(binary), str(ROOT/'scripts/check-desktop-connection.swift'),
                        *[str(sources/name) for name in ['Bridge.swift', 'Models.swift', 'Keychain.swift']]], check=True, timeout=120)
        service = WorkspaceService(Path(tmp)/'data')
        token = secrets.token_urlsafe(48)
        server = make_server(service, token)
        destination_requests = []

        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                if self.path == '/rpc':
                    self.send_response(307)
                    self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/destination')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                else:
                    destination_requests.append(True)
                    self.send_response(500)
                    self.end_headers()

        redirect = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        for item in [server, redirect]:
            threading.Thread(target=item.serve_forever, daemon=True).start()
        try:
            env = dict(os.environ, STACK_TEST_URL=f'http://127.0.0.1:{server.server_port}', STACK_TEST_TOKEN=token,
                       STACK_TEST_REDIRECT=f'http://127.0.0.1:{redirect.server_port}')
            subprocess.run([str(binary)], env=env, check=True, timeout=60)
            if destination_requests:
                raise AssertionError('Swift forwarded a request to the redirect destination')
            print('PASS: redirect destination received zero requests')
        finally:
            for item in [server, redirect]:
                item.shutdown()
                item.server_close()
            service.close()


if __name__ == '__main__':
    main()
