"""Durable custom-agent and dispatch state for the Agents workspace.

The dashboard is single-user, but dispatch workers update state concurrently.
SQLite gives those background threads an atomic store without adding a runtime
dependency. Large model/tool output stays JSON-shaped so the Flask layer and
vanilla frontend can use it directly.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

import paths


DB_PATH = paths.data_dir() / ".dispatches.sqlite3"
AGENT_ID_RE = re.compile(r"^a_[0-9a-f]{32}$")
DISPATCH_ID_RE = re.compile(r"^d_[0-9a-f]{32}$")
PRIORITIES = ("fast", "balanced", "best")
KINDS = ("single", "group")
STATES = (
    "clarifying", "planning", "ready", "running", "awaiting_apply",
    "completed", "failed", "cancelled", "interrupted",
)
CAPABILITIES = frozenset({
    "vault_read", "vault_write", "code_read", "code_write", "run_checks",
    "web", "inbox_read", "inbox_draft",
})
PROFILES = {
    "research": ["vault_read", "code_read", "web"],
    "vault_editor": ["vault_read", "vault_write"],
    "code_editor": ["code_read", "code_write", "run_checks"],
    "inbox": ["inbox_read", "inbox_draft"],
}

_lock = threading.RLock()


class DispatchStoreError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> float:
    return time.time()


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _init() -> None:
    with _lock, _db() as con:
        con.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS agent_definitions (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dispatches (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dispatch_events (
                dispatch_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                data TEXT NOT NULL,
                created REAL NOT NULL,
                PRIMARY KEY (dispatch_id, seq)
            );
            CREATE INDEX IF NOT EXISTS idx_dispatch_updated
                ON dispatches(updated DESC);
            """
        )
        # Threads/subprocesses cannot survive a dashboard restart. Preserve the
        # audit trail and make the dispatch explicitly resumable instead of
        # leaving it looking live forever.
        rows = con.execute("SELECT id, data FROM dispatches").fetchall()
        for row in rows:
            obj = _loads(row["data"])
            if obj.get("state") in ("planning", "running"):
                obj["state"] = "interrupted"
                obj["error"] = "The dashboard restarted while this dispatch was running."
                obj["updated"] = _now()
                con.execute(
                    "UPDATE dispatches SET data=?, updated=? WHERE id=?",
                    (_dumps(obj), obj["updated"], row["id"]),
                )


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str) -> dict:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _clean_capabilities(raw, profile: str = "research") -> list[str]:
    values = raw if isinstance(raw, list) else PROFILES.get(profile, [])
    clean = []
    for value in values:
        name = str(value or "").strip().lower()
        if name in CAPABILITIES and name not in clean:
            clean.append(name)
    if not clean:
        raise DispatchStoreError("Choose at least one agent capability.")
    if "inbox_draft" in clean and "inbox_read" not in clean:
        clean.insert(0, "inbox_read")
    if "code_write" in clean and "code_read" not in clean:
        clean.insert(0, "code_read")
    if "vault_write" in clean and "vault_read" not in clean:
        clean.insert(0, "vault_read")
    return clean


def _agent_payload(data: dict, agent_id: str | None = None, created: float | None = None) -> dict:
    if not isinstance(data, dict):
        raise DispatchStoreError("Agent definition must be an object.")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 80:
        raise DispatchStoreError("Agent name must be 1-80 characters.")
    instructions = str(data.get("instructions") or data.get("system") or "").strip()
    if not instructions or len(instructions) > 12000:
        raise DispatchStoreError("Agent instructions must be 1-12,000 characters.")
    profile = str(data.get("profile") or "research").strip().lower()
    if profile not in PROFILES:
        raise DispatchStoreError(f"Unknown capability profile '{profile}'.")
    tier = str(data.get("tier") or "").strip().lower()
    if tier and tier not in ("fast", "smart", "openai", "chatgpt", "claude"):
        raise DispatchStoreError(f"Unknown tier '{tier}'.")
    now = _now()
    return {
        "id": agent_id or f"a_{uuid.uuid4().hex}",
        "name": name,
        "description": str(data.get("description") or "").strip()[:240],
        "instructions": instructions,
        "profile": profile,
        "capabilities": _clean_capabilities(data.get("capabilities"), profile),
        "scope": str(data.get("scope") or "").replace("\\", "/").strip().strip("/"),
        "tier": tier,
        "model": str(data.get("model") or "").strip()[:160],
        "created": created or now,
        "updated": now,
    }


