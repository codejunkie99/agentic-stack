"""Validation and staging for user-selected multimodal run attachments."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from pathlib import Path

MAX_ATTACHMENTS = 8
MAX_ATTACHMENT_BYTES = 12_000_000
MAX_TOTAL_BYTES = 24_000_000
_ALLOWED_PREFIXES = ("image/", "audio/", "video/", "text/")
_ALLOWED_TYPES = {
    "application/pdf", "application/json", "application/xml", "application/zip",
    "application/octet-stream", "application/x-yaml", "application/toml",
}


def _name(value, index):
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        raise ValueError("Each attachment needs a valid file name.")
    clean = Path(value).name
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "-", clean).strip(" .-") or f"attachment-{index}"
    return clean[:140]


def _kind(mime):
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("text/") or mime in {"application/json", "application/xml", "application/x-yaml", "application/toml"}:
        return "text"
    return "file"


def decode_attachments(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ATTACHMENTS:
        raise ValueError(f"Attach up to {MAX_ATTACHMENTS} files.")
    decoded, total, used = [], 0, set()
    for index, row in enumerate(value, 1):
        if not isinstance(row, dict) or set(row) != {"name", "mimeType", "data"}:
            raise ValueError("Invalid attachment payload.")
        mime = row["mimeType"]
        if not isinstance(mime, str) or len(mime) > 100 or not (mime.startswith(_ALLOWED_PREFIXES) or mime in _ALLOWED_TYPES):
            raise ValueError("This attachment type is not supported.")
        if not isinstance(row["data"], str):
            raise ValueError("Invalid attachment data.")
        try:
            data = base64.b64decode(row["data"], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid attachment data.") from None
        if not data or len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Each attachment must be between 1 byte and 12 MB.")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Attachments can use up to 24 MB per message.")
        name = _name(row["name"], index)
        stem, suffix = Path(name).stem, Path(name).suffix
        candidate, counter = name, 2
        while candidate.lower() in used:
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1
        used.add(candidate.lower())
        relative = f"ATTACHMENTS/{index:02d}-{candidate}"
        decoded.append({"name": candidate, "mimeType": mime, "kind": _kind(mime),
                        "size": len(data), "digest": hashlib.sha256(data).hexdigest(),
                        "relativePath": relative, "data": data})
    return decoded


def public_attachments(decoded):
    return [{key: row[key] for key in ("name", "mimeType", "kind", "size", "digest", "relativePath")}
            for row in decoded]


def stage_attachments(root, decoded):
    for row in decoded:
        destination = root / row["relativePath"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(row["data"])
