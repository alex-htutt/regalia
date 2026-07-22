"""Agent loop — a model driving vault tools to finish a task.

This is stage 3 of the workspace: it replaces the stubbed /api/agent/run with a
real run loop. An "agent" here is just a system prompt + an allowed set of vault
tools + a default tier. run_agent() drives the standard tool-use cycle:

    model -> tool calls -> run tools in the vault -> feed results back -> repeat

until the model answers with no more tool calls (or we hit the step cap). Every
model call goes through router.chat_tools(), so the same agent works on the local
(fast) or cloud (smart) tier with no code change here.

Tools are confined to the vault and traversal-safe. The loop emits a small event
per step so the UI can stream what the agent is doing in real time.

Nothing here is imported at module load beyond stdlib + router; app is imported
lazily inside tools to avoid a circular import (app imports agent at top).
"""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import externals
import mailbox
import router


class AgentError(Exception):
    """A run failure with a message safe to show the user."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ── Vault access (confined + traversal-safe) ─────────────────────────────────

def _vault_root() -> Path:
    import app
    return app.VAULT_ROOT.resolve()


def _ignore_dirs() -> set:
    import app
    return app.IGNORE_DIRS


@dataclass(frozen=True)
class AccessScope:
    """One run's immutable filesystem boundary.

    A missing folder means the vault root only. An explicit vault folder or
    external folder narrows every in-process tool and the Claude CLI cwd to that
    subtree; connected externals are never implicitly part of whole-vault runs.
    """

    kind: str                 # "vault" | "external"
    root: Path
    label: str = ""           # vault-relative folder or ext:<name>[/sub]
    explicit: bool = False
    approved_checks: tuple[str, ...] = ()


def resolve_scope(folder: str = "") -> AccessScope:
    """Validate a UI folder value and return the run's canonical boundary."""
    vault = _vault_root()
    folder = (folder or "").replace("\\", "/").strip().strip("/")
    if not folder:
        return AccessScope("vault", vault)
    if folder.lower().startswith("ext:"):
        try:
            target = externals.resolve(folder)
        except ValueError as e:
            raise AgentError(str(e))
        if target is None or not target.is_dir():
            raise AgentError(f"'{folder}' is not a connected external folder.")
        body = folder[4:].strip("/")
        name, _, sub = body.partition("/")
        canonical = f"ext:{name}" + (f"/{sub}" if sub else "")
        return AccessScope("external", target.resolve(), canonical, True)
    target = (vault / folder).resolve()
    if (target != vault and vault not in target.parents) or not target.is_dir():
        raise AgentError(f"'{folder}' is not a folder in the vault.")
    return AccessScope("vault", target, target.relative_to(vault).as_posix(), True)


def _normalized_scope(scope: AccessScope | None) -> AccessScope:
    return scope or AccessScope("vault", _vault_root())


def _inside(root: Path, target: Path) -> bool:
    return target == root or root in target.parents


def _safe_path(rel: str, must_exist: bool = False,
               scope: AccessScope | None = None) -> Path:
    """Resolve a path inside one run's explicit scope, traversal-safe."""
    active = _normalized_scope(scope)
    vault = _vault_root()
    rel = (rel or "").replace("\\", "/").strip().strip("/")
    if not rel:
        raise AgentError("A path is required.")
    if rel.lower().startswith("ext:"):
        if active.kind != "external":
            raise AgentError("External folders are available only when selected for this run.")
        try:
            target = externals.resolve(rel)
        except ValueError as e:
            raise AgentError(str(e))
        if target is None or not _inside(active.root, target):
            raise AgentError(f"Path '{rel}' is outside this run's assigned folder.")
    elif active.kind == "external":
        target = (active.root / rel).resolve()
        if not _inside(active.root, target):
            raise AgentError(f"Path '{rel}' is outside this run's assigned folder.")
    else:
        # In a narrowed vault scope, accept either a vault-relative path carrying
        # the selected prefix or a convenient path relative to the assigned root.
        if active.explicit and (rel == active.label or rel.startswith(active.label + "/")):
            target = (vault / rel).resolve()
        else:
            target = (active.root / rel).resolve()
        if not _inside(vault, target) or not _inside(active.root, target):
            raise AgentError(f"Path '{rel}' is outside this run's assigned folder.")
    if must_exist and not target.exists():
        raise AgentError(f"Nothing found at '{rel}'.")
    return target


def _rel_label(target: Path, scope: AccessScope | None = None) -> str:
    """Return a model-safe label without leaking an external absolute path."""
    active = _normalized_scope(scope)
    if active.kind == "external":
        sub = target.relative_to(active.root).as_posix()
        return active.label + (f"/{sub}" if sub != "." else "")
    return target.relative_to(_vault_root()).as_posix()


# ── Tool implementations ─────────────────────────────────────────────────────
# Each returns a plain string — what the model sees as the tool result.

