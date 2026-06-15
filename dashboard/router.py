"""Model router — one chat() over three backends.

This is the core primitive of the self-hosted workspace: every model call in the
app goes through chat(), which picks a backend by tier.

    tier="fast"   -> Ollama, local HTTP on :11434  (no API cost, needs Ollama)
    tier="smart"  -> Anthropic, cloud              (needs ANTHROPIC_API_KEY)
    tier="claude" -> Claude Code CLI, subprocess   (bills your Claude subscription,
                                                    not API credits; needs `claude`
                                                    installed and signed in)

chat() returns {"reply", "model", "tier"} on success, or raises RouterError with
a user-facing message + HTTP status the Flask layer can hand straight to the UI.
Adding a third backend later means one more branch here and nothing elsewhere.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import urllib.error
import urllib.request

# Local runtime. Override with env vars if Ollama lives elsewhere or you pull a
# different default model.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Cloud runtime. Smart tier defaults to the same model the twin uses.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# Subscription runtime. The `claude` tier shells out to the Claude Code CLI, which
# bills your logged-in Claude subscription (Pro/Max) instead of API credits — the
# same auth you use in Claude Code. CLAUDE_CLI_MODEL="" lets the CLI pick the
# plan's default model.
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "claude")
CLAUDE_CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "")
CLAUDE_CLI_TIMEOUT = int(os.environ.get("CLAUDE_CLI_TIMEOUT", "180"))

# The CLI confines file access to its working directory tree. Run it from the
# vault root (parent of this dashboard folder) so Chat/Twin can read the whole
# vault, not just dashboard/. Override with CLAUDE_CLI_CWD if the vault moves.
VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_CLI_CWD = os.environ.get("CLAUDE_CLI_CWD", VAULT_ROOT)

TIERS = ("fast", "smart", "claude")


# ── Attachments ──────────────────────────────────────────────────────────────
# A chat turn may carry attachments — already-saved files the app hands us as
# {"path": <abs path>, "name": <display name>, "mime": <type>}. Each tier consumes
# them differently: the claude CLI is told the paths and reads them with its own
# tools; Ollama gets vision images inlined as base64; the Anthropic API gets
# native image/document content blocks.

def _norm_attachments(attachments) -> list:
    """Normalize/validate an attachments list, filling in any missing mime."""
    out = []
    for a in attachments or []:
        if not isinstance(a, dict):
            continue
        path = a.get("path")
        if not path:
            continue
        name = a.get("name") or os.path.basename(path)
        mime = a.get("mime") or mimetypes.guess_type(name)[0] or "application/octet-stream"
        out.append({"path": path, "name": name, "mime": mime})
    return out


def _read_b64(path) -> str | None:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


class RouterError(Exception):
    """A failure with a message safe to show the user and an HTTP status."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def chat(messages, tier="fast", system=None, max_tokens=2048, model=None, attachments=None) -> dict:
    """Run a chat completion on the chosen tier.

    messages:    [{"role": "user"|"assistant", "content": str}, ...]
    system:      None, a string, or a list of Anthropic system blocks.
    attachments: None or [{"path", "name", "mime"}, ...] for the current turn;
                 applied to the most recent user message per the active tier.
    """
    tier = (tier or "fast").lower()
    if tier not in TIERS:
        tier = "fast"
    atts = _norm_attachments(attachments)
    if tier == "smart":
        return _anthropic_chat(messages, system, max_tokens, model, atts)
    if tier == "claude":
        return _claude_code_chat(messages, system, max_tokens, model, atts)
    return _ollama_chat(messages, system, max_tokens, model, atts)


def chat_tools(messages, tools, tier="smart", system=None, max_tokens=2048, model=None) -> dict:
    """One step of an agentic, tool-using exchange.

    Same idea as chat(), but the model may answer with tool calls instead of (or
    alongside) text. Returns a normalized dict the agent loop can act on without
    caring which backend produced it:

        {"text": str,                          # any assistant prose this turn
         "tool_calls": [{"id", "name", "input"}],   # tools the model wants run
         "stop_reason": str, "model": str, "tier": str}

    `messages` is canonical Anthropic-shaped history (content as a string OR a
    list of text/tool_use/tool_result blocks); the Ollama branch translates it.
    `tools` are Anthropic-style defs ({"name", "description", "input_schema"}).
    Defaults to the smart tier — tool use leans on the stronger model, and the
    fast tier needs Ollama running with a tool-capable local model.
    """
    tier = (tier or "smart").lower()
    if tier not in TIERS:
        tier = "smart"
    if tier == "fast":
        return _ollama_chat_tools(messages, tools, system, max_tokens, model)
    return _anthropic_chat_tools(messages, tools, system, max_tokens, model)


