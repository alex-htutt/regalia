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

OAuth *client* credentials (the app identity, not per-user tokens) are read from the
environment so nothing sensitive lives in the repo:
  - Gmail:   GMAIL_OAUTH_CLIENT  -> path to the Google "Desktop app" client_secret JSON
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

# ── OAuth client credentials (app identity) — from env, never committed ──────
GMAIL_CLIENT_SECRET_FILE = os.environ.get("GMAIL_OAUTH_CLIENT", "")
MS_CLIENT_ID = os.environ.get("MS_OAUTH_CLIENT_ID", "")
MS_TENANT = os.environ.get("MS_OAUTH_TENANT", "consumers")
MS_AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT}"

# ── Retrieval backend (M3: Hermes) ───────────────────────────────────────────
# Which engine mailbox.py uses to READ mail (the message shapes the Inbox UI
# renders are identical either way — only the retrieval guts differ):
#   "api"    -> direct Gmail REST + Microsoft Graph using the OAuth tokens below
#               (the original engine; needs the Google "Desktop app" / Azure app).
#   "hermes" -> the Hermes agent CLI's email skills ($GAPI gmail / Himalaya), so
#               there is no Google/Azure app and no per-account OAuth token store.
# Default stays "api" until the Hermes path is complete; flip with MAILBOX_BACKEND=hermes.
MAILBOX_BACKEND = os.environ.get("MAILBOX_BACKEND", "api").lower().strip()

# Address of the single inbox Hermes is connected to (from `hermes setup`). Used
# only to label the account in the UI when MAILBOX_BACKEND="hermes"; retrieval
# itself targets whatever inbox Hermes holds, so this is cosmetic.
HERMES_EMAIL_ADDRESS = os.environ.get("HERMES_EMAIL_ADDRESS", "")

# ── Fetch limits + cache ─────────────────────────────────────────────────────
DEFAULT_INBOX_LIMIT = 25     # messages shown in a list view by default
MAX_INBOX_LIMIT = 100        # hard cap so a tool/route can't ask for the world
SEARCH_LIMIT = 25            # results for a search query
BODY_MAX_CHARS = 20000       # truncate huge message bodies for tool/UI consumption
INBOX_CACHE_TTL = 120        # seconds to cache an inbox listing (per account+query)
HTTP_TIMEOUT = 20            # seconds for any single Graph/Gmail HTTP call
