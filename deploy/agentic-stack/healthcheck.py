"""Authenticated readiness check; never print credentials or response data."""
import json
import os
import sys
import urllib.request

try:
    request = urllib.request.Request('http://127.0.0.1:8765/rpc',
        data=b'{"method":"system.health","params":{}}',
        headers={'Authorization': 'Bearer '+os.environ['AGENTIC_CONTROL_TOKEN'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=5) as response:
        ready = json.load(response).get('result', {}).get('status') == 'ok'
    sys.exit(0 if ready else 1)
except Exception:
    sys.exit(1)
