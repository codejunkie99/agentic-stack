"""Shared CLI contract for host-agent tools: envelopes, exit codes, redaction.

Every new tool that an agent shells out to speaks the same contract, so a
caller can parse stdout without knowing which tool it ran:

    success  stdout: {"ok": true,  "data": {...}, "meta": {...}}   exit 0
    failure  stdout: {"ok": false, "error": {"type", "code", "message",
                                             "hint", "detail"}, "meta": {}}

`--format auto` resolves to `text` on a TTY and `json` when piped, so a human
sees prose and an agent sees an envelope. Text output is not a stable
contract; the JSON envelope and the exit-code mapping are.

Exit codes are coarse on purpose. Agents use both the exit code and
`error.type`:

    0    success
    1    business error (not_found, conflict, permission, upstream, ...)
    2    invalid_args
    3    not_logged_in / auth
    4    network
    5    io / internal
    130  cancelled

Redaction is part of the contract: anything that looks like a credential is
masked before bytes leave the output layer (first eight characters kept,
rest replaced with `_REDACTED`) so support output can still correlate a key
without exposing it. See docs/contracts.md.
"""
import json
import re
import sys

ERROR_EXIT = {
    "invalid_args": 2,
    "not_found": 1,
    "conflict": 1,
    "permission": 1,
    "upstream": 1,
    "rate_limit": 1,
    "plugin_not_detected": 1,
    "not_logged_in": 3,
    "auth": 3,
    "network": 4,
    "io": 5,
    "internal": 5,
    "cancelled": 130,
}

_KEEP = 8
_SUFFIX = "_REDACTED"

# Ordered: specific token shapes first, generic key=value last.
_SECRET_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                       # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),                   # OpenAI / Anthropic style
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),               # GitHub tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),            # Slack tokens
    re.compile(r"\b(?:emk|evt)_[A-Za-z0-9_\-]{8,}"),           # emk_/evt_ style keys
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{16,}"),    # Authorization headers
    re.compile(r"X-Amz-(?:Signature|Credential|Security-Token)=[A-Za-z0-9%._/\-]+"),
]
_KV_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd)(\s*[=:]\s*['\"]?)([A-Za-z0-9._~+/=\-]{12,})"
)


def _mask(token):
    return token[:_KEEP] + _SUFFIX


def redact(text):
    """Mask credential-looking substrings. Idempotent; safe on non-strings."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: _mask(m.group(0)), out)
    out = _KV_PATTERN.sub(lambda m: m.group(1) + m.group(2) + _mask(m.group(3)), out)
    return out


def redact_obj(obj):
    """Recursively redact strings inside dicts/lists."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    return obj


class CliError(Exception):
    """Raise anywhere inside a tool; `run()` turns it into the error envelope."""

    def __init__(self, type, message, hint=None, detail=None, code=0):
        super().__init__(message)
        if type not in ERROR_EXIT:
            type = "internal"
        self.type = type
        self.message = message
        self.hint = hint
        self.detail = detail
        self.code = code

    def envelope(self):
        err = {"type": self.type, "code": self.code, "message": self.message}
        if self.hint:
            err["hint"] = self.hint
        if self.detail is not None:
            err["detail"] = self.detail
        return {"ok": False, "error": redact_obj(err), "meta": {}}

    @property
    def exit_code(self):
        return ERROR_EXIT[self.type]


def add_format_arg(parser):
    parser.add_argument("--format", default="auto", choices=["auto", "text", "json"],
                        help="auto = text on a TTY, json when piped")
    return parser


def resolve_format(fmt):
    if fmt in (None, "auto"):
        return "text" if sys.stdout.isatty() else "json"
    return fmt


def emit_ok(data, meta=None, fmt="auto", text=None, stream=None):
    """Print a success envelope (json) or `text` (text mode). Returns 0."""
    stream = stream or sys.stdout
    fmt = resolve_format(fmt)
    data = redact_obj(data)
    if fmt == "json":
        env = {"ok": True, "data": data, "meta": redact_obj(meta or {})}
        stream.write(json.dumps(env, sort_keys=True) + "\n")
    else:
        if text is None:
            text = json.dumps(data, indent=2, sort_keys=True)
        stream.write(redact(text) + ("\n" if not text.endswith("\n") else ""))
    stream.flush()
    return 0


def emit_error(err, fmt="auto", stream=None, err_stream=None):
    """Print the error envelope (json → stdout, text → stderr). Returns exit code."""
    stream = stream or sys.stdout
    err_stream = err_stream or sys.stderr
    if not isinstance(err, CliError):
        err = CliError("internal", str(err))
    fmt = resolve_format(fmt)
    if fmt == "json":
        stream.write(json.dumps(err.envelope(), sort_keys=True) + "\n")
        stream.flush()
    else:
        err_stream.write(f"error: {redact(err.message)}\n")
        if err.hint:
            err_stream.write(f"hint: {redact(err.hint)}\n")
        err_stream.flush()
    return err.exit_code


def run(fn, fmt="auto"):
    """Run `fn()` (returns (data, meta, text) or data) under the contract.

    Returns the process exit code; never raises for CliError / Ctrl-C.
    """
    try:
        result = fn()
    except CliError as e:
        return emit_error(e, fmt)
    except KeyboardInterrupt:
        return emit_error(CliError("cancelled", "interrupted"), fmt)
    except (OSError, IOError) as e:
        return emit_error(CliError("io", str(e)), fmt)
    if isinstance(result, tuple):
        data, meta, text = (list(result) + [None, None])[:3]
    else:
        data, meta, text = result, None, None
    return emit_ok(data, meta=meta, fmt=fmt, text=text)


if __name__ == "__main__":  # self-check
    assert redact("key sk-abcdefghijklmnopqrstuvwxyz done") == "key sk-abcde_REDACTED done"
    assert redact("AKIAABCDEFGHIJKLMNOP") == "AKIAABCD_REDACTED"
    assert redact("api_key=0123456789abcdef") == "api_key=01234567_REDACTED"
    assert redact("nothing here") == "nothing here"
    assert redact(redact("ghp_abcdefghijklmnopqrstuvwxyz")) == "ghp_abcd_REDACTED"
    assert CliError("bogus", "x").type == "internal"
    assert CliError("invalid_args", "x").exit_code == 2
    print("ok")
