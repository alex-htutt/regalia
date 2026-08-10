"""Model router — one chat() over eight backends.

This is the core primitive of the self-hosted workspace: every model call in the
app goes through chat(), which picks a backend by tier.

    tier="fast"   -> Ollama, local HTTP on :11434  (no API cost, needs Ollama)
    tier="smart"  -> Anthropic, cloud              (needs an Anthropic API key)
    tier="openai" -> OpenAI, cloud                 (needs an OpenAI API key)
    tier="gemini" -> Google Gemini, cloud          (needs a Gemini API key)
    tier="vertex" -> Vertex AI, cloud              (bills a Google Cloud project
                                                    via Application Default
                                                    Credentials; no API key)
    tier="chatgpt"-> Codex CLI, subprocess         (uses your ChatGPT/Codex login)
    tier="google" -> Gemini CLI, subprocess        (uses your signed-in Google
                                                    account instead of an API key)
    tier="claude" -> Claude Code CLI, subprocess   (bills your Claude subscription,
                                                    not API credits; needs `claude`
                                                    installed and signed in)

Google gets a three-door treatment: `gemini` bills a Gemini API key, `vertex`
bills a GCP project through ADC, and `google` shells out to the Gemini CLI and
rides your personal Google sign-in. All three speak the same generateContent
wire format, so `vertex` reuses the Gemini payload/parsing helpers and differs
only in how the request is addressed and authorized.

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
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

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
    """Smart tier model id."""
    return _config.value("anthropic_model", "ANTHROPIC_MODEL", "claude-opus-4-8")


def _openai_base() -> str:
    """OpenAI runtime (ChatGPT models) — plain REST over stdlib urllib; no SDK dep."""
    return _config.value("openai_base", "OPENAI_BASE", "https://api.openai.com/v1").rstrip("/")


def _openai_model() -> str:
    # Default = the current balanced/cost tier (verify at
    # platform.openai.com/docs/models if it 404s; override via env or Settings).
    return _config.value("openai_model", "OPENAI_MODEL", "gpt-5.6-terra")


def _gemini_base() -> str:
    """Google Gemini runtime — plain REST over stdlib urllib; no SDK dep."""
    return _config.value(
        "gemini_base", "GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")


def _gemini_model() -> str:
    # A long-lived GA id is the safe default: model availability differs per key
    # and per project, so the picker below lists what the key can actually reach
    # (ListModels) and Settings → Models overrides this outright.
    return _config.value("gemini_model", "GEMINI_MODEL", "gemini-2.5-flash")


def _vertex_project() -> str:
    """GCP project billed by the vertex tier. Empty = fall back to whatever
    project Application Default Credentials resolve to (see _vertex_token)."""
    return _config.value("vertex_project", "GOOGLE_CLOUD_PROJECT", "")


def _vertex_location() -> str:
    """Vertex region, or "global" for the multi-region endpoint. "global" keeps
    availability widest; a specific region is what data-residency rules want."""
    return _config.value("vertex_location", "GOOGLE_CLOUD_LOCATION", "global")


def _vertex_model() -> str:
    """Vertex publisher model id. Availability is per project and per location,
    so Settings → Models overrides this outright."""
    return _config.value("vertex_model", "VERTEX_MODEL", "gemini-2.5-flash")


def _gemini_cli() -> str:
    """Google account runtime via Gemini CLI."""
    return _config.value("gemini_cli", "GEMINI_CLI", "gemini")


def _gemini_cli_model() -> str:
    """Empty string lets the CLI choose the signed-in account default."""
    return _config.value("gemini_cli_model", "GEMINI_CLI_MODEL", "")


def _gemini_cli_timeout() -> int:
    try:
        return int(_config.value("gemini_cli_timeout", "GEMINI_CLI_TIMEOUT", "180"))
    except ValueError:
        return 180


def _codex_cli() -> str:
    """ChatGPT account runtime via Codex CLI."""
    return _config.value("codex_cli", "CODEX_CLI", "codex")


def _codex_cli_model() -> str:
    """Empty string lets Codex choose the signed-in account default."""
    return _config.value("codex_cli_model", "CODEX_CLI_MODEL", "")


# Current GPT-5.6 family roles from the official model guide. Availability can
# vary by ChatGPT plan/rollout, so the account default remains the safe first
# choice and Codex surfaces a clear error if a selected model is unavailable.
CHATGPT_ACCOUNT_MODELS = (
    "gpt-5.6-sol",    # frontier capability / hardest work
    "gpt-5.6-terra",  # balanced quality and speed
    "gpt-5.6-luna",   # efficient, high-volume work
)


def chatgpt_model_choices() -> list[str]:
    """Suggested Codex/ChatGPT-account models, including a configured override."""
    configured = _codex_cli_model()
    return list(dict.fromkeys(([configured] if configured else []) + list(CHATGPT_ACCOUNT_MODELS)))


def _codex_cli_timeout() -> int:
    try:
        return int(_config.value("codex_cli_timeout", "CODEX_CLI_TIMEOUT", "180"))
    except ValueError:
        return 180


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
# ChatGPT account runtime via Codex CLI. The CLI reuses the user's saved
# Codex/ChatGPT login by default; CODEX_CLI_MODEL="" lets Codex choose.

# Subscription runtime. The `claude` tier shells out to the Claude Code CLI, which
# bills your logged-in Claude subscription (Pro/Max) instead of API credits — the
# same auth you use in Claude Code. CLAUDE_CLI_MODEL="" lets the CLI pick the
# plan's default model.

# The working directory is the CLI's primary workspace and write boundary; a
# read-only sandbox is not a general filesystem-read isolation guarantee. Run
# from the vault root so relative paths target the vault, not just dashboard/.
# Root resolution matches app.py (REGALIA_VAULT env → Settings vault_path → repo
# root). CLI cwd overrides stay env-only so the web UI cannot redirect agents.
_vault_override = os.path.expanduser(
    os.environ.get("REGALIA_VAULT") or _config.get("vault_path") or ""
)
if _vault_override and os.path.isdir(_vault_override):
    VAULT_ROOT = os.path.abspath(_vault_override)
elif _paths.is_frozen():
    VAULT_ROOT = str(_paths.default_vault())
else:
    VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEX_CLI_CWD = os.environ.get("CODEX_CLI_CWD", VAULT_ROOT)
CLAUDE_CLI_CWD = os.environ.get("CLAUDE_CLI_CWD", VAULT_ROOT)
GEMINI_CLI_CWD = os.environ.get("GEMINI_CLI_CWD", VAULT_ROOT)

TIERS = ("fast", "smart", "openai", "gemini", "vertex", "chatgpt", "google", "claude")

# ``status()`` stays cheap: it reports executable presence plus the most recent
# explicit login check. The browser performs that check automatically when the
# ChatGPT tier becomes relevant. The cache is keyed by the resolved executable
# so changing the CLI setting cannot attach stale auth state to another binary.
_CODEX_HEALTH = {
    "exe": None,
    "ok": None,
    "state": "unchecked",
    "reason": "",
    "checked_at": None,
}

# Same contract for the Gemini CLI (`google` tier). Unlike Codex, that CLI has no
# `login status` command, so the check reads its own on-disk auth state — see
# gemini_cli_health() for exactly what is (and isn't) proven by it.
_GEMINI_HEALTH = {
    "exe": None,
    "ok": None,
    "state": "unchecked",
    "reason": "",
    "checked_at": None,
}


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


def _gemini_key() -> str:
    """GEMINI_API_KEY is the name Google's own tooling uses; GOOGLE_API_KEY is
    accepted as the older alias so an existing shell doesn't need re-exporting."""
    return _config.secret("gemini_api_key", "GEMINI_API_KEY") or os.environ.get(
        "GOOGLE_API_KEY", ""
    )


