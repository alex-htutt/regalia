"""Mailbox engine — read inboxes and create drafts for Gmail + Outlook.

One module, one common shape across providers, so callers (the Flask routes in
app.py and the email tools in agent.py) never branch on provider:

    accounts_overview()                  -> {accounts:[...], errors:[...]}
    list_accounts()                      -> [{id, provider, address}]
    fetch_inbox(account_id, limit, q)    -> {account, messages:[...], errors:[...]}
    read_message(account_id, msg_id)     -> {id, from, to, subject, date, body, ...}
    search_messages(account_id, q, lim)  -> same shape as fetch_inbox
    create_draft(account_id, to, subject, body, reply_to_msg_id=None) -> {ok, id, ...}

A "message" dict is: {id, thread_id, from, subject, date, snippet, unread}; a full
message adds {to, body}.

Auth (#2.5): the OAuth token dance is delegated to auth-only libs — google-auth
(Gmail) and msal (Outlook) — imported LAZILY so the rest of the app runs even when
they aren't installed (you only need them once you connect an inbox). The actual
mail I/O below is plain stdlib urllib+json against the Gmail REST API / Microsoft
Graph. Tokens are read/refreshed from a gitignored per-account store and are NEVER
logged or returned to the client.

Write scope is **drafts only** by construction: there is no send function here, the
Graph token is requested without Mail.Send, and the Gmail code never calls the send
endpoint. Per-account/per-source failures degrade gracefully (collected in
`errors`), never crash a whole listing — mirroring the briefing in app.py.
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path

import email_sources as cfg

# Per-account token store. Gitignored (see .gitignore). From source it lives
# under dashboard/, which the vault walk ignores, so tokens never surface as
# notes; packaged builds keep it in the per-user data dir (paths.data_dir).
import paths

TOKENS_DIR = paths.data_dir() / ".email_tokens"


class MailboxError(Exception):
    """A failure with a user-safe message + HTTP status for the Flask layer."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


# ── Account id + token store (traversal-safe) ────────────────────────────────

def make_account_id(provider: str, address: str) -> str:
    """Stable, filesystem-safe id for an account, e.g. 'gmail-alice_example_com'."""
    provider = (provider or "").lower().strip()
    if provider not in cfg.PROVIDERS:
        raise MailboxError(f"Unknown provider '{provider}'.", 400)
    slug = re.sub(r"[^a-z0-9]+", "_", (address or "").lower()).strip("_")
    return f"{provider}-{slug}" if slug else provider


def _account_path(account_id: str) -> Path:
    """Resolve <store>/<id>.json, refusing any id that could escape the store."""
    raw = account_id or ""
    safe = re.sub(r"[^a-z0-9._-]", "", raw.lower())
    if not safe or safe != raw.lower():
        raise MailboxError(f"Invalid account id '{account_id}'.", 400)
    store = TOKENS_DIR.resolve()
    path = (store / f"{safe}.json").resolve()
    if path.parent != store:
        raise MailboxError("Account path escapes the token store.", 400)
    return path


def _load_account(account_id: str) -> dict:
    path = _account_path(account_id)
    if not path.is_file():
        raise MailboxError(f"No connected account '{account_id}'.", 404)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise MailboxError(f"Couldn't read account '{account_id}': {e}")


def _save_account(acct: dict) -> None:
    path = _account_path(acct["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acct, indent=2), encoding="utf-8")


def save_account(provider: str, address: str, *, google=None, msal_cache=None) -> str:
    """Persist a newly-connected account (called by connect_email.py). Returns id.

    Exactly one of `google` (a google creds dict) or `msal_cache` (a serialized
    msal cache string) is stored, depending on provider.
    """
    account_id = make_account_id(provider, address)
    acct = {"id": account_id, "provider": provider, "address": address}
    if google is not None:
        acct["google"] = google
    if msal_cache is not None:
        acct["msal_cache"] = msal_cache
    _save_account(acct)
    return account_id


def list_accounts() -> list[dict]:
    """Connected accounts (metadata only, no network) — id, provider, address."""
    store = TOKENS_DIR
    if not store.is_dir():
        return []
    out = []
    for f in sorted(store.glob("*.json")):
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"id": a.get("id", f.stem), "provider": a.get("provider", ""),
                    "address": a.get("address", "")})
    return out


# ── Token acquisition / refresh (lazy imports; tokens never logged) ──────────

