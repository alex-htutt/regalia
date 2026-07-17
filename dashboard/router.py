"""Model router — one chat() over four backends.

This is the core primitive of the self-hosted workspace: every model call in the
app goes through chat(), which picks a backend by tier.

    tier="fast"   -> Ollama, local HTTP on :11434  (no API cost, needs Ollama)
    tier="smart"  -> Anthropic, cloud              (needs an Anthropic API key)
    tier="openai" -> OpenAI, cloud                 (needs an OpenAI API key)
    tier="claude" -> Claude Code CLI, subprocess   (bills your Claude subscription,
                                                    not API credits; needs `claude`
                                                    installed and signed in)

API keys come from the environment OR the Settings store (config.secret — env
wins). chat() returns {"reply", "model", "tier"} on success, or raises
RouterError with a user-facing message + HTTP status the Flask layer can hand
straight to the UI. Adding a backend means one more branch here and nothing
elsewhere.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import threading
import urllib.error
import urllib.request

import config as _config  # stdlib-only module; no circular import
import paths as _paths

# ── Backend knobs — resolved lazily, per call ────────────────────────────────
# Each accessor resolves env var → Settings store → built-in default (via
# config.value), so a change saved in the Settings view applies to the next
# request without a restart. Nothing here is read at import time.


def _ollama_host() -> str:
    """Local runtime. Override if Ollama lives elsewhere."""
    return _config.value("ollama_host", "OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return _config.value("ollama_model", "OLLAMA_MODEL", "llama3.2")


def _anthropic_model() -> str:
    """Smart tier defaults to the same model the twin uses."""
    return _config.value("anthropic_model", "ANTHROPIC_MODEL", "claude-opus-4-8")


def _openai_base() -> str:
    """OpenAI runtime (ChatGPT models) — plain REST over stdlib urllib; no SDK dep."""
    return _config.value("openai_base", "OPENAI_BASE", "https://api.openai.com/v1").rstrip("/")


def _openai_model() -> str:
    # Default = the current balanced/cost tier (verify at
    # platform.openai.com/docs/models if it 404s; override via env or Settings).
    return _config.value("openai_model", "OPENAI_MODEL", "gpt-5.6-terra")


def _claude_cli() -> str:
    """The `claude` tier shells out to the Claude Code CLI, which bills your
    logged-in Claude subscription (Pro/Max) instead of API credits."""
    return _config.value("claude_cli", "CLAUDE_CLI", "claude")


def _claude_cli_model() -> str:
    """Empty string lets the CLI pick the plan's default model."""
    return _config.value("claude_cli_model", "CLAUDE_CLI_MODEL", "")


def _claude_cli_timeout() -> int:
    try:
        return int(_config.value("claude_cli_timeout", "CLAUDE_CLI_TIMEOUT", "180"))
    except ValueError:
        return 180

# The CLI confines file access to its working directory tree. Run it from the
# vault root so Chat/Twin can read the whole vault, not just dashboard/. Vault
# root follows the same resolution as app.py (REGALIA_VAULT env → the Settings
# view's vault_path → the repo root). CLAUDE_CLI_CWD stays env-only on purpose —
# it bounds what the CLI can touch, so it shouldn't be movable from the web UI.
_vault_override = os.path.expanduser(
    os.environ.get("REGALIA_VAULT") or _config.get("vault_path") or ""
)
if _vault_override and os.path.isdir(_vault_override):
    VAULT_ROOT = os.path.abspath(_vault_override)
elif _paths.is_frozen():
    VAULT_ROOT = str(_paths.default_vault())
else:
    VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_CLI_CWD = os.environ.get("CLAUDE_CLI_CWD", VAULT_ROOT)

TIERS = ("fast", "smart", "openai", "claude")


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


# ── API keys — environment wins, then the Settings store ────────────────────

def _anthropic_key() -> str:
    return _config.secret("anthropic_api_key", "ANTHROPIC_API_KEY")


def _openai_key() -> str:
    return _config.secret("openai_api_key", "OPENAI_API_KEY")