def chat(messages, tier="fast", system=None, max_tokens=2048, model=None, attachments=None,
         allow_write=False) -> dict:
    """Run a chat completion on the chosen tier.

    messages:    [{"role": "user"|"assistant", "content": str}, ...]
    system:      None, a string, or a list of Anthropic system blocks.
    attachments: None or [{"path", "name", "mime"}, ...] for the current turn;
                 applied to the most recent user message per the active tier.
    allow_write: "Edit mode." The ChatGPT-account and Claude CLI tiers honor it
                 here by switching their sandbox/tool policy. The fast/smart/API
                 tiers write via agent.chat_vault's tool loop, not this path.
    """
    tier = (tier or "fast").lower()
    if tier not in TIERS:
        tier = "fast"
    atts = _norm_attachments(attachments)
    if tier == "smart":
        return _anthropic_chat(messages, system, max_tokens, model, atts)
    if tier == "openai":
        return _openai_chat(messages, system, max_tokens, model, atts)
    if tier == "gemini":
        return _gemini_chat(messages, system, max_tokens, model, atts)
    if tier == "vertex":
        return _gemini_chat(messages, system, max_tokens, model, atts,
                            send=_vertex_request, tier="vertex")
    if tier == "chatgpt":
        return _codex_exec_chat(messages, system, max_tokens, model, atts, allow_write)
    if tier == "google":
        return _gemini_cli_chat(messages, system, max_tokens, model, atts, allow_write)
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
    if tier == "gemini":
        return _gemini_chat_tools(messages, tools, system, max_tokens, model)
    if tier == "vertex":
        return _gemini_chat_tools(messages, tools, system, max_tokens, model,
                                  send=_vertex_request, tier="vertex")
    if tier == "chatgpt":
        raise RouterError(
            "The ChatGPT account tier runs through Codex CLI and cannot use this "
            "app's in-process tool loop. Use Chat for ChatGPT account runs, or "
            "pick Fast, Smart, OpenAI API, or Gemini API for custom tools.",
            400,
        )
    if tier == "google":
        raise RouterError(
            "The Google account tier runs through Gemini CLI and cannot use this "
            "app's in-process tool loop. Use Chat for Google account runs, or pick "
            "Gemini API (an API key) for custom tools.",
            400,
        )
    return _anthropic_chat_tools(messages, tools, system, max_tokens, model)