def list_agents() -> list[dict]:
    with _lock, _db() as con:
        rows = con.execute("SELECT data FROM agent_definitions ORDER BY updated DESC").fetchall()
    return [_loads(row["data"]) for row in rows]


def get_agent(agent_id: str):
    if not AGENT_ID_RE.match(str(agent_id or "")):
        raise DispatchStoreError("Invalid custom agent id.")
    with _lock, _db() as con:
        row = con.execute("SELECT data FROM agent_definitions WHERE id=?", (agent_id,)).fetchone()
    return _loads(row["data"]) if row else None


def save_agent(data: dict, agent_id: str | None = None) -> dict:
    existing = get_agent(agent_id) if agent_id else None
    if agent_id and existing is None:
        raise DispatchStoreError("No such custom agent.", 404)
    obj = _agent_payload(data, agent_id=agent_id, created=(existing or {}).get("created"))
    with _lock, _db() as con:
        con.execute(
            "INSERT INTO agent_definitions(id,data,created,updated) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
            (obj["id"], _dumps(obj), obj["created"], obj["updated"]),
        )
    return obj


def validate_agent(data: dict) -> dict:
    """Validate and normalize an ephemeral agent without persisting it."""
    return _agent_payload(data)


def delete_agent(agent_id: str) -> bool:
    if not AGENT_ID_RE.match(str(agent_id or "")):
        raise DispatchStoreError("Invalid custom agent id.")
    with _lock, _db() as con:
        cur = con.execute("DELETE FROM agent_definitions WHERE id=?", (agent_id,))
        return cur.rowcount > 0


def create_dispatch(data: dict) -> dict:
    if not isinstance(data, dict):
        raise DispatchStoreError("Dispatch payload must be an object.")
    kind = str(data.get("kind") or "single").strip().lower()
    priority = str(data.get("priority") or "").strip().lower()
    if kind not in KINDS:
        raise DispatchStoreError(f"Unknown dispatch kind '{kind}'.")
    if priority not in PRIORITIES:
        raise DispatchStoreError("Choose Fast, Balanced, or Best quality before dispatching.")
    goal = str(data.get("goal") or "").strip()
    if not goal or len(goal) > 20000:
        raise DispatchStoreError("Dispatch goal must be 1-20,000 characters.")
    now = _now()
    did = f"d_{uuid.uuid4().hex}"
    planner = data.get("planner") if isinstance(data.get("planner"), dict) else {}
    state = "clarifying" if kind == "group" else "ready"
    obj = {
        "id": did,
        "kind": kind,
        "goal": goal,
        "priority": priority,
        "scope": str(data.get("scope") or "").replace("\\", "/").strip().strip("/"),
        "state": state,
        "planner": {
            "tier": str(planner.get("tier") or "").strip().lower(),
            "model": str(planner.get("model") or "").strip()[:160],
        },
        "messages": ([
            {"role": "user", "content": goal, "ts": now},
            {"role": "assistant", "content": (
                "Before I propose the team, what exact deliverable, boundaries, and "
                "must-pass checks should the group use?"
            ), "ts": now},
        ] if kind == "group" else []),
        "plan": data.get("plan") if isinstance(data.get("plan"), dict) else None,
        "plan_revision": 0,
        "workers": [],
        "result": None,
        "artifacts": [],
        "error": None,
        "cancel_requested": False,
        "created": now,
        "updated": now,
    }
    with _lock, _db() as con:
        con.execute(
            "INSERT INTO dispatches(id,data,created,updated) VALUES(?,?,?,?)",
            (did, _dumps(obj), now, now),
        )
    append_event(did, {"type": "dispatch_created", "state": state})
    return obj


