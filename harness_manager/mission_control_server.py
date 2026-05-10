"""HTTP server for the local Mission Control web UI."""
from __future__ import annotations

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .mission_control_collectors import API_PATHS, build_payloads, record_ops_event
from .mission_control_render import render_page


def write_snapshot(target_root: Path | str, stack_root: Path | str, output: Path | str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(target_root, stack_root), encoding="utf-8")
    return path


def serve(
    target_root: Path | str,
    stack_root: Path | str,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = False,
) -> int:
    handler = _handler_for(Path(target_root).resolve(), Path(stack_root).resolve())
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/"
    print(f"mission control: {url}")
    print(f"project: {Path(target_root).resolve()}")
    print("press Ctrl-C to stop")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


def run(
    target_root: Path | str,
    stack_root: Path | str,
    host: str = "127.0.0.1",
    port: int = 8787,
    snapshot: Path | str | None = None,
    open_browser: bool = False,
) -> int:
    if snapshot is not None:
        path = write_snapshot(target_root, stack_root, snapshot)
        print(f"mission control snapshot: {path}")
        return 0
    return serve(target_root, stack_root, host=host, port=port, open_browser=open_browser)


def _handler_for(target_root: Path, stack_root: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path in ("/", "/index.html"):
                self._send_html(render_page(target_root, stack_root))
                return
            if path in API_PATHS:
                payload = build_payloads(target_root, stack_root)[path]
                self._send_json(payload)
                return
            if path == "/healthz":
                self._send_json({"ok": True})
                return
            self._send_json({"error": "not found", "path": path}, status=404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path != "/api/ops/events":
                self._send_json({"error": "not found", "path": path}, status=404)
                return
            payload = self._read_json_body()
            if payload is None:
                return
            event = record_ops_event(target_root, payload)
            self._send_json(event, status=201)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"mission-control: {fmt % args}", file=sys.stderr)

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(encoded)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(encoded)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _read_json_body(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("content-length", "0") or "0")
            except ValueError:
                self._send_json({"error": "invalid content-length"}, status=400)
                return None
            if length > 65536:
                self._send_json({"error": "payload too large"}, status=413)
                return None
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json({"error": "invalid json"}, status=400)
                return None
            if not isinstance(payload, dict):
                self._send_json({"error": "json object required"}, status=400)
                return None
            return payload

    return Handler
