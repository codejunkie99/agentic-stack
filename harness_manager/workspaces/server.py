"""Authenticated private HTTP bridge for the native app. Stdlib only."""
from __future__ import annotations

import argparse
import fcntl
import hmac
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .box import ProviderError
from .service import WorkspaceService

# Multimodal conversation attachments are base64 encoded and capped at 24 MB
# before encoding by attachments.py. Leave room for JSON framing and prompts.
MAX_BODY = 34_000_000


def make_server(service, token, port=0, host="127.0.0.1"):
    if len(token) < 32:
        raise ValueError("Control token must have at least 32 characters.")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Request bodies and credentials never enter logs.

        def reply(self, status, value):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if self.path != "/rpc":
                return self.reply(404, {"ok": False, "error": "Unknown endpoint."})
            if self.headers.get("Origin"):
                return self.reply(403, {"ok": False, "error": "Browser requests are not accepted."})
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return self.reply(401, {"ok": False, "error": "Authentication required."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self.reply(413, {"ok": False, "error": "Request is too large or empty."})
                self.connection.settimeout(15)
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict) or not isinstance(request.get("method"), str):
                    raise ValueError("Invalid request.")
                result = service.dispatch(request["method"], request.get("params", {}))
                return self.reply(200, {"ok": True, "result": result})
            except (ValueError, TypeError, ProviderError) as exc:
                return self.reply(400, {"ok": False, "error": str(exc)[:4000]})
            except Exception:
                return self.reply(500, {"ok": False, "error": "The operation failed. Refresh the workspace to check its state before retrying."})

    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Agentic Stack desktop backend locally or behind an HTTPS proxy.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--allow-network", action="store_true", help="Allow a network bind behind a TLS reverse proxy")
    parser.add_argument("--token-file", type=Path, help="Read the control token from a private file")
    parser.add_argument("--project-root", type=Path, help="Restrict attached projects to this server directory")
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"} and not args.allow_network:
        parser.error("A network bind requires --allow-network and an HTTPS reverse proxy.")
    token = os.environ.pop("AGENTIC_CONTROL_TOKEN", "")
    if args.token_file:
        token = args.token_file.read_text().strip()
    if len(token) < 32:
        parser.error("Provide a control token of at least 32 characters using --token-file or AGENTIC_CONTROL_TOKEN.")
    args.data_root = args.data_root.resolve()
    args.data_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (args.data_root / "service.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another workspace service is using this data directory.")
    service = WorkspaceService(args.data_root, project_root=args.project_root)
    server = make_server(service, token, args.port, args.host)
    stopped = threading.Event()

    def stop(*_):
        if not stopped.is_set():
            stopped.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def watch_parent():
        while not stopped.wait(2):
            try:
                os.kill(args.parent_pid, 0)
            except ProcessLookupError:
                stop()

    if args.parent_pid:
        threading.Thread(target=watch_parent, daemon=True).start()
    print(json.dumps({"port": server.server_port}), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        stopped.set()
        service.close()
        server.server_close()
        lock.close()


if __name__ == "__main__":
    main()