def chat(messages, tier="fast", system=None, max_tokens=2048, model=None, attachments=None,
         allow_write=False) -> dict:
    """Run a chat completion on the chosen tier.

    messages:    [{"role": "user"|"assistant", "content": str}, ...]
    system:      None, a string, or a list of Anthropic system blocks.
    attachments: None or [{"path", "name", "mime"}, ...] for the current turn;
                 applied to the most recent user message per the active tier.
    allow_write: "Edit mode." Only the claude tier honors it here — it unlocks the
                 CLI's file-editing tools (confined to the vault working dir) so the
                 subscription tier can change notes. The fast/smart tiers write via
                 agent.chat_vault's tool loop, not this path, so they ignore it.
    """
    tier = (tier or "fast").lower()
    if tier not in TIERS:
        tier = "fast"
    atts = _norm_attachments(attachments)
    if tier == "smart":
        return _anthropic_chat(messages, system, max_tokens, model, atts)
    if tier == "openai":
        return _openai_chat(messages, system, max_tokens, model, atts)
    if tier == "claude":
        return _claude_code_chat(messages, system, max_tokens, model, atts, allow_write)
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
    if tier == "openai":
        return _openai_chat_tools(messages, tools, system, max_tokens, model)
    return _anthropic_chat_tools(messages, tools, system, max_tokens, model)


