"""Chat conversation store — one JSON file per conversation.

Persists the Chat view's conversations (multi-chat, v1.20) so they survive page
reloads and app restarts. One conversation = one file in the gitignored
``dashboard/.chats/`` store:

    {id, title, created, updated, tier, model, edit, messages: [{role, content, ...}]}

Pure functions, no Flask — ``app.py`` wraps these in the /api/chats CRUD routes,
mirroring how ``mailbox.py`` backs the inbox routes. Generation itself stays
stateless (/api/chat is untouched); this module only stores transcripts.

Message attachments are stored as display metadata only ({name, mime}) — the
uploaded files live in the transient ``.chat_attachments/`` store and are pruned
after 24h, so a persisted transcript never depends on them.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

import paths

CHATS_DIR = paths.data_dir() / ".chats"
DEFAULT_TITLE = "New chat"
TITLE_MAX_CHARS = 40

# Conversation ids are minted by create_chat() and must match exactly — the
# regex is the traversal guard (no dots, slashes, or anything path-like).
_ID_RE = re.compile(r"^c_[0-9a-f]{32}$")


class ChatStoreError(Exception):
    """Store failure with an HTTP-ish status for the Flask layer."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


def _chat_path(cid: str) -> Path:
    """Resolve <store>/<id>.json, refusing any id that could escape the store."""
    if not isinstance(cid, str) or not _ID_RE.match(cid):
        raise ChatStoreError(f"Invalid chat id '{cid}'.", 400)
    store = CHATS_DIR.resolve()
    path = (store / f"{cid}.json").resolve()
    if path.parent != store:  # belt-and-braces; the regex already forbids this
        raise ChatStoreError("Chat path escapes the store.", 400)
    return path


def _derive_title(obj: dict) -> str:
    """First user message, squashed and clipped, else the default title."""
    for m in obj.get("messages") or []:
        if isinstance(m, dict) and m.get("role") == "user":
            text = re.sub(r"\s+", " ", str(m.get("content") or "")).strip()
            if text:
                return text[:TITLE_MAX_CHARS] + ("…" if len(text) > TITLE_MAX_CHARS else "")
    return DEFAULT_TITLE


def _meta(obj: dict) -> dict:
    """The lean sidebar payload — everything but the message bodies."""
    return {
        "id": obj.get("id"),
        "title": obj.get("title") or DEFAULT_TITLE,
        "created": obj.get("created"),
        "updated": obj.get("updated"),
        "tier": obj.get("tier") or "fast",
        "messages": len(obj.get("messages") or []),
    }


def list_chats() -> list[dict]:
    """All conversations' metadata (no bodies), most recently updated first."""
    if not CHATS_DIR.is_dir():
        return []
    out = []
    for p in CHATS_DIR.glob("c_*.json"):
        try:
            out.append(_meta(json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue  # skip a corrupt file rather than break the sidebar
    out.sort(key=lambda m: m.get("updated") or 0, reverse=True)
    return out


def load_chat(cid: str):
    """Full conversation object, or None if it doesn't exist."""
    path = _chat_path(cid)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ChatStoreError(f"Couldn't read chat '{cid}': {e}")


def save_chat(obj: dict) -> dict:
    """Validate, stamp `updated`, auto-title if still default, persist. Returns obj."""
    if not isinstance(obj, dict):
        raise ChatStoreError("Chat must be an object.", 400)
    path = _chat_path(obj.get("id") or "")
    msgs = obj.get("messages")
    obj["messages"] = [m for m in msgs if isinstance(m, dict)] if isinstance(msgs, list) else []
    obj["updated"] = time.time()
    if not obj.get("title") or obj["title"] == DEFAULT_TITLE:
        obj["title"] = _derive_title(obj)
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return obj


def create_chat(tier: str = "fast") -> dict:
    """Mint a new empty conversation with defaults and persist it.
    `tier` seeds the conversation's model tier (the Settings default)."""
    now = time.time()
    obj = {
        "id": f"c_{uuid.uuid4().hex}",
        "title": DEFAULT_TITLE,
        "created": now,
        "updated": now,
        "tier": tier if tier in ("fast", "smart", "openai", "claude") else "fast",
        "model": None,
        "edit": False,
        "messages": [],
    }
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    _chat_path(obj["id"]).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return obj


def delete_chat(cid: str) -> bool:
    """Remove a conversation; True if it existed."""
    path = _chat_path(cid)
    if path.is_file():
        path.unlink()
        return True
    return False
