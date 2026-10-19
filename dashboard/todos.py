"""To-do store — one small JSON file holding the user's own task list.

The Overview and Calendar views are *derived*: they read whatever notes happen to
sit in the vault. This list is the opposite — things the user (or the chat) put on
it deliberately, which may have no note behind them at all ("email the advisor",
"submit the form"). So it gets its own store rather than a synthetic note:

    <data dir>/.todos.json  ->  {"todos": [{id, title, due, note, done, ...}]}

One file, not one-per-item like ``chats.py``: a to-do is a couple of hundred bytes
and the list is always read whole, so per-item files would buy nothing and cost a
directory walk per render. Writes are atomic (tempfile + os.replace) and guarded by
a lock, because the chat tools write from a worker thread while the UI reads.

Pure functions, no Flask — ``app.py`` wraps these in the /api/todos routes and
``agent.py`` wraps them as chat tools, so both paths hit the same validation.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import date

import paths

TODOS_FILE = paths.data_dir() / ".todos.json"

TITLE_MAX_CHARS = 200
NOTE_MAX_CHARS = 500
# A hand-kept list that grows past this is a symptom, not a use case; the cap
# stops a looping agent from writing an unbounded file.
MAX_TODOS = 500
# Where an item came from, for the "added by chat" hint in the UI.
SOURCES = ("manual", "chat", "agent")

# Ids are minted by add_todo() and must match exactly. Unlike chats there is no
# path built from an id, but the same strict shape keeps a caller-supplied id
# from matching anything unexpected.
_ID_RE = re.compile(r"^t_[0-9a-f]{32}$")
_lock = threading.Lock()


class TodoStoreError(Exception):
    """Store failure with an HTTP-ish status for the Flask layer."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


def _clean_title(raw) -> str:
    title = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not title:
        raise TodoStoreError("A to-do needs a title.", 400)
    return title[:TITLE_MAX_CHARS]


def _clean_due(raw) -> str:
    """'' (no due date) or a validated YYYY-MM-DD string.

    Stored as the plain ISO string, never a datetime: the UI compares it against
    integer day ordinals, so parsing it into a local-time Date anywhere would
    shift every due date a day west of UTC (same trap as the calendar view)."""
    due = str(raw or "").strip()
    if not due:
        return ""
    try:
        return date.fromisoformat(due).isoformat()
    except ValueError:
        raise TodoStoreError(f"Due date '{due}' isn't a valid YYYY-MM-DD date.", 400)


def _clean_note(raw) -> str:
    return re.sub(r"\s+", " ", str(raw or "")).strip()[:NOTE_MAX_CHARS]


def _sort_key(item: dict):
    """Open items first, then soonest due (undated last), then oldest first."""
    due = item.get("due") or ""
    return (bool(item.get("done")), not due, due, item.get("created") or 0)


def _read_all() -> list[dict]:
    """Every stored item, or [] if the store doesn't exist yet."""
    if not TODOS_FILE.is_file():
        return []
    try:
        data = json.loads(TODOS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise TodoStoreError(f"Couldn't read the to-do list: {e}")
    items = data.get("todos") if isinstance(data, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _write_all(items: list[dict]) -> None:
    """Atomically replace the store so a reader never sees partial JSON."""
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(TODOS_FILE.parent), prefix=".todos-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"todos": items}, stream, indent=2, ensure_ascii=False)
        os.replace(tmp, TODOS_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def list_todos() -> list[dict]:
    """The whole list, sorted for display (open first, soonest due first)."""
    with _lock:
        return sorted(_read_all(), key=_sort_key)


def add_todo(title: str, due: str = "", note: str = "", source: str = "manual") -> dict:
    """Validate and append one item. Returns the stored item."""
    item = {
        "id": f"t_{uuid.uuid4().hex}",
        "title": _clean_title(title),
        "due": _clean_due(due),
        "note": _clean_note(note),
        "done": False,
        "source": source if source in SOURCES else "manual",
        "created": time.time(),
        "updated": time.time(),
    }
    with _lock:
        items = _read_all()
        if len(items) >= MAX_TODOS:
            raise TodoStoreError(
                f"The to-do list is full ({MAX_TODOS} items) — clear some first.", 400)
        items.append(item)
        _write_all(items)
    return item


def update_todo(tid: str, **fields) -> dict:
    """Patch title/due/note/done on one item. Unknown keys are ignored."""
    if not isinstance(tid, str) or not _ID_RE.match(tid):
        raise TodoStoreError(f"Invalid to-do id '{tid}'.", 400)
    with _lock:
        items = _read_all()
        target = next((i for i in items if i.get("id") == tid), None)
        if target is None:
            raise TodoStoreError("No such to-do.", 404)
        if "title" in fields:
            target["title"] = _clean_title(fields["title"])
        if "due" in fields:
            target["due"] = _clean_due(fields["due"])
        if "note" in fields:
            target["note"] = _clean_note(fields["note"])
        if "done" in fields:
            target["done"] = bool(fields["done"])
        target["updated"] = time.time()
        _write_all(items)
    return target


def delete_todo(tid: str) -> bool:
    """Remove one item; True if it existed."""
    if not isinstance(tid, str) or not _ID_RE.match(tid):
        raise TodoStoreError(f"Invalid to-do id '{tid}'.", 400)
    with _lock:
        items = _read_all()
        kept = [i for i in items if i.get("id") != tid]
        if len(kept) == len(items):
            return False
        _write_all(kept)
    return True


def clear_done() -> int:
    """Drop every completed item; returns how many went."""
    with _lock:
        items = _read_all()
        kept = [i for i in items if not i.get("done")]
        removed = len(items) - len(kept)
        if removed:
            _write_all(kept)
    return removed


def revision() -> str:
    """Cheap fingerprint of the store, for the UI's live-sync poller.

    One stat, no read — the poller runs every few seconds and must stay an order
    of magnitude cheaper than fetching the list itself (dashboard/CLAUDE.md, live
    vault sync). '0-0' means the store doesn't exist yet."""
    try:
        st = TODOS_FILE.stat()
    except OSError:
        return "0-0"
    return f"{st.st_mtime_ns}-{st.st_size}"
