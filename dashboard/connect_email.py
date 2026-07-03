"""One-time interactive OAuth consent — connect a Gmail or Outlook inbox.

    python connect_email.py gmail
    python connect_email.py outlook

Opens your browser for consent, then writes the account's tokens to the gitignored
store (dashboard/.email_tokens/) so the dashboard can read the inbox and create
drafts. Run once per account; re-run to refresh a revoked/expired connection.

This is deliberately a standalone CLI, NOT a Flask route: the consent flow spins up
a local redirect server and blocks on the browser, which has no place in a request
handler. The Inbox view points here when no account is connected.

Prerequisites (one-time, outside this repo):
  Gmail   — a Google Cloud OAuth client of type "Desktop app". Download its
            client_secret JSON and point GMAIL_OAUTH_CLIENT at the file.
  Outlook — an Azure AD app registration (Mobile & desktop, redirect
            http://localhost) as a public client. Set MS_OAUTH_CLIENT_ID (and
            MS_OAUTH_TENANT=consumers for personal Outlook.com accounts).
"""

from __future__ import annotations

import json
import sys
import urllib.request

import email_sources as cfg
import mailbox


def _connect_gmail() -> str:
    if not cfg.GMAIL_CLIENT_SECRET_FILE:
        raise SystemExit("Set GMAIL_OAUTH_CLIENT to your Google client_secret JSON path first.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit("google-auth-oauthlib not installed — run: pip install -r requirements.txt")

    flow = InstalledAppFlow.from_client_secrets_file(
        cfg.GMAIL_CLIENT_SECRET_FILE, scopes=cfg.GMAIL_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    # Resolve the account's email address for a friendly id/label.
    address = ""
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"})
        with urllib.request.urlopen(req, timeout=cfg.HTTP_TIMEOUT) as resp:
            address = (json.loads(resp.read()) or {}).get("email", "")
    except Exception:  # noqa: BLE001 — address is cosmetic; fall back below
        pass
    address = address or "account"
    return mailbox.save_account("gmail", address, google=json.loads(creds.to_json()))


def _connect_outlook() -> str:
    if not cfg.MS_CLIENT_ID:
        raise SystemExit("Set MS_OAUTH_CLIENT_ID to your Azure app (public client) id first.")
    try:
        import msal
    except ImportError:
        raise SystemExit("msal not installed — run: pip install -r requirements.txt")

    cache = msal.SerializableTokenCache()
    app = msal.PublicClientApplication(
        cfg.MS_CLIENT_ID, authority=cfg.MS_AUTHORITY, token_cache=cache)
    result = app.acquire_token_interactive(scopes=cfg.MS_SCOPES)
    if "access_token" not in result:
        raise SystemExit(f"Consent failed: {result.get('error_description', result)}")

    claims = result.get("id_token_claims", {}) or {}
    address = claims.get("preferred_username") or claims.get("email") or ""
    if not address:
        try:
            req = urllib.request.Request(
                f"{cfg.GRAPH_API_BASE}/me?$select=mail,userPrincipalName",
                headers={"Authorization": f"Bearer {result['access_token']}"})
            with urllib.request.urlopen(req, timeout=cfg.HTTP_TIMEOUT) as resp:
                me = json.loads(resp.read()) or {}
                address = me.get("mail") or me.get("userPrincipalName") or ""
        except Exception:  # noqa: BLE001
            pass
    address = address or "account"
    return mailbox.save_account("outlook", address, msal_cache=cache.serialize())


def main(argv) -> int:
    provider = (argv[1].lower() if len(argv) > 1 else "").strip()
    if provider not in cfg.PROVIDERS:
        print(f"Usage: python connect_email.py [{' | '.join(cfg.PROVIDERS)}]")
        return 2
    account_id = _connect_gmail() if provider == "gmail" else _connect_outlook()
    print(f"\nConnected ✓  account id: {account_id}")
    print(f"Tokens stored in: {mailbox.TOKENS_DIR}")
    print("Open the dashboard's Inbox view to read mail and save drafts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
