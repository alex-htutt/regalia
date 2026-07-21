"""Regalia settings store — a tiny JSON file, mirroring the .chats/ pattern.

User-tunable preferences (theme, accent, default tier) and locally-stored
secrets (API keys) live in the gitignored dashboard/.config.json. Env vars
still work and WIN over the file for secrets/paths — the file is the "set it
from the UI" layer, env is the "I manage my own environment" layer.

Design notes:
- stdlib only; no dep.
- Atomic writes (temp file + os.replace) under a module lock, so concurrent
  Flask threads can't interleave a torn write.
- Secrets are stored in plaintext (single-user local tool — same trust model
  as .email_tokens/). They are NEVER returned by the settings API: mask()
  reduces each secret to a set/unset boolean the UI can render.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

import paths

CONFIG_PATH = paths.data_dir() / ".config.json"

# Every key the store accepts, with its default. Unknown keys are rejected so a
# typo'd POST can't silently plant garbage. For the backend/email knobs, "" means
# "not set here — fall through to the env var, then the built-in default" (the
# resolution order value()/secret() implement), so the store only ever pins what
# the user actually typed into Settings.
DEFAULTS: dict = {
    "theme": "dark",           # "dark" | "light"
    "accent": "",              # hex like "#e7c59a"; empty = theme default
    "default_tier": "fast",    # tier newly-created chats start on
    "landing_enabled": True,   # show the scrollytelling landing page
    "autoupdate": False,       # self-replace + relaunch when out of date (frozen builds)
    "onboarded": False,        # has the first-run setup wizard been completed/skipped?
    "vault_path": "",          # vault root override; empty = repo root (restart to apply)
    "anthropic_api_key": "",   # secret — masked by the API
    "openai_api_key": "",      # secret — masked by the API
    # ── backends (env var of the same upper-cased name wins; "" = unset) ──
    "ollama_host": "",         # e.g. http://localhost:11434
    "ollama_model": "",        # e.g. llama3.2
    "anthropic_model": "",     # smart-tier model id
    "openai_model": "",        # openai-tier model id
    "openai_base": "",         # OpenAI-compatible API base URL
    "codex_cli": "",           # codex binary name/path
    "codex_cli_model": "",     # empty = ChatGPT account default
    "codex_cli_timeout": "",   # seconds (stored as string; "" = default)
    "claude_cli": "",          # claude binary name/path
    "claude_cli_model": "",    # empty = plan default
    "claude_cli_timeout": "",  # seconds (stored as string; "" = default)
    "news_ttl": "",            # briefing cache seconds ("" = default)
    # ── email OAuth client (app identity, not per-user tokens) ──
    "ms_oauth_client_id": "",     # Azure public-client app id (not a secret)
    "ms_oauth_tenant": "",        # "" = consumers
    "gmail_oauth_client_json": "",  # secret — pasted client_secret.json contents
}

SECRET_KEYS = frozenset({"anthropic_api_key", "openai_api_key", "gmail_oauth_client_json"})

_VALID_THEMES = ("dark", "light")
_VALID_TIERS = ("fast", "smart", "openai", "chatgpt", "claude")

# Store keys that are plain booleans (coerced from any truthy value, never
# string-stripped like the rest).
_BOOL_KEYS = ("landing_enabled", "autoupdate", "onboarded")

# Store keys that must parse as a positive integer when non-empty.
_INT_KEYS = ("codex_cli_timeout", "claude_cli_timeout", "news_ttl")

_lock = threading.Lock()


def load() -> dict:
    """Defaults overlaid with whatever the file holds. Never raises on a
    missing/corrupt file — settings degrade to defaults, not a 500."""
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for k, v in data.items():
                if k in DEFAULTS:
                    cfg[k] = v
    except (OSError, ValueError):
        pass
    return cfg


def get(key: str, default=None):
    """One setting, file-backed. For secrets, prefer secret() (env-aware)."""
    return load().get(key, default if default is not None else DEFAULTS.get(key))


def secret(key: str, env_var: str) -> str:
    """Resolve a secret: environment wins, then the store. Returns "" if unset."""
    return os.environ.get(env_var) or str(load().get(key) or "")


def value(key: str, env_var: str, default: str = "") -> str:
    """Resolve a plain (non-secret) knob: env wins, then the store, then the
    built-in default. Always returns a string — callers convert (int(...))."""
    return os.environ.get(env_var) or str(load().get(key) or "") or default


def update(changes: dict) -> dict:
    """Validate + merge a partial dict into the store; returns the new config.
    Raises ValueError with a UI-safe message on a bad key/value."""
    if not isinstance(changes, dict):
        raise ValueError("Settings payload must be an object.")
    for k in changes:
        if k not in DEFAULTS:
            raise ValueError(f"Unknown setting: {k!r}")
    if "theme" in changes and changes["theme"] not in _VALID_THEMES:
        raise ValueError(f"theme must be one of {_VALID_THEMES}")
    if "default_tier" in changes and changes["default_tier"] not in _VALID_TIERS:
        raise ValueError(f"default_tier must be one of {_VALID_TIERS}")
    for bk in _BOOL_KEYS:
        if bk in changes:
            changes[bk] = bool(changes[bk])
    for k in changes:
        if k in _BOOL_KEYS:
            continue
        if not isinstance(changes[k], str):
            raise ValueError(f"{k} must be a string")
        changes[k] = changes[k].strip()
    if changes.get("accent") and not _looks_like_hex(changes["accent"]):
        raise ValueError("accent must be a hex color like #e7c59a (or empty)")
    for k in _INT_KEYS:
        if changes.get(k):
            if not changes[k].isdigit() or not 1 <= int(changes[k]) <= 86400:
                raise ValueError(
                    f"{k} must be 1 to 86400 whole seconds (or empty)"
                )
    for k in ("ollama_host", "openai_base"):
        if changes.get(k) and not changes[k].lower().startswith(("http://", "https://")):
            raise ValueError(f"{k} must be an http(s):// URL (or empty)")
    if changes.get("gmail_oauth_client_json"):
        try:
            parsed = json.loads(changes["gmail_oauth_client_json"])
        except ValueError:
            raise ValueError("That doesn't look like valid JSON — paste the whole client_secret file.")
        if not isinstance(parsed, dict) or not ({"installed", "web"} & parsed.keys()):
            raise ValueError(
                'That JSON isn\'t a Google OAuth client — expected a top-level "installed" '
                '(Desktop app) or "web" key. Download it from Google Cloud → Credentials.')

    with _lock:
        cfg = load()
        cfg.update(changes)
        payload = {k: v for k, v in cfg.items() if v != DEFAULTS[k]}
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(CONFIG_PATH.parent), prefix=".config-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, CONFIG_PATH)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return cfg


def mask(cfg: dict) -> dict:
    """A copy safe to return over HTTP: secrets become {"set": bool}."""
    out = {}
    for k, v in cfg.items():
        out[k] = {"set": bool(v)} if k in SECRET_KEYS else v
    return out


def _looks_like_hex(s: str) -> bool:
    if not s.startswith("#") or len(s) not in (4, 7):
        return False
    try:
        int(s[1:], 16)
        return True
    except ValueError:
        return False
