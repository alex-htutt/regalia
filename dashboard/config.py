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

import copy
import json
import os
import tempfile
import threading
import urllib.parse
from pathlib import Path

import paths

CONFIG_PATH = paths.data_dir() / ".config.json"

# ── Personalization (v1.33) ──────────────────────────────────────────────────
# The overview briefing (job openings + tech news) is tailored to the individual
# user, not baked into the shipped news_sources.py profile. This dict is the
# per-user overlay; every field empty/[] means "fall through to the shipped
# defaults in news_sources.py" so a fresh install shows a generic briefing, not
# the creator's. The UI always POSTs the WHOLE object (missing sub-keys reset to
# these defaults) — see update() / personalization().
CAREER_STAGES = ("student", "early", "mid", "senior", "any")
DEFAULT_PERSONALIZATION: dict = {
    "job_interests": [],   # bucket labels from news_sources.INTEREST_KEYWORDS; [] = all
    "career_stage": "any",  # one of CAREER_STAGES — biases early-career vs senior roles
    "job_locations": [],   # preferred location strings; [] = shipped defaults
    "job_boards": [],      # Greenhouse board tokens; [] = shipped defaults
    "news_feeds": [],      # [{"name","url"}] RSS/Atom feeds; [] = shipped defaults
    "show_jobs": True,     # render the "Opportunities" briefing column
    "show_news": True,     # render the "Tech news" briefing column
}

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
    "personalization": copy.deepcopy(DEFAULT_PERSONALIZATION),  # overview briefing profile
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

# Store keys whose value is a structured dict, not a string/bool. Validated by a
# dedicated cleaner and skipped by the generic string-strip pass in update().
_DICT_KEYS = ("personalization",)

_lock = threading.Lock()


def load() -> dict:
    """Defaults overlaid with whatever the file holds. Never raises on a
    missing/corrupt file — settings degrade to defaults, not a 500."""
    cfg = dict(DEFAULTS)
    # Deep-copy the mutable dict defaults so a caller can never mutate the shared
    # DEFAULTS template through a returned config.
    for k in _DICT_KEYS:
        cfg[k] = copy.deepcopy(DEFAULTS[k])
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


def personalization() -> dict:
    """The effective overview-briefing profile: DEFAULT_PERSONALIZATION overlaid
    with whatever the user has saved. Always a fresh, fully-populated dict (every
    sub-key present) that callers may freely read/mutate."""
    merged = copy.deepcopy(DEFAULT_PERSONALIZATION)
    stored = load().get("personalization")
    if isinstance(stored, dict):
        for k, v in stored.items():
            if k in merged:
                merged[k] = v
    return merged


def _clean_str_list(value, field: str) -> list:
    """Normalize a submitted list into a de-duplicated list of trimmed strings."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings")
        s = item.strip()
        if s and s not in out:
            out.append(s)
    return out


def _clean_feeds(value) -> list:
    """Normalize news_feeds into [{"name","url"}] with http(s) URLs; a bare URL
    string is accepted and its name derived later from the feed itself."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("news_feeds must be a list")
    out: list[dict] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            name, url = "", item.strip()
        elif isinstance(item, dict):
            name, url = str(item.get("name") or "").strip(), str(item.get("url") or "").strip()
        else:
            raise ValueError("news_feeds entries must be objects or URL strings")
        if not url:
            continue
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("news feed URLs must be an http(s):// address")
        if url in seen:
            continue
        seen.add(url)
        out.append({"name": name, "url": url})
    return out


def _clean_personalization(raw) -> dict:
    """Validate a personalization payload and merge it over the defaults. Missing
    sub-keys reset to default (the UI posts the whole object), so this is a
    replace, not a partial merge onto the stored value."""
    if not isinstance(raw, dict):
        raise ValueError("personalization must be an object")
    for k in raw:
        if k not in DEFAULT_PERSONALIZATION:
            raise ValueError(f"Unknown personalization field: {k!r}")
    out = copy.deepcopy(DEFAULT_PERSONALIZATION)
    if "career_stage" in raw:
        stage = str(raw["career_stage"] or "any").strip().lower()
        if stage not in CAREER_STAGES:
            raise ValueError(f"career_stage must be one of {CAREER_STAGES}")
        out["career_stage"] = stage
    for lk in ("job_interests", "job_locations", "job_boards"):
        if lk in raw:
            out[lk] = _clean_str_list(raw[lk], lk)
    if "news_feeds" in raw:
        out["news_feeds"] = _clean_feeds(raw["news_feeds"])
    for bk in ("show_jobs", "show_news"):
        if bk in raw:
            out[bk] = bool(raw[bk])
    return out


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
    if "personalization" in changes:
        changes["personalization"] = _clean_personalization(changes["personalization"])
    for k in changes:
        if k in _BOOL_KEYS or k in _DICT_KEYS:
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
    # A pasted ollama.com model link is normalized to the bare pullable name so
    # the router's /api/chat gets a valid model, not a URL.
    if changes.get("ollama_model"):
        changes["ollama_model"] = normalize_ollama_model(changes["ollama_model"])
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


def normalize_ollama_model(raw) -> str:
    """Accept either a bare Ollama model name or an ollama.com model link and
    return the name Ollama's `/api/pull` (and `/api/chat`) expects.

    Pasting `https://ollama.com/library/llama3.2:1b` and typing the bare
    `llama3.2:1b` both resolve to `llama3.2:1b`. The official-library prefix is
    dropped (those pull by bare name); community/namespaced models
    (`ollama.com/<user>/<model>`) keep their `<user>/<model>` namespace. Query
    strings and fragments (`?…`, `#…`) are discarded. A value that isn't a link
    is returned trimmed but otherwise untouched — this never rejects, so callers
    still run it through their own name validation.
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    if "://" in s or s.lower().startswith("ollama.com/"):
        # Prepend a scheme for the bare-host form so urlparse fills in .path.
        parsed = urllib.parse.urlparse(s if "://" in s else "https://" + s)
        path = parsed.path.strip("/")
        if path:
            s = path
    if s.lower().startswith("library/"):
        s = s[len("library/"):]
    return s.strip("/")


def _looks_like_hex(s: str) -> bool:
    if not s.startswith("#") or len(s) not in (4, 7):
        return False
    try:
        int(s[1:], 16)
        return True
    except ValueError:
        return False