def status() -> dict:
    """Best-effort availability of each tier, for the UI to show what's live."""
    return {
        "fast": {"backend": "ollama", "model": _ollama_model(), "available": _ollama_up()},
        "smart": {
            "backend": "anthropic",
            "model": _anthropic_model(),
            "available": bool(
                _anthropic_key() or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            ),
        },
        "openai": {
            "backend": "openai",
            "model": _openai_model(),
            "available": bool(_openai_key()),
        },
        "claude": {
            "backend": "claude-code",
            "model": _claude_cli_model() or "plan default",
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
    key = _anthropic_key()
    if not (key or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RouterError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY in your environment "
            "or add a key in Settings → Connections.",
            401,
        )
    client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return anthropic, client, (model or _anthropic_model())


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


# ── Cloud: OpenAI ────────────────────────────────────────────────────────────
# Plain REST (POST {OPENAI_BASE}/chat/completions) over stdlib urllib — same
# pattern as the Ollama branch, whose wire format OpenAI's mirrors. Canonical
# (Anthropic-shaped) history translates per message; tool defs translate the
# same way as _to_ollama_tools but arguments ride as JSON strings.

def _openai_request(payload: dict) -> dict:
    key = _openai_key()
    if not key:
        raise RouterError(
            "No OpenAI API key found. Set OPENAI_API_KEY in your environment "
            "or add a key in Settings → Connections.",
            401,
        )
    req = urllib.request.Request(
        _openai_base() + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = (json.loads(e.read().decode("utf-8")).get("error") or {}).get("message", "")
        except Exception:  # noqa: BLE001
            pass
        if e.code == 401:
            raise RouterError("OpenAI rejected the API key. Check it in Settings → Connections.", 401)
        if e.code == 404 and "model" in detail.lower():
            raise RouterError(
                f"OpenAI model '{payload.get('model')}' wasn't found. Pick a model your "
                "account can use in Settings → Models (see platform.openai.com/docs/models).",
                503,
            )
        raise RouterError(f"OpenAI error: {detail or e}", 502)
    except (urllib.error.URLError, OSError) as e:
        raise RouterError(f"Couldn't reach OpenAI: {e}", 503)


def _to_openai_messages(messages, atts=None) -> list:
    """Translate canonical (Anthropic-shaped) history into OpenAI's chat format.

    Same walk as _to_ollama_messages, with OpenAI's two quirks: tool_calls carry
    an id + JSON-string arguments, and tool results are `role: "tool"` messages
    tied back by tool_call_id. Image attachments become image_url data URIs on
    the latest user turn (PDFs and other files are skipped — the app inlines
    small text files itself before calling us).
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
                    calls.append({
                        "id": b.get("id") or f"call_{len(calls)}",
                        "type": "function",
                        "function": {
                            "name": b.get("name"),
                            "arguments": json.dumps(b.get("input") or {}),
                        },
                    })
            msg = {"role": "assistant", "content": "\n".join(texts) or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:  # user turn: plain text and/or tool results
            texts = []
            for b in content or []:
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "tool_result":
                    out.append({
                        "role": "tool",
                        "tool_call_id": b.get("tool_use_id") or "",
                        "content": _result_to_str(b.get("content")),
                    })
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})

    # Vision: inline image attachments on the most recent user message.
    images = [a for a in (atts or []) if a["mime"].startswith("image/")]
    if images:
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") == "user" and isinstance(out[i].get("content"), str):
                parts = [{"type": "text", "text": out[i]["content"]}]
                for a in images:
                    b64 = _read_b64(a["path"])
                    if b64:
                        parts.append({"type": "image_url",
                                      "image_url": {"url": f"data:{a['mime']};base64,{b64}"}})
                out[i] = {"role": "user", "content": parts}
                break
    return out


def _openai_chat(messages, system, max_tokens, model, attachments=None) -> dict:
    mdl = model or _openai_model()
    msgs = _to_openai_messages(messages, attachments)
    sys_text = _flatten_system(system)
    if sys_text:
        msgs = [{"role": "system", "content": sys_text}] + msgs
    data = _openai_request({
        "model": mdl,
        "messages": msgs,
        "max_completion_tokens": max_tokens,
    })
    choice = (data.get("choices") or [{}])[0]
    reply = ((choice.get("message") or {}).get("content") or "").strip()
    return {"reply": reply or "…(the model went quiet — try again)",
            "model": data.get("model") or mdl, "tier": "openai"}


def _openai_chat_tools(messages, tools, system, max_tokens, model) -> dict:
    mdl = model or _openai_model()
    msgs = _to_openai_messages(messages)
    sys_text = _flatten_system(system)
    if sys_text:
        msgs = [{"role": "system", "content": sys_text}] + msgs
    data = _openai_request({
        "model": mdl,
        "messages": msgs,
        "tools": _to_ollama_tools(tools),  # same {type:"function",...} shape
        "max_completion_tokens": max_tokens,
    })
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
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
        tool_calls.append({
            "id": tc.get("id") or f"call_{i}",
            "name": fn.get("name"),
            "input": args if isinstance(args, dict) else {},
        })
    stop = choice.get("finish_reason") or ""
    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": "tool_use" if stop == "tool_calls" else (stop or "end_turn"),
        "model": data.get("model") or mdl,
        "tier": "openai",
    }


# ── Subscription: Claude Code CLI ────────────────────────────────────────────

def _claude_cli_path():
    """Resolve the `claude` executable on PATH, or None if it isn't installed."""
    return shutil.which(_claude_cli())


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


def _claude_code_chat(messages, system, max_tokens, model, attachments=None, allow_write=False) -> dict:
    """Run a chat turn through the Claude Code CLI (subscription-billed).

    max_tokens is accepted for signature parity but not forwarded — the CLI
    manages its own output budget. Attachments are passed by path: the CLI reads
    them with its own Read tool (handles images, PDFs, and text), which we enable
    non-interactively only when files are attached.

    allow_write ("Edit mode") additionally grants the file-editing tools (Edit,
    Write) plus navigation (Glob, Grep) and switches the CLI to acceptEdits so it
    never blocks on a permission prompt — there's no terminal to answer one. Bash
    is deliberately never allowed: this tier edits files, it does not run commands.
    File access stays confined to the vault working dir (cwd=CLAUDE_CLI_CWD).
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
    # Tool permissions, narrowest-first. Edit mode unlocks the file tools and
    # auto-accepts edits (no terminal to approve them); otherwise Read is granted
    # only to ingest attachments. Never grant Bash.
    if allow_write:
        cmd += ["--allowedTools", "Read,Edit,Write,Glob,Grep",
                "--permission-mode", "acceptEdits"]
    elif attachments:
        cmd += ["--allowedTools", "Read"]
    sys_text = _flatten_system(system)
    if sys_text:
        cmd += ["--system-prompt", sys_text]
    mdl = model or _claude_cli_model()
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
            timeout=_claude_cli_timeout(),
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


def claude_code_stream(prompt, system=None, allowed_tools=None, model=None,
                       cwd=None, timeout=None, mcp_config=None):
    """Run the Claude Code CLI in streaming mode, yielding parsed JSON events.

    This is the agentic, subscription-billed counterpart to chat_tools(): instead
    of the dashboard driving the tool loop, the CLI runs its *own* model→tools→
    repeat loop and emits newline-delimited JSON as it goes (`--output-format
    stream-json`, which requires `--verbose`). We yield each parsed event —
    system/assistant/user/result messages, mirroring the Anthropic message shape —
    so the caller can stream steps live. The trailing 'result' event carries the
    final summary text.

    allowed_tools is a list of CLI tool names to pre-approve (e.g. ["Read","Grep",
    "Write"]); when it includes a write tool the CLI is switched to acceptEdits so
    it never blocks on a permission prompt (there's no terminal to answer one).
    Callers here never grant Bash. File access stays confined to cwd. As with the
    plain claude tier, ANTHROPIC_API_KEY/AUTH_TOKEN are stripped from the child env
    so it always bills the signed-in subscription, never API credits.

    mcp_config (optional) is a path to an MCP servers JSON ({"mcpServers": {...}});
    when given, the CLI loads ONLY those servers (--strict-mcp-config ignores any
    globally-configured ones), and the matching mcp__<server>__<tool> names must be
    pre-approved via allowed_tools. The router stays generic — which servers/tools
    to attach is the caller's business (see agent._run_agent_claude).

    Raises RouterError on a startup failure, timeout, or non-zero exit.
    """
    exe = _claude_cli_path()
    if exe is None:
        raise RouterError(
            "The Claude CLI isn't installed or isn't on PATH. Install Claude Code "
            "and sign in with your subscription, then restart the dashboard.",
            503,
        )
    if not (prompt or "").strip():
        raise RouterError("Nothing to send to Claude.", 400)

    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose"]
    allowed_tools = list(allowed_tools or [])
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
        if any(t in ("Write", "Edit") for t in allowed_tools):
            cmd += ["--permission-mode", "acceptEdits"]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config, "--strict-mcp-config"]
    sys_text = _flatten_system(system)
    if sys_text:
        cmd += ["--append-system-prompt", sys_text]
    mdl = model or _claude_cli_model()
    if mdl:
        cmd += ["--model", mdl]

    env = {
        k: v for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=cwd or CLAUDE_CLI_CWD,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        raise RouterError("The Claude CLI vanished mid-call — is it still installed?", 503)

    # Send the prompt on stdin and close it so the CLI starts working.
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    # Drain stderr in the background so a chatty CLI can't deadlock on a full pipe.
    stderr_chunks: list = []

    def _drain_stderr():
        try:
            for line in proc.stderr:
                stderr_chunks.append(line)
        except (ValueError, OSError):
            pass

    err_thread = threading.Thread(target=_drain_stderr, daemon=True)
    err_thread.start()

    # Watchdog: kill the run if it blows the timeout. Popen streaming has no
    # built-in timeout the way subprocess.run does.
    timed_out = {"v": False}

    def _kill():
        timed_out["v"] = True
        try:
            proc.kill()
        except OSError:
            pass

    timer = threading.Timer(timeout or _claude_cli_timeout(), _kill)
    timer.start()

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # ignore any non-JSON noise on the stream
    finally:
        timer.cancel()
        proc.wait()
        err_thread.join(timeout=1)

    if timed_out["v"]:
        raise RouterError(
            "The Claude CLI took too long to answer. Try again, or switch tiers.", 504
        )
    if proc.returncode:
        detail = "".join(stderr_chunks).strip()
        raise RouterError(f"The Claude CLI failed: {detail or 'unknown error'}", 502)


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
        with urllib.request.urlopen(_ollama_host() + "/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def list_ollama_models() -> list:
    """Names of locally-pulled Ollama models ([] if Ollama is unreachable)."""
    try:
        with urllib.request.urlopen(_ollama_host() + "/api/tags", timeout=3) as r:
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
    mdl = model or _ollama_model()
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
        _ollama_host() + "/api/chat",
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
            f"Local model (Ollama) isn't reachable on {_ollama_host()}. Install it from "
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
    mdl = model or _ollama_model()
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
        _ollama_host() + "/api/chat",
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
            f"Local model (Ollama) isn't reachable on {_ollama_host()}. Install it from "
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
