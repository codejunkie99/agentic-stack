"""Small transactional store. No credentials are persisted here."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..transfer_bundle import now_iso


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "workspaces.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id))")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self, kind: str) -> list[dict]:
        with self.lock, self.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute("SELECT data FROM records WHERE kind=?", (kind,))]
        return sorted(rows, key=lambda row: row.get("createdAt", ""), reverse=True)

    def get(self, kind: str, identifier: str) -> dict:
        with self.lock, self.connect() as db:
            row = db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        if row is None:
            raise ValueError(f"{kind.capitalize()} not found.")
        return json.loads(row[0])

    def create(self, kind: str, values: dict) -> dict:
        row = dict(values, id=uuid.uuid4().hex, createdAt=now_iso(), updatedAt=now_iso())
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO records VALUES(?,?,?)", (kind, row["id"], json.dumps(row)))
        return row

    def update(self, kind: str, identifier: str, **values) -> dict:
        with self.lock:
            row = self.get(kind, identifier)
            row.update(values, updatedAt=now_iso())
            with self.connect() as db:
                db.execute("UPDATE records SET data=? WHERE kind=? AND id=?", (json.dumps(row), kind, identifier))
        return row

    def workspace_path(self, identifier: str) -> Path:
        # Only server-generated persisted identifiers can address the filesystem.
        self.get("workspace", identifier)
        if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
            raise ValueError("Invalid workspace identifier.")
        path = self.root / "projects" / identifier
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path
