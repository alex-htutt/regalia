"""Regalia local task dashboard."""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import threading
import uuid

import yaml
from flask import Flask, jsonify, render_template, request, send_file

import agent
import chats
import config
import dispatch_engine
import dispatches
import externals
import mailbox
import news_sources
import paths
import router
import updater

app = Flask(__name__)

# Vault root resolution (read once at startup — restart to change):
#   1. REGALIA_VAULT env var, 2. the Settings view's vault_path, 3. from source:
# the repo root this dashboard lives in; packaged (frozen): ~/RegaliaVault,
# created on first run. Lets an installed Regalia point at any vault instead of
# assuming it lives inside one.
_vault_override = os.environ.get("REGALIA_VAULT") or config.get("vault_path")
if _vault_override and Path(_vault_override).expanduser().is_dir():
    VAULT_ROOT = Path(_vault_override).expanduser().resolve()
elif paths.is_frozen():
    VAULT_ROOT = paths.default_vault()
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
else:
    VAULT_ROOT = Path(__file__).parent.parent
IGNORE_DIRS = {".obsidian", ".cursor", ".claude", "templates", "__pycache__", "dashboard", "founders-edition"}
IGNORE_FILES = {"CLAUDE.md", "README_HOME.md", "USAGE.md", "Home.md"}

# The vault map is broader than the task loader: every normal file type is a
# node. It retains the existing noise/safety exclusions, with Home.md restored
# as the authored graph root.
BROWSER_IGNORE_FILES = IGNORE_FILES - {"Home.md"}
BROWSER_TEXT_EXTS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".log", ".py",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css",
    ".toml", ".ini", ".cfg", ".sh", ".ps1", ".bat", ".luau",
}
BROWSER_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
BROWSER_PREVIEW_BYTES = 64 * 1024

# Update check — runs ONCE here, at import (i.e. launch), on a background thread.
# Offline-safe; the routes only read its cached result. If autoupdate is on and a
# packaged build is out of date, the check applies it. Skipped when
# REGALIA_UPDATE_CHECK=0 (the smoke suite sets this to stay network-free).
updater.startup(autoupdate=bool(config.get("autoupdate")))

# Claude Code writes per-session transcripts here; each line carries a
# message.usage block we aggregate. We read ONLY token counts / model /
# timestamp — never message content.
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Chat attachments land here (gitignored). From source it lives under dashboard/,
# which is in IGNORE_DIRS so the vault walk never surfaces uploads as notes.
# Packaged builds move it to the per-user data dir. API tiers inline supported
# data; CLI tiers receive a per-turn staged copy when needed.
ATTACH_DIR = paths.data_dir() / ".chat_attachments"
MAX_ATTACH_BYTES = 25 * 1024 * 1024  # 25 MB per file
ATTACH_MAX_AGE = 24 * 3600           # prune uploads older than a day
ALLOWED_ATTACH_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",        # images
    ".pdf",                                            # docs
    ".txt", ".md", ".csv", ".json", ".log", ".py",    # text
}

# Approx Anthropic API list prices, USD per million tokens, matched by model
# family substring: (input, output, cache_write_5m, cache_read).
MODEL_PRICING = {
    "opus": (15.0, 75.0, 18.75, 1.50),
    "sonnet": (3.0, 15.0, 3.75, 0.30),
    "haiku": (0.80, 4.0, 1.0, 0.08),
}


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    try:
        fm = yaml.safe_load(content[3:end])
        return fm or {}, content[end + 3 :].strip()
    except yaml.YAMLError:
        return {}, content


def _first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _course(tags: list[str]) -> str:
    for t in tags:
        if t.startswith("course/"):
            return t.split("/", 1)[1]
    return ""


def _coerce_tags(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(t) for t in raw]
    if isinstance(raw, str):
        return [raw]
    return []


def load_tasks() -> list[dict]:
    tasks = []
    for md_file in VAULT_ROOT.rglob("*.md"):
        rel = md_file.relative_to(VAULT_ROOT)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        name = md_file.name.lower()
        if md_file.name in IGNORE_FILES or name.startswith("_context_") or name.startswith("readme"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(content)
            if not fm:
                continue
            tags = _coerce_tags(fm.get("tags"))
            deadline = fm.get("deadline")
            tasks.append(
                {
                    "title": _first_heading(body, md_file.stem),
                    "file": rel.as_posix(),
                    "date": str(fm.get("date", "")),
                    "deadline": str(deadline) if deadline else "",
                    "status": str(fm.get("status", "active")),
                    "tags": tags,
                    "course": _course(tags),
                    "topic": str(fm.get("topic") or ""),
                }
            )
        except Exception:
            continue
    return tasks


def _personalization_catalog() -> dict:
    """Choices the Personalization UI renders: the interest-bucket catalog, the
    career-stage options, and the shipped defaults (shown as hints/placeholders
    when the user hasn't overridden them)."""
    return {
        "interests": list(news_sources.INTEREST_KEYWORDS.keys()),
        "career_stages": list(config.CAREER_STAGES),
        "default_boards": list(news_sources.GREENHOUSE_BOARDS),
        "default_locations": list(news_sources.PREFERRED_LOCATIONS),
        "default_feeds": [{"name": n, "url": u} for n, u in news_sources.NEWS_FEEDS],
    }


@app.route("/")
def index():
    # Boot settings ride into the page inline so the theme applies before first
    # paint (no flash of the wrong palette). Secrets are masked by config.mask.
    return render_template(
        "index.html",
        boot_settings=json.dumps(config.mask(config.load())),
        boot_catalog=json.dumps(_personalization_catalog()),
    )


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """Read (GET) or partially update (POST) the settings store.

    Secrets never leave the server: responses carry {"set": bool} per secret.
    A posted secret value overwrites; posting "" clears it; omitting leaves it.
    """
    if request.method == "POST":
        data = request.get_json(silent=True)
        try:
            cfg = config.update(data if isinstance(data, dict) else None)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"settings": config.mask(cfg), "vault_root": str(VAULT_ROOT),
                        "catalog": _personalization_catalog()})
    return jsonify({"settings": config.mask(config.load()), "vault_root": str(VAULT_ROOT),
                    "catalog": _personalization_catalog()})


@app.route("/api/update")
def api_update():
    """Cached result of the launch-time release check (never hits the network).

    Shape: {checked, current, latest, out_of_date, can_self_update, releases_url,
    error, apply:{state, detail}}. The check runs once at startup — this route
    only reports it, so polling here honors the "check only on launch" contract.
    """
    return jsonify(updater.snapshot())


@app.route("/api/update/apply", methods=["POST"])
def api_update_apply():
    """Start a self-update (frozen builds swap the binary in place + relaunch).

    From source this is a no-op that reports the `git pull` path. Poll
    /api/update afterward — the `apply.state` field tracks progress. On a
    successful frozen update the process exits mid-relaunch, so the caller may
    simply see the connection drop."""
    result = updater.apply()
    status = 200 if result.get("started") or result.get("reason") == "already-running" else 409
    return jsonify({**result, "update": updater.snapshot()}), status


@app.route("/api/tasks")
def api_tasks():
    return jsonify(load_tasks())


def _excerpt(body: str, limit: int = 120) -> str:
    in_code = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s or s.startswith(("#", ">")):
            continue
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", s)
        s = re.sub(r"[`*]", "", s).strip()
        if s and s != "-":
            return s if len(s) <= limit else s[:limit].rstrip() + "…"
    return ""


