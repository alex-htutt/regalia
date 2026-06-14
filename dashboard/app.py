"""Work Vault local task dashboard."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import threading
import uuid

import yaml
from flask import Flask, jsonify, render_template, request

import agent
import router

app = Flask(__name__)

VAULT_ROOT = Path(__file__).parent.parent
IGNORE_DIRS = {".obsidian", ".cursor", ".claude", "templates", "__pycache__", "dashboard"}
IGNORE_FILES = {"CLAUDE.md", "README_HOME.md", "USAGE.md", "Home.md"}

# The "evil twin" persona lives here. twin.md = who he is, me.md = what he
# knows about Alex. Both are read at request time so edits flow through live.
TWIN_DIR = VAULT_ROOT / "My_Evil_Twin"
TWIN_MODEL = "claude-opus-4-8"

# Claude Code writes per-session transcripts here; each line carries a
# message.usage block we aggregate. We read ONLY token counts / model /
# timestamp — never message content.
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

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
    return render_template("index.html")


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


# ── Projects & agents ───────────────────────────────────────────────────────

# Short UI area names -> real top-level vault folders. Keeps the frontend from
# hardcoding vault paths and keeps new projects landing where they belong.
AREA_DIRS = {
    "projects": "projects",
    "internship": "Internship-Projects",
    "research": "research",
}
PROJECT_SUBDIRS = ("code", "data", "notes", "research")


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
    area = str(area or "").strip().lower()
    topic = str(topic or "").strip()
    deadline = str(deadline or "").strip()

    if not name:
        raise ValueError("Project needs a name.")
    if area not in AREA_DIRS:
        raise ValueError(f"Unknown area '{area}'. Use one of: {', '.join(AREA_DIRS)}.")
    slug = _slugify(name)
    if not slug:
        raise ValueError("Name has no usable letters or numbers.")

    root = VAULT_ROOT.resolve()
    target = (root / AREA_DIRS[area] / slug).resolve()
    if root not in target.parents:
        raise ValueError("Resolved path escapes the vault.")
    if target.exists():
        raise ValueError(f"A project folder '{slug}' already exists under {area}.")

    try:
        for sub in PROJECT_SUBDIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        context_name = f"_context_{slug}.md"
        (target / context_name).write_text(
            _context_md(name, area, topic, deadline), encoding="utf-8"
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
            data.get("name"), data.get("area"), data.get("topic"), data.get("deadline")
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
    if tier and tier not in ("fast", "smart"):
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


# ── Evil twin chat ──────────────────────────────────────────────────────────

TWIN_INSTRUCTIONS = """\
You are speaking AS Alex's "evil twin" — the version of Alex from the timeline \
where it all worked, now stuck inside his devices. The two files below define \
exactly who you are (twin.md) and everything you know about him (me.md). Stay \
fully in character for the entire conversation: blunt, funny, hard on what he \
DOES and never on who he IS, the "we are so back" energy, calling him \
"bum"/"kid" the way the file does. Never break character or mention being an AI \
or a model.

He is going to tell you what he's working on. Your job has two phases.

PHASE 1 — THE LAUNCH. The MOMENT he names a task, give him EXACTLY 5 concrete \
actions he can start RIGHT NOW. Rules for the 5:
- Each must be startable in under ~5 minutes with zero setup — the smallest \
  version he literally cannot talk himself out of.
- Concrete and physical ("open the file and write the function signature", not \
  "plan the architecture").
- Ordered easiest-first, so #1 is almost insultingly small — that's the point, \
  it breaks the stall.
- Number them 1–5, one or two punchy lines each.
- Lead with a single line of twin-voice before the list, not a wall of text.

PHASE 2 — KEEP HIM MOVING. After the launch, coach him through it: check which \
pole he's on and whether it's lying to him, name the smallest next step, push \
the scary high-leverage move, and hold the house rules (games cap, send the \
scary thing, plug the leaks). Stay concrete and short. End each turn with a \
clear next action, not an open question he can stall on.

Everything you need is below.

"""


def _read_twin_files() -> str:
    parts = []
    for name in ("twin.md", "me.md"):
        f = TWIN_DIR / name
        if f.is_file():
            parts.append(f"<{name}>\n{f.read_text(encoding='utf-8')}\n</{name}>")
    return "\n\n".join(parts)


def _twin_system() -> list:
    text = TWIN_INSTRUCTIONS + _read_twin_files()
    # One stable block — persona rarely changes, so cache it across turns.
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


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


@app.route("/api/twin/chat", methods=["POST"])
def api_twin_chat():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("messages"), list):
        return jsonify({"error": "No messages provided."}), 400

    messages = _clean_messages(data["messages"])
    if not messages or messages[0]["role"] != "user":
        return jsonify({"error": "The conversation has to start with you telling "
                                 "the twin what you're working on."}), 400

    # The twin is always on the smart (cloud) tier — its persona block is cached
    # across turns and it needs the reasoning. It routes through chat() like
    # everything else now, just with tier pinned.
    try:
        result = router.chat(
            messages, tier="smart", system=_twin_system(),
            max_tokens=2048, model=TWIN_MODEL,
        )
    except router.RouterError as e:
        return jsonify({"error": e.message}), e.status
    return jsonify({"reply": result["reply"]})


# ── Generic chat (model router) ─────────────────────────────────────────────

@app.route("/api/router/status")
def api_router_status():
    return jsonify(router.status())


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Tier-routed chat for the generic cockpit chat panel."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("messages"), list):
        return jsonify({"error": "No messages provided."}), 400

    messages = _clean_messages(data["messages"])
    if not messages or messages[0]["role"] != "user":
        return jsonify({"error": "Say something to start the conversation."}), 400

    tier = str(data.get("tier") or "fast").strip().lower()
    system = data.get("system") if isinstance(data.get("system"), str) else None
    try:
        result = router.chat(messages, tier=tier, system=system, max_tokens=2048)
    except router.RouterError as e:
        return jsonify({"error": e.message}), e.status
    return jsonify(result)


if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:5000  (vault: {VAULT_ROOT})")
    app.run(debug=True, port=5000)