def _tool_search_vault(query: str = "", limit: int = 12,
                       _scope: AccessScope | None = None, **_) -> str:
    query = (query or "").strip()
    if not query:
        return "Error: search needs a non-empty query."
    active = _normalized_scope(_scope)
    root = active.root
    ignore = _ignore_dirs() if active.kind == "vault" else set()
    q = query.lower()
    hits = []
    for md in root.rglob("*.md"):
        rel = md.relative_to(root)
        if any(part in ignore or part.startswith(".") for part in rel.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        name_hit = q in md.name.lower()
        line_hit = ""
        for line in text.splitlines():
            if q in line.lower():
                line_hit = line.strip()[:160]
                break
        if name_hit or line_hit:
            hits.append(f"{_rel_label(md, active)} — {line_hit or '(filename match)'}")
        if len(hits) >= max(1, min(int(limit or 12), 40)):
            break
    if not hits:
        return f"No notes match '{query}'."
    return f"{len(hits)} match(es) for '{query}':\n" + "\n".join(hits)


def _tool_read_note(path: str = "", _scope: AccessScope | None = None, **_) -> str:
    target = _safe_path(path, must_exist=True, scope=_scope)
    if target.is_dir() or target.suffix.lower() != ".md":
        return f"Error: '{path}' is not a markdown note."
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return f"Error reading '{path}': {e}"
    if len(text) > 8000:
        text = text[:8000] + "\n…(truncated)"
    return text or "(empty note)"


def _tool_list_notes(area: str = "", status: str = "", type: str = "", limit: int = 60,
                     _scope: AccessScope | None = None, **_) -> str:
    import app
    active = _normalized_scope(_scope)
    if active.kind == "external":
        rows = []
        for md in active.root.rglob("*.md"):
            rel = md.relative_to(active.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
                fm, _ = app._parse_frontmatter(text)
            except OSError:
                continue
            tags = app._coerce_tags(fm.get("tags")) if fm else []
            if area and f"area/{area.strip().lower()}" not in tags:
                continue
            if status and str(fm.get("status", "")).lower() != status.strip().lower():
                continue
            if type and f"type/{type.strip().lower()}" not in tags:
                continue
            rows.append(
                f"[{fm.get('status', '?') if fm else '?'}] {_rel_label(md, active)}"
                + (f" — {fm.get('topic')}" if fm and fm.get("topic") else "")
            )
            if len(rows) >= max(1, min(int(limit or 60), 200)):
                break
        return (f"{len(rows)} note(s):\n" + "\n".join(rows)) if rows else "No notes match those filters."

    tasks = app.load_tasks()
    if active.explicit:
        prefix = active.root.relative_to(_vault_root()).as_posix()
        tasks = [t for t in tasks if t.get("file") == prefix
                 or str(t.get("file") or "").startswith(prefix + "/")]
    area = (area or "").strip().lower()
    status = (status or "").strip().lower()
    type_ = (type or "").strip().lower()

    def keep(t):
        tags = t.get("tags") or []
        if area and not any(x == f"area/{area}" for x in tags):
            return False
        if status and t.get("status", "").lower() != status:
            return False
        if type_ and not any(x == f"type/{type_}" for x in tags):
            return False
        return True

    rows = [t for t in tasks if keep(t)]
    rows.sort(key=lambda t: (t.get("date") or ""), reverse=True)
    rows = rows[: max(1, min(int(limit or 60), 200))]
    if not rows:
        return "No notes match those filters."
    lines = []
    for t in rows:
        dl = f" · due {t['deadline']}" if t.get("deadline") else ""
        topic = f" — {t['topic']}" if t.get("topic") else ""
        lines.append(f"[{t.get('status','?')}] {t['file']} :: {t['title']}{topic}{dl}")
    return f"{len(rows)} note(s):\n" + "\n".join(lines)


def _tool_list_folder(path: str = "", _scope: AccessScope | None = None, **_) -> str:
    active = _normalized_scope(_scope)
    root = active.root
    ignore = _ignore_dirs()
    target = root if not (path or "").strip().strip("/") else _safe_path(
        path, must_exist=True, scope=active)
    if not target.is_dir():
        return f"Error: '{path}' is not a folder."
    folders, notes = [], []
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith(".") or child.name in ignore:
            continue
        if child.is_dir():
            folders.append(child.name + "/")
        elif child.suffix.lower() == ".md":
            notes.append(child.name)
    rel = _rel_label(target, active) if target != root else (
        "(vault root)" if not active.explicit else active.label)
    body = []
    if folders:
        body.append("Folders: " + ", ".join(folders))
    if notes:
        body.append("Notes: " + ", ".join(notes))
    return f"{rel}\n" + ("\n".join(body) if body else "(empty)")


def _tool_write_note(path: str = "", content: str = "",
                     _scope: AccessScope | None = None, **_) -> str:
    target = _safe_path(path, scope=_scope)
    if target.suffix.lower() != ".md":
        return "Error: write_note only writes .md files."
    if not (content or "").strip():
        return "Error: refusing to write an empty note."
    existed = target.exists()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Error writing '{path}': {e}"
    return f"{'Overwrote' if existed else 'Created'} {_rel_label(target, _scope)} ({len(content)} chars)."


def _tool_create_project(name: str = "", area: str = "projects", topic: str = "",
                         deadline: str = "", _scope: AccessScope | None = None, **_) -> str:
    import app
    active = _normalized_scope(_scope)
    if active.kind == "external":
        return "Error: project scaffolding is never written into an external folder."
    if active.explicit:
        rel = active.root.relative_to(_vault_root())
        if len(rel.parts) != 1:
            return "Error: create_project needs the whole vault or a top-level area scope."
        try:
            requested = app._safe_area(area)
        except ValueError as e:
            return f"Error: {e}"
        if requested.lower() != rel.parts[0].lower():
            return f"Error: this run is assigned to area '{rel.parts[0]}'."
    try:
        result = app.create_project_core(name, area, topic, deadline)
    except ValueError as e:
        return f"Error: {e}"
    return (
        f"Created project '{result['path']}' with subfolders "
        f"{', '.join(result['subdirs'])} and {result['context_file']}"
        + (" · linked in Home." if result.get("home_linked") else ".")
    )


# ── General scoped file + research tools for custom dispatch agents ──────────

def _iter_scope_files(scope: AccessScope, pattern: str = "**/*"):
    ignore = _ignore_dirs() if scope.kind == "vault" else set()
    try:
        candidates = scope.root.glob(pattern or "**/*")
    except (ValueError, OSError):
        candidates = scope.root.rglob("*")
    for path in candidates:
        try:
            rel = path.relative_to(scope.root)
        except ValueError:
            continue
        if any(part in ignore or part in (".git", ".dispatch_work") for part in rel.parts):
            continue
        if any(part.startswith(".") and part not in (".github",) for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path, rel.as_posix()


def _tool_list_files(pattern: str = "**/*", limit: int = 200,
                     _scope: AccessScope | None = None, **_) -> str:
    scope = _normalized_scope(_scope)
    limit = max(1, min(int(limit or 200), 500))
    rows = []
    for path, rel in _iter_scope_files(scope, pattern):
        try:
            rows.append(f"{rel} ({path.stat().st_size} bytes)")
        except OSError:
            rows.append(rel)
        if len(rows) >= limit:
            break
    return "\n".join(rows) if rows else "No files matched."


def _tool_read_file(path: str = "", max_bytes: int = 200000,
                    _scope: AccessScope | None = None, **_) -> str:
    target = _safe_path(path, must_exist=True, scope=_scope)
    if not target.is_file():
        return f"Error: '{path}' is not a file."
    max_bytes = max(1024, min(int(max_bytes or 200000), 1000000))
    try:
        raw = target.read_bytes()[:max_bytes + 1]
    except OSError as e:
        return f"Error reading '{path}': {e}"
    if b"\x00" in raw[:4096]:
        return f"Error: '{path}' appears to be binary."
    clipped = len(raw) > max_bytes
    text = raw[:max_bytes].decode("utf-8", errors="replace")
    return text + (f"\n\n…(truncated at {max_bytes} bytes)" if clipped else "")


def _tool_search_files(query: str = "", pattern: str = "**/*", limit: int = 50,
                       _scope: AccessScope | None = None, **_) -> str:
    query = str(query or "").strip()
    if not query:
        return "Error: query is required."
    scope = _normalized_scope(_scope)
    needle = query.lower()
    hits = []
    for path, rel in _iter_scope_files(scope, pattern):
        try:
            if path.stat().st_size > 1000000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{rel}:{line_no}: {line.strip()[:240]}")
                break
        if len(hits) >= max(1, min(int(limit or 50), 200)):
            break
    return "\n".join(hits) if hits else f"No files matched '{query}'."


def _tool_write_file(path: str = "", content: str = "",
                     _scope: AccessScope | None = None, **_) -> str:
    scope = _normalized_scope(_scope)
    target = _safe_path(path, scope=scope)
    if ".git" in target.relative_to(scope.root).parts:
        return "Error: agent writes cannot target .git metadata."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content or ""), encoding="utf-8")
    except OSError as e:
        return f"Error writing '{path}': {e}"
    return f"Wrote {_rel_label(target, scope)} ({len(str(content or ''))} characters)."


def _tool_run_check(command: str = "", timeout: int = 120,
                    _scope: AccessScope | None = None, **_) -> str:
    scope = _normalized_scope(_scope)
    command = str(command or "").strip()
    if not command:
        return "Error: command is required."
    if not any(command == allowed or command.startswith(allowed + " ")
               for allowed in scope.approved_checks):
        return "Error: that command was not approved in the dispatch plan."
    try:
        argv = shlex.split(command, posix=(os.name != "nt"))
    except ValueError as e:
        return f"Error parsing command: {e}"
    safe_env_keys = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "LANG",
        "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in safe_env_keys}
    try:
        proc = subprocess.run(
            argv, cwd=str(scope.root), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=max(1, min(int(timeout or 120), 600)),
        )
    except subprocess.TimeoutExpired:
        return "Error: approved check timed out."
    except (OSError, ValueError) as e:
        return f"Error starting approved check: {e}"
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    return f"exit {proc.returncode}\n{output[:12000]}"


def _public_http_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise AgentError("Only public http/https URLs are allowed.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as e:
        raise AgentError(f"Could not resolve that URL: {e}")
    for item in addresses:
        try:
            ip = ipaddress.ip_address(item[4][0])
        except ValueError:
            continue
        if not ip.is_global:
            raise AgentError("Private, local, and reserved network addresses are blocked.")
    return parsed.geturl()


def _http_text(url: str, max_bytes: int = 750000) -> tuple[str, str]:
    safe = _public_http_url(url)
    req = urllib.request.Request(safe, headers={
        "User-Agent": "Mozilla/5.0 (compatible; RegaliaResearch/1.0)",
        "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            final_url = _public_http_url(response.geturl())
            ctype = (response.headers.get_content_type() or "").lower()
            if ctype not in ("text/html", "text/plain", "application/json", "application/xml", "text/xml"):
                raise AgentError(f"Unsupported web content type: {ctype or 'unknown'}.")
            raw = response.read(max_bytes + 1)
    except AgentError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise AgentError(f"Web request failed: {e}")
    return raw[:max_bytes].decode("utf-8", errors="replace"), final_url


def _tool_web_search(query: str = "", limit: int = 6, **_) -> str:
    query = str(query or "").strip()
    if not query:
        return "Error: search query is required."
    limit = max(1, min(int(limit or 6), 10))
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        body, _ = _http_text(url)
    except AgentError as e:
        return f"Error: {e.message}"
    links = re.findall(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        body, re.I | re.S,
    )
    snippets = re.findall(
        r'<(?:a|div)[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
        body, re.I | re.S,
    )
    rows = []
    for i, (href, title) in enumerate(links[:limit]):
        href = html.unescape(href)
        parsed = urllib.parse.urlparse(href)
        if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
            href = urllib.parse.parse_qs(parsed.query).get("uddg", [href])[0]
        clean_title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        snippet = html.unescape(re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "")).strip()
        rows.append(f"{i + 1}. {clean_title}\n   {href}\n   {snippet}".rstrip())
    return "\n".join(rows) if rows else "No web results were returned."


def _tool_fetch_url(url: str = "", **_) -> str:
    try:
        body, final_url = _http_text(url)
    except AgentError as e:
        return f"Error: {e.message}"
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return f"Source: {final_url}\n\n{text[:60000]}"


# ── Email tools (Gmail + Outlook, via mailbox.py) ────────────────────────────
# Read-only tools (list/read/search) plus a single write tool, draft_email, which
# creates a DRAFT only — there is deliberately no send tool. draft_email is gated
# like write_note: it's only handed to agents that explicitly list it, never to a
# read-only chat turn. Each returns a plain string for the model to read.

def _fmt_message_line(m: dict) -> str:
    flag = "● " if m.get("unread") else "  "
    return (f"{flag}[{m.get('id','')}] {m.get('from','?')} — "
            f"{m.get('subject','(no subject)')} · {m.get('date','')}".rstrip())


def _tool_list_inboxes(**_) -> str:
    data = mailbox.accounts_overview()
    accts = data.get("accounts", [])
    if not accts:
        return ("No inboxes connected. Connect one by running "
                "`python connect_email.py gmail` or `... outlook`.")
    lines = []
    for a in accts:
        unread = a.get("unread")
        ucount = f"{unread} unread" if isinstance(unread, int) else a.get("status", "")
        lines.append(f"{a['id']} ({a['provider']}: {a.get('address','')}) — {ucount}")
    out = f"{len(accts)} inbox(es):\n" + "\n".join(lines)
    if data.get("errors"):
        out += "\nNote: " + "; ".join(data["errors"])
    return out


def _tool_read_inbox(account_id: str = "", limit: int = 10, **_) -> str:
    if not account_id.strip():
        return "Error: account_id is required (see list_inboxes)."
    try:
        data = mailbox.fetch_inbox(account_id, limit=limit or 10)
    except mailbox.MailboxError as e:
        return f"Error: {e.message}"
    msgs = data.get("messages", [])
    if not msgs:
        return f"Inbox '{account_id}' has no recent messages."
    return f"{len(msgs)} recent message(s) in {account_id}:\n" + "\n".join(
        _fmt_message_line(m) for m in msgs)


def _tool_search_email(account_id: str = "", query: str = "", limit: int = 10, **_) -> str:
    if not account_id.strip():
        return "Error: account_id is required (see list_inboxes)."
    if not query.strip():
        return "Error: search needs a non-empty query."
    try:
        data = mailbox.search_messages(account_id, query, limit=limit or 10)
    except mailbox.MailboxError as e:
        return f"Error: {e.message}"
    msgs = data.get("messages", [])
    if not msgs:
        return f"No messages in {account_id} match '{query}'."
    return f"{len(msgs)} match(es) for '{query}' in {account_id}:\n" + "\n".join(
        _fmt_message_line(m) for m in msgs)


def _tool_read_email(account_id: str = "", msg_id: str = "", **_) -> str:
    if not account_id.strip() or not msg_id.strip():
        return "Error: account_id and msg_id are required."
    try:
        m = mailbox.read_message(account_id, msg_id)
    except mailbox.MailboxError as e:
        return f"Error: {e.message}"
    return (f"From: {m.get('from','')}\nTo: {m.get('to','')}\n"
            f"Subject: {m.get('subject','')}\nDate: {m.get('date','')}\n\n"
            f"{m.get('body','') or '(empty body)'}")


def _tool_draft_email(account_id: str = "", to: str = "", subject: str = "",
                      body: str = "", reply_to: str = "", **_) -> str:
    if not account_id.strip():
        return "Error: account_id is required (see list_inboxes)."
    try:
        result = mailbox.create_draft(account_id, to=to, subject=subject, body=body,
                                      reply_to_msg_id=reply_to)
    except mailbox.MailboxError as e:
        return f"Error: {e.message}"
    return (f"Draft saved in {account_id} (id {result.get('id','?')}). "
            "It was NOT sent — review and send it from your mail client.")


def _tool_stage_email_draft(account_id: str = "", to: str = "", subject: str = "",
                            body: str = "", reply_to: str = "", **_) -> str:
    """Record a dispatch draft proposal without touching the mailbox."""
    if not account_id.strip():
        return "Error: account_id is required (see list_inboxes)."
    if not body.strip():
        return "Error: a draft body is required."
    if not to.strip() and not reply_to.strip():
        return "Error: provide either to or reply_to."
    return (
        f"Draft proposal staged for review in {account_id}. It has NOT been saved "
        "to the mailbox; the user must apply the dispatch first."
    )


TOOL_FNS = {
    "search_vault": _tool_search_vault,
    "read_note": _tool_read_note,
    "list_notes": _tool_list_notes,
    "list_folder": _tool_list_folder,
    "write_note": _tool_write_note,
    "create_project": _tool_create_project,
    "list_files": _tool_list_files,
    "read_file": _tool_read_file,
    "search_files": _tool_search_files,
    "write_file": _tool_write_file,
    "run_check": _tool_run_check,
    "web_search": _tool_web_search,
    "fetch_url": _tool_fetch_url,
    "list_inboxes": _tool_list_inboxes,
    "read_inbox": _tool_read_inbox,
    "search_email": _tool_search_email,
    "read_email": _tool_read_email,
    "draft_email": _tool_draft_email,
    "stage_email_draft": _tool_stage_email_draft,
}

# Anthropic-style tool schemas. router.chat_tools translates these for Ollama.
TOOL_SCHEMAS = {
    "search_vault": {
        "name": "search_vault",
        "description": "Search every markdown note in the vault for a substring (filename or body). Returns matching paths with a snippet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to look for."},
                "limit": {"type": "integer", "description": "Max results (default 12)."},
            },
            "required": ["query"],
        },
    },
    "read_note": {
        "name": "read_note",
        "description": "Read the full markdown content of one note by its vault-relative path.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Vault-relative path, e.g. 'projects/foo/notes/bar.md'."}},
            "required": ["path"],
        },
    },
    "list_notes": {
        "name": "list_notes",
        "description": "List notes that have frontmatter, optionally filtered by area tag (the part after area/ in a note's tags), status (active/complete/archived), or type (daily-log/standup/meeting/...). Newest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {"type": "string"},
                "status": {"type": "string"},
                "type": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    "list_folder": {
        "name": "list_folder",
        "description": "List the subfolders and notes directly inside a vault folder. Omit path for the vault root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Vault-relative folder path. Empty = vault root."}},
        },
    },
    "write_note": {
        "name": "write_note",
        "description": "Create or overwrite a markdown note at a vault-relative path. Include valid YAML frontmatter (date, tags, status, topic, deadline, related) per the vault schema. Use this to save the output of your work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    "create_project": {
        "name": "create_project",
        "description": "Scaffold a new project folder (code/data/notes/research subdirs + a _context_*.md) and link it into Home.md.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "area": {"type": "string", "description": "Top-level vault folder to file the project under (created if missing). Check existing top-level folders with list_folder first and reuse one that fits; default 'projects'."},
                "topic": {"type": "string"},
                "deadline": {"type": "string", "description": "YYYY-MM-DD, optional."},
            },
            "required": ["name"],
        },
    },
    "list_files": {
        "name": "list_files",
        "description": "List files inside the assigned workspace scope. Hidden metadata and .git are excluded.",
        "input_schema": {"type": "object", "properties": {
            "pattern": {"type": "string", "description": "Glob such as '**/*.py'."},
            "limit": {"type": "integer"},
        }},
    },
    "read_file": {
        "name": "read_file",
        "description": "Read a UTF-8 text file inside the assigned workspace scope.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string"}, "max_bytes": {"type": "integer"},
        }, "required": ["path"]},
    },
    "search_files": {
        "name": "search_files",
        "description": "Search text files inside the assigned workspace scope and return matching paths and lines.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}, "pattern": {"type": "string"},
            "limit": {"type": "integer"},
        }, "required": ["query"]},
    },
    "write_file": {
        "name": "write_file",
        "description": "Create or replace a UTF-8 text file inside the isolated assigned workspace.",
        "input_schema": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]},
    },
    "run_check": {
        "name": "run_check",
        "description": "Run one command explicitly approved in the dispatch plan, inside the isolated workspace.",
        "input_schema": {"type": "object", "properties": {
            "command": {"type": "string"}, "timeout": {"type": "integer"},
        }, "required": ["command"]},
    },
    "web_search": {
        "name": "web_search",
        "description": "Search the public web. Returns titles, URLs, and snippets; cite URLs in the final answer.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer"},
        }, "required": ["query"]},
    },
    "fetch_url": {
        "name": "fetch_url",
        "description": "Read a public web page as text. Private/local network addresses are blocked.",
        "input_schema": {"type": "object", "properties": {
            "url": {"type": "string"},
        }, "required": ["url"]},
    },
    "list_inboxes": {
        "name": "list_inboxes",
        "description": "List the connected email inboxes (Gmail/Outlook) with their account ids, addresses, and unread counts. Call this first to get the account_id the other email tools need.",
        "input_schema": {"type": "object", "properties": {}},
    },
    "read_inbox": {
        "name": "read_inbox",
        "description": "List recent messages in an inbox (newest first). Returns each message's id, sender, subject, date, and unread flag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "From list_inboxes."},
                "limit": {"type": "integer", "description": "Max messages (default 10)."},
            },
            "required": ["account_id"],
        },
    },
    "search_email": {
        "name": "search_email",
        "description": "Search an inbox for messages matching a query (sender, subject, or body). Returns matching message ids + headers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "From list_inboxes."},
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Max results (default 10)."},
            },
            "required": ["account_id", "query"],
        },
    },
    "read_email": {
        "name": "read_email",
        "description": "Read one full email (headers + body) by its message id within an account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "From list_inboxes."},
                "msg_id": {"type": "string", "description": "From read_inbox/search_email."},
            },
            "required": ["account_id", "msg_id"],
        },
    },
    "draft_email": {
        "name": "draft_email",
        "description": "Save a DRAFT email (it is never sent — the user reviews and sends it). Provide either `to` for a new message, or `reply_to` (a message id) to draft a reply on that thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "From list_inboxes."},
                "to": {"type": "string", "description": "Recipient(s), comma-separated. Omit for a reply."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain-text body."},
                "reply_to": {"type": "string", "description": "Message id to reply to (optional)."},
            },
            "required": ["account_id"],
        },
    },
    "stage_email_draft": {
        "name": "stage_email_draft",
        "description": "Stage a DRAFT email proposal for dispatch review. It is not saved to the mailbox until the user explicitly applies the dispatch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "From list_inboxes."},
                "to": {"type": "string", "description": "Recipient(s), comma-separated. Omit for a reply."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain-text body."},
                "reply_to": {"type": "string", "description": "Message id to reply to (optional)."},
            },
            "required": ["account_id", "body"],
        },
    },
}


