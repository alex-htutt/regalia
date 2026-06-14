"""Model router — one chat() over two backends.

This is the core primitive of the self-hosted workspace: every model call in the
app goes through chat(), which picks a backend by tier.

    tier="fast"  -> Ollama, local HTTP on :11434   (no API cost, needs Ollama)
    tier="smart" -> Anthropic, cloud               (needs ANTHROPIC_API_KEY)

chat() returns {"reply", "model", "tier"} on success, or raises RouterError with
a user-facing message + HTTP status the Flask layer can hand straight to the UI.
Adding a third backend later means one more branch here and nothing elsewhere.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Local runtime. Override with env vars if Ollama lives elsewhere or you pull a
# different default model.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Cloud runtime. Smart tier defaults to the same model the twin uses.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

TIERS = ("fast", "smart")


class RouterError(Exception):
    """A failure with a message safe to show the user and an HTTP status."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def chat(messages, tier="fast", system=None, max_tokens=2048, model=None) -> dict:
    """Run a chat completion on the chosen tier.

    messages: [{"role": "user"|"assistant", "content": str}, ...]
    system:   None, a string, or a list of Anthropic system blocks.
    """
    tier = (tier or "fast").lower()
    if tier not in TIERS:
        tier = "fast"
    if tier == "smart":
        return _anthropic_chat(messages, system, max_tokens, model)
    return _ollama_chat(messages, system, max_tokens, model)


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


def _anthropic_chat(messages, system, max_tokens, model) -> dict:
    anthropic, client, mdl = _require_anthropic(model)
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


def _ollama_chat(messages, system, max_tokens, model) -> dict:
    mdl = model or OLLAMA_MODEL
    msgs = list(messages)
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
