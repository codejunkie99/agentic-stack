"""Box v1 provider. Auth stays in memory; creation retries reuse one identity."""
from __future__ import annotations

import json
import ssl
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to a redirect destination.


class BoxProvider:
    base_url = "https://ascii.dev/api/box/v1"

    def __init__(self, token: str):
        if not isinstance(token, str) or not token.strip():
            raise ProviderError("Add a Box API key in Settings to use cloud workspaces.")
        self.token = token.strip()
        cafile = "/etc/ssl/cert.pem" if os.path.isfile("/etc/ssl/cert.pem") else None
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=cafile)))

    def request(self, method: str, path: str, body=None, *, key=None, timeout=35):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if key:
            headers["Idempotency-Key"] = key
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ProviderError("Box returned an oversized response.")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            message = {401: "Box key was rejected. Reconnect in Settings.",
                       402: "Box requires billing setup in its dashboard.",
                       429: "Box rate limit reached. Wait before retrying."}.get(exc.code)
            if not message:
                try:
                    error = json.loads(exc.read(4096))
                    code = error.get("code", "request_failed")
                    message = f"Box request failed ({exc.code}, {code}). Check the Box dashboard."
                except (ValueError, AttributeError):
                    message = f"Box request failed (HTTP {exc.code})."
            raise ProviderError(message.replace(self.token, "[redacted]")) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError("Box could not be reached. The request may have been accepted; refresh before retrying.") from None
        except (json.JSONDecodeError, UnicodeError):
            raise ProviderError("Box returned an unreadable response.") from None
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise ProviderError("Box did not confirm the operation. Refresh its state before retrying.")
        return result

    @staticmethod
    def path(box_id: str, suffix="") -> str:
        if not box_id or not all(c.isalnum() or c in "_-" for c in box_id):
            raise ValueError("Invalid Box identifier.")
        return "/boxes/" + urllib.parse.quote(box_id, safe="") + suffix

    def create(self, workspace: dict):
        return self.request("POST", "/boxes", {
            "type": "small", "ttlSeconds": workspace["ttlMinutes"] * 60,
            "noEnv": not workspace["inheritCredentials"],
        }, key="agentic-" + workspace["id"])

    def inspect(self, box_id):
        return self.request("GET", self.path(box_id))

    def action(self, box_id, action, body=None, *, key=None):
        if action not in {"stop", "resume", "fork", "desktop", "prompt", "interrupt", "commands"}:
            raise ValueError("Unsupported Box action.")
        return self.request("POST", self.path(box_id, "/" + action), body or {}, key=key)
