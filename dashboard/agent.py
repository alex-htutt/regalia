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

import json
from pathlib import Path

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


def _safe_path(rel: str, must_exist: bool = False) -> Path:
    """Resolve a vault-relative path, refusing anything that escapes the vault."""
    root = _vault_root()
    rel = (rel or "").replace("\\", "/").strip("/")
    if not rel:
        raise AgentError("A path is required.")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise AgentError(f"Path '{rel}' is outside the vault.")
    if must_exist and not target.exists():
        raise AgentError(f"Nothing found at '{rel}'.")
    return target


# ── Tool implementations ─────────────────────────────────────────────────────
# Each returns a plain string — what the model sees as the tool result.

def _tool_search_vault(query: str = "", limit: int = 12, **_) -> str:
    query = (query or "").strip()
    if not query:
        return "Error: search needs a non-empty query."
    root = _vault_root()
    ignore = _ignore_dirs()
    q = query.lower()
    hits = []
    for md in root.rglob("*.md"):
        rel = md.relative_to(root)
        if any(part in ignore for part in rel.parts):
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
            hits.append(f"{rel.as_posix()} — {line_hit or '(filename match)'}")
        if len(hits) >= max(1, min(int(limit or 12), 40)):
            break
    if not hits:
        return f"No notes match '{query}'."
    return f"{len(hits)} match(es) for '{query}':\n" + "\n".join(hits)


def _tool_read_note(path: str = "", **_) -> str:
    target = _safe_path(path, must_exist=True)
    if target.is_dir() or target.suffix.lower() != ".md":
        return f"Error: '{path}' is not a markdown note."
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return f"Error reading '{path}': {e}"
    if len(text) > 8000:
        text = text[:8000] + "\n…(truncated)"
    return text or "(empty note)"


def _tool_list_notes(area: str = "", status: str = "", type: str = "", limit: int = 60, **_) -> str:
    import app
    tasks = app.load_tasks()
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


def _tool_list_folder(path: str = "", **_) -> str:
    root = _vault_root()
    ignore = _ignore_dirs()
    target = root if not (path or "").strip().strip("/") else _safe_path(path, must_exist=True)
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
    rel = target.relative_to(root).as_posix() if target != root else "(vault root)"
    body = []
    if folders:
        body.append("Folders: " + ", ".join(folders))
    if notes:
        body.append("Notes: " + ", ".join(notes))
    return f"{rel}\n" + ("\n".join(body) if body else "(empty)")


def _tool_write_note(path: str = "", content: str = "", **_) -> str:
    target = _safe_path(path)
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
    root = _vault_root()
    return f"{'Overwrote' if existed else 'Created'} {target.relative_to(root).as_posix()} ({len(content)} chars)."


def _tool_create_project(name: str = "", area: str = "projects", topic: str = "", deadline: str = "", **_) -> str:
    import app
    try:
        result = app.create_project_core(name, area, topic, deadline)
    except ValueError as e:
        return f"Error: {e}"
    return (
        f"Created project '{result['path']}' with subfolders "
        f"{', '.join(result['subdirs'])} and {result['context_file']}"
        + (" · linked in Home." if result.get("home_linked") else ".")
    )


TOOL_FNS = {
    "search_vault": _tool_search_vault,
    "read_note": _tool_read_note,
    "list_notes": _tool_list_notes,
    "list_folder": _tool_list_folder,
    "write_note": _tool_write_note,
    "create_project": _tool_create_project,
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
        "description": "List notes that have frontmatter, optionally filtered by area (internship/projects/research), status (active/complete/archived), or type (daily-log/standup/meeting/...). Newest first.",
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
                "area": {"type": "string", "description": "projects | internship | research"},
                "topic": {"type": "string"},
                "deadline": {"type": "string", "description": "YYYY-MM-DD, optional."},
            },
            "required": ["name"],
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

