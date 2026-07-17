"""Email connection configuration for the Inbox view + email tools.

Config only — no secrets, no I/O. The engine in ``mailbox.py`` reads from here so
provider details (API hosts, OAuth scopes, limits) live in one place and are never
hardcoded in the logic, mirroring how ``news_sources.py`` configures the briefing.

Two providers are supported:
  - "gmail"   -> Google, via the Gmail REST API + Google OAuth
  - "outlook" -> Microsoft (Outlook.com / 365), via Microsoft Graph + MSAL

Auth approach (#2.5): the OAuth/token dance is handled by small official auth-only
libraries (google-auth-oauthlib, msal); the actual mail I/O is plain urllib+json
against the REST endpoints below. Write scope is **drafts only** — note the Graph
scopes deliberately omit ``Mail.Send`` so Outlook *cannot* send, and the Gmail code
never calls the send endpoint.

OAuth *client* credentials (the app identity, not per-user tokens) come from the
environment OR the Settings view (env wins; nothing sensitive lives in the repo):
  - Gmail:   GMAIL_OAUTH_CLIENT  -> path to the Google "Desktop app" client_secret JSON,
             or paste the JSON itself into Settings → Email (stored in the gitignored
             config, materialized to a private file on demand)
  - Outlook: MS_OAUTH_CLIENT_ID  -> the Azure app (public client) application id
             MS_OAUTH_TENANT     -> tenant; default "consumers" for personal accounts
"""

from __future__ import annotations

import os

PROVIDERS = ("gmail", "outlook")

# ── REST endpoints (mail I/O via stdlib urllib in mailbox.py) ────────────────
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# ── OAuth scopes ─────────────────────────────────────────────────────────────
# Gmail: read messages + manage drafts. gmail.compose is the narrowest scope that
# can create drafts (there is no draft-only scope); we never call send regardless.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    # userinfo.email lets us label the connected account by address.
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
# Microsoft Graph: read + read/write (create drafts). Mail.Send is INTENTIONALLY
# absent — without it the token literally cannot send, enforcing drafts-only.
MS_SCOPES = ["Mail.Read", "Mail.ReadWrite", "User.Read"]

# ── OAuth client credentials (app identity) — env wins, then Settings ────────
# Resolved lazily so values saved in the Settings view apply without a restart.
# The Gmail client can be provided two ways: GMAIL_OAUTH_CLIENT (a path to the
# downloaded client_secret JSON — the power-user/env route) or pasted straight
# into Settings → Email, in which case the store holds the JSON itself and we
# materialize it to a private file for google-auth's from_client_secrets_file.

def gmail_client_secret_file() -> str:
    """Path to the Google client_secret JSON, or "" if not configured."""
    path = os.environ.get("GMAIL_OAUTH_CLIENT", "")
    if path:
        return path
    import config  # lazy: keep this module import-light

    raw = str(config.get("gmail_oauth_client_json") or "")
    if not raw:
        return ""
    import paths

    dest = paths.data_dir() / ".oauth_clients" / "gmail_client_secret.json"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_text(encoding="utf-8") != raw:
            dest.write_text(raw, encoding="utf-8")
            os.chmod(dest, 0o600)
    except OSError:
        return ""
    return str(dest)


def ms_client_id() -> str:
    import config

    return config.value("ms_oauth_client_id", "MS_OAUTH_CLIENT_ID", "")


def ms_tenant() -> str:
    import config

    return config.value("ms_oauth_tenant", "MS_OAUTH_TENANT", "consumers")


def ms_authority() -> str:
    return f"https://login.microsoftonline.com/{ms_tenant()}"

# ── Fetch limits + cache ─────────────────────────────────────────────────────
DEFAULT_INBOX_LIMIT = 25     # messages shown in a list view by default
MAX_INBOX_LIMIT = 100        # hard cap so a tool/route can't ask for the world
SEARCH_LIMIT = 25            # results for a search query
BODY_MAX_CHARS = 20000       # truncate huge message bodies for tool/UI consumption
INBOX_CACHE_TTL = 120        # seconds to cache an inbox listing (per account+query)
HTTP_TIMEOUT = 20            # seconds for any single Graph/Gmail HTTP call

# ── Important-mail scoring (overview panel) ──────────────────────────────────
# The "Important mail" column on the overview pulls the last IMPORTANT_DAYS of
# mail from every connected inbox and keeps only work/school-relevant messages.
# Scoring is DELIBERATELY deterministic (keywords + sender domains, no model
# call) — it runs on every page load, so it must be fast, free, and private.
# Tune the lists below to your life; weights are additive, penalties subtract.
IMPORTANT_DAYS = 2            # look-back window (days)
IMPORTANT_FETCH_PER_ACCOUNT = 25   # messages pulled per inbox before scoring
IMPORTANT_MAX_SHOWN = 8       # rows shown in the panel
IMPORTANT_MIN_SCORE = 2       # below this a message is dropped as noise

# keyword -> weight, matched (case-insensitive) against subject + snippet.
IMPORTANT_KEYWORDS = {
    # school
    "assignment": 3, "homework": 3, "exam": 3, "quiz": 2, "grade": 2,
    "professor": 2, "course": 2, "lecture": 2, "syllabus": 3, "registrar": 3,
    "tuition": 3, "financial aid": 3, "due": 2, "deadline": 3, "submission": 2,
    "office hours": 2, "advisor": 2, "enrollment": 2, "transcript": 2,
    # work / internship
    "interview": 4, "offer": 3, "internship": 3, "recruiter": 3, "onboarding": 3,
    "meeting": 2, "standup": 2, "invoice": 3, "payroll": 3, "timesheet": 3,
    "contract": 2, "application": 2, "action required": 3, "urgent": 2,
    "schedule": 1, "project": 1, "review": 1,
}

# sender-address substring -> weight (e.g. school/work domains).
IMPORTANT_SENDER_DOMAINS = {
    ".edu": 3,          # any university address (rpi.edu, …)
    "greenhouse.io": 2, # recruiting pipeline mail
    "lever.co": 2,
}

# marketing/noise signals: substring (checked in subject+snippet AND sender) -> penalty.
IMPORTANT_PENALTIES = {
    "unsubscribe": 2, "newsletter": 2, "% off": 3, "sale": 2, "coupon": 3,
    "free shipping": 3, "deal of": 3, "webinar": 1, "promotion": 2,
    "marketing": 2, "digest": 1,
}