# ── Agent registry ───────────────────────────────────────────────────────────

_VAULT_RULES = (
    "You work inside an Obsidian markdown vault. Conventions: notes use YAML "
    "frontmatter (date YYYY-MM-DD, tags like [area/projects, type/lab], status, "
    "topic, deadline, related). Links are [[wikilinks]], never relative paths. "
    "Use the tools to read real vault content — never invent file contents or paths. "
    "When you finish, give a short plain-text summary of what you did."
)

def _scope_note(scope: AccessScope) -> str:
    """Describe only the selected scope; never enumerate or leak other roots."""
    if not scope.explicit:
        return ""
    if scope.kind == "external":
        name = scope.label[4:].split("/", 1)[0]
        return (
            f"\n\nTHIS RUN IS SCOPED ONLY TO CONNECTED EXTERNAL FOLDER '{name}'. "
            f"Vault tools accept paths relative to it or prefixed '{scope.label}/'. "
            "Native file tools start in that assigned folder. Do not create Regalia "
            "vault scaffolding inside it. No other vault or external folder is in scope."
        )
    return (
        f"\n\nTHIS RUN IS SCOPED ONLY TO VAULT FOLDER '{scope.label}'. "
        "Tool paths may be relative to that folder. No sibling vault folder or "
        "connected external folder is in scope."
    )