def _subdirs(d: Path) -> list[Path]:
    return sorted(
        (s for s in d.iterdir()
         if s.is_dir() and s.name not in IGNORE_DIRS and not s.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )


def _folder_info(d: Path, root: Path) -> dict:
    notes = sum(
        1 for f in d.rglob("*.md")
        if not any(p in IGNORE_DIRS for p in f.relative_to(root).parts)
        and not f.name.startswith("_context_")
    )
    info = {"name": d.name, "has_context": False, "excerpt": "", "folders": len(_subdirs(d)), "notes": notes}
    matches = sorted(d.glob("_context_*.md"))
    if matches:
        fm, body = _parse_frontmatter(matches[0].read_text(encoding="utf-8"))
        info["has_context"] = True
        info["excerpt"] = str(fm.get("topic") or "") or _excerpt(body)
    return info


@app.route("/api/browse")
def api_browse():
    root = VAULT_ROOT.resolve()
    rel = request.args.get("path", "").replace("\\", "/").strip("/")
    target = (root / rel).resolve() if rel else root
    if target != root and root not in target.parents:
        return jsonify({"error": "path outside vault"}), 400
    if not target.is_dir():
        return jsonify({"error": "folder not found"}), 404

    context = None
    matches = sorted(target.glob("_context_*.md"))
    if matches:
        _, body = _parse_frontmatter(matches[0].read_text(encoding="utf-8"))
        context = {"file": matches[0].relative_to(root).as_posix(), "content": body}

    return jsonify(
        {
            "path": target.relative_to(root).as_posix() if target != root else "",
            "folders": [_folder_info(d, root) for d in _subdirs(target)],
            "context": context,
        }
    )


def _browser_preview_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in BROWSER_TEXT_EXTS:
        return "text"
    if ext in BROWSER_IMAGE_EXTS:
        return "image"
    return "none"


def _browser_rel_allowed(rel: Path) -> bool:
    """Whether a vault-relative path belongs in the read-only browser map."""
    if not rel.parts or any(part.startswith(".") for part in rel.parts):
        return False
    if any(part in IGNORE_DIRS for part in rel.parts):
        return False
    return rel.name not in BROWSER_IGNORE_FILES


def _browser_stat(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
        return stat.st_size, round(stat.st_mtime)
    except OSError:
        return 0, 0


def _vault_map() -> dict:
    """Build the read-only graph/tree inventory for the active vault.

    Home.md is the graph root. The filesystem hierarchy is kept separate from
    authored Markdown links so the frontend can style and toggle them without
    losing the dependable folder skeleton.
    """
    root = VAULT_ROOT.resolve()
    home_path = root / "Home.md"
    home_size, home_modified = _browser_stat(home_path)
    home_id = "file:Home.md"
    nodes: list[dict] = [{
        "id": home_id,
        "path": "Home.md",
        "name": "Home.md",
        "kind": "home",
        "extension": ".md",
        "parent": "",
        "depth": 0,
        "size": home_size,
        "modified": home_modified,
        "preview_kind": "text" if home_path.is_file() else "none",
        "exists": home_path.is_file(),
        "children": 0,
        "folder_children": 0,
        "file_children": 0,
        "links": 0,
    }]
    edges: list[dict] = []
    node_by_id = {home_id: nodes[0]}
    path_to_id: dict[str, str] = {"home.md": home_id}
    file_stems: dict[str, list[str]] = {"home": [home_id]}
    file_names: dict[str, list[str]] = {"home.md": [home_id]}

    def add_child(parent_id: str, child: dict, edge_kind: str) -> None:
        nodes.append(child)
        node_by_id[child["id"]] = child
        path_to_id[child["path"].lower()] = child["id"]
        edges.append({"source": parent_id, "target": child["id"], "kind": edge_kind})
        parent = node_by_id[parent_id]
        parent["children"] += 1
        if child["kind"] == "folder":
            parent["folder_children"] += 1
        else:
            parent["file_children"] += 1

    def walk(directory: Path, parent_id: str) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        directories = sorted(
            (p for p in entries if p.is_dir() and not p.is_symlink()),
            key=lambda p: p.name.lower(),
        )
        files = sorted(
            (p for p in entries if p.is_file() and not p.is_symlink()),
            key=lambda p: p.name.lower(),
        )
        for child_dir in directories:
            rel = child_dir.relative_to(root)
            if not _browser_rel_allowed(rel):
                continue
            path = rel.as_posix()
            node_id = f"folder:{path}"
            _, modified = _browser_stat(child_dir)
            node = {
                "id": node_id, "path": path, "name": child_dir.name,
                "kind": "folder", "extension": "", "parent": parent_id,
                "depth": len(rel.parts), "size": 0, "modified": modified,
                "preview_kind": "none", "exists": True, "children": 0,
                "folder_children": 0, "file_children": 0, "links": 0,
            }
            add_child(parent_id, node, "branch" if parent_id == home_id else "contains")
            walk(child_dir, node_id)
        for child_file in files:
            rel = child_file.relative_to(root)
            if rel.as_posix().lower() == "home.md" or not _browser_rel_allowed(rel):
                continue
            path = rel.as_posix()
            node_id = f"file:{path}"
            size, modified = _browser_stat(child_file)
            node = {
                "id": node_id, "path": path, "name": child_file.name,
                "kind": "file", "extension": child_file.suffix.lower(),
                "parent": parent_id, "depth": len(rel.parts), "size": size,
                "modified": modified, "preview_kind": _browser_preview_kind(child_file),
                "exists": True, "children": 0, "folder_children": 0,
                "file_children": 0, "links": 0,
            }
            add_child(parent_id, node, "branch" if parent_id == home_id else "contains")
            file_stems.setdefault(child_file.stem.lower(), []).append(node_id)
            file_names.setdefault(child_file.name.lower(), []).append(node_id)

    walk(root, home_id)

    def exact_target(candidate: str) -> str | None:
        candidate = posixpath.normpath(candidate.replace("\\", "/")).lstrip("/")
        if candidate in ("", ".", "..") or candidate.startswith("../"):
            return None
        for value in (candidate, candidate + ".md"):
            found = path_to_id.get(value.lower())
            if found:
                return found
        return None

    def resolve_link(source_path: str, raw: str, markdown: bool) -> str | None:
        target = urllib.parse.unquote(raw.strip())
        if not target or target.startswith("#"):
            return None
        if markdown:
            if target.startswith("<") and ">" in target:
                target = target[1:target.index(">")]
            else:
                target = re.sub(r"\s+[\"'].*$", "", target).strip()
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("//"):
                return None
        else:
            target = target.split("|", 1)[0].strip()
        target = target.split("#", 1)[0].strip().replace("\\", "/")
        if not target:
            return None

        source_dir = posixpath.dirname(source_path)
        # Standard Markdown paths are source-relative. Explicit wikilink paths
        # are traditionally vault-relative, but same-folder remains a useful
        # fallback for local vault conventions.
        candidates = []
        if markdown:
            candidates.extend((posixpath.join(source_dir, target), target))
        else:
            candidates.extend((target, posixpath.join(source_dir, target)))
        for candidate in candidates:
            found = exact_target(candidate)
            if found:
                return found

        key_name = posixpath.basename(target).lower()
        named = file_names.get(key_name, [])
        if len(named) == 1:
            return named[0]
        key_stem = Path(key_name).stem if "." in key_name else key_name
        stemmed = file_stems.get(key_stem, [])
        return stemmed[0] if len(stemmed) == 1 else None

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    markdown_link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    authored: set[tuple[str, str]] = set()
    for node in nodes:
        if node["extension"] != ".md" or not node["exists"]:
            continue
        source_path = node["path"]
        try:
            content = (root / source_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in wikilink_re.finditer(content):
            target_id = resolve_link(source_path, match.group(1), markdown=False)
            if target_id and target_id != node["id"]:
                authored.add((node["id"], target_id))
        for match in markdown_link_re.finditer(content):
            target_id = resolve_link(source_path, match.group(1), markdown=True)
            if target_id and target_id != node["id"]:
                authored.add((node["id"], target_id))

    for source, target in sorted(authored):
        edges.append({"source": source, "target": target, "kind": "link"})
        node_by_id[source]["links"] += 1
        node_by_id[target]["links"] += 1

    return {"root": home_id, "nodes": nodes, "edges": edges}


@app.route("/api/vault-map")
def api_vault_map():
    return jsonify(_vault_map())


@app.route("/api/vault-preview")
def api_vault_preview():
    root = VAULT_ROOT.resolve()
    rel_text = request.args.get("path", "").replace("\\", "/").strip("/")
    if not rel_text:
        return jsonify({"error": "file path required"}), 400
    target = (root / rel_text).resolve()
    if target != root and root not in target.parents:
        return jsonify({"error": "path outside vault"}), 400
    if not target.is_file():
        return jsonify({"error": "file not found"}), 404
    try:
        rel = target.relative_to(root)
    except ValueError:
        return jsonify({"error": "path outside vault"}), 400
    if not _browser_rel_allowed(rel) and rel.as_posix().lower() != "home.md":
        return jsonify({"error": "file is excluded from browser"}), 404

    kind = _browser_preview_kind(target)
    if kind == "none":
        return jsonify({"error": "preview unavailable for this file type"}), 415
    if kind == "image":
        response = send_file(
            target,
            mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            conditional=True,
            max_age=0,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    try:
        with target.open("rb") as preview_file:
            data = preview_file.read(BROWSER_PREVIEW_BYTES + 1)
    except OSError:
        return jsonify({"error": "could not read file"}), 404
    truncated = len(data) > BROWSER_PREVIEW_BYTES
    text = data[:BROWSER_PREVIEW_BYTES].decode("utf-8", errors="replace")
    response = app.response_class(text, mimetype="text/plain")
    response.headers["X-Preview-Truncated"] = "1" if truncated else "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _rel_time(epoch: float) -> str:
    """Human 'time since' for a file mtime — coarse, no external deps."""
    delta = max(0.0, time.time() - epoch)
    if delta < 90:
        return "just now"
    if delta < 3600:
        m = int(delta // 60)
        return f"{m} min ago"
    if delta < 86400:
        h = int(delta // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = int(delta // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        w = days // 7
        return f"{w} week{'s' if w != 1 else ''} ago"
    mo = days // 30
    return f"{mo} month{'s' if mo != 1 else ''} ago"


@app.route("/api/recent-folders")
def api_recent_folders():
    """Folders worked in most recently, ranked by the newest note mtime inside
    them. Groups notes by their immediate containing folder (loose vault-root
    notes are skipped — those aren't a folder to 'work in')."""
    root = VAULT_ROOT.resolve()
    folders: dict[str, dict] = {}
    for md_file in root.rglob("*.md"):
        rel = md_file.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        name = md_file.name.lower()
        if md_file.name in IGNORE_FILES or name.startswith("_context_") or name.startswith("readme"):
            continue
        parent = rel.parent
        if parent == Path("."):
            continue
        try:
            mtime = md_file.stat().st_mtime
        except OSError:
            continue
        # Group at project level: cap the key at the first two path segments so
        # deep vendored/resource subtrees roll up into their project instead of
        # flooding the list (e.g. research/RAG-pipelines/resources/... → research/RAG-pipelines).
        key_parts = parent.parts[:2]
        path = "/".join(key_parts)
        info = folders.get(path)
        if info is None:
            folders[path] = {
                "path": path,
                "name": key_parts[-1],
                "parent": "/".join(key_parts[:-1]),
                "mtime": mtime,
                "notes": 1,
            }
        else:
            info["notes"] += 1
            info["mtime"] = max(info["mtime"], mtime)

    items = sorted(folders.values(), key=lambda f: f["mtime"], reverse=True)[:6]
    for it in items:
        it["ago"] = _rel_time(it["mtime"])
        it["mtime"] = round(it["mtime"])
    return jsonify(items)


def _price_for(model: str) -> tuple[float, float, float, float] | None:
    m = (model or "").lower()
    if "opus" in m:
        return MODEL_PRICING["opus"]
    if "haiku" in m:
        return MODEL_PRICING["haiku"]
    if "sonnet" in m:
        return MODEL_PRICING["sonnet"]
    return None


def _local_day(ts: str) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return ts[:10]


def load_usage(days: int = 14) -> dict:
    """Aggregate Claude Code token usage from local session transcripts."""
    if not CLAUDE_PROJECTS_DIR.is_dir():
        return {"available": False}

    seen: set[tuple] = set()
    totals = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "cost": 0.0}
    today_iso = date.today().isoformat()
    today = {"total": 0, "cost": 0.0}
    by_model: dict[str, dict] = {}
    by_day: dict[str, int] = {}
    messages = 0
    sessions = 0

    for jf in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        sessions += 1
        try:
            lines = jf.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue

            mid = msg.get("id")
            key = (mid, obj.get("requestId"))
            if mid and key in seen:
                continue
            if mid:
                seen.add(key)

            inp = int(usage.get("input_tokens") or 0)
            out = int(usage.get("output_tokens") or 0)
            cc = int(usage.get("cache_creation_input_tokens") or 0)
            cr = int(usage.get("cache_read_input_tokens") or 0)
            row_total = inp + out + cc + cr
            if row_total == 0:
                continue

            model = str(msg.get("model") or "unknown")
            price = _price_for(model)
            cost = (
                inp / 1e6 * price[0]
                + out / 1e6 * price[1]
                + cc / 1e6 * price[2]
                + cr / 1e6 * price[3]
            ) if price else 0.0

            messages += 1
            totals["input"] += inp
            totals["output"] += out
            totals["cache_creation"] += cc
            totals["cache_read"] += cr
            totals["cost"] += cost

            day = _local_day(obj.get("timestamp", ""))
            if day:
                by_day[day] = by_day.get(day, 0) + row_total
            if day == today_iso:
                today["total"] += row_total
                today["cost"] += cost

            m = by_model.setdefault(model, {"model": model, "total": 0, "cost": 0.0, "messages": 0})
            m["total"] += row_total
            m["cost"] += cost
            m["messages"] += 1

    totals["total"] = totals["input"] + totals["output"] + totals["cache_creation"] + totals["cache_read"]

    window = [(date.today() - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    daily = [{"day": d, "total": by_day.get(d, 0)} for d in window]

    return {
        "available": True,
        "totals": totals,
        "today": today,
        "messages": messages,
        "sessions": sessions,
        "by_model": sorted(by_model.values(), key=lambda x: x["total"], reverse=True),
        "by_day": daily,
    }


@app.route("/api/usage")
def api_usage():
    return jsonify(load_usage())


# ── Home-page briefing: tech news + job openings ────────────────────────────
#
# All fetched with stdlib only (urllib + xml.etree + json); no API keys. These
# are slow, rate-limited network calls, so the result is cached in-process with
# a TTL — that cache IS the "routine". The first request after the TTL expires
# triggers a refresh; everything in between is served from memory. Every source
# is wrapped so one dead feed degrades to a skipped section, never a 500.

def _news_ttl() -> int:
    """Briefing cache TTL, seconds — env → Settings store → 30 min default."""
    try:
        return int(config.value("news_ttl", "NEWS_TTL", "1800"))
    except ValueError:
        return 1800


_HTTP_TIMEOUT = 6
_UA = "WorkVaultDashboard/1.0 (+local)"
_NEWS_CACHE = {"data": None, "ts": 0.0}
_NEWS_LOCK = threading.Lock()


def _http_get(url: str, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read()


def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_feed(xml_bytes: bytes, limit: int) -> list[dict]:
    """Parse RSS <item> or Atom <entry> into [{title, url, time}], namespace-agnostic."""
    root = ET.fromstring(xml_bytes)
    items = [e for e in root.iter() if _localname(e.tag) in ("item", "entry")]
    out = []
    for it in items[:limit]:
        title = ""
        url = ""
        ts = ""
        for child in it:
            ln = _localname(child.tag)
            if ln == "title" and child.text:
                title = child.text.strip()
            elif ln == "link":
                href = child.get("href")  # Atom
                if href:
                    url = href
                elif child.text:  # RSS
                    url = child.text.strip()
            elif ln in ("pubDate", "published", "updated") and child.text and not ts:
                ts = child.text.strip()
        if title:
            out.append({"title": title, "url": url, "time": ts})
    return out


def _fetch_rss_group(feeds, limit) -> tuple[list[dict], list[str]]:
    items, errors = [], []
    for source, url in feeds:
        try:
            for it in _parse_feed(_http_get(url, "application/rss+xml, application/xml, */*"), limit):
                it["source"] = source
                items.append(it)
        except Exception as e:  # noqa: BLE001 — one bad feed shouldn't sink the panel
            errors.append(f"{source}: {type(e).__name__}")
    return items, errors


def _resolve_profile() -> dict:
    """The effective jobs/news profile: the user's saved personalization
    (config) overlaid on the shipped news_sources defaults. Every field is
    concrete here so the scorer/fetchers never re-read config mid-pass.

    Returns {interests: {bucket: [kw]}, locations: [str], stage: str,
    boards: [token], feeds: [(name,url)], show_jobs: bool, show_news: bool}.
    """
    p = config.personalization()
    picked = [b for b in (p.get("job_interests") or []) if b in news_sources.INTEREST_KEYWORDS]
    interests = ({b: news_sources.INTEREST_KEYWORDS[b] for b in picked}
                 if picked else dict(news_sources.INTEREST_KEYWORDS))
    locations = [s.lower() for s in (p.get("job_locations") or news_sources.PREFERRED_LOCATIONS)]
    boards = list(p.get("job_boards") or news_sources.GREENHOUSE_BOARDS)
    feeds = ([(f.get("name") or "", f.get("url") or "") for f in p.get("news_feeds") if f.get("url")]
             if p.get("news_feeds") else list(news_sources.NEWS_FEEDS))
    return {
        "interests": interests,
        "locations": locations,
        "stage": p.get("career_stage") or "any",
        "boards": boards,
        "feeds": feeds,
        "show_jobs": p.get("show_jobs", True),
        "show_news": p.get("show_news", True),
    }


def _score_job(title: str, location: str, profile: dict) -> tuple[int, list[str]]:
    """Rank one posting against the resolved user profile.

    Returns (score, tags). Interest-bucket hits add points and a tag; the user's
    career stage boosts on-stage roles and penalizes off-stage ones (a student
    wants internships, a senior wants senior roles); a preferred location is a
    soft bonus. Score <= 0 means "not for you" and the posting is dropped by the
    caller. Title matching is word-bounded so short tokens (ml, ai) don't fire
    inside other words.
    """
    t = (title or "").lower()
    loc = (location or "").lower()
    tags: list[str] = []
    score = 0
    for bucket, kws in profile["interests"].items():
        if any(re.search(rf"\b{re.escape(kw)}\b", t) for kw in kws):
            tags.append(bucket)
            score += 3
    is_early = any(sig in t for sig in news_sources.EARLY_CAREER_SIGNALS)
    is_senior = any(sig in t for sig in news_sources.SENIOR_SIGNALS)
    stage = profile["stage"]
    if stage in ("student", "early"):
        if is_early:
            score += 5
            tags.insert(0, "Intern" if "intern" in t else "Early career")
        if is_senior:
            score -= 4
    elif stage == "senior":
        if is_senior:
            score += 4
            tags.insert(0, "Senior")
        if is_early:
            score -= 4
    elif stage == "mid":
        if is_senior:
            score -= 1
        if is_early:
            score -= 1
    else:  # "any" — light early-career nudge, no penalties
        if is_early:
            score += 2
            tags.insert(0, "Intern" if "intern" in t else "Early career")
    if any(p in loc for p in profile["locations"]):
        score += 1
    return score, tags


def _fetch_jobs(profile: dict) -> tuple[list[dict], list[str]]:
    """Pull a wide pool of postings, score each against the resolved profile, drop
    the irrelevant ones, and return the top matches (best fit first)."""
    pool, errors = [], []
    for board in profile["boards"]:
        try:
            raw = _http_get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
            for job in json.loads(raw).get("jobs", [])[: news_sources.MAX_PER_BOARD]:
                pool.append({
                    "source": board,
                    "title": job.get("title", "").strip(),
                    "url": job.get("absolute_url", ""),
                    "location": (job.get("location") or {}).get("name", ""),
                })
        except Exception as e:  # noqa: BLE001
            errors.append(f"gh/{board}: {type(e).__name__}")
    for board in news_sources.LEVER_BOARDS:
        try:
            raw = _http_get(f"https://api.lever.co/v0/postings/{board}?mode=json")
            for job in json.loads(raw)[: news_sources.MAX_PER_BOARD]:
                cats = job.get("categories") or {}
                pool.append({
                    "source": board,
                    "title": job.get("text", "").strip(),
                    "url": job.get("hostedUrl", ""),
                    "location": cats.get("location", ""),
                })
        except Exception as e:  # noqa: BLE001
            errors.append(f"lever/{board}: {type(e).__name__}")

    for job in pool:
        job["score"], job["tags"] = _score_job(job["title"], job["location"], profile)
    matches = [j for j in pool if j["score"] > 0]
    # Number each posting within its own board (0,1,2,…) so we can break score
    # ties by round-robining across companies — keeps one board (e.g. Anthropic's
    # dozens of AI roles) from filling every slot while still honoring fit score.
    seen: dict[str, int] = {}
    for j in matches:
        seen[j["source"]] = j["occ"] = seen.get(j["source"], 0)
        seen[j["source"]] += 1
    # Best fit first; within a score, interleave boards (lower occ index first).
    # Fall back to the raw pool only if nothing scored (never empty for no reason).
    ranked = sorted(matches, key=lambda j: (-j["score"], j["occ"])) or pool
    for j in ranked:
        j.pop("occ", None)
    return ranked[: news_sources.MAX_JOBS_SHOWN], errors


def _build_briefing() -> dict:
    # (v1.23) The old "social" section (Bluesky + blog feeds) was replaced by the
    # Important-mail panel, which has its own endpoint: GET /api/mail/important.
    # (v1.33) Sources + scoring come from the resolved personalization profile.
    profile = _resolve_profile()
    news, e1 = (_fetch_rss_group(profile["feeds"], news_sources.MAX_PER_NEWS_FEED)
                if profile["show_news"] else ([], []))
    jobs, e2 = _fetch_jobs(profile) if profile["show_jobs"] else ([], [])
    return {
        "available": True,
        "fetched": datetime.now().astimezone().isoformat(timespec="seconds"),
        "news": news,
        "jobs": jobs,
        "show_news": profile["show_news"],
        "show_jobs": profile["show_jobs"],
        "errors": e1 + e2,
    }


def _profile_sig() -> str:
    """A stable fingerprint of the personalization that affects the briefing, so
    the TTL cache refreshes immediately when the user edits their profile."""
    return json.dumps(config.personalization(), sort_keys=True, ensure_ascii=False)


def load_briefing(force: bool = False) -> dict:
    """Return the cached briefing, refreshing if older than NEWS_TTL, if the
    personalization profile changed, or if forced."""
    sig = _profile_sig()
    with _NEWS_LOCK:
        fresh = (_NEWS_CACHE["data"] is not None
                 and (time.time() - _NEWS_CACHE["ts"]) < _news_ttl()
                 and _NEWS_CACHE.get("sig") == sig)
        if fresh and not force:
            return _NEWS_CACHE["data"]
    data = _build_briefing()  # network I/O outside the lock
    with _NEWS_LOCK:
        _NEWS_CACHE["data"] = data
        _NEWS_CACHE["ts"] = time.time()
        _NEWS_CACHE["sig"] = sig
    return data


@app.route("/api/news")
def api_news():
    return jsonify(load_briefing(force=request.args.get("refresh") == "1"))


# ── Projects & agents ───────────────────────────────────────────────────────

# Areas are the vault's real top-level folders — discovered, not hardcoded.
# One legacy short name survives so old agent prompts/API callers keep working.
AREA_ALIASES = {"internship": "Internship-Projects"}
# Folder-name → area-tag continuity: existing notes tag area/internship, not
# area/internship-projects, so new projects under that folder must match.
AREA_TAG_OVERRIDES = {"internship-projects": "internship"}
_AREA_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")
PROJECT_SUBDIRS = ("code", "data", "notes", "research")


def _area_tag(folder: str) -> str:
    """Frontmatter tag value (`area/<tag>`) for a top-level area folder."""
    tag = re.sub(r"[^a-z0-9]+", "-", folder.lower()).strip("-")
    return AREA_TAG_OVERRIDES.get(tag, tag)


def _safe_area(area: str) -> str:
    """Validate an area name and canonicalize it to a real top-level folder.

    Accepts any sane folder name (created on demand); reuses an existing
    top-level folder case-insensitively so `projects` and `Projects` never
    end up side by side on a case-sensitive filesystem. Raises ValueError
    on anything empty, ignored, or path-shaped."""
    area = str(area or "").strip()
    area = AREA_ALIASES.get(area.lower(), area)
    if not _AREA_NAME_RE.match(area):
        raise ValueError(
            "Area must be a plain folder name (letters, numbers, spaces, - or _)."
        )
    reserved = {d.lower() for d in IGNORE_DIRS} | {"external"}
    if area.lower() in reserved:
        raise ValueError(f"'{area}' is reserved and can't hold projects.")
    root = VAULT_ROOT.resolve()
    for existing in _subdirs(root):
        if existing.name.lower() == area.lower():
            area = existing.name
            break
    if (root / area).resolve().parent != root:
        raise ValueError("Resolved path escapes the vault.")
    return area


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _context_md(name: str, area: str, topic: str, deadline: str) -> str:
    """A clean _context_<slug>.md following the vault frontmatter schema."""
    return (
        "---\n"
        f"date: {date.today().isoformat()}\n"
        f"tags: [area/{area}, type/reference]\n"
        "status: active\n"
        f"topic: {json.dumps(str(topic or ''), ensure_ascii=False)}\n"
        f"deadline: {deadline}\n"
        "related: []\n"
        "---\n\n"
        f"# {name} — Context\n\n"
        "## Current state\n-\n\n"
        "## Active deliverable(s)\n-\n\n"
        "## Open questions\n-\n\n"
        "## Key people / resources\n-\n\n"
        "## Next deadline\n-\n"
    )


def _add_home_link(rel_context: str, name: str, topic: str) -> bool:
    """Append a wikilink to the new project under Home.md's '## Active' list.
    Best-effort — a failure here never fails the project creation."""
    home = VAULT_ROOT / "Home.md"
    if not home.is_file():
        return False
    try:
        lines = home.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    target = rel_context[:-3] if rel_context.endswith(".md") else rel_context
    bullet = f"- [[{target}|{name}]] — {topic or 'new project'}"
    for i, line in enumerate(lines):
        if line.strip().lower() == "## active":
            j = i + 1
            # advance past the existing bullets, stop at the blank line / next heading
            while j < len(lines) and lines[j].lstrip().startswith("- "):
                j += 1
            lines.insert(j, bullet)
            try:
                home.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except OSError:
                return False
            return True
    return False


def create_project_core(name: str, area: str, topic: str = "", deadline: str = "") -> dict:
    """Scaffold a project folder + context file and link it into Home.

    Shared by the HTTP route and the agent's create_project tool. Raises
    ValueError (with a user-facing message) on any bad input or conflict;
    returns the same dict the route hands back to the UI.
    """
    name = str(name or "").strip()
    topic = str(topic or "").strip()
    deadline = str(deadline or "").strip()

    if not name:
        raise ValueError("Project needs a name.")
    area = _safe_area(area)
    slug = _slugify(name)
    if not slug:
        raise ValueError("Name has no usable letters or numbers.")

    root = VAULT_ROOT.resolve()
    target = (root / area / slug).resolve()
    if root not in target.parents:
        raise ValueError("Resolved path escapes the vault.")
    if target.exists():
        raise ValueError(f"A project folder '{slug}' already exists under {area}.")

    try:
        for sub in PROJECT_SUBDIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        context_name = f"_context_{slug}.md"
        (target / context_name).write_text(
            _context_md(name, _area_tag(area), topic, deadline), encoding="utf-8"
        )
    except OSError as e:
        raise ValueError(f"Couldn't create the project: {e}")

    rel_dir = target.relative_to(root).as_posix()
    rel_context = f"{rel_dir}/{context_name}"
    linked = _add_home_link(rel_context, name, topic)

    return {
        "ok": True,
        "path": rel_dir,
        "context_file": rel_context,
        "subdirs": list(PROJECT_SUBDIRS),
        "home_linked": linked,
    }


# ── External folders ─────────────────────────────────────────────────────────
# Folders that live outside the vault but that Regalia can work on. All context
# lives in the vault under external/<name>/ — the external folder itself is
# never scaffolded or restructured (that's the contract; see externals.py).

EXTERNAL_DIR_NAME = "external"


def _external_context_rel(name: str) -> str:
    return f"{EXTERNAL_DIR_NAME}/{name}/_context_{_slugify(name)}.md"


def _scaffold_external_context(name: str) -> tuple[str, bool]:
    """Create external/<name>/ + context note in the VAULT (never the external
    folder). Returns (rel_context_path, created). Best-effort by design."""
    root = VAULT_ROOT.resolve()
    rel = _external_context_rel(name)
    target = root / EXTERNAL_DIR_NAME / name
    context = root / rel
    # A pre-existing symlink/junction under external/ must not redirect this
    # vault-side write. Resolve both the directory and note before touching them.
    resolved_target = target.resolve()
    resolved_context = context.resolve()
    if (root not in resolved_target.parents
            or root not in resolved_context.parents
            or resolved_context.parent != resolved_target):
        raise OSError("The external context path resolves outside the vault.")
    if context.is_file():
        return rel, False
    target.mkdir(parents=True, exist_ok=True)
    context.write_text(
        _context_md(name, "external", "Connected external workspace", ""),
        encoding="utf-8",
    )
    return rel, True


@app.route("/api/external", methods=["GET", "POST"])
def api_external():
    if request.method == "GET":
        folders = externals.list_folders()
        for f in folders:
            rel = _external_context_rel(f["name"])
            f["context"] = rel if (VAULT_ROOT / rel).is_file() else ""
        return jsonify({"folders": folders})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    try:
        entry = externals.add(data.get("name", ""), data.get("path", ""), VAULT_ROOT)
    except ValueError as e:
        status = 409 if "already connected" in str(e) else 400
        return jsonify({"error": str(e)}), status
    try:
        entry["context"], entry["context_created"] = _scaffold_external_context(
            entry["name"])
    except OSError as e:
        entry["context"], entry["context_created"] = "", False
        entry["warning"] = f"Connected, but couldn't write the context note: {e}"
    return jsonify(entry)


@app.route("/api/external/<name>", methods=["DELETE"])
def api_external_delete(name):
    if not externals.remove(name):
        return jsonify({"error": f"No external folder named '{name}'."}), 404
    # The vault-side context folder is the user's notes — deliberately kept.
    return jsonify({"ok": True, "kept_context": True})


# One Tk root at a time — tkinter isn't thread-safe, and the dev server serves
# each request on its own thread. A single local user clicking Browse never
# needs concurrency; the lock just makes an accidental double-click safe.
_PICK_LOCK = threading.Lock()


def _tk_pick_folder() -> str:
    """Native folder picker via tkinter (stdlib). Browser/dev fallback path.

    Created and destroyed inside the calling thread for a one-shot modal dialog;
    askdirectory runs its own local event loop, so no mainloop is needed.
    Returns '' if the user cancels."""
    import tkinter
    from tkinter import filedialog

    with _PICK_LOCK:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            path = filedialog.askdirectory(title="Choose a folder to connect")
        finally:
            root.destroy()
    return path or ""


@app.route("/api/pick-folder", methods=["POST"])
def api_pick_folder():
    """Open a native folder picker on this machine and return the chosen path.

    Local-only convenience for the External-folders connect flow. Two backends:
    the pywebview window's native dialog when running as the desktop app, else a
    tkinter dialog in browser/dev mode. Returns {"path": ""} on cancel and
    {"unavailable": true} when no picker is available (the UI then falls back to
    manual entry). Never touches the registry — the returned path still goes
    through externals.add()'s validation on Connect."""
    # Desktop app: reuse the already-running native webview window. Its dialog
    # is dispatched to the GUI thread internally, so calling it here is safe.
    try:
        import webview  # optional dep; present only with pywebview installed
        have_window = bool(getattr(webview, "windows", None))
    except Exception:
        have_window = False
    if have_window:
        try:
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            return jsonify({"path": (result[0] if result else "")})
        except Exception as e:  # pragma: no cover - GUI backend specific
            return jsonify({"unavailable": True, "error": str(e)})

    # Browser/dev: fall back to a tkinter dialog in-process.
    try:
        return jsonify({"path": _tk_pick_folder()})
    except Exception as e:  # tkinter missing/headless
        return jsonify({"unavailable": True, "error": str(e)})


@app.route("/api/onboard/vault", methods=["POST"])
def api_onboard_vault():
    """First-run vault setup: point Regalia at the user's work vault, then mark
    onboarding complete. Two modes:

      • existing — adopt a folder the user already keeps notes in as the vault
        root. Regalia reads its organization as-is and adds NO scaffolding.
      • new — create a fresh vault folder (default name "RegaliaVault") inside a
        chosen destination and use that.

    Both just pin `vault_path` (+ `onboarded`) in the settings store. VAULT_ROOT
    is resolved once at startup, so the change only takes effect after a restart;
    `restart_required` in the response says whether one is needed. Local,
    single-user trust model — same as /api/pick-folder: the path is the user's
    own absolute path on this machine.
    """
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "").strip()
    raw = (data.get("path") or "").strip()
    if mode not in ("existing", "new"):
        return jsonify({"error": "mode must be 'existing' or 'new'."}), 400
    if not raw:
        return jsonify({"error": "Choose a folder first."}), 400
    try:
        chosen = Path(raw).expanduser()
    except (OSError, ValueError):
        return jsonify({"error": "That path isn't valid."}), 400

    if mode == "existing":
        if not chosen.is_dir():
            return jsonify({"error": "That folder doesn't exist."}), 400
        vault = chosen.resolve()
    else:  # new: chosen is the destination; make a vault folder inside it
        if not chosen.is_dir():
            return jsonify({"error": "That destination folder doesn't exist."}), 400
        # Keep the name a single safe folder component (no separators / traversal).
        name = re.sub(r"[^A-Za-z0-9 _-]", "-", (data.get("name") or "").strip()).strip(" .-")
        name = name or "RegaliaVault"
        vault = (chosen / name).resolve()
        if chosen.resolve() not in vault.parents:
            return jsonify({"error": "Invalid vault folder name."}), 400
        try:
            vault.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return jsonify({"error": f"Couldn't create the vault folder: {e}"}), 400

    try:
        config.update({"vault_path": str(vault), "onboarded": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "ok": True,
        "vault_path": str(vault),
        "restart_required": str(vault) != str(VAULT_ROOT.resolve()),
    })


@app.route("/api/project", methods=["POST"])
def api_create_project():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Project payload must be an object."}), 400
    try:
        result = create_project_core(
            data.get("name", ""),
            data.get("area", ""),
            data.get("topic", ""),
            data.get("deadline", ""),
        )
    except ValueError as e:
        msg = str(e)
        status = 409 if "already exists" in msg else 400
        return jsonify({"error": msg}), status
    return jsonify(result)


# Live agent runs. Each run executes in a background thread and appends step
# events as it goes; the UI starts a run, gets a run_id, then polls status. The
# store is in-memory (single-user, local) and capped so it can't grow forever.
_RUNS: dict[str, dict] = {}
_RUNS_LOCK = threading.Lock()
_RUNS_MAX = 50


def _trim_runs_locked() -> None:
    """Keep all active runs plus the newest `_RUNS_MAX` terminal results."""
    finished = sorted(
        (value for value in _RUNS.values() if value["status"] != "running"),
        key=lambda value: value["started"],
    )
    for old in finished[:-_RUNS_MAX]:
        _RUNS.pop(old["id"], None)


def _emit_to(run_id: str):
    def emit(event):
        event = {**event, "ts": datetime.now().astimezone().isoformat(timespec="seconds")}
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["steps"].append(event)
    return emit


def _run_worker(run_id: str, agent_id: str, task: str, tier: str, folder: str = "", model: str = ""):
    try:
        result = agent.run_agent(agent_id, task, tier, emit=_emit_to(run_id), folder=folder, model=model)
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "done"
                run["result"] = result
                _trim_runs_locked()
    except agent.AgentError as e:
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = e.message
                _trim_runs_locked()
    except Exception as e:  # noqa: BLE001 — never let a crash leave a run "running"
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = f"Unexpected error: {e}"
                _trim_runs_locked()


@app.route("/api/agents")
def api_agents():
    return jsonify({"agents": agent.list_agents()})


@app.route("/api/agent/run", methods=["POST"])
def api_agent_run():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Agent payload must be an object."}), 400
    agent_id = str(data.get("agent") or "").strip()
    task = str(data.get("task") or "").strip()
    tier = str(data.get("tier") or "").strip().lower()
    folder = str(data.get("folder") or "").replace("\\", "/").strip().strip("/")
    # Optional per-run model override (honored on the claude CLI tier; empty falls
    # back to the plan default). Other agent tiers keep the Settings model.
    raw_model = data.get("model")
    model = raw_model.strip() if (isinstance(raw_model, str) and raw_model.strip()) else ""
    if agent_id not in agent.AGENTS:
        return jsonify({"error": f"Unknown agent '{agent_id}'."}), 400
    if folder:
        if not agent.supports_folder(agent_id):
            return jsonify({"error": f"{agent.AGENTS[agent_id]['name']} has no filesystem tools."}), 400
        try:
            agent.resolve_scope(folder)
        except agent.AgentError as e:
            return jsonify({"error": e.message}), 400
    legacy_agent_tiers = tuple(t for t in agent.AGENT_TIERS if t != "chatgpt")
    if tier and tier not in legacy_agent_tiers:
        return jsonify({
            "error": f"Tier '{tier}' cannot run agents. Use one of: "
                     f"{', '.join(legacy_agent_tiers)}."
        }), 400

    run_id = uuid.uuid4().hex[:12]
    run = {
        "id": run_id,
        "agent": agent_id,
        "name": agent.AGENTS[agent_id]["name"],
        "task": task,
        "tier": tier or agent.AGENTS[agent_id]["tier"],
        "folder": folder,
        "status": "running",
        "steps": [],
        "result": None,
        "error": None,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with _RUNS_LOCK:
        if any(value["status"] == "running" and value["agent"] == agent_id
               for value in _RUNS.values()):
            return jsonify({"error": f"{run['name']} is already running."}), 409
        _RUNS[run_id] = run
        _trim_runs_locked()

    threading.Thread(
        target=_run_worker, args=(run_id, agent_id, task, tier, folder, model), daemon=True
    ).start()
    return jsonify({"ok": True, "run_id": run_id, "agent": agent_id, "tier": run["tier"]})


@app.route("/api/agent/runs")
def api_agent_runs():
    """Light metadata for every stored run (no steps) — powers the running-agents
    sidebar and lets a reloaded page rediscover in-flight runs."""
    with _RUNS_LOCK:
        runs = [
            {k: r[k] for k in ("id", "agent", "name", "task", "tier", "folder", "status", "started")}
            for r in _RUNS.values()
        ]
    runs.sort(key=lambda r: r["started"], reverse=True)
    return jsonify({"runs": runs})


_ACTIVITY_WRITE_TOOLS = {
    "write_note", "write_file", "write", "edit", "multiedit",
    "notebookedit", "file_change",
}
_ACTIVITY_FILE_CAPS = {"vault_read", "vault_write", "code_read", "code_write", "run_checks"}


def _activity_provider(tier: str) -> str:
    tier = str(tier or "").lower()
    if tier in ("smart", "claude"):
        return "anthropic"
    if tier in ("openai", "chatgpt"):
        return "openai"
    return "local"


def _activity_vault_rel(scope: str, raw_path) -> str | None:
    """Normalize an agent tool path onto the active vault without escaping it."""
    text = str(raw_path or "").replace("\\", "/").strip().strip('"\'')
    if not text:
        return None
    root = VAULT_ROOT.resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(root)
        except (OSError, ValueError):
            return None
    else:
        clean_scope = str(scope or "").replace("\\", "/").strip("/")
        raw_normalized = posixpath.normpath(text)
        if raw_normalized == ".." or raw_normalized.startswith("../"):
            return None
        if clean_scope and (text == clean_scope or text.startswith(clean_scope + "/")):
            joined = text
        else:
            joined = posixpath.join(clean_scope, text)
        normalized = posixpath.normpath(joined).lstrip("/")
        if normalized in ("", ".", "..") or normalized.startswith("../"):
            return None
        rel = Path(normalized)
    if not _browser_rel_allowed(rel) and rel.as_posix().lower() != "home.md":
        return None
    return rel.as_posix()


def _activity_edit_paths(events: list[dict], scope: str) -> list[str]:
    paths: set[str] = set()
    for event in events:
        if event.get("type") != "tool":
            continue
        tool = str(event.get("tool") or "").split("__")[-1].lower()
        if tool not in _ACTIVITY_WRITE_TOOLS:
            continue
        tool_input = event.get("input") if isinstance(event.get("input"), dict) else {}
        raw_paths = [tool_input.get(key) for key in ("path", "file_path", "notebook_path")]
        for change in tool_input.get("changes") or []:
            if isinstance(change, dict):
                raw_paths.append(change.get("path") or change.get("file_path"))
        for raw in raw_paths:
            rel = _activity_vault_rel(scope, raw)
            if rel:
                paths.add(rel)
    return sorted(paths, key=str.lower)


def _vault_activity() -> dict:
    """Current folder/file activity for both classic runs and dispatch workers."""
    activities: list[dict] = []
    with _RUNS_LOCK:
        classic = [dict(run, steps=list(run.get("steps") or [])) for run in _RUNS.values()
                   if run.get("status") == "running"]
    for run in classic:
        folder = str(run.get("folder") or "").replace("\\", "/").strip("/")
        if folder.startswith("ext:") or (not folder and not agent.supports_folder(run.get("agent") or "")):
            continue
        activities.append({
            "id": f"run:{run['id']}",
            "name": run.get("name") or run.get("agent") or "Agent",
            "tier": run.get("tier") or "",
            "provider": _activity_provider(run.get("tier") or ""),
            "scope": folder,
            "editing_paths": _activity_edit_paths(run["steps"], folder),
            "source": "agent",
        })

    try:
        active_dispatches = [item for item in dispatches.list_dispatches(limit=200)
                             if item.get("state") == "running"]
    except Exception:  # noqa: BLE001 - activity is best-effort UI status
        active_dispatches = []
    for summary in active_dispatches:
        try:
            obj = dispatches.get_dispatch(summary["id"])
            events = dispatches.events(summary["id"], 0).get("events") or []
        except Exception:  # noqa: BLE001 - one damaged dispatch must not hide others
            continue
        events_by_worker: dict[str, list[dict]] = {}
        for event in events:
            worker_id = str(event.get("worker") or "")
            if worker_id:
                events_by_worker.setdefault(worker_id, []).append(event)
        for worker in obj.get("workers") or []:
            if worker.get("status") != "running":
                continue
            scope = str(worker.get("scope") or obj.get("scope") or "").replace("\\", "/").strip("/")
            capabilities = set(worker.get("capabilities") or [])
            if scope.startswith("ext:") or not capabilities.intersection(_ACTIVITY_FILE_CAPS):
                continue
            worker_id = str(worker.get("id") or "worker")
            activities.append({
                "id": f"dispatch:{obj['id']}:{worker_id}",
                "name": worker.get("title") or worker_id,
                "tier": worker.get("tier") or "",
                "provider": _activity_provider(worker.get("tier") or ""),
                "scope": scope,
                "editing_paths": _activity_edit_paths(events_by_worker.get(worker_id, []), scope),
                "source": "dispatch",
            })
    activities.sort(key=lambda item: (item["scope"].lower(), item["name"].lower(), item["id"]))
    return {"activities": activities, "poll_ms": 1200}


@app.route("/api/vault-activity")
def api_vault_activity():
    return jsonify(_vault_activity())


@app.route("/api/agent/run/<run_id>")
def api_agent_run_status(run_id):
    raw_after = request.args.get("after", "0")
    try:
        after = int(raw_after)
    except (TypeError, ValueError):
        return jsonify({"error": "after must be a non-negative integer."}), 400
    if after < 0:
        return jsonify({"error": "after must be a non-negative integer."}), 400
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        snapshot = dict(run) if run else None
        if snapshot is not None:
            total = len(run.get("steps") or [])
            snapshot["steps"] = list((run.get("steps") or [])[min(after, total):])
            snapshot["cursor"] = total
    if snapshot is None:
        return jsonify({"error": "No such run."}), 404
    return jsonify(snapshot)


# ── Custom agents + durable single/group dispatches ──────────────────────────

def _dispatch_error(error):
    status = getattr(error, "status", 400)
    message = getattr(error, "message", str(error))
    return jsonify({"error": message}), status


@app.route("/api/agent-definitions", methods=["GET", "POST"])
def api_agent_definitions():
    if request.method == "GET":
        return jsonify({"agents": dispatches.list_agents(), "profiles": dispatches.PROFILES})
    data = request.get_json(silent=True)
    try:
        return jsonify(dispatches.save_agent(data)), 201
    except dispatches.DispatchStoreError as e:
        return _dispatch_error(e)


@app.route("/api/agent-definitions/<agent_id>", methods=["GET", "PUT", "DELETE"])
def api_agent_definition(agent_id):
    try:
        if request.method == "GET":
            obj = dispatches.get_agent(agent_id)
            return (jsonify(obj) if obj else (jsonify({"error": "No such custom agent."}), 404))
        if request.method == "DELETE":
            return jsonify({"deleted": dispatches.delete_agent(agent_id)})
        return jsonify(dispatches.save_agent(request.get_json(silent=True), agent_id=agent_id))
    except dispatches.DispatchStoreError as e:
        return _dispatch_error(e)


@app.route("/api/agent/models")
def api_agent_models():
    return jsonify(dispatch_engine.model_catalog())


@app.route("/api/dispatches", methods=["GET", "POST"])
def api_dispatches():
    if request.method == "GET":
        return jsonify({"dispatches": dispatches.list_dispatches(request.args.get("limit", 50))})
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise dispatches.DispatchStoreError("Dispatch payload must be an object.")
        scope = str(data.get("scope") or "").replace("\\", "/").strip().strip("/")
        if scope:
            agent.resolve_scope(scope)
        definition = None
        if str(data.get("kind") or "single").lower() == "single":
            definition = data.get("definition") if isinstance(data.get("definition"), dict) else None
            custom_id = str(data.get("agent_id") or "")
            if definition is None and custom_id:
                definition = dispatches.get_agent(custom_id)
                if definition is None:
                    raise dispatch_engine.DispatchError("No such custom agent.", 404)
            if definition is None:
                raise dispatch_engine.DispatchError("A single dispatch needs an agent definition.")
            if not custom_id:
                definition = dispatches.validate_agent(definition)
            definition = {**definition, "scope": definition.get("scope") or scope}
            if definition.get("scope"):
                agent.resolve_scope(definition["scope"])
        obj = dispatches.create_dispatch(data)
        if obj["kind"] == "single":
            obj = dispatch_engine.configure_single(obj["id"], definition)
        return jsonify(dispatch_engine.public_dispatch(obj)), 201
    except (dispatches.DispatchStoreError, dispatch_engine.DispatchError,
            agent.AgentError) as e:
        return _dispatch_error(e)


@app.route("/api/dispatches/<dispatch_id>", methods=["GET", "DELETE"])
def api_dispatch(dispatch_id):
    try:
        obj = dispatches.get_dispatch(dispatch_id)
        if obj is None:
            return jsonify({"error": "No such dispatch."}), 404
        if request.method == "DELETE":
            if obj.get("state") in ("planning", "running"):
                return jsonify({"error": "Cancel the running dispatch before deleting it."}), 409
            return jsonify({"deleted": dispatches.delete_dispatch(dispatch_id)})
        return jsonify(dispatch_engine.public_dispatch(obj))
    except dispatches.DispatchStoreError as e:
        return _dispatch_error(e)


@app.route("/api/dispatches/<dispatch_id>/messages", methods=["POST"])
def api_dispatch_message(dispatch_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Planning message must be an object."}), 400
    try:
        obj = dispatch_engine.submit_planner_message(
            dispatch_id, data.get("content"), data.get("planner"),
        )
        return jsonify(dispatch_engine.public_dispatch(obj)), 202
    except (dispatches.DispatchStoreError, dispatch_engine.DispatchError) as e:
        return _dispatch_error(e)


@app.route("/api/dispatches/<dispatch_id>/plan", methods=["PUT"])
def api_dispatch_plan(dispatch_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Plan must be an object."}), 400
    try:
        return jsonify(dispatch_engine.public_dispatch(
            dispatch_engine.update_plan(dispatch_id, data)
        ))
    except (dispatches.DispatchStoreError, dispatch_engine.DispatchError) as e:
        return _dispatch_error(e)


@app.route("/api/dispatches/<dispatch_id>/<action>", methods=["POST"])
def api_dispatch_action(dispatch_id, action):
    actions = {
        "launch": dispatch_engine.launch,
        "resume": dispatch_engine.launch,
        "cancel": dispatch_engine.cancel,
        "apply": dispatch_engine.apply,
        "discard": dispatch_engine.discard,
    }
    fn = actions.get(action)
    if fn is None:
        return jsonify({"error": f"Unknown dispatch action '{action}'."}), 404
    try:
        result = fn(dispatch_id)
        if isinstance(result, dict) and result.get("id") == dispatch_id:
            result = dispatch_engine.public_dispatch(result)
        return jsonify(result)
    except (dispatches.DispatchStoreError, dispatch_engine.DispatchError) as e:
        return _dispatch_error(e)


@app.route("/api/dispatches/<dispatch_id>/events")
def api_dispatch_events(dispatch_id):
    try:
        after = int(request.args.get("after", "0"))
        if after < 0:
            raise ValueError
        return jsonify(dispatches.events(dispatch_id, after))
    except ValueError:
        return jsonify({"error": "after must be a non-negative integer."}), 400
    except dispatches.DispatchStoreError as e:
        return _dispatch_error(e)


# ── Inbox / email (Gmail + Outlook) ──────────────────────────────────────────
# Read inboxes and create drafts via mailbox.py. Write scope is drafts-only by
# construction — there is no send route. Per-account failures degrade gracefully
# (mailbox collects them in `errors`); a MailboxError carries a user-safe message
# + HTTP status straight to the UI, the same way RouterError does for chat.

@app.route("/api/inboxes")
def api_inboxes():
    """Connected accounts + unread counts. Never 500s on one bad account."""
    try:
        return jsonify(mailbox.accounts_overview())
    except mailbox.MailboxError as e:
        return jsonify({"accounts": [], "errors": [e.message]}), e.status


# In-app inbox connection. The OAuth consent flow blocks on a browser, so it
# can't run inside a request handler — POST starts it on a background thread
# (it pops the system browser on THIS machine; Regalia is a localhost app) and
# GET /api/connect/status reports where it got to. Same drafts-only scopes as
# the connect_email.py CLI — this is just a UI trigger for the same flow.
_CONNECT_STATE = {"state": "idle", "provider": "", "detail": ""}  # single-flight
_CONNECT_LOCK = threading.Lock()


def _run_connect(provider: str) -> None:
    import connect_email
    try:
        fn = connect_email._connect_gmail if provider == "gmail" else connect_email._connect_outlook
        account_id = fn()
        _CONNECT_STATE.update(state="done", detail=f"Connected {account_id} ✓")
    except SystemExit as e:  # the CLI helpers signal misconfiguration this way
        _CONNECT_STATE.update(state="error", detail=str(e) or "Connection cancelled.")
    except Exception as e:  # noqa: BLE001 — surface anything to the UI
        _CONNECT_STATE.update(state="error", detail=f"Connection failed: {e}")


@app.route("/api/connect/email", methods=["POST"])
def api_connect_email():
    """Kick off the OAuth consent flow for gmail|outlook in the background."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Connection payload must be an object."}), 400
    provider = str(data.get("provider") or "").strip().lower()
    if provider not in ("gmail", "outlook"):
        return jsonify({"error": "provider must be 'gmail' or 'outlook'"}), 400
    with _CONNECT_LOCK:
        if _CONNECT_STATE["state"] == "running":
            return jsonify({"error": "A connection is already in progress — finish it in the browser."}), 409
        _CONNECT_STATE.update(state="running", provider=provider,
                              detail="Waiting for you to approve access in the browser…")
        threading.Thread(target=_run_connect, args=(provider,), daemon=True).start()
    return jsonify({"started": True, "provider": provider})


@app.route("/api/connect/status")
def api_connect_status():
    return jsonify(dict(_CONNECT_STATE))


# ── Ollama model pull (Settings → Models) ────────────────────────────────────
# `ollama pull` from the UI: POST starts a background thread streaming Ollama's
# /api/pull (JSON-lines progress; can run for many minutes on a big model), GET
# reports progress. Same single-flight shape as the email connect flow above.
_PULL_STATE = {"state": "idle", "model": "", "detail": ""}
_PULL_LOCK = threading.Lock()

_MODEL_NAME_RE = re.compile(r"^[\w.\-/:]{1,128}$")


def _run_ollama_pull(model: str) -> None:
    req = urllib.request.Request(
        router._ollama_host() + "/api/pull",
        data=json.dumps({"model": model}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        # timeout guards socket inactivity, not total duration — pulls may run long.
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if evt.get("error"):
                    _PULL_STATE.update(state="error", detail=str(evt["error"]))
                    return
                status = str(evt.get("status") or "")
                total, done = evt.get("total") or 0, evt.get("completed") or 0
                pct = f" {done * 100 // total}%" if total else ""
                _PULL_STATE.update(detail=f"{status}{pct}".strip() or "pulling…")
        _PULL_STATE.update(state="done", detail=f"Pulled {model} ✓")
    except (urllib.error.URLError, OSError) as e:
        _PULL_STATE.update(
            state="error",
            detail=f"Ollama isn't reachable on {router._ollama_host()} ({e}). "
                   "Install/start it from ollama.com, then retry.")


@app.route("/api/ollama/pull", methods=["POST"])
def api_ollama_pull():
    """Download a model into the local Ollama in the background."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Model payload must be an object."}), 400
    # Accept a bare name or a pasted ollama.com model link (normalized to the name).
    model = config.normalize_ollama_model(data.get("model"))
    if not _MODEL_NAME_RE.match(model):
        return jsonify({"error": "model must be a name like 'llama3.2' or 'qwen3:8b', "
                                 "or an ollama.com model link"}), 400
    with _PULL_LOCK:
        if _PULL_STATE["state"] == "running":
            return jsonify({"error": f"Already pulling {_PULL_STATE['model']} — one at a time."}), 409
        _PULL_STATE.update(state="running", model=model, detail="Contacting Ollama…")
        threading.Thread(target=_run_ollama_pull, args=(model,), daemon=True).start()
    return jsonify({"started": True, "model": model})


@app.route("/api/ollama/pull/status")
def api_ollama_pull_status():
    return jsonify(dict(_PULL_STATE))


# ── Claude CLI connection test (Settings → Models) ───────────────────────────
# The status dot only proves the binary is on PATH; this actually runs a tiny
# prompt through the CLI to prove it's signed in (sign-in itself is interactive
# in a terminal — the error detail says exactly that when it isn't).
_CLAUDE_TEST_STATE = {"state": "idle", "detail": ""}
_CLAUDE_TEST_LOCK = threading.Lock()


def _run_claude_test() -> None:
    try:
        out = router.chat([{"role": "user", "content": "Reply with the single word: ok"}],
                          tier="claude", max_tokens=20)
        _CLAUDE_TEST_STATE.update(
            state="done", detail=f"Signed in ✓ — {out.get('model') or 'CLI'} replied.")
    except router.RouterError as e:
        _CLAUDE_TEST_STATE.update(state="error", detail=e.message)
    except Exception as e:  # noqa: BLE001 — surface anything to the UI
        _CLAUDE_TEST_STATE.update(state="error", detail=f"Test failed: {e}")


@app.route("/api/claude/test", methods=["POST"])
def api_claude_test():
    """Verify the Claude CLI is installed AND signed in by running a tiny prompt."""
    with _CLAUDE_TEST_LOCK:
        if _CLAUDE_TEST_STATE["state"] == "running":
            return jsonify({"error": "A test is already running."}), 409
        _CLAUDE_TEST_STATE.update(state="running", detail="Running a tiny prompt through the CLI…")
        threading.Thread(target=_run_claude_test, daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/claude/test/status")
def api_claude_test_status():
    return jsonify(dict(_CLAUDE_TEST_STATE))


@app.route("/api/mail/important")
def api_mail_important():
    """Work/school-relevant mail (last N days) for the overview panel.

    Deliberately NOT under /api/inbox/… — that segment is a dynamic
    <account_id> route. Degrades to available:false with no inbox connected;
    per-account failures come back in `errors`, never a 500.
    """
    try:
        return jsonify(mailbox.important_messages())
    except mailbox.MailboxError as e:
        return jsonify({"available": False, "messages": [], "errors": [e.message]})


@app.route("/api/inbox/<account_id>")
def api_inbox(account_id):
    limit = request.args.get("limit", "")
    query = request.args.get("q", "")
    try:
        return jsonify(mailbox.fetch_inbox(account_id, limit=limit or mailbox.cfg.DEFAULT_INBOX_LIMIT,
                                           query=query))
    except mailbox.MailboxError as e:
        return jsonify({"error": e.message}), e.status


@app.route("/api/email/<account_id>/<path:msg_id>")
def api_email(account_id, msg_id):
    try:
        return jsonify(mailbox.read_message(account_id, msg_id))
    except mailbox.MailboxError as e:
        return jsonify({"error": e.message}), e.status


@app.route("/api/email/draft", methods=["POST"])
def api_email_draft():
    """Create a DRAFT (never send). Body: {account_id, to, subject, body, reply_to?}."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Draft payload must be an object."}), 400
    account_id = str(data.get("account_id") or "").strip()
    if not account_id:
        return jsonify({"error": "account_id is required."}), 400
    try:
        result = mailbox.create_draft(
            account_id,
            to=str(data.get("to") or ""),
            subject=str(data.get("subject") or ""),
            body=str(data.get("body") or ""),
            reply_to_msg_id=str(data.get("reply_to") or ""),
        )
    except mailbox.MailboxError as e:
        return jsonify({"error": e.message}), e.status
    return jsonify(result)


def _clean_messages(raw) -> list[dict]:
    """Keep only well-formed user/assistant turns with non-empty string content."""
    messages = []
    for m in raw or []:
        if not isinstance(m, dict):
            continue
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    return messages


# ── Generic chat (model router) ─────────────────────────────────────────────

VAULT_CHAT_PREAMBLE = (
    "You are a helpful assistant answering questions about the user's personal "
    "Obsidian knowledge vault. Below is the current folder-and-file structure of "
    "the vault — use it to answer questions about what the vault contains, where "
    "things live, and how it's organized. You can see the structure but not the "
    "contents of individual notes, so if asked what a specific note actually says, "
    "tell the user you can see the file exists but can't read its contents from "
    "here.\n\n=== VAULT STRUCTURE ===\n{outline}\n=== END VAULT STRUCTURE ==="
)


def _vault_outline(max_lines: int = 250) -> str:
    """A compact, indented tree of vault folders and note filenames.

    Injected into the local (fast) chat system prompt so the weak local model can
    answer questions about what's in the vault without any tool calls. Honors the
    same IGNORE_DIRS / dotfile skips as the rest of the app, lists each folder's
    notes adjacent to its header, and is hard-capped so it can never blow up a
    small model's context window. Read fresh per request, like everything else."""
    root = VAULT_ROOT.resolve()
    lines: list[str] = []

    def walk(d: Path, depth: int) -> None:
        if len(lines) >= max_lines:
            return
        pad = "  " * depth
        notes = sorted(
            (f for f in d.iterdir()
             if f.is_file() and f.suffix.lower() == ".md" and not f.name.startswith(".")),
            key=lambda p: p.name.lower(),
        )
        for f in notes:
            if len(lines) >= max_lines:
                return
            lines.append(f"{pad}{f.name}")
        for sub in _subdirs(d):
            if len(lines) >= max_lines:
                return
            lines.append(f"{pad}{sub.name}/")
            walk(sub, depth + 1)

    walk(root, 0)
    out = "\n".join(lines) or "(vault is empty)"
    if len(lines) >= max_lines:
        out += "\n…(structure truncated)"
    return out


def _vault_chat_system(user_system: str | None) -> str:
    """Build the fast-tier chat system prompt: vault structure + any caller system."""
    base = VAULT_CHAT_PREAMBLE.format(outline=_vault_outline())
    if user_system and user_system.strip():
        return base + "\n\n" + user_system.strip()
    return base


@app.route("/api/router/status")
def api_router_status():
    return jsonify(router.status())


@app.route("/api/router/check", methods=["POST"])
def api_router_check():
    """Cheap backend check for Settings.

    This verifies local reachability/configuration only (Ollama HTTP, API key
    presence, CLI on PATH). It deliberately avoids sending a model prompt.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Settings payload must be an object."}), 400
    tier = str(data.get("tier") or "").strip().lower()
    if tier not in router.TIERS:
        return jsonify({"error": f"Unknown tier '{tier}'."}), 400
    if tier == "chatgpt":
        ok, reason = router.codex_cli_health()
        info = router.status_for(tier)  # health just populated auth-aware status
        return jsonify({"ok": ok, "tier": tier, "reason": reason, "status": info})
    info = router.status_for(tier)
    ok = bool(info.get("available"))
    reason = "ready" if ok else {
        "fast": "Ollama is not reachable.",
        "smart": "No Anthropic API key is configured.",
        "openai": "No OpenAI API key is configured.",
        "chatgpt": "Codex CLI was not found on PATH.",
        "claude": "Claude CLI was not found on PATH.",
    }.get(tier, "Not available.")
    return jsonify({"ok": ok, "tier": tier, "reason": reason, "status": info})


@app.route("/api/ollama/models")
def api_ollama_models():
    """Locally-pulled Ollama models + the configured default, for the model picker."""
    return jsonify({"models": router.list_ollama_models(), "default": router._ollama_model()})


# ── Chat attachments ────────────────────────────────────────────────────────

def _prune_attachments() -> None:
    """Best-effort cleanup of old uploads so the folder never grows unbounded."""
    try:
        now = time.time()
        for p in ATTACH_DIR.glob("*"):
            if p.is_file() and now - p.stat().st_mtime > ATTACH_MAX_AGE:
                try:
                    p.unlink()
                except OSError:
                    pass
    except OSError:
        pass


@app.route("/api/chat/upload", methods=["POST"])
def api_chat_upload():
    """Accept a single chat attachment, store it, return a handle for /api/chat.

    The frontend uploads each picked file here first; the returned `id` is what it
    later sends in the message's `attachments` list. Files are validated by
    extension + size and stored under a randomized name to avoid collisions and
    path games."""
    f = request.files.get("file")
    if f is None or not (f.filename or "").strip():
        return jsonify({"error": "No file uploaded."}), 400

    name = os.path.basename(f.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_ATTACH_EXTS:
        allowed = ", ".join(sorted(ALLOWED_ATTACH_EXTS))
        return jsonify({"error": f"Can't attach {ext or 'that file'} — allowed: {allowed}."}), 400

    # Size check without trusting any client-sent length.
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size == 0:
        return jsonify({"error": "That file is empty."}), 400
    if size > MAX_ATTACH_BYTES:
        return jsonify({"error": "File is too large (max 25 MB)."}), 400

    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    _prune_attachments()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name) or f"file{ext}"
    stored = f"{uuid.uuid4().hex}_{safe}"
    f.save(str(ATTACH_DIR / stored))

    mime = f.mimetype or mimetypes.guess_type(name)[0] or "application/octet-stream"
    return jsonify({"id": stored, "name": name, "mime": mime, "size": size})


def _resolve_attachments(raw) -> list:
    """Turn client attachment handles into {path, name, mime}, traversal-safe.

    Only ids that resolve to an existing file *inside* ATTACH_DIR survive — a
    crafted id can't point the router at an arbitrary file."""
    base = ATTACH_DIR.resolve()
    out = []
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if not isinstance(aid, str) or not aid:
            continue
        p = (ATTACH_DIR / aid).resolve()
        try:
            p.relative_to(base)
        except ValueError:
            continue
        if not p.is_file():
            continue
        out.append({"path": str(p), "name": a.get("name") or aid, "mime": a.get("mime") or ""})
    return out


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Tier-routed chat for the generic cockpit chat panel."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Chat payload must be an object."}), 400
    if not isinstance(data.get("messages"), list):
        return jsonify({"error": "No messages provided."}), 400

    messages = _clean_messages(data["messages"])
    attachments = _resolve_attachments(data.get("attachments"))
    # An attachment-only turn (no typed text) is valid — _clean_messages drops the
    # empty user message, so re-add one for the model to anchor the files to.
    if attachments and (not messages or messages[-1]["role"] != "user"):
        messages.append({"role": "user", "content": "(see attached file(s))"})
    if not messages or messages[0]["role"] != "user":
        return jsonify({"error": "Say something to start the conversation."}), 400

    tier = str(data.get("tier") or "fast").strip().lower()
    if tier not in router.TIERS:
        return jsonify({"error": f"Unknown tier '{tier}'."}), 400
    user_system = data.get("system") if isinstance(data.get("system"), str) else None
    # "Edit mode" — lets chat change vault notes. Each tier honors it differently:
    # fast/smart/openai unlock the write tools in the loop below; the ChatGPT and
    # Claude CLI tiers switch their sandbox/tool policy in router.chat().
    edit_mode = bool(data.get("edit"))
    # A per-request model override is honored for the tiers whose UI exposes a
    # model picker: the local (fast/Ollama) tier and the two account-CLI tiers
    # (chatgpt/Codex, claude). Smart/OpenAI stay on the Settings-configured model,
    # so an Ollama model name can never be handed to Anthropic on the smart tier.
    raw_model = data.get("model")
    model = (raw_model.strip()
             if (tier in ("fast", "chatgpt", "claude")
                 and isinstance(raw_model, str) and raw_model.strip())
             else None)

    # Tool-loop tiers run the model over the real vault tools. Fast (local) always
    # uses the read-only loop so it can answer "what does note X say" — not just
    # see the outline; smart/openai join the loop only when Edit mode is on (else
    # they take the plain cloud-chat path below). With Edit mode, the loop also gets the
    # write/scaffold tools. The local model needs tool support; if it can't (or any
    # other fast-tier hiccup), fall back to outline-grounded plain chat so the panel
    # still answers. Smart-tier failures surface to the user. Attachment turns skip
    # the loop (chat_tools has no attachment path) and use the image-inlining chat.
    use_loop = (tier == "fast" or (tier in ("smart", "openai") and edit_mode))
    if use_loop and not attachments:
        try:
            return jsonify(agent.chat_vault(
                messages, tier=tier, system=user_system, max_tokens=2048, model=model,
                allow_write=edit_mode, max_steps=8 if edit_mode else 6,
            ))
        except router.RouterError as e:
            if tier != "fast":
                return jsonify({"error": e.message}), e.status
            pass  # fast: fall through to plain outline-grounded chat below

    # The weak local model is blind on its own, so ground it with the live vault
    # structure. The cloud/subscription tiers can read files themselves, so they
    # keep the caller's system prompt untouched.
    system = _vault_chat_system(user_system) if tier == "fast" else user_system
    try:
        result = router.chat(
            messages, tier=tier, system=system, max_tokens=2048,
            model=model, attachments=attachments, allow_write=edit_mode,
        )
    except router.RouterError as e:
        return jsonify({"error": e.message}), e.status
    return jsonify(result)


# ── Live Claude chat streams ─────────────────────────────────────────────────
# The claude tier runs the CLI's own agentic loop, which can legitimately take a
# while. Rather than block /api/chat for the whole run (and hide everything until
# it finishes), the panel starts a stream, gets a run_id, then polls for the
# thinking / tool / text events as they arrive. Mirrors the agent-run store: an
# in-memory, single-user, capped dict. Only the claude tier uses this path — the
# other tiers stay on the blocking /api/chat above.
_CHAT_STREAMS: dict[str, dict] = {}
_CHAT_STREAMS_LOCK = threading.Lock()
_CHAT_STREAMS_MAX = 40


def _trim_chat_streams_locked() -> None:
    finished = sorted(
        (v for v in _CHAT_STREAMS.values() if v["status"] != "running"),
        key=lambda v: v["started"],
    )
    for old in finished[:-_CHAT_STREAMS_MAX]:
        _CHAT_STREAMS.pop(old["id"], None)


def _chat_stream_worker(run_id, messages, system, model, attachments, edit_mode):
    """Consume the Claude CLI stream and map its events onto UI steps.

    think = extended-thinking blocks; text = intermediate/answer text as it
    streams; tool/tool_result = the CLI's file work. The authoritative final
    reply comes from the trailing 'result' event."""
    def append(ev):
        with _CHAT_STREAMS_LOCK:
            run = _CHAT_STREAMS.get(run_id)
            if run is not None:
                run["steps"].append(ev)

    names: dict = {}
    reply = ""
    model_used = ""
    try:
        for ev in router.claude_code_chat_stream(
                messages, system=system, model=model,
                attachments=attachments, allow_write=edit_mode):
            etype = ev.get("type")
            if etype == "system" and ev.get("subtype") == "init":
                model_used = ev.get("model") or model_used
            elif etype == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    bt = b.get("type")
                    if bt == "thinking" and (b.get("thinking") or "").strip():
                        append({"type": "think", "text": b["thinking"]})
                    elif bt == "text" and (b.get("text") or "").strip():
                        append({"type": "text", "text": b["text"]})
                    elif bt == "tool_use":
                        names[b.get("id")] = b.get("name")
                        append({"type": "tool", "tool": b.get("name")})
            elif etype == "user":
                for b in (ev.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_result":
                        append({"type": "tool_result",
                                "tool": names.get(b.get("tool_use_id"), "tool")})
            elif etype == "result":
                if ev.get("is_error"):
                    why = ev.get("result") or ev.get("subtype") or "unknown error"
                    raise router.RouterError(
                        f"The Claude CLI returned an error: {why}", 502)
                reply = (ev.get("result") or "").strip()
                model_used = next(iter(ev.get("modelUsage") or {}), None) or model_used
        with _CHAT_STREAMS_LOCK:
            run = _CHAT_STREAMS.get(run_id)
            if run is not None:
                run["status"] = "done"
                run["reply"] = reply or "…(the model went quiet — try again)"
                run["model"] = model_used or "claude (plan)"
                _trim_chat_streams_locked()
    except router.RouterError as e:
        with _CHAT_STREAMS_LOCK:
            run = _CHAT_STREAMS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = e.message
                _trim_chat_streams_locked()
    except Exception as e:  # noqa: BLE001 — never leave a stream stuck "running"
        with _CHAT_STREAMS_LOCK:
            run = _CHAT_STREAMS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = f"Unexpected error: {e}"
                _trim_chat_streams_locked()


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """Start a live Claude chat run; returns a run_id to poll. Claude tier only."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Chat payload must be an object."}), 400
    if not isinstance(data.get("messages"), list):
        return jsonify({"error": "No messages provided."}), 400

    messages = _clean_messages(data["messages"])
    attachments = _resolve_attachments(data.get("attachments"))
    if attachments and (not messages or messages[-1]["role"] != "user"):
        messages.append({"role": "user", "content": "(see attached file(s))"})
    if not messages or messages[0]["role"] != "user":
        return jsonify({"error": "Say something to start the conversation."}), 400

    user_system = data.get("system") if isinstance(data.get("system"), str) else None
    edit_mode = bool(data.get("edit"))
    # Per-conversation Claude model override; empty falls back to the plan default.
    raw_model = data.get("model")
    model = raw_model.strip() if (isinstance(raw_model, str) and raw_model.strip()) else None

    run_id = uuid.uuid4().hex[:12]
    with _CHAT_STREAMS_LOCK:
        _CHAT_STREAMS[run_id] = {
            "id": run_id,
            "status": "running",
            "steps": [],
            "reply": "",
            "model": "",
            "error": None,
            "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        _trim_chat_streams_locked()

    threading.Thread(
        target=_chat_stream_worker,
        args=(run_id, messages, user_system, model, attachments, edit_mode),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "run_id": run_id})


@app.route("/api/chat/stream/<run_id>")
def api_chat_stream_status(run_id):
    """Poll a live Claude chat run. `since` is a step cursor to fetch only new
    events; `total` in the response is the next cursor to pass."""
    since = request.args.get("since", default=0, type=int) or 0
    with _CHAT_STREAMS_LOCK:
        run = _CHAT_STREAMS.get(run_id)
        if run is None:
            return jsonify({"error": "No such chat stream."}), 404
        steps = run["steps"]
        return jsonify({
            "status": run["status"],
            "steps": steps[since:] if since < len(steps) else [],
            "total": len(steps),
            "reply": run["reply"],
            "model": run["model"],
            "error": run["error"],
        })


# ── Chat conversation store (multi-chat, v1.20) ──────────────────────────────
# Thin CRUD wrappers over chats.py. Generation stays on the stateless /api/chat
# above — these routes only persist/list transcripts so conversations survive
# reloads and restarts. Ids are traversal-guarded in chats._chat_path.

@app.errorhandler(chats.ChatStoreError)
def _chat_store_error(e: chats.ChatStoreError):
    return jsonify({"error": e.message}), e.status


@app.route("/api/chats", methods=["GET", "POST"])
def api_chats():
    """List conversation metadata (GET) or mint a new conversation (POST)."""
    if request.method == "POST":
        return jsonify(chats.create_chat(tier=config.get("default_tier")))
    return jsonify({"chats": chats.list_chats()})


@app.route("/api/chats/<cid>", methods=["GET", "PUT", "DELETE"])
def api_chat_one(cid: str):
    """Fetch, replace, or delete one stored conversation."""
    if request.method == "GET":
        obj = chats.load_chat(cid)
        if obj is None:
            return jsonify({"error": "No such chat."}), 404
        return jsonify(obj)
    if request.method == "DELETE":
        return jsonify({"deleted": chats.delete_chat(cid)})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Chat must be an object."}), 400
    data["id"] = cid  # the URL is authoritative — a body id can't redirect the write
    existing = chats.load_chat(cid) or {}
    data.setdefault("created", existing.get("created"))
    return jsonify(chats.save_chat(data))


if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:5000  (vault: {VAULT_ROOT})")
    app.run(debug=True, port=5000)
