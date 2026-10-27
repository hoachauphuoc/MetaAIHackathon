"""SQLite storage. Every company row hangs off a sandbox id and every read filters by it,
so one sandbox can never see another's data (principle 6). There is no table for chat.
"""
import json
import secrets
import sqlite3
import time

SANDBOX_TTL = 24 * 3600
MODEL_CALL_CAP = 40  # per sandbox; hitting it returns the labelled demo answer

SCHEMA = """
CREATE TABLE IF NOT EXISTS sandboxes (
    id TEXT PRIMARY KEY, created_at REAL NOT NULL, model_calls INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS companies (
    sandbox_id TEXT PRIMARY KEY REFERENCES sandboxes(id) ON DELETE CASCADE,
    data TEXT NOT NULL);
"""


class SandboxExpired(Exception):
    """Unknown or older than the TTL; the UI offers "Start again"."""


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def create_sandbox(self, now=None):
        self._purge_expired(now)
        sandbox_id = secrets.token_urlsafe(16)
        with self.db:
            self.db.execute("INSERT INTO sandboxes (id, created_at) VALUES (?, ?)",
                            (sandbox_id, now or time.time()))
        return sandbox_id

    def require_sandbox(self, sandbox_id, now=None):
        # Expired rows are deleted here, on a request: Cloud Run throttles background threads.
        self._purge_expired(now)
        row = self.db.execute("SELECT model_calls FROM sandboxes WHERE id = ?",
                              (sandbox_id,)).fetchone()
        if row is None:
            raise SandboxExpired(sandbox_id)
        return {"id": sandbox_id, "model_calls": row[0]}

    def try_spend_model_call(self, sandbox_id):
        """True and counted if the sandbox is under its cap; False means answer in demo mode."""
        with self.db:
            cur = self.db.execute(
                "UPDATE sandboxes SET model_calls = model_calls + 1 WHERE id = ? AND model_calls < ?",
                (sandbox_id, MODEL_CALL_CAP))
        return cur.rowcount == 1

    def save_company(self, sandbox_id, company):
        self.require_sandbox(sandbox_id)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO companies (sandbox_id, data) VALUES (?, ?)",
                            (sandbox_id, json.dumps(company)))

    def get_company(self, sandbox_id):
        self.require_sandbox(sandbox_id)
        row = self.db.execute("SELECT data FROM companies WHERE sandbox_id = ?",
                              (sandbox_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _purge_expired(self, now=None):
        cutoff = (now or time.time()) - SANDBOX_TTL
        with self.db:
            self.db.execute("DELETE FROM sandboxes WHERE created_at < ?", (cutoff,))