def get_dispatch(dispatch_id: str):
    if not DISPATCH_ID_RE.match(str(dispatch_id or "")):
        raise DispatchStoreError("Invalid dispatch id.")
    with _lock, _db() as con:
        row = con.execute("SELECT data FROM dispatches WHERE id=?", (dispatch_id,)).fetchone()
    return _loads(row["data"]) if row else None


def list_dispatches(limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    with _lock, _db() as con:
        rows = con.execute(
            "SELECT data FROM dispatches ORDER BY updated DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for row in rows:
        obj = _loads(row["data"])
        out.append({k: obj.get(k) for k in (
            "id", "kind", "goal", "priority", "scope", "state", "created", "updated",
        )})
    return out


def replace_dispatch(dispatch_id: str, obj: dict) -> dict:
    if not DISPATCH_ID_RE.match(str(dispatch_id or "")):
        raise DispatchStoreError("Invalid dispatch id.")
    if not isinstance(obj, dict):
        raise DispatchStoreError("Dispatch must be an object.")
    obj = dict(obj)
    obj["id"] = dispatch_id
    obj["updated"] = _now()
    with _lock, _db() as con:
        cur = con.execute(
            "UPDATE dispatches SET data=?, updated=? WHERE id=?",
            (_dumps(obj), obj["updated"], dispatch_id),
        )
        if cur.rowcount == 0:
            raise DispatchStoreError("No such dispatch.", 404)
    return obj


def mutate_dispatch(dispatch_id: str, mutator) -> dict:
    with _lock:
        obj = get_dispatch(dispatch_id)
        if obj is None:
            raise DispatchStoreError("No such dispatch.", 404)
        updated = mutator(dict(obj))
        return replace_dispatch(dispatch_id, updated if isinstance(updated, dict) else obj)


def delete_dispatch(dispatch_id: str) -> bool:
    if not DISPATCH_ID_RE.match(str(dispatch_id or "")):
        raise DispatchStoreError("Invalid dispatch id.")
    with _lock, _db() as con:
        con.execute("DELETE FROM dispatch_events WHERE dispatch_id=?", (dispatch_id,))
        cur = con.execute("DELETE FROM dispatches WHERE id=?", (dispatch_id,))
        return cur.rowcount > 0


def append_event(dispatch_id: str, event: dict) -> dict:
    if not DISPATCH_ID_RE.match(str(dispatch_id or "")):
        raise DispatchStoreError("Invalid dispatch id.")
    clean = dict(event or {})
    clean.setdefault("ts", _now())
    with _lock, _db() as con:
        row = con.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM dispatch_events WHERE dispatch_id=?",
            (dispatch_id,),
        ).fetchone()
        seq = int(row["seq"] or 0) + 1
        clean["seq"] = seq
        con.execute(
            "INSERT INTO dispatch_events(dispatch_id,seq,data,created) VALUES(?,?,?,?)",
            (dispatch_id, seq, _dumps(clean), clean["ts"]),
        )
    return clean


def events(dispatch_id: str, after: int = 0) -> dict:
    if not DISPATCH_ID_RE.match(str(dispatch_id or "")):
        raise DispatchStoreError("Invalid dispatch id.")
    after = max(0, int(after or 0))
    with _lock, _db() as con:
        rows = con.execute(
            "SELECT seq,data FROM dispatch_events WHERE dispatch_id=? AND seq>? "
            "ORDER BY seq LIMIT 500",
            (dispatch_id, after),
        ).fetchall()
        last = con.execute(
            "SELECT COALESCE(MAX(seq),0) AS seq FROM dispatch_events WHERE dispatch_id=?",
            (dispatch_id,),
        ).fetchone()
    return {"events": [_loads(row["data"]) for row in rows], "cursor": int(last["seq"] or 0)}


_init()
