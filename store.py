"""SQLite storage. Every company row hangs off a sandbox id and every read filters by it,
so one sandbox can never see another's data (principle 6). There is no table for chat.
"""
import datetime
import json
import os
import secrets
import functools
import sqlite3
import threading
import time

SANDBOX_TTL = 24 * 3600
MODEL_CALL_CAP = 80  # per sandbox; hitting it returns the labelled demo answer
DAILY_CEILING_USD = float(os.environ.get("DAILY_CEILING_USD", "10"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sandboxes (
    id TEXT PRIMARY KEY, created_at REAL NOT NULL, model_calls INTEGER NOT NULL DEFAULT 0,
    muse_off INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS companies (
    sandbox_id TEXT PRIMARY KEY REFERENCES sandboxes(id) ON DELETE CASCADE,
    data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assistants (
    sandbox_id TEXT NOT NULL REFERENCES sandboxes(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (sandbox_id, role_id));
CREATE TABLE IF NOT EXISTS people (
    token TEXT PRIMARY KEY,
    sandbox_id TEXT NOT NULL REFERENCES sandboxes(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL, display_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS personal_rules (
    token TEXT PRIMARY KEY REFERENCES people(token) ON DELETE CASCADE,
    data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    sandbox_id TEXT NOT NULL REFERENCES sandboxes(id) ON DELETE CASCADE,
    data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    package_id TEXT NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, role_id TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daily_cost (day TEXT PRIMARY KEY, usd REAL NOT NULL);
"""


class SandboxExpired(Exception):
    """Unknown or older than the TTL; the UI offers "Start again"."""


class PersonLeft(SandboxExpired):
    """The link was revoked because the person left; the browser is told to clear its data."""


def locked(method):
    """One sqlite connection is shared by all request threads; calls must not interleave."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


class Store:
    def __init__(self, path=":memory:"):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    @locked
    def create_sandbox(self, now=None):
        self._purge_expired(now)
        sandbox_id = secrets.token_urlsafe(16)
        with self.db:
            self.db.execute("INSERT INTO sandboxes (id, created_at) VALUES (?, ?)",
                            (sandbox_id, now or time.time()))
        return sandbox_id

    @locked
    def require_sandbox(self, sandbox_id, now=None):
        # Expired rows are deleted here, on a request: Cloud Run throttles background threads.
        self._purge_expired(now)
        row = self.db.execute("SELECT model_calls FROM sandboxes WHERE id = ?",
                              (sandbox_id,)).fetchone()
        if row is None:
            raise SandboxExpired(sandbox_id)
        return {"id": sandbox_id, "model_calls": row[0]}

    @locked
    def spend_model_call(self, sandbox_id):
        """None if the call may go ahead (and is counted), else the reason to answer in demo mode."""
        with self.db:
            row = self.db.execute("SELECT muse_off FROM sandboxes WHERE id = ?",
                                  (sandbox_id,)).fetchone()
            if row is None or row[0]:
                return "Muse switched off"
            if self.cost_today() >= DAILY_CEILING_USD:
                return "Demo limit reached"
            cur = self.db.execute(
                "UPDATE sandboxes SET model_calls = model_calls + 1 WHERE id = ? AND model_calls < ?",
                (sandbox_id, MODEL_CALL_CAP))
        return None if cur.rowcount == 1 else "Demo limit reached"

    @locked
    def save_package(self, sandbox_id, package):
        self.require_sandbox(sandbox_id)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO packages VALUES (?, ?, ?)",
                            (package["id"], sandbox_id, json.dumps(package)))

    @locked
    def get_package(self, sandbox_id, package_id):
        row = self.db.execute("SELECT data FROM packages WHERE id = ? AND sandbox_id = ?",
                              (package_id, sandbox_id)).fetchone()
        return json.loads(row[0]) if row else None

    @locked
    def list_packages(self, sandbox_id):
        rows = self.db.execute("SELECT data FROM packages WHERE sandbox_id = ?", (sandbox_id,))
        return [json.loads(r[0]) for r in rows]

    @locked
    def log_decision(self, package_id, kind, role_id, reason=""):
        """Decisions belong to the document and name the role that acted, never the person."""
        with self.db:
            self.db.execute("INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
                            (package_id, kind, role_id, reason, datetime.date.today().isoformat()))

    @locked
    def decisions_for(self, package_id):
        rows = self.db.execute("SELECT kind, role_id, reason, day FROM decisions WHERE package_id = ?",
                               (package_id,))
        return [dict(zip(("kind", "role_id", "reason", "day"), r)) for r in rows]

    @locked
    def cost_today(self):
        row = self.db.execute("SELECT usd FROM daily_cost WHERE day = ?",
                              (datetime.date.today().isoformat(),)).fetchone()
        return row[0] if row else 0.0

    @locked
    def add_cost(self, usd):
        """Money only, never who or what: this is the service-wide daily ceiling."""
        with self.db:
            self.db.execute("INSERT INTO daily_cost VALUES (?, ?) ON CONFLICT(day) "
                            "DO UPDATE SET usd = usd + excluded.usd",
                            (datetime.date.today().isoformat(), usd))

    @locked
    def set_muse_off(self, sandbox_id, off):
        self.require_sandbox(sandbox_id)
        with self.db:
            self.db.execute("UPDATE sandboxes SET muse_off = ? WHERE id = ?", (int(off), sandbox_id))

    @locked
    def save_company(self, sandbox_id, company):
        self.require_sandbox(sandbox_id)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO companies (sandbox_id, data) VALUES (?, ?)",
                            (sandbox_id, json.dumps(company)))

    @locked
    def get_company(self, sandbox_id):
        self.require_sandbox(sandbox_id)
        row = self.db.execute("SELECT data FROM companies WHERE sandbox_id = ?",
                              (sandbox_id,)).fetchone()
        return json.loads(row[0]) if row else None

    @locked
    def save_assistant(self, sandbox_id, role_id, kit):
        self.require_sandbox(sandbox_id)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO assistants VALUES (?, ?, ?)",
                            (sandbox_id, role_id, json.dumps(kit)))

    @locked
    def get_assistants(self, sandbox_id):
        self.require_sandbox(sandbox_id)
        rows = self.db.execute("SELECT role_id, data FROM assistants WHERE sandbox_id = ?",
                               (sandbox_id,))
        return {role_id: json.loads(data) for role_id, data in rows}

    @locked
    def add_person(self, sandbox_id, role_id, display_name, headcount):
        """Return the invite token, or None when every seat of the role is taken."""
        self.require_sandbox(sandbox_id)
        held = self.db.execute(
            "SELECT COUNT(*) FROM people WHERE sandbox_id = ? AND role_id = ? AND status = 'active'",
            (sandbox_id, role_id)).fetchone()[0]
        if held >= headcount:
            return None
        token = secrets.token_urlsafe(16)
        with self.db:
            self.db.execute("INSERT INTO people (token, sandbox_id, role_id, display_name) "
                            "VALUES (?, ?, ?, ?)", (token, sandbox_id, role_id, display_name))
        return token

    @locked
    def list_people(self, sandbox_id):
        """For the owner: who holds which seat. No activity, counts or metrics."""
        self.require_sandbox(sandbox_id)
        rows = self.db.execute("SELECT rowid, role_id, display_name, status FROM people "
                               "WHERE sandbox_id = ?", (sandbox_id,))
        return [dict(zip(("id", "role_id", "display_name", "status"), r)) for r in rows]

    @locked
    def offboard(self, sandbox_id, person_id):
        """Revoke the link at once and send every package the person held back to the queue."""
        self.require_sandbox(sandbox_id)
        row = self.db.execute("SELECT token FROM people WHERE rowid = ? AND sandbox_id = ?",
                              (person_id, sandbox_id)).fetchone()
        if row is None:
            return False
        with self.db:
            self.db.execute("UPDATE people SET status = 'left' WHERE token = ?", (row[0],))
            self.db.execute("DELETE FROM personal_rules WHERE token = ?", (row[0],))
        for package in self.list_packages(sandbox_id):
            if package["claimed_by"] == row[0]:
                package["claimed_by"] = None
                self.save_package(sandbox_id, package)
        return True

    @locked
    def person_by_token(self, token):
        """The token is the whole credential; an expired sandbox takes its people with it."""
        self._purge_expired()
        row = self.db.execute("SELECT sandbox_id, role_id, display_name, status FROM people "
                              "WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise SandboxExpired(token)
        if row[3] != "active":
            raise PersonLeft(token)
        return {"sandbox_id": row[0], "role_id": row[1], "display_name": row[2]}

    @locked
    def save_personal_rules(self, token, values):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO personal_rules (token, data) VALUES (?, ?)",
                            (token, json.dumps(values)))

    @locked
    def get_personal_rules(self, token):
        row = self.db.execute("SELECT data FROM personal_rules WHERE token = ?", (token,)).fetchone()
        return json.loads(row[0]) if row else None

    @locked
    def table_names(self):
        return [r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]

    @locked
    def _purge_expired(self, now=None):
        cutoff = (now or time.time()) - SANDBOX_TTL
        with self.db:
            self.db.execute("DELETE FROM sandboxes WHERE created_at < ?", (cutoff,))