def status() -> dict:
    """Best-effort availability of each tier, for the UI to show what's live."""
    return {
        "fast": {"backend": "ollama", "model": OLLAMA_MODEL, "available": _ollama_up()},
        "smart": {
            "backend": "anthropic",
            "model": ANTHROPIC_MODEL,
            "available": bool(
                os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            ),
        },
        "claude": {
            "backend": "claude-code",
            "model": CLAUDE_CLI_MODEL or "plan default",
            "available": _claude_cli_path() is not None,
        },
    }


# ── Cloud: Anthropic ─────────────────────────────────────────────────────────

def _require_anthropic(model):
    """Import the SDK and confirm a key is present, or raise a UI-safe error.
    Returns (anthropic_module, client, resolved_model)."""
    try:
        import anthropic
    except ImportError:
        raise RouterError(
            "The `anthropic` package isn't installed. Run "
            "`pip install -r requirements.txt` and restart.",
            503,
        )
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RouterError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY in your environment, "
            "then restart the dashboard.",
            401,
        )
    return anthropic, anthropic.Anthropic(), (model or ANTHROPIC_MODEL)


def _attach_to_anthropic(messages, atts) -> list:
    """Prepend native image/document blocks to the latest user message.

    Images and PDFs become base64 content blocks the model reads directly. Other
    file types are skipped here (the app can inline small text files itself); a
    string user turn is promoted to a block list so blocks and text coexist.
    """
    blocks = []
    for a in atts:
        b64 = _read_b64(a["path"])
        if b64 is None:
            continue
        mime = a["mime"]
        if mime == "application/pdf":
            blocks.append({"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": b64}})
        elif mime.startswith("image/"):
            blocks.append({"type": "image", "source": {
                "type": "base64", "media_type": mime, "data": b64}})
    if not blocks:
        return list(messages)
    msgs = [dict(m) for m in messages]
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "user":
            content = msgs[i].get("content")
            tail = [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])
            msgs[i] = {"role": "user", "content": blocks + tail}
            break
    return msgs


def _anthropic_chat(messages, system, max_tokens, model, attachments=None) -> dict:
    anthropic, client, mdl = _require_anthropic(model)
    if attachments:
        messages = _attach_to_anthropic(messages, attachments)
    try:
        kwargs = {"model": mdl, "max_tokens": max_tokens, "messages": messages}
        if system is not None:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        raise RouterError(
            "No valid Anthropic API key found. Set ANTHROPIC_API_KEY and restart.", 401
        )
    except Exception as e:  # noqa: BLE001 — surface anything else to the UI
        raise RouterError(f"The cloud model couldn't get through: {e}", 502)

    reply = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()
    return {"reply": reply or "…(the model went quiet — try again)", "model": mdl, "tier": "smart"}


def _anthropic_chat_tools(messages, tools, system, max_tokens, model) -> dict:
    anthropic, client, mdl = _require_anthropic(model)
    try:
        kwargs = {
            "model": mdl,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
        }
        if system is not None:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        raise RouterError(
            "No valid Anthropic API key found. Set ANTHROPIC_API_KEY and restart.", 401
        )
    except Exception as e:  # noqa: BLE001 — surface anything else to the UI
        raise RouterError(f"The cloud model couldn't get through: {e}", 502)

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()
    tool_calls = [
        {"id": b.id, "name": b.name, "input": dict(b.input or {})}
        for b in resp.content
        if getattr(b, "type", None) == "tool_use"
    ]
    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": resp.stop_reason,
        "model": mdl,
        "tier": "smart",
    }


# ── Subscription: Claude Code CLI ────────────────────────────────────────────