def _gmail_token(acct: dict) -> str:
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import google.auth.exceptions as gerr
    except ImportError:
        raise MailboxError("google-auth not installed — run: pip install -r requirements.txt")
    info = acct.get("google") or {}
    if not info.get("refresh_token"):
        raise MailboxError(f"Reconnect '{acct['id']}' — no refresh token stored.", 401)
    try:
        creds = Credentials.from_authorized_user_info(info, scopes=info.get("scopes"))
    except ValueError as e:
        raise MailboxError(f"Reconnect '{acct['id']}' — stored token is malformed: {e}", 401)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except gerr.GoogleAuthError as e:
            raise MailboxError(f"Reconnect '{acct['id']}' — token refresh failed: {e}", 401)
        acct["google"] = json.loads(creds.to_json())
        _save_account(acct)
    return creds.token


def _ms_token(acct: dict) -> str:
    try:
        import msal
    except ImportError:
        raise MailboxError("msal not installed — run: pip install -r requirements.txt")
    if not cfg.MS_CLIENT_ID:
        raise MailboxError("MS_OAUTH_CLIENT_ID is not set — can't refresh Outlook tokens.", 401)
    cache = msal.SerializableTokenCache()
    if acct.get("msal_cache"):
        cache.deserialize(acct["msal_cache"])
    app = msal.PublicClientApplication(
        cfg.MS_CLIENT_ID, authority=cfg.MS_AUTHORITY, token_cache=cache)
    accounts = app.get_accounts()
    if not accounts:
        raise MailboxError(f"Reconnect '{acct['id']}' — no cached Outlook session.", 401)
    result = app.acquire_token_silent(cfg.MS_SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        raise MailboxError(f"Reconnect '{acct['id']}' — couldn't refresh the Outlook token.", 401)
    if cache.has_state_changed:
        acct["msal_cache"] = cache.serialize()
        _save_account(acct)
    return result["access_token"]


def _token(acct: dict) -> str:
    return _gmail_token(acct) if acct["provider"] == "gmail" else _ms_token(acct)


# ── HTTP (stdlib urllib; token in header, never in error text) ───────────────

def _api(method: str, url: str, token: str, body=None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=cfg.HTTP_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        # Surface the provider's status + a short reason, but never the auth header.
        detail = ""
        try:
            payload = json.loads(e.read().decode("utf-8", "ignore"))
            detail = (payload.get("error", {}) or {}).get("message") or payload.get("error_description") or ""
        except Exception:  # noqa: BLE001
            pass
        raise MailboxError(f"Mail API error {e.code}{': ' + detail if detail else ''}",
                           502 if e.code >= 500 else (e.code if e.code in (401, 403, 404) else 502))
    except urllib.error.URLError as e:
        raise MailboxError(f"Couldn't reach the mail API: {e.reason}")
    return json.loads(raw) if raw else {}


def _b64url_decode(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + pad).decode("utf-8", "ignore")
    except (ValueError, TypeError):
        return ""


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = _TAG_RE.sub("", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


# ── Gmail provider ────────────────────────────────────────────────────────────

def _gmail_headers(payload: dict) -> dict:
    return {h.get("name", "").lower(): h.get("value", "")
            for h in (payload.get("headers") or [])}


def _gmail_list(acct, token, query: str, limit: int) -> list[dict]:
    q = query.strip() if query.strip() else "in:inbox"
    params = urllib.parse.urlencode({"q": q, "maxResults": limit})
    listing = _api("GET", f"{cfg.GMAIL_API_BASE}/users/me/messages?{params}", token)
    out = []
    for stub in listing.get("messages", [])[:limit]:
        mp = urllib.parse.urlencode(
            [("format", "metadata"),
             ("metadataHeaders", "From"), ("metadataHeaders", "Subject"),
             ("metadataHeaders", "Date")])
        msg = _api("GET", f"{cfg.GMAIL_API_BASE}/users/me/messages/{stub['id']}?{mp}", token)
        h = _gmail_headers(msg.get("payload", {}))
        out.append({
            "id": msg.get("id", stub["id"]),
            "thread_id": msg.get("threadId", ""),
            "from": h.get("from", ""),
            "subject": h.get("subject", "(no subject)"),
            "date": h.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "unread": "UNREAD" in (msg.get("labelIds") or []),
        })
    return out


def _gmail_body(payload: dict) -> str:
    def walk(part, want):
        if part.get("mimeType", "") == want and part.get("body", {}).get("data"):
            return _b64url_decode(part["body"]["data"])
        for sub in part.get("parts", []) or []:
            got = walk(sub, want)
            if got:
                return got
        return ""
    text = walk(payload, "text/plain")
    if not text:
        html = walk(payload, "text/html")
        text = _strip_html(html) if html else ""
    return text


def _gmail_read(acct, token, msg_id: str) -> dict:
    msg = _api("GET", f"{cfg.GMAIL_API_BASE}/users/me/messages/{msg_id}?format=full", token)
    payload = msg.get("payload", {})
    h = _gmail_headers(payload)
    body = _gmail_body(payload) or msg.get("snippet", "")
    return {
        "id": msg.get("id", msg_id),
        "thread_id": msg.get("threadId", ""),
        "from": h.get("from", ""),
        "to": h.get("to", ""),
        "subject": h.get("subject", "(no subject)"),
        "date": h.get("date", ""),
        "message_id": h.get("message-id", ""),
        "body": body[: cfg.BODY_MAX_CHARS],
        "unread": "UNREAD" in (msg.get("labelIds") or []),
    }


def _gmail_unread(acct, token) -> int:
    label = _api("GET", f"{cfg.GMAIL_API_BASE}/users/me/labels/INBOX", token)
    return int(label.get("messagesUnread", 0) or 0)


def _gmail_draft(acct, token, to, subject, body, reply_to_msg_id) -> dict:
    msg = EmailMessage()
    msg["To"] = to
    thread_id = ""
    if reply_to_msg_id:
        orig = _gmail_read(acct, token, reply_to_msg_id)
        thread_id = orig.get("thread_id", "")
        if orig.get("message_id"):
            msg["In-Reply-To"] = orig["message_id"]
            msg["References"] = orig["message_id"]
        if not subject:
            subject = orig.get("subject", "")
            if subject and not subject.lower().startswith("re:"):
                subject = "Re: " + subject
    msg["Subject"] = subject or "(no subject)"
    msg.set_content(body or "")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    message = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id
    created = _api("POST", f"{cfg.GMAIL_API_BASE}/users/me/drafts", token, {"message": message})
    return {"ok": True, "id": created.get("id", ""), "provider": "gmail",
            "account_id": acct["id"], "link": ""}


# ── Outlook (Microsoft Graph) provider ───────────────────────────────────────

_GRAPH_SELECT = "id,conversationId,subject,from,receivedDateTime,bodyPreview,isRead"


def _graph_msg(m: dict, full: bool = False) -> dict:
    sender = ((m.get("from") or {}).get("emailAddress") or {})
    out = {
        "id": m.get("id", ""),
        "thread_id": m.get("conversationId", ""),
        "from": sender.get("address", "") or sender.get("name", ""),
        "subject": m.get("subject", "(no subject)"),
        "date": m.get("receivedDateTime", ""),
        "snippet": m.get("bodyPreview", ""),
        "unread": not m.get("isRead", True),
    }
    if full:
        body = m.get("body", {}) or {}
        content = body.get("content", "")
        if (body.get("contentType", "") or "").lower() == "html":
            content = _strip_html(content)
        out["to"] = ", ".join(
            (r.get("emailAddress") or {}).get("address", "")
            for r in (m.get("toRecipients") or []))
        out["body"] = content[: cfg.BODY_MAX_CHARS]
    return out


def _graph_list(acct, token, query: str, limit: int) -> list[dict]:
    if query.strip():
        params = urllib.parse.urlencode(
            {"$search": f'"{query.strip()}"', "$select": _GRAPH_SELECT, "$top": limit})
        url = f"{cfg.GRAPH_API_BASE}/me/messages?{params}"
    else:
        params = urllib.parse.urlencode(
            {"$select": _GRAPH_SELECT, "$top": limit, "$orderby": "receivedDateTime desc"})
        url = f"{cfg.GRAPH_API_BASE}/me/mailFolders/inbox/messages?{params}"
    data = _api("GET", url, token)
    return [_graph_msg(m) for m in data.get("value", [])[:limit]]


def _graph_read(acct, token, msg_id: str) -> dict:
    params = urllib.parse.urlencode(
        {"$select": "id,conversationId,subject,from,toRecipients,receivedDateTime,body,isRead"})
    m = _api("GET", f"{cfg.GRAPH_API_BASE}/me/messages/{urllib.parse.quote(msg_id)}?{params}", token)
    return _graph_msg(m, full=True)


def _graph_unread(acct, token) -> int:
    data = _api("GET", f"{cfg.GRAPH_API_BASE}/me/mailFolders/inbox?$select=unreadItemCount", token)
    return int(data.get("unreadItemCount", 0) or 0)


def _graph_draft(acct, token, to, subject, body, reply_to_msg_id) -> dict:
    recipients = [{"emailAddress": {"address": a.strip()}}
                  for a in re.split(r"[,;]", to or "") if a.strip()]
    if reply_to_msg_id:
        # createReply returns a draft reply (correct threading); PATCH our body in.
        draft = _api("POST",
                     f"{cfg.GRAPH_API_BASE}/me/messages/{urllib.parse.quote(reply_to_msg_id)}/createReply",
                     token, {})
        patch = {"body": {"contentType": "Text", "content": body or ""}}
        if subject:
            patch["subject"] = subject
        _api("PATCH", f"{cfg.GRAPH_API_BASE}/me/messages/{draft['id']}", token, patch)
        return {"ok": True, "id": draft.get("id", ""), "provider": "outlook",
                "account_id": acct["id"], "link": draft.get("webLink", "")}
    payload = {
        "subject": subject or "(no subject)",
        "body": {"contentType": "Text", "content": body or ""},
        "toRecipients": recipients,
    }
    created = _api("POST", f"{cfg.GRAPH_API_BASE}/me/messages", token, payload)
    return {"ok": True, "id": created.get("id", ""), "provider": "outlook",
            "account_id": acct["id"], "link": created.get("webLink", "")}


# ── Public API (provider-agnostic) ───────────────────────────────────────────

# Per (account_id, query, limit) TTL cache for inbox listings — same shape as the
# briefing cache in app.py. Keeps the Inbox view snappy and the N+1 Gmail metadata
# fetches off the hot path.
_CACHE: dict[tuple, dict] = {}
_CACHE_LOCK = threading.Lock()


def _clamp_limit(limit) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = cfg.DEFAULT_INBOX_LIMIT
    return max(1, min(n, cfg.MAX_INBOX_LIMIT))


def fetch_inbox(account_id: str, limit: int = cfg.DEFAULT_INBOX_LIMIT, query: str = "") -> dict:
    """Recent inbox messages (or search results if `query` is given), cached."""
    limit = _clamp_limit(limit)
    query = (query or "").strip()
    key = (account_id, query, limit)
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and (now - hit["ts"]) < cfg.INBOX_CACHE_TTL:
            return hit["data"]
    acct = _load_account(account_id)
    token = _token(acct)
    fn = _gmail_list if acct["provider"] == "gmail" else _graph_list
    messages = fn(acct, token, query, limit)
    acct_meta = {"id": acct["id"], "provider": acct["provider"], "address": acct["address"]}
    data = {"account": acct_meta, "query": query, "messages": messages}
    with _CACHE_LOCK:
        _CACHE[key] = {"data": data, "ts": now}
    return data


def search_messages(account_id: str, query: str, limit: int = cfg.SEARCH_LIMIT) -> dict:
    if not (query or "").strip():
        raise MailboxError("Search needs a non-empty query.", 400)
    return fetch_inbox(account_id, limit=limit, query=query)


def read_message(account_id: str, msg_id: str) -> dict:
    if not (msg_id or "").strip():
        raise MailboxError("A message id is required.", 400)
    acct = _load_account(account_id)
    token = _token(acct)
    fn = _gmail_read if acct["provider"] == "gmail" else _graph_read
    return fn(acct, token, msg_id)


def create_draft(account_id: str, to: str = "", subject: str = "", body: str = "",
                 reply_to_msg_id: str = "") -> dict:
    """Create a DRAFT (never send). Reply if reply_to_msg_id is given."""
    if not (to or "").strip() and not (reply_to_msg_id or "").strip():
        raise MailboxError("A draft needs a recipient (or a message to reply to).", 400)
    acct = _load_account(account_id)
    token = _token(acct)
    fn = _gmail_draft if acct["provider"] == "gmail" else _graph_draft
    result = fn(acct, token, to, subject, body, reply_to_msg_id or "")
    # A new draft changes the inbox/draft state — drop this account's cached lists.
    with _CACHE_LOCK:
        for k in [k for k in _CACHE if k[0] == account_id]:
            _CACHE.pop(k, None)
    return result


def accounts_overview() -> dict:
    """All connected accounts with unread counts. Degrades gracefully per account.

    Used by GET /api/inboxes. One account failing to refresh never sinks the rest;
    its error is collected and it's marked status='error'.
    """
    accounts, errors = [], []
    for a in list_accounts():
        entry = {**a, "unread": None, "status": "ok"}
        try:
            acct = _load_account(a["id"])
            token = _token(acct)
            entry["unread"] = (_gmail_unread if a["provider"] == "gmail"
                               else _graph_unread)(acct, token)
        except MailboxError as e:
            entry["status"] = "error"
            errors.append(f"{a['id']}: {e.message}")
        except Exception as e:  # noqa: BLE001 — one bad account never sinks the list
            entry["status"] = "error"
            errors.append(f"{a['id']}: {type(e).__name__}")
        accounts.append(entry)
    return {"accounts": accounts, "errors": errors}


# ── Important mail (overview panel) ──────────────────────────────────────────
# Deterministic work/school triage for the home page: pull the last
# cfg.IMPORTANT_DAYS of mail from every connected inbox, score each message
# against the keyword/domain/penalty config in email_sources.py (no model call —
# this runs on page load), and return the top rows. Reuses fetch_inbox(), so the
# per-(account, query) TTL cache keeps this cheap between loads.

def _parse_msg_date(raw: str):
    """Parse a message date — RFC 2822 (Gmail) or ISO 8601 (Graph) — to aware UTC.

    Returns None when unparseable; callers treat that as 'keep the message'
    (better a stray old mail than a silently dropped important one).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _importance_score(msg: dict) -> tuple[int, list[str]]:
    """Score one message dict for work/school relevance. Pure — easy to test.

    Returns (score, why): keyword/domain hits add, marketing signals subtract,
    unread nudges up. `why` lists the top matched signals for the UI tooltip.
    """
    text = f"{msg.get('subject', '')} {msg.get('snippet', '')}".lower()
    sender = (msg.get("from", "") or "").lower()
    score, why = 0, []
    for kw, w in cfg.IMPORTANT_KEYWORDS.items():
        if kw in text:
            score += w
            why.append(kw)
    for dom, w in cfg.IMPORTANT_SENDER_DOMAINS.items():
        if dom in sender:
            score += w
            why.append(dom)
    for kw, w in cfg.IMPORTANT_PENALTIES.items():
        if kw in text or kw in sender:
            score -= w
    if msg.get("unread"):
        score += 1
    return score, why


def _fmt_when(dt) -> str:
    """Compact local-time label for the panel: 'HH:MM' today, else 'Thu 09'."""
    if dt is None:
        return ""
    local = dt.astimezone()
    now = datetime.now().astimezone()
    return local.strftime("%H:%M") if local.date() == now.date() else local.strftime("%a %d")


def _display_name(sender: str) -> str:
    """'Jane Doe <jane@x.com>' -> 'Jane Doe'; bare addresses pass through."""
    name = re.sub(r"<[^>]*>", "", sender or "").strip().strip('"')
    return name or (sender or "").strip("<> ")


def important_messages() -> dict:
    """Work/school-relevant mail from the last cfg.IMPORTANT_DAYS days, all inboxes.

    Returns {available, messages: [{subject, from, when, account, account_id,
    unread, score, why}], errors}. available=False means no inbox is connected.
    Per-account failures degrade gracefully, mirroring accounts_overview().
    """
    accounts = list_accounts()
    if not accounts:
        return {"available": False, "messages": [], "errors": []}
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.IMPORTANT_DAYS)
    rows, errors = [], []
    for a in accounts:
        try:
            # Gmail narrows server-side; Graph has no newer_than syntax, so its
            # recent listing is filtered by the date cutoff below instead.
            query = (f"in:inbox newer_than:{cfg.IMPORTANT_DAYS}d"
                     if a["provider"] == "gmail" else "")
            data = fetch_inbox(a["id"], limit=cfg.IMPORTANT_FETCH_PER_ACCOUNT, query=query)
        except MailboxError as e:
            errors.append(f"{a['id']}: {e.message}")
            continue
        except Exception as e:  # noqa: BLE001 — one bad inbox never sinks the panel
            errors.append(f"{a['id']}: {type(e).__name__}")
            continue
        for m in data.get("messages", []):
            dt = _parse_msg_date(m.get("date", ""))
            if dt is not None and dt < cutoff:
                continue
            score, why = _importance_score(m)
            if score < cfg.IMPORTANT_MIN_SCORE:
                continue
            rows.append({
                "subject": m.get("subject", "(no subject)"),
                "from": _display_name(m.get("from", "")),
                "when": _fmt_when(dt),
                "account": (a.get("address", "") or a["id"]).split("@")[0],
                "account_id": a["id"],
                "unread": bool(m.get("unread")),
                "score": score,
                "why": why[:3],
                "_ts": dt.timestamp() if dt else 0.0,
            })
    rows.sort(key=lambda r: (-r["score"], -r["_ts"]))
    for r in rows:
        r.pop("_ts", None)
    return {"available": True, "messages": rows[: cfg.IMPORTANT_MAX_SHOWN],
            "errors": errors}
