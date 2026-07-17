"""Regalia local task dashboard."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import threading
import uuid

import yaml
from flask import Flask, jsonify, render_template, request

import agent
import chats
import config
import mailbox
import news_sources
import paths
import router

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
IGNORE_DIRS = {".obsidian", ".cursor", ".claude", "templates", "__pycache__", "dashboard"}
IGNORE_FILES = {"CLAUDE.md", "README_HOME.md", "USAGE.md", "Home.md"}

# Claude Code writes per-session transcripts here; each line carries a
# message.usage block we aggregate. We read ONLY token counts / model /
# timestamp — never message content.
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Chat attachments land here (gitignored). From source it lives under dashboard/,
# which is in IGNORE_DIRS so the vault walk never surfaces uploads as notes — but
# it's still inside the vault tree, so the claude CLI (cwd = vault root) can read
# the files. Packaged builds move it to the per-user data dir; there the claude
# tier can't reach attachments by path (fast/smart/openai inline them instead).
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


@app.route("/")
def index():
    # Boot settings ride into the page inline so the theme applies before first
    # paint (no flash of the wrong palette). Secrets are masked by config.mask.
    return render_template(
        "index.html",
        boot_settings=json.dumps(config.mask(config.load())),
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
        return jsonify({"settings": config.mask(cfg), "vault_root": str(VAULT_ROOT)})
    return jsonify({"settings": config.mask(config.load()), "vault_root": str(VAULT_ROOT)})


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


def _score_job(title: str, location: str) -> tuple[int, list[str]]:
    """Rank one posting against the user's profile (news_sources config).

    Returns (score, tags). Interest-bucket hits add points and a tag;
    internship/new-grad roles get a big boost (early-career profile); senior
    roles are pushed down; a preferred location is a soft bonus. Score <= 0 means
    "not for you" and the posting is dropped by the caller. Title matching is
    word-bounded so short tokens (ml, ai) don't fire inside other words.
    """
    t = (title or "").lower()
    loc = (location or "").lower()
    tags: list[str] = []
    score = 0
    for bucket, kws in news_sources.INTEREST_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", t) for kw in kws):
            tags.append(bucket)
            score += 3
    if any(sig in t for sig in news_sources.EARLY_CAREER_SIGNALS):
        score += 5
        tags.insert(0, "Intern" if "intern" in t else "Early career")
    if any(sig in t for sig in news_sources.SENIOR_SIGNALS):
        score -= 4
    if any(p in loc for p in news_sources.PREFERRED_LOCATIONS):
        score += 1
    return score, tags


def _fetch_jobs() -> tuple[list[dict], list[str]]:
    """Pull a wide pool of postings, score each against the user's profile, drop
    the irrelevant ones, and return the top matches (best fit first)."""
    pool, errors = [], []
    for board in news_sources.GREENHOUSE_BOARDS:
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
        job["score"], job["tags"] = _score_job(job["title"], job["location"])
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
    news, e1 = _fetch_rss_group(news_sources.NEWS_FEEDS, news_sources.MAX_PER_NEWS_FEED)
    jobs, e2 = _fetch_jobs()
    return {
        "available": True,
        "fetched": datetime.now().astimezone().isoformat(timespec="seconds"),
        "news": news,
        "jobs": jobs,
        "errors": e1 + e2,
    }


def load_briefing(force: bool = False) -> dict:
    """Return the cached briefing, refreshing if older than NEWS_TTL (or forced)."""
    with _NEWS_LOCK:
        fresh = _NEWS_CACHE["data"] is not None and (time.time() - _NEWS_CACHE["ts"]) < _news_ttl()
        if fresh and not force:
            return _NEWS_CACHE["data"]
    data = _build_briefing()  # network I/O outside the lock
    with _NEWS_LOCK:
        _NEWS_CACHE["data"] = data
        _NEWS_CACHE["ts"] = time.time()
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
    if area.lower() in {d.lower() for d in IGNORE_DIRS}:
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
        f'topic: "{topic}"\n'
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


@app.route("/api/project", methods=["POST"])
def api_create_project():
    data = request.get_json(silent=True) or {}
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


def _emit_to(run_id: str):
    def emit(event):
        event = {**event, "ts": datetime.now().astimezone().isoformat(timespec="seconds")}
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["steps"].append(event)
    return emit


def _run_worker(run_id: str, agent_id: str, task: str, tier: str):
    try:
        result = agent.run_agent(agent_id, task, tier, emit=_emit_to(run_id))
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "done"
                run["result"] = result
    except agent.AgentError as e:
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = e.message
    except Exception as e:  # noqa: BLE001 — never let a crash leave a run "running"
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
            if run is not None:
                run["status"] = "error"
                run["error"] = f"Unexpected error: {e}"


@app.route("/api/agents")
def api_agents():
    return jsonify({"agents": agent.list_agents()})


@app.route("/api/agent/run", methods=["POST"])
def api_agent_run():
    data = request.get_json(silent=True) or {}
    agent_id = str(data.get("agent") or "").strip()
    task = str(data.get("task") or "").strip()
    tier = str(data.get("tier") or "").strip().lower()
    if agent_id not in agent.AGENTS:
        return jsonify({"error": f"Unknown agent '{agent_id}'."}), 400
    if tier and tier not in ("fast", "smart", "claude"):
        tier = ""

    run_id = uuid.uuid4().hex[:12]
    run = {
        "id": run_id,
        "agent": agent_id,
        "name": agent.AGENTS[agent_id]["name"],
        "task": task,
        "tier": tier or agent.AGENTS[agent_id]["tier"],
        "status": "running",
        "steps": [],
        "result": None,
        "error": None,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with _RUNS_LOCK:
        _RUNS[run_id] = run
        # Trim oldest finished runs if the store grows past the cap.
        if len(_RUNS) > _RUNS_MAX:
            for old in sorted(_RUNS, key=lambda k: _RUNS[k]["started"])[: len(_RUNS) - _RUNS_MAX]:
                _RUNS.pop(old, None)

    threading.Thread(
        target=_run_worker, args=(run_id, agent_id, task, tier), daemon=True
    ).start()
    return jsonify({"ok": True, "run_id": run_id, "agent": agent_id, "tier": run["tier"]})


@app.route("/api/agent/run/<run_id>")
def api_agent_run_status(run_id):
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        snapshot = dict(run) if run else None
    if snapshot is None:
        return jsonify({"error": "No such run."}), 404
    return jsonify(snapshot)


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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    model = str(data.get("model") or "").strip()
    if not _MODEL_NAME_RE.match(model):
        return jsonify({"error": "model must be a name like 'llama3.2' or 'qwen3:8b'"}), 400
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    tier = str(data.get("tier") or "").strip().lower()
    st = router.status()
    if tier not in st:
        return jsonify({"error": f"Unknown tier '{tier}'."}), 400
    info = st[tier]
    if tier == "chatgpt":
        ok, reason = router.codex_cli_health()
        return jsonify({"ok": ok, "tier": tier, "reason": reason, "status": info})
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
    data = request.get_json(silent=True) or {}
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
    user_system = data.get("system") if isinstance(data.get("system"), str) else None
    # "Edit mode" — lets chat change vault notes. Each tier honors it differently:
    # fast/smart/openai unlock the write tools in the tool loop below; the claude
    # CLI tier gets the file-editing tools via router.chat(allow_write=...). Every
    # tier can write when it's on.
    edit_mode = bool(data.get("edit"))
    # A model override only applies to the local (fast) tier — guard it so an
    # Ollama model name can never be handed to Anthropic on the smart tier.
    raw_model = data.get("model")
    model = raw_model.strip() if (tier == "fast" and isinstance(raw_model, str) and raw_model.strip()) else None

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
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Chat must be an object."}), 400
    data["id"] = cid  # the URL is authoritative — a body id can't redirect the write
    existing = chats.load_chat(cid) or {}
    data.setdefault("created", existing.get("created"))
    return jsonify(chats.save_chat(data))


if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:5000  (vault: {VAULT_ROOT})")
    app.run(debug=True, port=5000)