# External folders keep their own conventions: agents must never impose the
# Regalia vault schema on a connected folder. If the folder declares a workflow
# (CLAUDE.md, AGENTS.md, cursor rules, …) we inject that instead; otherwise
# this neutral fallback applies.
_GENERIC_EXTERNAL_RULES = (
    "You are working in the user's own folder, which does not follow Regalia's "
    "vault conventions. Do NOT add YAML frontmatter, [[wikilinks]], _context_ "
    "files, or any Regalia scaffolding. Match the folder's existing structure, "
    "file types, and naming. Use the tools to read real content — never invent "
    "file contents or paths. When you finish, give a short plain-text summary "
    "of what you did."
)

# Convention files probed (in priority order) inside an external folder. Only
# the first group that yields content is used; .cursor/rules/*.mdc are read raw
# and concatenated (no frontmatter parsing).
_WORKFLOW_FILES = ("CLAUDE.md", "AGENTS.md", ".cursor/rules/*.mdc",
                   ".github/copilot-instructions.md", "README.md")
_WORKFLOW_CHAR_CAP = 4000


def _external_conn_root(scope: AccessScope) -> Path | None:
    """The registered connection root for an external scope (label ext:<name>[/sub])."""
    if scope.kind != "external" or not scope.label.lower().startswith("ext:"):
        return None
    name = scope.label[4:].split("/", 1)[0]
    match = next((p for n, p in externals.load().items()
                  if n.lower() == name.lower()), None)
    return Path(match).resolve() if match else None