AGENTS = {
    "summarizer": {
        "id": "summarizer",
        "name": "Daily Summarizer",
        "desc": "Roll up recent daily-logs into a standup note.",
        "tier": "fast",
        "tools": ["list_notes", "read_note", "write_note"],
        "default_task": "Summarize my most recent daily-log notes into a concise standup.",
        "system": (
            "You are the Daily Summarizer. Use list_notes (type 'daily-log') to find "
            "recent logs, read the latest few with read_note, then synthesize a tight "
            "standup: what got done, what's next, and any blockers. If the user asks you "
            "to save it, write it with write_note as a type/standup note with correct "
            "frontmatter; otherwise just return the standup text. " + _VAULT_RULES
        ),
    },
    "scaffolder": {
        "id": "scaffolder",
        "name": "Project Scaffolder",
        "desc": "Turn a one-line brief into a project folder + context file.",
        "tier": "fast",
        "tools": ["list_folder", "create_project"],
        "default_task": "",
        "system": (
            "You are the Project Scaffolder. Turn the user's one-line brief into exactly "
            "one project: infer a clear name, pick the area (projects/internship/research), "
            "write a one-line topic, and call create_project once. If the brief is too "
            "vague to name a project, ask for the missing detail instead of guessing. " + _VAULT_RULES
        ),
    },
    "researcher": {
        "id": "researcher",
        "name": "Research Agent",
        "desc": "Read vault sources and synthesize them into a research note.",
        "tier": "smart",
        "tools": ["search_vault", "read_note", "list_notes", "write_note"],
        "default_task": "",
        "system": (
            "You are the Research Agent. Given a topic, search_vault and read the most "
            "relevant notes, then synthesize a well-structured research note (overview, "
            "key findings with note references via [[wikilinks]], open questions). Save it "
            "with write_note under the relevant project's research/ folder as a "
            "type/research note with proper frontmatter, then summarize what you wrote. " + _VAULT_RULES
        ),
    },
}


def list_agents() -> list:
    """Public, UI-facing view of the registry (no prompts/tools internals)."""
    return [
        {"id": a["id"], "name": a["name"], "desc": a["desc"], "tier": a["tier"], "status": "idle"}
        for a in AGENTS.values()
    ]


# ── The run loop ─────────────────────────────────────────────────────────────

def run_agent(agent_id: str, task: str, tier: str = "", emit=None, max_steps: int = 8) -> dict:
    """Drive one agent to completion. Returns {reply, steps, tier, model, agent}.

    `emit(event)` (optional) is called as each step happens, for live streaming.
    Events: {"type": "start"|"think"|"tool"|"tool_result"|"final"|"limit", ...}.
    Raises AgentError on an unusable request or a backend failure.
    """
    spec = AGENTS.get(agent_id)
    if not spec:
        raise AgentError(f"Unknown agent '{agent_id}'.")
    task = (task or "").strip() or spec.get("default_task", "")
    if not task:
        raise AgentError(f"{spec['name']} needs a task — tell it what to do.")
    tier = (tier or spec["tier"]).lower()
    if tier not in ("fast", "smart"):
        tier = spec["tier"]

    tools = [TOOL_SCHEMAS[name] for name in spec["tools"] if name in TOOL_SCHEMAS]
    system = spec["system"]
    messages = [{"role": "user", "content": [{"type": "text", "text": task}]}]

    def _emit(ev):
        if emit:
            try:
                emit(ev)
            except Exception:  # noqa: BLE001 — never let UI plumbing break a run
                pass

    _emit({"type": "start", "agent": agent_id, "tier": tier, "task": task})
    steps = []
    model = ""

    for _ in range(max_steps):
        try:
            res = router.chat_tools(messages, tools, tier=tier, system=system, max_tokens=3072)
        except router.RouterError as e:
            _emit({"type": "error", "text": e.message})
            raise AgentError(e.message)

        model = res.get("model", model)
        text, tool_calls = res.get("text", ""), res.get("tool_calls", [])
        if text:
            _emit({"type": "think", "text": text})

        if not tool_calls:
            _emit({"type": "final", "text": text})
            return {"reply": text or "(the agent finished without a summary)",
                    "steps": steps, "tier": tier, "model": model, "agent": agent_id}

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
                    out = fn(**args) if isinstance(args, dict) else fn()
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
            "steps": steps, "tier": tier, "model": model, "agent": agent_id}