def status_for(tier: str) -> dict:
    """Best-effort status for one tier without probing unrelated backends."""
    if tier == "fast":
        return {"backend": "ollama", "model": _ollama_model(), "available": _ollama_up()}
    if tier == "smart":
        return {
            "backend": "anthropic",
            "model": _anthropic_model(),
            "available": bool(_anthropic_key() or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
        }
    if tier == "openai":
        return {
            "backend": "openai",
            "model": _openai_model(),
            "available": bool(_openai_key()),
        }
    if tier == "gemini":
        return {
            "backend": "gemini",
            "model": _gemini_model(),
            "available": bool(_gemini_key()),
        }
    if tier == "vertex":
        ready, reason = _vertex_health()
        return {
            "backend": "vertex-ai",
            "model": _vertex_model(),
            "project": _vertex_project() or _VERTEX_STATE.get("project") or "",
            "location": _vertex_location(),
            "auth_reason": "" if ready else reason,
            # Credentials resolving is not proof the project can serve the
            # model; a wrong project/location surfaces on the first request.
            "available": ready,
        }
    if tier == "google":
        exe = _gemini_cli_path()
        checked = _GEMINI_HEALTH["exe"] == exe
        auth = _GEMINI_HEALTH.get("ok") if checked else None
        auth_state = _GEMINI_HEALTH.get("state", "unchecked") if checked else "unchecked"
        return {
            "backend": "gemini-cli",
            "model": _gemini_cli_model() or "Google account default",
            "installed": exe is not None,
            "authenticated": auth,
            "auth_state": auth_state,
            "auth_reason": _GEMINI_HEALTH.get("reason", "") if checked else "",
            "auth_checked_at": _GEMINI_HEALTH.get("checked_at") if checked else None,
            # As with Codex: an installed CLI that is logged out, or logged in
            # with an API key rather than a Google account, is not ready.
            "available": exe is not None and auth is True,
        }
    if tier == "chatgpt":
        exe = _codex_cli_path()
        checked = _CODEX_HEALTH["exe"] == exe
        auth = _CODEX_HEALTH.get("ok") if checked else None
        auth_state = _CODEX_HEALTH.get("state", "unchecked") if checked else "unchecked"
        return {
            "backend": "codex-cli",
            "model": _codex_cli_model() or "ChatGPT account default",
            "installed": exe is not None,
            "authenticated": auth,
            "auth_state": auth_state,
            "auth_reason": _CODEX_HEALTH.get("reason", "") if checked else "",
            "auth_checked_at": _CODEX_HEALTH.get("checked_at") if checked else None,
            # Executable presence alone is not readiness: an installed CLI may
            # be logged out or authenticated with the wrong account method.
            "available": exe is not None and auth is True,
        }
    if tier == "claude":
        return {
            "backend": "claude-code",
            "model": _claude_cli_model() or "plan default",
            "available": _claude_cli_path() is not None,
        }
    raise ValueError(f"Unknown tier {tier!r}")


def status() -> dict:
    """Best-effort availability of every tier, for the UI status display."""
    return {tier: status_for(tier) for tier in TIERS}


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


# ── Cloud: Google Gemini ─────────────────────────────────────────────────────
# The Gemini REST API is close enough to the others to share this file's shape,
# but its wire format differs in three ways worth naming up front:
#   * roles are "user"/"model" (not "assistant"), and the system prompt is its
#     own top-level `systemInstruction` rather than a message;
#   * tool calls/results are *parts* inside normal contents (functionCall /
#     functionResponse), keyed by function **name** — there are no call ids, so
#     tool_use ids from our canonical history are resolved back to names here;
#   * declaration schemas are an OpenAPI subset with an upper-case type enum, so
#     tool schemas are sanitized before they go out (_to_gemini_tools).


def _gemini_request(model: str, payload: dict, path: str = "generateContent") -> dict:
    key = _gemini_key()
    if not key:
        raise RouterError(
            "No Gemini API key found. Set GEMINI_API_KEY in your environment or add "
            "a key in Settings → Connections (get one at aistudio.google.com/apikey).",
            401,
        )
    # The key rides a header, never the query string: URLs land in proxy and
    # server logs in a way headers do not.
    req = urllib.request.Request(
        f"{_gemini_base()}/models/{model}:{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
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
        if e.code in (401, 403):
            raise RouterError(
                "Google rejected the Gemini API key. Check it in Settings → Connections.",
                401,
            )
        if e.code == 404:
            raise RouterError(
                f"Gemini model '{model}' wasn't found for this key. Pick one your key "
                "can use in Settings → Models (see ai.google.dev/gemini-api/docs/models).",
                503,
            )
        if e.code == 429:
            raise RouterError(
                "Gemini rate limit or quota reached. Wait a moment, or check your quota "
                "at aistudio.google.com.",
                429,
            )
        raise RouterError(f"Gemini error: {detail or e}", 502)
    except (urllib.error.URLError, OSError) as e:
        raise RouterError(f"Couldn't reach Gemini: {e}", 503)


# ── Cloud: Vertex AI (Google Cloud project billing via ADC) ──────────────────
# Same generateContent wire format as the Gemini API tier, so everything below
# is about addressing and authorization only. Auth is Application Default
# Credentials — `gcloud auth application-default login`, a service-account key
# via GOOGLE_APPLICATION_CREDENTIALS, or an attached GCE/Cloud Run identity.
#
# Deliberately NOT the same door as the `google` tier: that one shells out to
# the Gemini CLI with ADC stripped from its environment on purpose (see
# _GEMINI_ENV_KEYS) so account billing cannot silently become project billing.
# This tier is the sanctioned way to bill a GCP project, and the two coexist.

_VERTEX_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Cached ADC credentials + the project they resolved to. google.auth.default()
# touches disk and (on GCE) the metadata server, so it runs once per process and
# the credentials object refreshes its own token in place.
_VERTEX_STATE: dict = {"creds": None, "project": "", "error": ""}
_VERTEX_LOCK = threading.Lock()


def _vertex_credentials():
    """Resolve (and cache) ADC, or raise a RouterError the UI can show."""
    with _VERTEX_LOCK:
        if _VERTEX_STATE["creds"] is not None:
            return _VERTEX_STATE["creds"]
        try:
            import google.auth
        except ImportError:
            raise RouterError(
                "The `google-auth` package isn't installed. Run "
                "`pip install -r requirements.txt` and restart.",
                503,
            )
        try:
            creds, project = google.auth.default(scopes=[_VERTEX_SCOPE])
        except Exception as e:  # google.auth.exceptions.DefaultCredentialsError & friends
            _VERTEX_STATE["error"] = str(e)
            raise RouterError(
                "No Google Cloud credentials found. Run "
                "`gcloud auth application-default login`, then set the project in "
                "Settings → Connections (or GOOGLE_CLOUD_PROJECT).",
                401,
            )
        _VERTEX_STATE.update(creds=creds, project=project or "", error="")
        return creds


def _vertex_token() -> str:
    """A valid OAuth access token for Vertex, refreshing when it has expired."""
    creds = _vertex_credentials()
    if not creds.valid:
        import google.auth.transport.requests

        with _VERTEX_LOCK:
            if not creds.valid:  # another thread may have refreshed it already
                try:
                    creds.refresh(google.auth.transport.requests.Request())
                except Exception as e:  # noqa: BLE001 — surfaced verbatim to the UI
                    raise RouterError(
                        "Google Cloud credentials could not be refreshed "
                        f"({e}). Run `gcloud auth application-default login` again.",
                        401,
                    )
    return creds.token


def _vertex_endpoint(model: str, path: str) -> str:
    """Publisher-model URL. The multi-region endpoint drops the region prefix."""
    project = _vertex_project() or _VERTEX_STATE.get("project") or ""
    if not project:
        raise RouterError(
            "No Google Cloud project set for the Vertex tier. Add one in "
            "Settings → Connections, or set GOOGLE_CLOUD_PROJECT.",
            400,
        )
    loc = _vertex_location() or "global"
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    return (
        f"https://{host}/v1/projects/{project}/locations/{loc}"
        f"/publishers/google/models/{model}:{path}"
    )


def _vertex_request(model: str, payload: dict, path: str = "generateContent") -> dict:
    token = _vertex_token()  # resolves the project too, so call it before the URL
    req = urllib.request.Request(
        _vertex_endpoint(model, path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
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
        project = _vertex_project() or _VERTEX_STATE.get("project") or "?"
        if e.code in (401, 403):
            raise RouterError(
                f"Google Cloud rejected the request for project '{project}'. Check that "
                "the Vertex AI API is enabled and your account has the Vertex AI User "
                f"role. ({detail or e})",
                401,
            )
        if e.code == 404:
            raise RouterError(
                f"Vertex model '{model}' wasn't found in {project}/"
                f"{_vertex_location()}. Pick a model available in that location "
                "(Settings → Models), or switch location.",
                503,
            )
        if e.code == 429:
            raise RouterError(
                f"Vertex AI quota reached for project '{project}'. Wait a moment, or "
                "request more quota in the Google Cloud console.",
                429,
            )
        raise RouterError(f"Vertex AI error: {detail or e}", 502)
    except (urllib.error.URLError, OSError) as e:
        raise RouterError(f"Couldn't reach Vertex AI: {e}", 503)


def _vertex_health() -> tuple[bool, str]:
    """Cheap readiness for status(): can we resolve credentials and a project?

    Does not call the API — a wrong model or a missing role only shows up on a
    real request, exactly like the Gemini key tier's `available` flag.
    """
    try:
        _vertex_credentials()
    except RouterError as e:
        return False, str(e)
    if not (_vertex_project() or _VERTEX_STATE.get("project")):
        return False, "No Google Cloud project set (Settings → Connections)."
    return True, ""


def _gemini_tool_names(messages) -> dict:
    """Map tool_use id → function name, so tool_results can name their call."""
    names = {}
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                names[b.get("id")] = b.get("name")
    return names


def _to_gemini_contents(messages, atts=None) -> list:
    """Translate canonical (Anthropic-shaped) history into Gemini `contents`.

    Assistant turns become role "model"; tool results go back as functionResponse
    parts on a "user" turn, which is the shape the API documents. Image
    attachments are inlined as inlineData on the latest user turn (other file
    types are skipped — the app inlines small text files itself before calling).
    """
    names = _gemini_tool_names(messages)
    out = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        gem_role = "model" if role == "assistant" else "user"
        if isinstance(content, str):
            if content:
                out.append({"role": gem_role, "parts": [{"text": content}]})
            continue
        parts = []
        for b in content or []:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")
            if btype == "text" and b.get("text"):
                parts.append({"text": b["text"]})
            elif btype == "tool_use":
                parts.append({"functionCall": {"name": b.get("name"),
                                               "args": b.get("input") or {}}})
            elif btype == "tool_result":
                parts.append({"functionResponse": {
                    "name": names.get(b.get("tool_use_id")) or "tool",
                    # A functionResponse payload must be an object, so plain
                    # string results are wrapped rather than sent bare.
                    "response": {"result": _result_to_str(b.get("content"))},
                }})
        if parts:
            out.append({"role": gem_role, "parts": parts})

    images = [a for a in (atts or []) if a["mime"].startswith("image/")]
    if images:
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") == "user":
                for a in images:
                    b64 = _read_b64(a["path"])
                    if b64:
                        out[i]["parts"].append(
                            {"inlineData": {"mimeType": a["mime"], "data": b64}}
                        )
                break
    return out


# Fields Gemini's OpenAPI-subset schema validator accepts. Anything else in a
# tool's input_schema (``$schema``, ``additionalProperties``, ``default``, …) is
# dropped rather than passed through — the API rejects the whole request on an
# unknown field, which would break every tool at once.
_GEMINI_SCHEMA_KEYS = frozenset({
    "type", "format", "description", "nullable", "enum", "items", "properties",
    "required",
})


def _to_gemini_schema(schema):
    """Reduce a JSON Schema to Gemini's accepted subset (types upper-cased)."""
    if not isinstance(schema, dict):
        return {}
    out = {}
    for key, val in schema.items():
        if key not in _GEMINI_SCHEMA_KEYS:
            continue
        if key == "type" and isinstance(val, str):
            out[key] = val.upper()
        elif key == "items":
            out[key] = _to_gemini_schema(val)
        elif key == "properties" and isinstance(val, dict):
            out[key] = {k: _to_gemini_schema(v) for k, v in val.items()}
        else:
            out[key] = val
    return out


def _to_gemini_tools(tools) -> list:
    """Anthropic-style tool defs → one Gemini tool with functionDeclarations."""
    decls = []
    for t in tools:
        decl = {"name": t["name"], "description": t.get("description", "")}
        schema = _to_gemini_schema(t.get("input_schema") or {})
        # A parameterless tool must omit `parameters` entirely; an empty
        # properties object is rejected.
        if schema.get("properties"):
            decl["parameters"] = schema
        decls.append(decl)
    return [{"functionDeclarations": decls}] if decls else []


def _gemini_parts(data: dict) -> list:
    """The parts of the first candidate, or [] if the model returned nothing."""
    candidate = (data.get("candidates") or [{}])[0]
    return (candidate.get("content") or {}).get("parts") or []


def _gemini_blocked_reason(data: dict) -> str:
    """A user-facing explanation when a response carries no usable content."""
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        return f"Gemini blocked the prompt ({feedback['blockReason']})."
    finish = ((data.get("candidates") or [{}])[0]).get("finishReason") or ""
    if finish == "MAX_TOKENS":
        return "Gemini hit the output limit before writing an answer."
    if finish and finish not in ("STOP", "FINISH_REASON_UNSPECIFIED"):
        return f"Gemini stopped early ({finish})."
    return ""


def _gemini_payload(messages, system, max_tokens, atts=None) -> dict:
    payload = {
        "contents": _to_gemini_contents(messages, atts),
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    sys_text = _flatten_system(system)
    if sys_text:
        payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
    return payload


def _gemini_default_model(tier: str) -> str:
    """The configured model for whichever generateContent tier is calling."""
    return _vertex_model() if tier == "vertex" else _gemini_model()


def _gemini_chat(messages, system, max_tokens, model, attachments=None,
                 send=None, tier="gemini") -> dict:
    """Chat over the generateContent wire format.

    `send(model, payload)` selects the door: _gemini_request bills a Gemini API
    key, _vertex_request bills a Google Cloud project through ADC. The payload
    and response shapes are identical, so only the caller differs.
    """
    send = send or _gemini_request
    mdl = model or _gemini_default_model(tier)
    data = send(mdl, _gemini_payload(messages, system, max_tokens, attachments))
    reply = "\n".join(p["text"] for p in _gemini_parts(data) if p.get("text")).strip()
    if not reply:
        reply = _gemini_blocked_reason(data) or "…(the model went quiet — try again)"
    return {"reply": reply, "model": data.get("modelVersion") or mdl, "tier": tier}


def _gemini_chat_tools(messages, tools, system, max_tokens, model,
                       send=None, tier="gemini") -> dict:
    send = send or _gemini_request
    mdl = model or _gemini_default_model(tier)
    payload = _gemini_payload(messages, system, max_tokens)
    gem_tools = _to_gemini_tools(tools)
    if gem_tools:
        payload["tools"] = gem_tools
    data = send(mdl, payload)
    texts, tool_calls = [], []
    for i, part in enumerate(_gemini_parts(data)):
        if part.get("text"):
            texts.append(part["text"])
        call = part.get("functionCall")
        if isinstance(call, dict) and call.get("name"):
            # Gemini has no call ids; the loop only needs them to pair results
            # back up, so synthesize a stable one per call.
            tool_calls.append({
                "id": f"gemini_{i}_{call['name']}",
                "name": call["name"],
                "input": call.get("args") if isinstance(call.get("args"), dict) else {},
            })
    finish = ((data.get("candidates") or [{}])[0]).get("finishReason") or ""
    return {
        "text": "\n".join(texts).strip(),
        "tool_calls": tool_calls,
        "stop_reason": "tool_use" if tool_calls else (finish.lower() or "end_turn"),
        "model": data.get("modelVersion") or mdl,
        "tier": tier,
    }


# Model lists are per-key (and change faster than any hard-coded list here), so
# the picker asks the API. Cached briefly: the catalog is rebuilt on every Agents
# render and this is a network round trip, unlike the local Ollama probe.
_GEMINI_MODELS_CACHE: dict = {"key": None, "models": [], "at": 0.0}
_GEMINI_MODELS_TTL = 300.0


def list_gemini_models() -> list:
    """Gemini models this key can call generateContent on. [] if unavailable."""
    key = _gemini_key()
    if not key:
        return []
    now = time.time()
    if (_GEMINI_MODELS_CACHE["key"] == key
            and now - _GEMINI_MODELS_CACHE["at"] < _GEMINI_MODELS_TTL):
        return list(_GEMINI_MODELS_CACHE["models"])
    req = urllib.request.Request(
        f"{_gemini_base()}/models?pageSize=200", headers={"x-goog-api-key": key}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return []  # the picker falls back to the configured model
    models = []
    for m in data.get("models") or []:
        methods = m.get("supportedGenerationMethods") or []
        name = str(m.get("name") or "")
        if name.startswith("models/") and "generateContent" in methods:
            models.append(name[len("models/"):])
    models.sort()
    _GEMINI_MODELS_CACHE.update(key=key, models=models, at=now)
    return models


def gemini_model_choices() -> list[str]:
    """Models for the picker: whatever the key exposes, else the configured one."""
    configured = _gemini_model()
    live = list_gemini_models()
    return list(dict.fromkeys(([configured] if configured else []) + live))


# ── Account: ChatGPT via Codex CLI ───────────────────────────────────────────

def _codex_cli_path():
    """Resolve the `codex` executable on PATH, or None if it isn't installed."""
    return shutil.which(_codex_cli())


_CODEX_ENV_KEYS = frozenset({
    # Executable/runtime discovery and per-user Codex auth storage.
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE",
    "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
    "XDG_DATA_HOME", "USER", "USERNAME", "LOGNAME", "SHELL",
    # Temporary files, locale, and corporate proxies/CAs. ChatGPT authentication
    # itself comes from the Codex auth store under the user's profile/CODEX_HOME.
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "HTTP_PROXY", "HTTPS_PROXY",
    "ALL_PROXY", "NO_PROXY", "CODEX_HOME",
    "CODEX_CA_CERTIFICATE", "SSL_CERT_FILE", "SSL_CERT_DIR",
})


def _codex_env() -> dict:
    """Minimal child environment: enough for Codex/auth, no unrelated secrets.

    Edit-mode Codex can run shell commands inside its sandbox. Passing the full
    dashboard environment would therefore expose unrelated cloud/database keys
    to model-visible commands. Keys are compared case-insensitively for Windows.
    """
    return {k: v for k, v in os.environ.items() if k.upper() in _CODEX_ENV_KEYS}


def codex_cli_health() -> tuple[bool, str]:
    """Check that Codex is installed and using ChatGPT-backed authentication."""
    exe = _codex_cli_path()

    def finish(ok: bool, reason: str, state: str) -> tuple[bool, str]:
        _CODEX_HEALTH.update(
            exe=exe, ok=ok, state=state, reason=reason, checked_at=time.time()
        )
        return ok, reason

    if exe is None:
        return finish(False, "Codex CLI was not found on PATH.", "not_installed")
    if not os.path.isdir(CODEX_CLI_CWD):
        return finish(
            False,
            f"Codex working folder does not exist: {CODEX_CLI_CWD}",
            "check_failed",
        )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            [exe, "login", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            env=_codex_env(),
            cwd=CODEX_CLI_CWD,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        return finish(False, "Codex CLI vanished mid-check.", "not_installed")
    except PermissionError as e:
        return finish(False, f"Couldn't start Codex CLI: {e}", "check_failed")
    except subprocess.TimeoutExpired:
        return finish(False, "Codex CLI login check timed out.", "timed_out")
    except OSError as e:
        return finish(False, f"Couldn't check Codex CLI: {e}", "check_failed")

    # Some CLI versions write status to stderr even on success. Inspect both so
    # a warning cannot hide the actual authentication method.
    detail = "\n".join(
        part.strip() for part in (proc.stdout, proc.stderr) if (part or "").strip()
    )
    low = detail.lower()
    if "not logged in" in low or "not signed in" in low:
        return finish(
            False,
            "Codex CLI is installed, but not signed in. Run `codex login` and choose ChatGPT.",
            "signed_out",
        )
    if "api key" in low or "api-key" in low or "access token" in low:
        return finish(
            False,
            "Codex CLI is signed in with an API key or access token, not ChatGPT. "
            "Run `codex logout`, then `codex login` and choose ChatGPT sign-in.",
            "wrong_method",
        )
    if proc.returncode == 0 and "chatgpt" in low:
        return finish(True, "Codex CLI is signed in with ChatGPT.", "chatgpt")
    if proc.returncode != 0 and ("login" in low or "logged" in low or "auth" in low):
        return finish(
            False,
            "Codex CLI is installed, but not signed in. Run `codex login` and choose ChatGPT.",
            "signed_out",
        )
    if proc.returncode == 0:
        return finish(
            False,
            "Codex CLI responded, but Regalia could not confirm a ChatGPT account login. "
            "Use Recheck after signing in with `codex login`.",
            "unknown",
        )
    return finish(False, detail or "Codex CLI login check failed.", "check_failed")


def _stage_cli_attachments(attachments, directory: str) -> list[dict]:
    """Copy uploads into a dedicated temp workspace visible to the CLI.

    Frozen Regalia stores uploads outside the vault. Disposable staged copies
    avoid granting write access to the source, and are removed after one turn.
    """
    staged = []
    for index, attachment in enumerate(attachments or []):
        source = str(attachment.get("path") or "")
        if not os.path.isfile(source):
            raise RouterError(f"Attached file is no longer available: {attachment.get('name') or source}", 400)
        name = os.path.basename(str(attachment.get("name") or source)) or f"attachment-{index}"
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        target = os.path.join(directory, f"{index}_{safe}")
        try:
            shutil.copy2(source, target)
        except OSError as e:
            raise RouterError(f"Couldn't prepare attachment {name}: {e}", 500)
        staged.append({**attachment, "path": target, "name": name})
    return staged


def _codex_prompt(messages, system, attachments=None, allow_write=False) -> str:
    """Build one stdin prompt for `codex exec -`.

    Codex exec already persists/reuses its ChatGPT login; the app persists chat
    history separately, so each subprocess receives the relevant transcript.
    State Regalia's edit policy explicitly as well as enforcing it with the CLI
    sandbox: otherwise the model can describe itself as read-only even when the
    workspace-write sandbox was selected.
    """
    sys_text = _flatten_system(system)
    convo = _flatten_conversation(messages)
    if not sys_text and not convo.strip() and not attachments:
        return ""

    parts = []
    if sys_text:
        parts.append("System instructions:\n" + sys_text)
    if allow_write:
        parts.append(
            "Regalia Edit mode is ON. You may create, modify, rename, or delete "
            "files inside the current working root when the user requests it. "
            "Carry out requested edits with your tools instead of only describing "
            "them."
        )
    else:
        parts.append(
            "Regalia Edit mode is OFF. Treat the workspace as read-only: do not "
            "create, modify, rename, or delete files."
        )
    if convo.strip():
        parts.append("Conversation:\n" + convo)
    if attachments:
        listing = "\n".join(f"- {a['path']}" for a in attachments)
        parts.append(
            "The user attached these file(s). If the sandbox permits it, read "
            "them before answering:\n" + listing
        )
    return "\n\n".join(parts).strip()


def _codex_exec_chat(messages, system, max_tokens, model, attachments=None,
                     allow_write=False) -> dict:
    """Run a chat turn through Codex CLI using the signed-in ChatGPT account.

    max_tokens is accepted for signature parity but not forwarded; Codex manages
    its own output budget. Normal chat runs read-only. Edit mode switches Codex
    to workspace-write so it can change vault files when the user asks.
    """
    exe = _codex_cli_path()
    if exe is None:
        raise RouterError(
            "The Codex CLI isn't installed or isn't on PATH. Install Codex, run "
            "`codex login` with your ChatGPT account, then restart the dashboard.",
            503,
        )
    if not os.path.isdir(CODEX_CLI_CWD):
        raise RouterError(f"Codex working folder does not exist: {CODEX_CLI_CWD}", 503)

    # Frozen builds keep uploads outside the vault. Stage copies in a fresh temp
    # workspace and grant only that directory to this one Codex invocation.
    staged_dir = tempfile.TemporaryDirectory(prefix="regalia-codex-") if attachments else None
    try:
        staged = _stage_cli_attachments(attachments, staged_dir.name) if staged_dir else []
        prompt = _codex_prompt(messages, system, staged, allow_write=allow_write)
        if not prompt:
            raise RouterError("Nothing to send to ChatGPT.", 400)

        sandbox = "workspace-write" if allow_write else "read-only"
        cmd = [
            exe, "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox", sandbox,
            "-C", CODEX_CLI_CWD,
            "-c", 'forced_login_method="chatgpt"',
        ]
        if staged_dir:
            cmd += ["--add-dir", staged_dir.name]
        mdl = model or _codex_cli_model()
        if mdl:
            cmd += ["-m", mdl]
        cmd.append("-")  # stdin avoids command-line length limits.

        # Headless `codex exec` hardcodes approval policy to Never. Passing the
        # interactive CLI's --ask-for-approval flag here is a parser error.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_codex_cli_timeout(),
                env=_codex_env(),
                cwd=CODEX_CLI_CWD,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            raise RouterError("The Codex CLI vanished mid-call — is it still installed?", 503)
        except PermissionError as e:
            raise RouterError(f"Couldn't start the Codex CLI: {e}", 503)
        except subprocess.TimeoutExpired:
            raise RouterError(
                "The ChatGPT account run took too long to answer. Try again, or switch tiers.",
                504,
            )
        except OSError as e:
            raise RouterError(f"Couldn't run the Codex CLI: {e}", 503)

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:4000]
            hint = ""
            if ("login" in detail.lower() or "logged" in detail.lower()
                    or "auth" in detail.lower()):
                hint = " Run `codex login` and choose ChatGPT sign-in."
                _CODEX_HEALTH.update(
                    exe=exe, ok=False, state="signed_out",
                    reason=detail or hint.strip(), checked_at=time.time(),
                )
            raise RouterError(f"The Codex CLI failed: {detail or 'unknown error'}{hint}", 502)

        _CODEX_HEALTH.update(
            exe=exe, ok=True, state="chatgpt",
            reason="Codex CLI is signed in with ChatGPT.", checked_at=time.time(),
        )
        reply = (proc.stdout or "").strip()
        return {
            "reply": reply or "…(the model went quiet — try again)",
            "model": mdl or "ChatGPT account",
            "tier": "chatgpt",
        }
    finally:
        if staged_dir:
            staged_dir.cleanup()


def codex_agent_stream(prompt, system=None, model=None, cwd=None, allow_write=False,
                       timeout=None, cancel_event=None, extra_dirs=None):
    """Run a scoped Codex account agent and yield its JSONL execution events.

    Unlike chat_tools(), Codex drives its own file/shell loop. It runs in an
    isolated dispatch workspace, with ChatGPT authentication forced and the
    same allowlisted environment used by account chat.
    """
    exe = _codex_cli_path()
    if exe is None:
        raise RouterError(
            "The Codex CLI isn't installed or isn't on PATH. Install Codex and "
            "sign in with your ChatGPT account first.", 503,
        )
    prompt = (prompt or "").strip()
    if not prompt:
        raise RouterError("Nothing to send to the Codex agent.", 400)
    active_cwd = str(cwd or CODEX_CLI_CWD)
    if not os.path.isdir(active_cwd):
        raise RouterError(f"Codex working folder does not exist: {active_cwd}", 503)
    sys_text = _flatten_system(system)
    if sys_text:
        prompt = "System instructions:\n" + sys_text + "\n\nTask:\n" + prompt
    cmd = [
        exe, "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--ignore-rules", "--skip-git-repo-check",
        "--sandbox", "workspace-write" if allow_write else "read-only",
        "-C", active_cwd, "-c", 'forced_login_method="chatgpt"',
    ]
    for directory in extra_dirs or ():
        if directory and os.path.isdir(directory):
            cmd += ["--add-dir", str(directory)]
    mdl = model or _codex_cli_model()
    if mdl:
        cmd += ["-m", mdl]
    cmd.append("-")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=_codex_env(),
            cwd=active_cwd, creationflags=creationflags,
        )
    except (FileNotFoundError, PermissionError, OSError) as e:
        raise RouterError(f"Couldn't start the Codex agent: {e}", 503)
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    stderr_chunks: list[str] = []

    def _drain():
        try:
            for line in proc.stderr:
                stderr_chunks.append(line)
        except (OSError, ValueError):
            pass

    threading.Thread(target=_drain, daemon=True).start()
    stdout_lines: queue.Queue = queue.Queue()

    def _read_stdout():
        try:
            for output_line in proc.stdout:
                stdout_lines.put(output_line)
        except (OSError, ValueError):
            pass
        finally:
            stdout_lines.put(None)

    threading.Thread(target=_read_stdout, daemon=True).start()
    idle_limit = timeout or _codex_cli_timeout()
    last_output = time.monotonic()
    cancelled = False
    timed_out = False
    stream_closed = False
    try:
        while not stream_closed:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                proc.kill()
                break
            try:
                line = stdout_lines.get(timeout=0.1)
            except queue.Empty:
                line = ""
            if line is None:
                stream_closed = True
            elif line:
                last_output = time.monotonic()
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif time.monotonic() - last_output > idle_limit:
                timed_out = True
                proc.kill()
                break
        while not stdout_lines.empty():
            line = stdout_lines.get_nowait()
            if line is None:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                pass
    finally:
        proc.wait()
    if cancelled:
        raise RouterError("The Codex agent was cancelled.", 409)
    if timed_out:
        raise RouterError(f"The Codex agent was silent for over {idle_limit}s and was stopped.", 504)
    if proc.returncode:
        detail = "".join(stderr_chunks).strip()
        if "login" in detail.lower() or "auth" in detail.lower():
            _CODEX_HEALTH.update(
                exe=exe, ok=False, state="signed_out", reason=detail,
                checked_at=time.time(),
            )
        raise RouterError(f"The Codex agent failed: {detail or 'unknown error'}", 502)
    _CODEX_HEALTH.update(
        exe=exe, ok=True, state="chatgpt",
        reason="Codex CLI is signed in with ChatGPT.", checked_at=time.time(),
    )


def codex_chat_stream(messages, system=None, model=None, attachments=None,
                      allow_write=False):
    """Stream a ChatGPT-account chat turn as Codex JSONL events.

    The final answer and user-safe activity events come from `codex exec
    --json`. Attachments use the same disposable staging boundary as blocking
    account chat and remain readable only for this invocation.
    """
    staged_dir = tempfile.TemporaryDirectory(prefix="regalia-codex-") if attachments else None
    try:
        staged = _stage_cli_attachments(attachments, staged_dir.name) if staged_dir else []
        prompt = _codex_prompt(messages, system, staged, allow_write=allow_write)
        if not prompt:
            raise RouterError("Nothing to send to ChatGPT.", 400)
        yield from codex_agent_stream(
            prompt,
            model=model,
            cwd=CODEX_CLI_CWD,
            allow_write=allow_write,
            extra_dirs=[staged_dir.name] if staged_dir else None,
        )
    finally:
        if staged_dir:
            staged_dir.cleanup()


# ── Account: Google via Gemini CLI ───────────────────────────────────────────
# The point of this tier is that it runs on a *Google account sign-in* rather
# than an API key — if you have a key, the `gemini` tier above is the better
# path (structured tool use, no subprocess). Chat is driven non-interactively
# with the conversation on stdin; account agents use stream-json headless mode.


def _gemini_cli_path():
    """Resolve the `gemini` executable on PATH, or None if it isn't installed."""
    return shutil.which(_gemini_cli())


_GEMINI_ENV_KEYS = frozenset({
    # Executable/runtime discovery and per-user Gemini CLI auth storage.
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE",
    "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
    "XDG_DATA_HOME", "USER", "USERNAME", "LOGNAME", "SHELL",
    # Temporary files, locale, and corporate proxies/CAs.
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "HTTP_PROXY", "HTTPS_PROXY",
    "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
})
# Deliberately absent, and load-bearing: GEMINI_API_KEY / GOOGLE_API_KEY /
# GOOGLE_APPLICATION_CREDENTIALS. The Gemini CLI prefers a key when it finds one
# in its environment, so inheriting those would silently bill this tier to the
# key it exists to avoid. The allowlist is what keeps "Google account" honest.


def _gemini_env() -> dict:
    """Minimal child environment: enough for the CLI and its OAuth store, no
    API keys and no unrelated secrets. Case-insensitive for Windows."""
    return {k: v for k, v in os.environ.items() if k.upper() in _GEMINI_ENV_KEYS}


def _gemini_cli_home() -> Path:
    """Where the Gemini CLI keeps its settings and OAuth credentials."""
    return Path(os.path.expanduser("~")) / ".gemini"


def _gemini_auth_type() -> str:
    """The CLI's recorded auth method, or "" when it hasn't been set."""
    try:
        data = json.loads((_gemini_cli_home() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    # The key has lived at the top level and under a "security.auth" group
    # depending on CLI version; check both rather than assume one layout.
    selected = data.get("selectedAuthType")
    if not selected:
        auth = ((data.get("security") or {}).get("auth")
                if isinstance(data.get("security"), dict) else None)
        selected = (auth or {}).get("selectedType") if isinstance(auth, dict) else None
    return str(selected or "")


def gemini_cli_health() -> tuple[bool, str]:
    """Check that the Gemini CLI is installed and using a Google account login.

    The CLI has no `login status` command, so this proves what it can: the
    binary runs (`--version`), and its own auth store says the selected method
    is personal OAuth with saved credentials. It does not prove the token is
    still valid — an expired sign-in surfaces on the first real request.
    """
    exe = _gemini_cli_path()

    def finish(ok: bool, reason: str, state: str) -> tuple[bool, str]:
        _GEMINI_HEALTH.update(
            exe=exe, ok=ok, state=state, reason=reason, checked_at=time.time()
        )
        return ok, reason

    if exe is None:
        return finish(False, "Gemini CLI was not found on PATH.", "not_installed")
    if not os.path.isdir(GEMINI_CLI_CWD):
        return finish(
            False, f"Gemini working folder does not exist: {GEMINI_CLI_CWD}", "check_failed"
        )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env=_gemini_env(),
            cwd=GEMINI_CLI_CWD,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        return finish(False, "Gemini CLI vanished mid-check.", "not_installed")
    except PermissionError as e:
        return finish(False, f"Couldn't start Gemini CLI: {e}", "check_failed")
    except subprocess.TimeoutExpired:
        return finish(False, "Gemini CLI version check timed out.", "timed_out")
    except OSError as e:
        return finish(False, f"Couldn't check Gemini CLI: {e}", "check_failed")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return finish(False, detail[:300] or "Gemini CLI did not run.", "check_failed")

    version = (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
    auth_type = _gemini_auth_type().lower()
    has_oauth = (_gemini_cli_home() / "oauth_creds.json").is_file()
    if "api" in auth_type and "key" in auth_type:
        return finish(
            False,
            "Gemini CLI is signed in with an API key, not a Google account. Use the "
            "Gemini API tier for key billing, or run `gemini` → /auth and choose "
            "'Login with Google'.",
            "wrong_method",
        )
    if "vertex" in auth_type:
        return finish(
            False,
            "Gemini CLI is configured for Vertex AI, not a personal Google account. "
            "Run `gemini` → /auth and choose 'Login with Google'.",
            "wrong_method",
        )
    if has_oauth:
        label = f"Gemini CLI is signed in with a Google account{f' ({version})' if version else ''}."
        return finish(True, label, "google")
    if auth_type:
        return finish(
            False,
            f"Gemini CLI reports auth type '{auth_type}' with no saved Google sign-in. "
            "Run `gemini` → /auth and choose 'Login with Google'.",
            "signed_out",
        )
    return finish(
        False,
        "Gemini CLI is installed, but no Google sign-in was found. Run `gemini` once "
        "and choose 'Login with Google', then use Recheck.",
        "signed_out",
    )


def _gemini_cli_prompt(messages, system, attachments=None, allow_write=False) -> str:
    """Build the single stdin prompt for a non-interactive Gemini CLI run.

    Mirrors _codex_prompt: the app owns chat history, so each invocation gets the
    relevant transcript, and the edit policy is stated in words as well as being
    enforced by the CLI's approval mode.
    """
    sys_text = _flatten_system(system)
    convo = _flatten_conversation(messages)
    if not sys_text and not convo.strip() and not attachments:
        return ""
    parts = []
    if sys_text:
        parts.append("System instructions:\n" + sys_text)
    if allow_write:
        parts.append(
            "Regalia Edit mode is ON. You may create, modify, rename, or delete "
            "files inside the current working root when the user requests it. "
            "Carry out requested edits with your tools instead of only describing "
            "them."
        )
    else:
        parts.append(
            "Regalia Edit mode is OFF. Treat the workspace as read-only: do not "
            "create, modify, rename, or delete files."
        )
    if convo.strip():
        parts.append("Conversation:\n" + convo)
    if attachments:
        listing = "\n".join(f"- {a['path']}" for a in attachments)
        parts.append(
            "The user attached these file(s). Read them before answering:\n" + listing
        )
    return "\n\n".join(parts).strip()


def _gemini_cli_chat(messages, system, max_tokens, model, attachments=None,
                     allow_write=False) -> dict:
    """Run a chat turn through the Gemini CLI on the signed-in Google account.

    max_tokens is accepted for signature parity but not forwarded; the CLI
    manages its own output budget. Read-only runs leave approvals at the CLI
    default (so a write would have to be confirmed, which cannot happen in a
    non-interactive run); Edit mode passes --yolo to auto-approve tool use.
    """
    exe = _gemini_cli_path()
    if exe is None:
        raise RouterError(
            "The Gemini CLI isn't installed or isn't on PATH. Install it "
            "(`npm install -g @google/gemini-cli`), run `gemini` once and sign in "
            "with your Google account, then restart the dashboard.",
            503,
        )
    staged_dir = tempfile.TemporaryDirectory(prefix="regalia-gemini-") if attachments else None
    try:
        staged = _stage_cli_attachments(attachments, staged_dir.name) if staged_dir else []
        prompt = _gemini_cli_prompt(messages, system, staged, allow_write=allow_write)
        if not prompt:
            raise RouterError("Nothing to send to Gemini.", 400)
        mdl = model or _gemini_cli_model()
        cmd = [exe]
        if mdl:
            cmd += ["--model", mdl]
        if allow_write:
            cmd.append("--yolo")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,          # non-interactive: the prompt is piped in
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_gemini_cli_timeout(),
                env=_gemini_env(),
                cwd=GEMINI_CLI_CWD,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired:
            raise RouterError(
                f"Gemini CLI timed out after {_gemini_cli_timeout()}s. Raise the timeout "
                "in Settings → Connections, or ask something smaller.",
                504,
            )
        except OSError as e:
            raise RouterError(f"Couldn't run the Gemini CLI: {e}", 502)
        reply = (proc.stdout or "").strip()
        if proc.returncode != 0 and not reply:
            detail = (proc.stderr or "").strip()
            low = detail.lower()
            if "auth" in low or "login" in low or "credential" in low:
                raise RouterError(
                    "The Gemini CLI isn't signed in. Run `gemini` once, choose 'Login "
                    "with Google', then use Recheck in Settings.",
                    401,
                )
            raise RouterError(f"Gemini CLI failed: {detail[:500] or 'unknown error'}", 502)
        return {
            "reply": reply or "…(the model went quiet — try again)",
            "model": mdl or "Google account default",
            "tier": "google",
        }
    finally:
        if staged_dir:
            staged_dir.cleanup()


# ── Subscription: Claude Code CLI ────────────────────────────────────────────

def gemini_agent_stream(prompt, system=None, model=None, cwd=None, allow_write=False,
                        timeout=None, cancel_event=None):
    """Run a scoped Google-account agent and yield Gemini CLI JSONL events.

    Gemini CLI drives its own tool loop. Read-only workers keep the CLI's
    default approval policy and receive an explicit no-write instruction;
    write-capable workers use headless YOLO approval so edits do not stall on
    an impossible interactive prompt. _gemini_env() strips API credentials so
    this path cannot silently switch away from Google-account billing.
    """
    exe = _gemini_cli_path()
    if exe is None:
        raise RouterError(
            "The Gemini CLI isn't installed or isn't on PATH. Install it and "
            "sign in with your Google account first.", 503,
        )
    prompt = (prompt or "").strip()
    if not prompt:
        raise RouterError("Nothing to send to the Gemini agent.", 400)
    active_cwd = str(cwd or GEMINI_CLI_CWD)
    if not os.path.isdir(active_cwd):
        raise RouterError(f"Gemini working folder does not exist: {active_cwd}", 503)
    sys_text = _flatten_system(system)
    policy = (
        "You may create, modify, rename, or delete files only inside the current "
        "working root when the task requires it."
        if allow_write else
        "Treat the current working root as read-only. Do not create, modify, "
        "rename, or delete files."
    )
    prompt = (("System instructions:\n" + sys_text + "\n\n") if sys_text else "") + \
             "Workspace policy:\n" + policy + "\n\nTask:\n" + prompt
    cmd = [exe, "--output-format", "stream-json"]
    if allow_write:
        cmd += ["--approval-mode", "yolo"]
    mdl = model or _gemini_cli_model()
    if mdl:
        cmd += ["--model", mdl]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=_gemini_env(),
            cwd=active_cwd, creationflags=creationflags,
        )
    except (FileNotFoundError, PermissionError, OSError) as e:
        raise RouterError(f"Couldn't start the Gemini agent: {e}", 503)
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    stderr_chunks: list[str] = []

    def _drain_stderr():
        try:
            for line in proc.stderr:
                stderr_chunks.append(line)
        except (OSError, ValueError):
            pass

    threading.Thread(target=_drain_stderr, daemon=True).start()
    stdout_lines: queue.Queue = queue.Queue()

    def _read_stdout():
        try:
            for output_line in proc.stdout:
                stdout_lines.put(output_line)
        except (OSError, ValueError):
            pass
        finally:
            stdout_lines.put(None)

    threading.Thread(target=_read_stdout, daemon=True).start()
    idle_limit = timeout or _gemini_cli_timeout()
    last_output = time.monotonic()
    cancelled = False
    timed_out = False
    stream_closed = False
    try:
        while not stream_closed:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                proc.kill()
                break
            try:
                line = stdout_lines.get(timeout=0.1)
            except queue.Empty:
                line = ""
            if line is None:
                stream_closed = True
            elif line:
                last_output = time.monotonic()
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif time.monotonic() - last_output > idle_limit:
                timed_out = True
                proc.kill()
                break
        while not stdout_lines.empty():
            line = stdout_lines.get_nowait()
            if line is None:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                pass
    finally:
        proc.wait()
    if cancelled:
        raise RouterError("The Gemini agent was cancelled.", 409)
    if timed_out:
        raise RouterError(f"The Gemini agent was silent for over {idle_limit}s and was stopped.", 504)
    if proc.returncode:
        detail = "".join(stderr_chunks).strip()
        low = detail.lower()
        if "login" in low or "auth" in low or "credential" in low:
            _GEMINI_HEALTH.update(
                exe=exe, ok=False, state="signed_out", reason=detail,
                checked_at=time.time(),
            )
        raise RouterError(f"The Gemini agent failed: {detail or 'unknown error'}", 502)
    _GEMINI_HEALTH.update(
        exe=exe, ok=True, state="google",
        reason="Gemini CLI is signed in with a Google account.", checked_at=time.time(),
    )


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


def _claude_automation_flags(builtin_tools=None, allowed_tools=None) -> list[str]:
    """Exact, non-interactive Claude Code capability/configuration boundary.

    `--allowedTools` pre-approves calls but does not hide other built-ins. The
    separate `--tools` list is therefore load-bearing: an empty element disables
    every built-in for text/email-only calls. User/project/local settings, skills,
    commands and ambient MCP servers are also excluded from automated runs.
    """
    builtins = ",".join(builtin_tools or [])
    allowed = ",".join(allowed_tools or [])
    return [
        "--setting-sources", "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--permission-mode", "dontAsk",
        "--tools", builtins,
        "--allowedTools", allowed,
        "--strict-mcp-config",
    ]


def _claude_absolute_rule(tool: str, directory: str) -> str:
    """Claude permission-rule syntax for one absolute directory, cross-platform."""
    normalized = Path(directory).resolve().as_posix()
    if re.match(r"^[A-Za-z]:/", normalized):
        normalized = "/" + normalized[0].lower() + normalized[2:]
    return f"{tool}(/{normalized.rstrip('/')}/**)"


def primary_model(usage, fallback: str = "") -> str:
    """Pick the model that actually answered out of a CLI `modelUsage` map.

    Claude Code bills its own side work (titles, small background calls) to a
    cheaper model, so `modelUsage` is a *multi-model* map and its first key is
    often haiku even on an opus run — labelling the reply with it is simply
    wrong. Rank by output tokens instead: the model that wrote the answer
    dominates them. Callers that already know the session model (the stream
    `init` event) should prefer that and use this only as a fallback.
    """
    best, best_out = "", -1
    for name, entry in (usage or {}).items():
        raw = entry.get("outputTokens", entry.get("output_tokens", 0)) \
            if isinstance(entry, dict) else 0
        try:
            out = int(raw)
        except (TypeError, ValueError):
            out = 0
        if out > best_out:
            best, best_out = str(name), out
    return best or fallback


def _claude_code_chat(messages, system, max_tokens, model, attachments=None,
                      allow_write=False) -> dict:
    """Stage uploads into a disposable, explicitly granted CLI directory."""
    if not attachments:
        return _claude_code_chat_inner(
            messages, system, max_tokens, model, [], allow_write, None)
    with tempfile.TemporaryDirectory(prefix="regalia-claude-") as directory:
        staged = _stage_cli_attachments(attachments, directory)
        return _claude_code_chat_inner(
            messages, system, max_tokens, model, staged, allow_write, directory)


def _claude_code_chat_inner(messages, system, max_tokens, model, attachments=None,
                            allow_write=False, attachment_dir=None) -> dict:
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
    # Exact available + pre-approved built-ins. Never expose Bash, Agent, Web,
    # skills, plugins, hooks, ambient MCP servers, or connected external roots.
    if allow_write:
        builtin_tools = ["Read", "Edit", "Write", "Glob", "Grep"]
        allowed_tools = ["Read(./**)", "Edit(./**)"]
        if attachment_dir:
            allowed_tools.append(_claude_absolute_rule("Read", attachment_dir))
    elif attachments:
        builtin_tools = ["Read"]
        allowed_tools = ["Read(./**)"]
    else:
        builtin_tools = []
        allowed_tools = []
    cmd += _claude_automation_flags(builtin_tools, allowed_tools)
    if attachment_dir and allow_write:
        cmd += ["--add-dir", attachment_dir]
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
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"

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
            cwd=attachment_dir if attachment_dir and not allow_write else CLAUDE_CLI_CWD,
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
    used_model = primary_model(data.get("modelUsage")) or mdl or "claude (plan)"
    return {
        "reply": reply or "…(the model went quiet — try again)",
        "model": used_model,
        "tier": "claude",
    }


def claude_code_chat_stream(messages, system=None, model=None, attachments=None,
                            allow_write=False):
    """Streaming counterpart of _claude_code_chat for the Chat panel's claude tier.

    Builds the same prompt / tool grants / attachment staging as the blocking
    path, but drives claude_code_stream so the caller can surface thinking, tool
    steps, and text live instead of hiding everything until the CLI finishes.
    Yields the same parsed CLI events; the trailing 'result' event carries the
    final reply. Raises RouterError like claude_code_stream (including on the
    idle timeout). System is *appended* to the CLI's own prompt (vs replaced in
    the blocking path) — for a chat turn the caller's system is usually empty, so
    this only ever adds context, never drops the CLI defaults.
    """
    atts = _norm_attachments(attachments)
    if not atts:
        yield from _claude_code_chat_stream_inner(messages, system, model, [], allow_write, None)
        return
    # The temp dir must outlive the whole stream, so hold it open while yielding.
    with tempfile.TemporaryDirectory(prefix="regalia-claude-") as directory:
        staged = _stage_cli_attachments(atts, directory)
        yield from _claude_code_chat_stream_inner(
            messages, system, model, staged, allow_write, directory)


def _claude_code_chat_stream_inner(messages, system, model, attachments,
                                   allow_write, attachment_dir):
    """Compute prompt + tool grants (mirrors _claude_code_chat_inner) and stream."""
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

    if allow_write:
        builtins = ["Read", "Edit", "Write", "Glob", "Grep"]
        allowed = ["Read(./**)", "Edit(./**)"]
        if attachment_dir:
            allowed.append(_claude_absolute_rule("Read", attachment_dir))
    elif attachments:
        builtins = ["Read"]
        allowed = ["Read(./**)"]
    else:
        builtins = []
        allowed = []

    cwd = attachment_dir if (attachment_dir and not allow_write) else CLAUDE_CLI_CWD
    extra_dirs = [attachment_dir] if (attachment_dir and allow_write) else None

    yield from claude_code_stream(
        prompt, system=system, builtin_tools=builtins, allowed_tools=allowed,
        model=model, cwd=cwd, extra_dirs=extra_dirs,
    )


def claude_code_stream(prompt, system=None, builtin_tools=None, allowed_tools=None,
                       model=None, cwd=None, timeout=None, mcp_config=None,
                       extra_dirs=None, cancel_event=None):
    """Run the Claude Code CLI in streaming mode, yielding parsed JSON events.

    This is the agentic, subscription-billed counterpart to chat_tools(): instead
    of the dashboard driving the tool loop, the CLI runs its *own* model→tools→
    repeat loop and emits newline-delimited JSON as it goes (`--output-format
    stream-json`, which requires `--verbose`). We yield each parsed event —
    system/assistant/user/result messages, mirroring the Anthropic message shape —
    so the caller can stream steps live. The trailing 'result' event carries the
    final summary text.

    builtin_tools is the exact available built-in set; allowed_tools is the exact
    built-in/MCP set pre-approved for this run. Dispatch callers may grant only
    the validation commands approved in the reviewed plan. File
    access stays confined to cwd plus explicit extra_dirs. As with the
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
    builtin_tools = list(builtin_tools or [])
    allowed_tools = list(allowed_tools or [])
    cmd += _claude_automation_flags(builtin_tools, allowed_tools)
    for directory in extra_dirs or []:
        cmd += ["--add-dir", str(directory)]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]
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
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
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

    # Idle watchdog: kill the run only after it goes *silent* for the timeout,
    # not after a fixed wall-clock cap. A long-but-working task streams events
    # (thinking, tool calls, text) the whole time, so it keeps resetting the
    # clock and never trips; only a genuinely stalled CLI does. Popen streaming
    # has no built-in timeout the way subprocess.run does, hence the manual one.
    idle_limit = timeout or _claude_cli_timeout()
    timed_out = {"v": False}
    cancelled = {"v": False}
    last_event = {"t": time.monotonic()}
    watch_done = threading.Event()

    def _watchdog():
        while not watch_done.wait(1.0):
            if cancel_event is not None and cancel_event.is_set():
                cancelled["v"] = True
                try:
                    proc.kill()
                except OSError:
                    pass
                return
            if time.monotonic() - last_event["t"] > idle_limit:
                timed_out["v"] = True
                try:
                    proc.kill()
                except OSError:
                    pass
                return

    watch_thread = threading.Thread(target=_watchdog, daemon=True)
    watch_thread.start()

    try:
        for line in proc.stdout:
            last_event["t"] = time.monotonic()  # any output resets the idle clock
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # ignore any non-JSON noise on the stream
    finally:
        watch_done.set()
        proc.wait()
        err_thread.join(timeout=1)
        watch_thread.join(timeout=1)

    if cancelled["v"]:
        raise RouterError("The Claude agent was cancelled.", 409)
    if timed_out["v"]:
        raise RouterError(
            f"The Claude CLI went silent for over {idle_limit}s and was stopped. "
            "It may have stalled — try again, or switch tiers.", 504
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