def _detect_external_workflow(scope: AccessScope) -> str:
    """Read the external folder's own convention files, wrapped for injection.

    Probes the run's scope root first, then the registered connection root (an
    ext:<name>/sub scope roots at the subfolder while CLAUDE.md usually lives at
    the connection root). Best-effort: unreadable files are skipped, content is
    capped, and "" means nothing was found.
    """
    roots = [scope.root]
    conn = _external_conn_root(scope)
    if conn is not None and conn != scope.root:
        roots.append(conn)
    for root in roots:
        for pattern in _WORKFLOW_FILES:
            try:
                files = sorted(root.glob(pattern)) if "*" in pattern else \
                    [root / pattern]
                parts = []
                for f in files:
                    if not f.is_file():
                        continue
                    text = f.read_text(encoding="utf-8", errors="replace").strip()
                    if text:
                        parts.append((f.name, text))
                if not parts:
                    continue
                body = "\n\n".join(f"--- {name} ---\n{text}" if len(parts) > 1
                                   else text for name, text in parts)
                body = body[:_WORKFLOW_CHAR_CAP]
                names = ", ".join(name for name, _ in parts)
                if pattern == "README.md":
                    return (
                        f"Context about this folder (from its {names}) — use it to "
                        "match the project's structure and purpose; do not impose "
                        f"any other schema:\n\n{body}"
                    )
                return (
                    f"This folder defines its own working conventions (from "
                    f"{names}). Follow them instead of any other schema:\n\n{body}"
                )
            except OSError:
                continue
    return ""


def _workflow_rules(scope: AccessScope) -> str:
    """The workflow block appended to a vault-tool agent's system prompt."""
    if scope.kind == "external":
        return "\n\n" + (_detect_external_workflow(scope) or _GENERIC_EXTERNAL_RULES)
    return "\n\n" + _VAULT_RULES


AGENTS = {
    "summarizer": {
        "id": "summarizer",
        "name": "Daily Summarizer",
        "desc": "Roll up recent daily-logs into a standup note.",
        "tier": "fast",
        "tools": ["list_notes", "read_note", "write_note"],
        "default_task": "Summarize my most recent daily-log notes into a concise standup.",
        "presets": [
            "Summarize my most recent daily-log notes into a concise standup.",
            "Write a short weekly review: what happened across my active notes, what's next, and any looming deadlines.",
            "Find notes whose deadline is within the next 7 days and list them by urgency.",
        ],
        "system": (
            "You are the Daily Summarizer. Use list_notes (type 'daily-log') to find "
            "recent logs, read the latest few with read_note, then synthesize a tight "
            "standup: what got done, what's next, and any blockers. If the user asks you "
            "to save it, write it with write_note as a type/standup note with correct "
            "frontmatter; otherwise just return the standup text."
        ),
    },
    "scaffolder": {
        "id": "scaffolder",
        "name": "Project Scaffolder",
        "desc": "Turn a one-line brief into a project folder + context file.",
        "tier": "fast",
        "tools": ["list_folder", "create_project"],
        "default_task": "",
        "presets": [
            "List the vault's top-level folders and tell me where a new project would fit best.",
            "Create a project called Scratchpad for quick experiments, under the area that fits best.",
        ],
        "system": (
            "You are the Project Scaffolder. Turn the user's one-line brief into exactly "
            "one project: infer a clear name, pick the area (check the vault's top-level "
            "folders with list_folder and reuse one that fits, else choose a short new "
            "name — default 'projects'), write a one-line topic, and call create_project "
            "once. If the brief is too vague to name a project, ask for the missing "
            "detail instead of guessing."
        ),
    },
    "researcher": {
        "id": "researcher",
        "name": "Research Agent",
        "desc": "Research a topic across the vault and synthesize a structured research note.",
        "tier": "smart",
        "tools": ["search_vault", "read_note", "list_notes", "write_note"],
        "default_task": "",
        "presets": [
            "Survey my research notes and write an overview of the main themes and open questions.",
            "Pick my most active project and synthesize a research note on its current state from the vault.",
        ],
        "system": (
            "You are the Research Agent. Given a topic, search_vault and read the most "
            "relevant notes, then synthesize a well-structured research note (overview, "
            "key findings with note references via [[wikilinks]], open questions). Save it "
            "with write_note under the relevant project's research/ folder as a "
            "type/research note with proper frontmatter, then summarize what you wrote."
        ),
    },
    "inbox_triage": {
        "id": "inbox_triage",
        "name": "Inbox Triage",
        "desc": "Read connected inboxes, summarize what needs attention, and draft replies for review.",
        # Defaults to the claude tier (subscription-billed, no API key): the CLI
        # reaches mailbox.py through the mail_mcp.py MCP bridge (mcp__mailbox__*
        # grants only — no filesystem tools). On fast/smart it drives the same
        # tools in-process. Drafts-only by construction either way: draft_email
        # creates a DRAFT in the account; nothing in the codebase can send.
        "tier": "claude",
        "tools": ["list_inboxes", "read_inbox", "search_email", "read_email", "draft_email"],
        "default_task": "Summarize the unread mail across my connected inboxes and flag anything that needs a reply.",
        "presets": [
            "Summarize the unread mail across my connected inboxes and flag anything that needs a reply.",
            "Review the last 2 days of mail and draft replies for anything urgent — drafts only, I'll review them.",
            "List everything work- or school-related that arrived today, most important first.",
        ],
        "system": (
            "You are Inbox Triage. Use list_inboxes to see the connected accounts, then "
            "read_inbox / search_email / read_email to review recent and unread mail — "
            "open anything important before judging it. Produce a concise, prioritized "
            "summary: who emailed, what they want, and what (if anything) needs a reply. "
            "When a reply is warranted, you may save one with draft_email — it creates a "
            "DRAFT for the human to review and send; nothing you do sends mail. Be "
            "accurate: never invent senders or message contents; read the mail before "
            "summarizing it."
        ),
    },
}

# Agent runs require tool-calling support. The ChatGPT-account backend is a
# plain chat backend, so keep the agent-capable tiers explicit here rather than
# inheriting every value accepted by router.chat().
AGENT_TIERS = ("fast", "smart", "openai", "chatgpt", "claude")
VAULT_TOOL_NAMES = frozenset({
    "search_vault", "read_note", "list_notes", "list_folder", "write_note", "create_project",
})
FILE_TOOL_NAMES = frozenset({"list_files", "read_file", "search_files", "write_file", "run_check"})
CAPABILITY_TOOLS = {
    "vault_read": ["search_vault", "read_note", "list_notes", "list_folder"],
    "vault_write": ["write_note", "create_project"],
    "code_read": ["list_files", "read_file", "search_files"],
    "code_write": ["write_file"],
    "run_checks": ["run_check"],
    "web": ["web_search", "fetch_url"],
    "inbox_read": ["list_inboxes", "read_inbox", "search_email", "read_email"],
    "inbox_draft": ["stage_email_draft"],
}


def spec_from_definition(definition: dict, worker_id: str = "") -> dict:
    """Turn a saved/ephemeral UI definition into run_agent's internal spec."""
    capabilities = [str(x) for x in definition.get("capabilities") or []]
    tools = []
    for capability in capabilities:
        for tool in CAPABILITY_TOOLS.get(capability, []):
            if tool not in tools:
                tools.append(tool)
    name = str(definition.get("name") or definition.get("title") or "Dispatched agent").strip()
    instructions = str(definition.get("instructions") or definition.get("objective") or "").strip()
    return {
        "id": worker_id or str(definition.get("id") or "dispatch_agent"),
        "name": name,
        "desc": str(definition.get("description") or "").strip(),
        "tier": str(definition.get("tier") or "fast").strip().lower(),
        "tools": tools,
        "default_task": str(definition.get("objective") or "").strip(),
        "presets": [],
        "approved_checks": [str(x).strip() for x in definition.get("approved_checks") or [] if str(x).strip()],
        "system": instructions or (
            f"You are {name}. Complete the assigned task using only the capabilities "
            "and workspace scope provided. Report evidence, changed files, and checks."
        ),
    }