def _claude_cli_path():
    """Resolve the `claude` executable on PATH, or None if it isn't installed."""
    return shutil.which(CLAUDE_CLI)


def _flatten_conversation(messages) -> str:
    """Collapse a string-content chat history into one prompt for `claude -p`.

    The CLI takes a single prompt (read from stdin here), so prior turns are
    folded in as a labeled transcript and the final user turn is the live
    question. Only string content is supported — the claude tier is for plain
    chat (the Agents view keeps using the smart tier for structured tool use).
    """
    turns = [m for m in messages if isinstance(m.get("content"), str)]
    if len(turns) == 1 and turns[0].get("role") == "user":
        return turns[0]["content"]
    lines = []
    for m in turns:
        who = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{who}: {m['content']}")
    return "\n\n".join(lines)


def _claude_code_chat(messages, system, max_tokens, model, attachments=None) -> dict:
    """Run a chat turn through the Claude Code CLI (subscription-billed).

    max_tokens is accepted for signature parity but not forwarded — the CLI
    manages its own output budget. Attachments are passed by path: the CLI reads
    them with its own Read tool (handles images, PDFs, and text), which we enable
    non-interactively only when files are attached.
    """
    exe = _claude_cli_path()
    if exe is None:
        raise RouterError(
            "The Claude CLI isn't installed or isn't on PATH. Install Claude Code "
            "and sign in with your subscription, then restart the dashboard.",
            503,
        )

    prompt = _flatten_conversation(messages)
    if attachments:
        listing = "\n".join(f"- {a['path']}" for a in attachments)
        prompt = (
            (prompt + "\n\n" if prompt.strip() else "")
            + "The user attached the following file(s). Read them with your tools "
            "to answer:\n" + listing
        )
    if not prompt.strip():
        raise RouterError("Nothing to send to Claude.", 400)

    cmd = [exe, "-p", "--output-format", "json"]
    if attachments:
        cmd += ["--allowedTools", "Read"]
    sys_text = _flatten_system(system)
    if sys_text:
        cmd += ["--system-prompt", sys_text]
    mdl = model or CLAUDE_CLI_MODEL
    if mdl:
        cmd += ["--model", mdl]

    # Force subscription (OAuth) auth: if an API key is in the environment the CLI
    # would bill it as API usage instead of the plan, defeating this tier's point.
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }

    # On Windows the child console app would flash up its own terminal window;
    # CREATE_NO_WINDOW suppresses it. The flag only exists on Windows, so guard it.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_CLI_TIMEOUT,
            env=env,
            cwd=CLAUDE_CLI_CWD,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        raise RouterError("The Claude CLI vanished mid-call — is it still installed?", 503)
    except subprocess.TimeoutExpired:
        raise RouterError(
            "The Claude CLI took too long to answer. Try again, or switch tiers.", 504
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RouterError(f"The Claude CLI failed: {detail or 'unknown error'}", 502)

    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        raise RouterError("Couldn't parse the Claude CLI response.", 502)

    if data.get("is_error"):
        why = data.get("result") or data.get("subtype") or "unknown error"
        raise RouterError(f"The Claude CLI returned an error: {why}", 502)

    reply = (data.get("result") or "").strip()
    used_model = next(iter(data.get("modelUsage") or {}), None) or mdl or "claude (plan)"
    return {
        "reply": reply or "…(the model went quiet — try again)",
        "model": used_model,
        "tier": "claude",
    }


# ── Local: Ollama ────────────────────────────────────────────────────────────

def _flatten_system(system) -> str:
    """Anthropic system can be blocks; Ollama wants one string."""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return "\n\n".join(
            b.get("text", "") for b in system if isinstance(b, dict)
        ).strip()
    return ""


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def list_ollama_models() -> list:
    """Names of locally-pulled Ollama models ([] if Ollama is unreachable)."""
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return []
    return sorted(m.get("name") for m in (data.get("models") or []) if m.get("name"))


def _attach_to_ollama(messages, atts) -> list:
    """Inline image attachments as base64 on the latest user message.

    Ollama vision models take an `images` array of base64 strings per message.
    Non-image files can't be fed to a local model here, so we just name them in
    the text and point the user at the Claude tier (which can read them).
    """
    images, others = [], []
    for a in atts:
        if a["mime"].startswith("image/"):
            b64 = _read_b64(a["path"])
            (images.append(b64) if b64 else others.append(a["name"]))
        else:
            others.append(a["name"])
    msgs = [dict(m) for m in messages]
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "user" and isinstance(msgs[i].get("content"), str):
            if images:
                msgs[i]["images"] = images
            if others:
                msgs[i]["content"] = (msgs[i]["content"] + (
                    "\n\n[Attached file(s) a local model can't read here: "
                    + ", ".join(others) + ". Switch to the Claude tier to have them read.]"
                ))
            break
    return msgs


def _ollama_chat(messages, system, max_tokens, model, attachments=None) -> dict:
    mdl = model or OLLAMA_MODEL
    msgs = list(messages)
    if attachments:
        msgs = _attach_to_ollama(msgs, attachments)
    if system is not None:
        sys_text = _flatten_system(system)
        if sys_text:
            msgs = [{"role": "system", "content": sys_text}] + msgs

    payload = json.dumps(
        {
            "model": mdl,
            "messages": msgs,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:  # noqa: BLE001
            pass
        if e.code == 404 or "not found" in detail.lower():
            raise RouterError(
                f"Local model '{mdl}' isn't pulled yet. Run `ollama pull {mdl}` "
                "and try again, or switch to the smart (cloud) tier.",
                503,
            )
        raise RouterError(f"Local model error: {detail or e}", 502)
    except (urllib.error.URLError, OSError):
        raise RouterError(
            f"Local model (Ollama) isn't reachable on {OLLAMA_HOST}. Install it from "
            f"ollama.com and run `ollama pull {mdl}`, or use the smart (cloud) tier.",
            503,
        )

    reply = (data.get("message") or {}).get("content", "").strip()
    return {"reply": reply or "…(empty response from the local model)", "model": mdl, "tier": "fast"}


def _result_to_str(content) -> str:
    """Tool-result content is a string in our canonical form; coerce anything else."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content)


def _to_ollama_messages(messages) -> list:
    """Translate canonical (Anthropic-shaped) history into Ollama's chat format.

    Text blocks collapse to a content string; tool_use becomes an assistant
    `tool_calls` entry; tool_result becomes a separate `role: tool` message.
    """
    out = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if role == "assistant":
            texts, calls = [], []
            for b in content or []:
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    calls.append({"function": {"name": b.get("name"), "arguments": b.get("input") or {}}})
            msg = {"role": "assistant", "content": "\n".join(texts)}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:  # user turn: plain text and/or tool results
            texts = []
            for b in content or []:
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "tool_result":
                    out.append({"role": "tool", "content": _result_to_str(b.get("content"))})
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})
    return out


def _to_ollama_tools(tools) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _ollama_chat_tools(messages, tools, system, max_tokens, model) -> dict:
    mdl = model or OLLAMA_MODEL
    msgs = _to_ollama_messages(messages)
    if system is not None:
        sys_text = _flatten_system(system)
        if sys_text:
            msgs = [{"role": "system", "content": sys_text}] + msgs

    payload = json.dumps(
        {
            "model": mdl,
            "messages": msgs,
            "tools": _to_ollama_tools(tools),
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:  # noqa: BLE001
            pass
        if e.code == 404 or "not found" in detail.lower():
            raise RouterError(
                f"Local model '{mdl}' isn't pulled yet. Run `ollama pull {mdl}` "
                "and try again, or switch the agent to the smart (cloud) tier.",
                503,
            )
        raise RouterError(f"Local model error: {detail or e}", 502)
    except (urllib.error.URLError, OSError):
        raise RouterError(
            f"Local model (Ollama) isn't reachable on {OLLAMA_HOST}. Install it from "
            f"ollama.com and run `ollama pull {mdl}`, or use the smart (cloud) tier.",
            503,
        )

    msg = data.get("message") or {}
    text = (msg.get("content") or "").strip()
    tool_calls = []
    for i, tc in enumerate(msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                args = {}
        tool_calls.append({"id": f"call_{i}", "name": fn.get("name"), "input": args or {}})
    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": "tool_use" if tool_calls else "end_turn",
        "model": mdl,
        "tier": "fast",
    }