def _spec_supports_folder(spec: dict) -> bool:
    return any(name in VAULT_TOOL_NAMES or name in FILE_TOOL_NAMES for name in spec.get("tools", []))


def supports_folder(agent_id: str) -> bool:
    spec = AGENTS.get(agent_id) or {}
    return _spec_supports_folder(spec)


def list_agents() -> list:
    """Public, UI-facing view of the registry (no prompts/tools internals)."""
    return [
        {"id": a["id"], "name": a["name"], "desc": a["desc"], "tier": a["tier"],
         "status": "idle", "presets": list(a.get("presets", [])),
         "folder_capable": supports_folder(a["id"])}
        for a in AGENTS.values()
    ]


# ── Vault-reading chat (read-only tool loop) ─────────────────────────────────
# Used by /api/chat's fast (local) tier so the local model can actually open
# notes instead of only seeing the folder outline. Only the read-only tools are
# exposed — a chat turn must never silently write or scaffold.

CHAT_TOOLS = ["search_vault", "read_note", "list_notes", "list_folder"]

# Extra tools unlocked only when the caller passes allow_write=True (the chat
# panel's "Edit mode" toggle). These mutate the vault, so they're never exposed
# on a normal read-only chat turn.
CHAT_WRITE_TOOLS = ["write_note", "create_project"]

CHAT_SYSTEM = (
    "You are a helpful assistant for the user's Obsidian knowledge vault, \"Regalia\". "
    "You have tools to search, list, and read the real notes — use them to ground "
    "your answers in actual vault content instead of guessing. To answer a question "
    "about what a note says, find it (search_vault / list_folder / list_notes) and "
    "then read_note to quote or summarize what it actually contains. Never invent "
    "file contents or paths; if you can't find something, say so. You don't need a "
    "tool for small talk or general questions — answer those directly in plain prose. "
    "The vault's current folder/file structure is below to help you target reads.\n\n"
    "=== VAULT STRUCTURE ===\n{outline}\n=== END VAULT STRUCTURE ===\n\n" + _VAULT_RULES
)

# Appended to CHAT_SYSTEM when Edit mode is on. write_note overwrites whole notes,
# so the model is told to read first and preserve existing content/frontmatter,
# and to act only on an explicit request.
CHAT_WRITE_RULES = (
    "\n\nEDIT MODE IS ON. You may now change the vault with write_note (create or "
    "overwrite a .md note — always include the full, valid YAML frontmatter the "
    "schema requires) and create_project (scaffold a new project folder). Only "
    "write when the user actually asks you to create or change something — never "
    "as a side effect of a question. write_note replaces the entire file, so to "
    "edit an existing note, read_note it first and write back the full updated "
    "content (keeping the existing frontmatter and the parts you weren't asked to "
    "change). After writing, tell the user exactly which file you changed and what "
    "you changed in it."
)


def chat_vault(messages, tier="fast", system=None, max_tokens=2048, model=None,
               max_steps=6, allow_write=False) -> dict:
    """Free-form chat that can read (and, with allow_write, change) the vault.

    Drop-in for router.chat() on the fast tier — same return shape
    ({"reply", "model", "tier"}) so /api/chat can use it directly. Drives the
    model -> tool calls -> results cycle over the full conversation history, then
    returns the model's final prose answer. Raises router.RouterError on a backend
    failure (e.g. the local model can't do tool calls), so the caller can fall back
    to plain outline-grounded chat.

    allow_write unlocks the write/scaffold tools (CHAT_WRITE_TOOLS) and the
    edit-mode guidance — the chat panel passes it only when "Edit mode" is on.
    """
    import app
    tool_names = CHAT_TOOLS + (CHAT_WRITE_TOOLS if allow_write else [])
    tools = [TOOL_SCHEMAS[n] for n in tool_names if n in TOOL_SCHEMAS]
    sys_text = CHAT_SYSTEM.format(outline=app._vault_outline())
    if allow_write:
        sys_text += CHAT_WRITE_RULES
    if system and str(system).strip():
        sys_text += "\n\n" + str(system).strip()

    # chat_tools accepts string OR block content; start from the caller's history
    # and append tool_use / tool_result blocks as the loop runs.
    convo = [{"role": m["role"], "content": m["content"]} for m in messages]
    model_used = ""

    for _ in range(max_steps):
        res = router.chat_tools(convo, tools, tier=tier, system=sys_text,
                                max_tokens=max_tokens, model=model)
        model_used = res.get("model", model_used)
        text, tool_calls = res.get("text", ""), res.get("tool_calls", [])

        if not tool_calls:
            return {"reply": text or "…(empty response from the local model)",
                    "model": model_used, "tier": res.get("tier", tier)}

        assistant_content = ([{"type": "text", "text": text}] if text else []) + [
            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
            for tc in tool_calls
        ]
        convo.append({"role": "assistant", "content": assistant_content})

        results = []
        for tc in tool_calls:
            fn = TOOL_FNS.get(tc["name"])
            args = tc.get("input") or {}
            if fn is None:
                out = f"Error: no such tool '{tc['name']}'."
            else:
                try:
                    out = fn(_scope=AccessScope("vault", _vault_root()), **args) if isinstance(args, dict) else fn()
                except AgentError as e:
                    out = f"Error: {e.message}"
                except Exception as e:  # noqa: BLE001 — tool errors feed back to the model
                    out = f"Error running {tc['name']}: {e}"
            results.append({"type": "tool_result", "tool_use_id": tc["id"], "content": out})
        convo.append({"role": "user", "content": results})

    return {"reply": "I read through several notes but couldn't settle on an answer — "
                     "try narrowing the question.",
            "model": model_used, "tier": tier}


# ── Subscription (claude CLI) agent runner — streamed (option 2) ─────────────
# The `claude` tier doesn't drive our in-process tool loop: the Claude Code CLI
# runs its OWN model→tools→repeat loop and we stream its events. It bills the
# signed-in subscription (no API key) and uses the CLI's native file tools rather
# than our custom vault tools, so the agent prompts get a translation note.

_CLAUDE_AGENT_RULES = (
    "\n\nRUNTIME NOTE: You are running with your own built-in tools (Read, Grep, "
    "Glob, and — when this task involves saving work — Write and Edit), with the "
    "run's assigned filesystem scope as your current working directory. Any tool names referenced above "
    "(search_vault, read_note, list_notes, list_folder, write_note, create_project) "
    "are conceptual — accomplish the equivalent with your own tools: search with "
    "Grep/Glob, open notes with Read, and save notes by writing .md files (with "
    "correct YAML frontmatter) via Write/Edit. To scaffold a project, create its "
    "folder (under a fitting existing top-level folder, or a sensible new one — "
    "default 'projects') with code/data/notes/research subfolders and a "
    "_context_<name>.md, then add a [[wikilink]] to it in Home.md. Finish with a "
    "short plain-text summary."
)

# External-scope variant: same tool translation, but no Regalia scaffolding
# steps — the connected folder keeps its own structure and file formats.
_CLAUDE_EXTERNAL_AGENT_RULES = (
    "\n\nRUNTIME NOTE: You are running with your own built-in tools (Read, Grep, "
    "Glob, and — when this task involves saving work — Write and Edit), with the "
    "run's assigned folder as your current working directory. Any tool names "
    "referenced above (search_vault, read_note, list_notes, list_folder, "
    "write_note, create_project) are conceptual — accomplish the equivalent with "
    "your own tools: search with Grep/Glob, open files with Read, and save work "
    "with Write/Edit, matching the folder's existing formats and naming. Finish "
    "with a short plain-text summary."
)


def _claude_runtime_note(scope: AccessScope) -> str:
    """The tool-translation note for the claude CLI tier, per scope kind."""
    return (_CLAUDE_EXTERNAL_AGENT_RULES if scope.kind == "external"
            else _CLAUDE_AGENT_RULES)

# The email tools ride to the claude tier over MCP (mail_mcp.py) — the CLI can't
# call our in-process Python tools, but it can call the same functions through the
# mailbox MCP server, granted per-tool as mcp__mailbox__<name>.
EMAIL_TOOL_NAMES = ("list_inboxes", "read_inbox", "search_email",
                    "read_email", "draft_email")

_CLAUDE_EMAIL_RULES = (
    "\n\nRUNTIME NOTE: Your email tools are the mcp__mailbox__* MCP tools "
    "(list_inboxes, read_inbox, search_email, read_email, draft_email) — use those, "
    "exactly as the instructions above describe. draft_email saves a DRAFT only; "
    "nothing you can call sends mail. Inboxes can be huge: scope your reads with "
    "search_email (Gmail syntax, e.g. \"is:unread newer_than:2d\") and limits "
    "rather than paging through everything. Finish with a short plain-text summary."
)


def _mailbox_mcp_config() -> str:
    """Write a temp MCP-config JSON pointing the CLI at mail_mcp.py; return its path.

    Built per-run (machine-independent — no hardcoded paths on disk). Source runs
    launch this folder's mail_mcp.py with Python; frozen desktop builds relaunch
    the packaged executable through its --mail-mcp entrypoint. The caller deletes
    the file when the run finishes.
    """
    if getattr(sys, "frozen", False):
        args = ["--mail-mcp"]
    else:
        server = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_mcp.py")
        args = [server]
    cfg = {"mcpServers": {"mailbox": {"command": sys.executable, "args": args}}}
    fd, path = tempfile.mkstemp(prefix="mailbox_mcp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return path


def _tool_result_text(content) -> str:
    """Coerce a CLI tool_result's content (str or list of blocks) to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or "")
            else:
                parts.append(str(b))
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else ""


def _run_agent_claude(spec, task, emit, scope: AccessScope, req_model: str = "",
                      cancel_event=None) -> dict:
    """Run an agent on the subscription `claude` CLI tier, streaming its steps.

    Consumes router.claude_code_stream and maps the CLI's native events onto the
    same step vocabulary the in-process loop emits (start / think / tool /
    tool_result / final), so the Agents view streams live regardless of tier.
    Returns run_agent's standard result dict. The CLI runs its own loop; the
    router's wall-clock timeout (CLAUDE_CLI_TIMEOUT) is the bound, not a step cap.

    Tool grants are category-aware: vault tools map onto the CLI's native file
    tools (Read/Grep/Glob, +Write/Edit for writers); email tools attach the
    mailbox MCP server (mail_mcp.py) and grant only mcp__mailbox__<tool> — so an
    email-only agent like inbox_triage gets NO filesystem tools at all.
    """
    workspace_tools = [t for t in spec["tools"]
                       if t in VAULT_TOOL_NAMES or t in FILE_TOOL_NAMES]
    web_tools = [t for t in spec["tools"] if t in ("web_search", "fetch_url")]
    email_tools = [t for t in spec["tools"]
                   if t in EMAIL_TOOL_NAMES or t == "stage_email_draft"]
    builtins: list = []
    allowed: list = []
    system = spec["system"]
    mcp_config = ""
    if workspace_tools:
        writes = any(t in ("write_note", "create_project", "write_file") for t in workspace_tools)
        builtins += ["Read", "Grep", "Glob"] + (["Write", "Edit"] if writes else [])
        # Bare Read/Edit rules would approve access system-wide. Relative glob
        # rules make the selected cwd the actual boundary (including symlinks).
        allowed += ["Read(./**)"] + (["Edit(./**)"] if writes else [])
        if "run_check" in workspace_tools and spec.get("approved_checks"):
            builtins.append("Bash")
            for command in spec["approved_checks"]:
                allowed += [f"Bash({command})", f"Bash({command} *)"]
        system += _workflow_rules(scope) + _claude_runtime_note(scope) + _scope_note(scope)
        if spec.get("approved_checks"):
            system += "\nApproved checks (run no other shell commands): " + "; ".join(spec["approved_checks"])
    if web_tools:
        builtins += ["WebSearch", "WebFetch"]
        allowed += ["WebSearch", "WebFetch"]
        system += "\nUse live web research when useful and cite every source URL in the final answer."
    if email_tools:
        mcp_config = _mailbox_mcp_config()
        allowed += [f"mcp__mailbox__{t}" for t in email_tools]
        system += _CLAUDE_EMAIL_RULES

    emit({"type": "start", "agent": spec["id"], "tier": "claude", "task": task})
    steps: list = []
    names: dict = {}   # tool_use_id -> (tool name, input), to label results
    reply = ""
    model = ""   # the model that actually ran (from the CLI's init/result events)
    try:
        for ev in router.claude_code_stream(
                task, system=system, builtin_tools=builtins, allowed_tools=allowed,
                cwd=str(scope.root), mcp_config=mcp_config or None, model=req_model or None,
                cancel_event=cancel_event):
            etype = ev.get("type")
            if etype == "system" and ev.get("subtype") == "init":
                model = ev.get("model") or model
            elif etype == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    bt = b.get("type")
                    if bt == "text" and (b.get("text") or "").strip():
                        emit({"type": "think", "text": b["text"]})
                    elif bt == "tool_use":
                        names[b.get("id")] = (b.get("name"), b.get("input") or {})
                        emit({"type": "tool", "tool": b.get("name"),
                              "input": b.get("input") or {}})
            elif etype == "user":
                for b in (ev.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_result":
                        name, tool_input = names.get(b.get("tool_use_id"), ("tool", {}))
                        out = _tool_result_text(b.get("content"))
                        recorded_input = tool_input if name.endswith("stage_email_draft") else {}
                        steps.append({"tool": name, "input": recorded_input, "output": out})
                        emit({"type": "tool_result", "tool": name, "output": out[:600]})
            elif etype == "result":
                if ev.get("is_error"):
                    why = ev.get("result") or ev.get("subtype") or "unknown error"
                    raise AgentError(f"The Claude CLI returned an error: {why}")
                reply = (ev.get("result") or "").strip()
                model = next(iter(ev.get("modelUsage") or {}), None) or model
    except router.RouterError as e:
        emit({"type": "error", "text": e.message})
        raise AgentError(e.message)
    finally:
        if mcp_config:
            try:
                os.unlink(mcp_config)
            except OSError:
                pass  # temp-file cleanup is best-effort

    emit({"type": "final", "text": reply})
    return {"reply": reply or "(the agent finished without a summary)",
            "steps": steps, "tier": "claude", "model": model or "claude (plan)",
            "agent": spec["id"]}


def _run_agent_codex(spec, task, emit, scope: AccessScope, req_model: str = "",
                     cancel_event=None) -> dict:
    """Run a custom worker through the ChatGPT-account Codex CLI."""
    writes = any(t in ("write_note", "create_project", "write_file") for t in spec["tools"])
    system = spec["system"] + _scope_note(scope)
    if any(t in ("web_search", "fetch_url") for t in spec["tools"]):
        seed = _tool_web_search(task, limit=6)
        system += (
            "\nWeb research is allowed. Here are live seed results from Regalia's "
            "search service; follow relevant public URLs if your runtime permits and cite URLs.\n" + seed
        )
    if spec.get("approved_checks"):
        system += "\nOnly these validation commands were approved: " + "; ".join(spec["approved_checks"])
    emit({"type": "start", "agent": spec["id"], "tier": "chatgpt", "task": task})
    steps = []
    reply = ""
    try:
        for ev in router.codex_agent_stream(
                task, system=system, model=req_model or None, cwd=str(scope.root),
                allow_write=writes, cancel_event=cancel_event):
            etype = ev.get("type")
            item = ev.get("item") if isinstance(ev.get("item"), dict) else {}
            itype = item.get("type")
            if etype in ("item.started", "item.completed") and itype in (
                    "command_execution", "file_change", "mcp_tool_call"):
                name = item.get("command") or item.get("name") or itype
                output = item.get("aggregated_output") or item.get("output") or ""
                if etype == "item.started":
                    tool_input = {"detail": str(name)[:500]}
                    if itype == "file_change" and isinstance(item.get("changes"), list):
                        tool_input["changes"] = [
                            {"path": str(change.get("path") or change.get("file_path") or "")[:500]}
                            for change in item["changes"] if isinstance(change, dict)
                        ]
                    emit({"type": "tool", "tool": itype, "input": tool_input})
                else:
                    if itype == "file_change" and isinstance(item.get("changes"), list):
                        emit({"type": "tool", "tool": itype, "input": {
                            "changes": [
                                {"path": str(change.get("path") or change.get("file_path") or "")[:500]}
                                for change in item["changes"] if isinstance(change, dict)
                            ],
                        }})
                    steps.append({"tool": itype, "input": {"detail": str(name)}, "output": str(output)})
                    emit({"type": "tool_result", "tool": itype, "output": str(output)[:600]})
            if etype == "item.completed" and itype == "agent_message":
                text = str(item.get("text") or "").strip()
                if text:
                    reply = text
                    emit({"type": "think", "text": text})
    except router.RouterError as e:
        emit({"type": "error", "text": e.message})
        raise AgentError(e.message)
    emit({"type": "final", "text": reply})
    return {"reply": reply or "(the agent finished without a summary)",
            "steps": steps, "tier": "chatgpt", "model": req_model or "ChatGPT account",
            "agent": spec["id"]}


# ── The run loop ─────────────────────────────────────────────────────────────

def run_agent(agent_id: str, task: str, tier: str = "", emit=None, max_steps: int = 8,
              folder: str = "", model: str = "", spec_override: dict | None = None,
              scope_override: AccessScope | None = None, cancel_event=None) -> dict:
    """Drive one agent to completion. Returns {reply, steps, tier, model, agent}.

    `emit(event)` (optional) is called as each step happens, for live streaming.
    Events: {"type": "start"|"think"|"tool"|"tool_result"|"final"|"limit", ...}.
    Raises AgentError on an unusable request or a backend failure.
    """
    spec = dict(spec_override) if isinstance(spec_override, dict) else AGENTS.get(agent_id)
    if not spec:
        raise AgentError(f"Unknown agent '{agent_id}'.")
    task = (task or "").strip() or spec.get("default_task", "")
    if not task:
        raise AgentError(f"{spec['name']} needs a task — tell it what to do.")
    folder = (folder or "").strip().strip("/")
    scope = scope_override or resolve_scope(folder)
    if spec.get("approved_checks") and not scope.approved_checks:
        scope = AccessScope(
            scope.kind, scope.root, scope.label, scope.explicit,
            tuple(spec.get("approved_checks") or ()),
        )
    if scope.explicit and not _spec_supports_folder(spec):
        raise AgentError(f"{spec['name']} has no filesystem tools and cannot take a folder scope.")
    if scope.kind == "external" and scope_override is None:
        name = scope.label[4:].split("/", 1)[0]
        task = (
            f"[Scope: only connected external folder '{name}'. Tool paths may be relative "
            f"to it or use '{scope.label}/…'. No vault or other external folder is accessible.]\n{task}"
        )
    elif scope.explicit and scope_override is None:
        task = (
            f"[Scope: only vault folder '{scope.label}'. Tool paths may be relative to it; "
            f"no sibling or external folder is accessible.]\n{task}"
        )
    tier = (tier or spec["tier"]).lower()
    if tier not in AGENT_TIERS:
        tier = spec["tier"]

    def _emit(ev):
        if emit:
            try:
                emit(ev)
            except Exception:  # noqa: BLE001 — never let UI plumbing break a run
                pass

    # The subscription tier doesn't drive our in-process tool loop — the external
    # CLI runs its own. Hand off to its runner and return its result.
    req_model = (model or "").strip()
    if tier == "claude":
        return _run_agent_claude(
            spec, task, _emit, scope, req_model=req_model, cancel_event=cancel_event,
        )
    if tier == "chatgpt":
        return _run_agent_codex(
            spec, task, _emit, scope, req_model=req_model, cancel_event=cancel_event,
        )

    tools = [TOOL_SCHEMAS[name] for name in spec["tools"] if name in TOOL_SCHEMAS]
    # Workflow rules are chosen per-run from the scope (vault conventions vs. the
    # external folder's own detected conventions) — vault-tool agents only, so
    # email-only agents like inbox_triage never get vault rules injected.
    system = spec["system"]
    if _spec_supports_folder(spec):
        system += _workflow_rules(scope) + _scope_note(scope)
    messages = [{"role": "user", "content": [{"type": "text", "text": task}]}]

    _emit({"type": "start", "agent": agent_id, "tier": tier, "task": task})
    steps = []
    used_model = ""

    for _ in range(max_steps):
        if cancel_event is not None and cancel_event.is_set():
            raise AgentError("The agent was cancelled.")
        try:
            res = router.chat_tools(
                messages, tools, tier=tier, system=system, max_tokens=3072,
                model=req_model or None,
            )
        except router.RouterError as e:
            _emit({"type": "error", "text": e.message})
            raise AgentError(e.message)

        used_model = res.get("model", used_model)
        text, tool_calls = res.get("text", ""), res.get("tool_calls", [])
        if text:
            _emit({"type": "think", "text": text})

        if not tool_calls:
            _emit({"type": "final", "text": text})
            return {"reply": text or "(the agent finished without a summary)",
                    "steps": steps, "tier": tier, "model": used_model, "agent": spec["id"]}

        # Record the assistant turn (text + tool_use) so history stays coherent.
        assistant_content = ([{"type": "text", "text": text}] if text else []) + [
            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
            for tc in tool_calls
        ]
        messages.append({"role": "assistant", "content": assistant_content})

        results = []
        for tc in tool_calls:
            name, args = tc["name"], (tc.get("input") or {})
            _emit({"type": "tool", "tool": name, "input": args})
            fn = TOOL_FNS.get(name)
            if fn is None:
                out = f"Error: no such tool '{name}'."
            else:
                try:
                    out = fn(_scope=scope, **args) if isinstance(args, dict) else fn()
                except AgentError as e:
                    out = f"Error: {e.message}"
                except Exception as e:  # noqa: BLE001 — tool errors feed back to the model
                    out = f"Error running {name}: {e}"
            steps.append({"tool": name, "input": args, "output": out})
            _emit({"type": "tool_result", "tool": name, "output": out[:600]})
            results.append({"type": "tool_result", "tool_use_id": tc["id"], "content": out})

        messages.append({"role": "user", "content": results})

    _emit({"type": "limit", "text": f"Stopped after {max_steps} steps."})
    return {"reply": f"Stopped after {max_steps} steps without a final answer.",
            "steps": steps, "tier": tier, "model": used_model, "agent": spec["id"]}
