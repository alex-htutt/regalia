"""Mailbox MCP server — the subscription-tier bridge to the email engine.

A stdio MCP server (official `mcp` SDK / FastMCP) exposing the dashboard's five
email tools so the **`claude` CLI tier** can reach the mailbox: the Claude Code
CLI runs its own agent loop (billed to the signed-in Claude subscription, no API
credits) and can't call our in-process Python tools — but it *can* speak MCP.
`agent._run_agent_claude` points the CLI here via `--mcp-config` when an agent
lists email tools, granting only `mcp__mailbox__<tool>` names (no Bash, no files).

Each tool is a thin wrapper over the SAME `agent._tool_*` functions the in-process
`fast`/`smart` loop uses, so the model sees identical output on every tier.

Drafts-only, by construction: there is deliberately NO send tool here (and none in
`mailbox.py` beneath it) — `draft_email` saves a draft the human reviews and sends.

Run standalone for debugging:  python mail_mcp.py  (speaks MCP JSON-RPC on stdio).
IMPORTANT: never print to stdout in this module — FastMCP owns stdout as the
JSON-RPC channel; any diagnostics must go to stderr.
"""

from __future__ import annotations

import os
import sys

# The CLI spawns this server from the vault root (its cwd); make sure our own
# folder is importable so `import agent`/`mailbox` resolve regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent  # noqa: E402 — needs the sys.path fix above

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("mailbox")


@mcp.tool()
def list_inboxes() -> str:
    """List the connected email inboxes (Gmail/Outlook) with their account ids,
    addresses, and unread counts. Call this first to get the account_id the other
    email tools need."""
    return agent._tool_list_inboxes()


@mcp.tool()
def read_inbox(account_id: str, limit: int = 10) -> str:
    """List recent messages in an inbox (newest first). Returns each message's id,
    sender, subject, date, and unread flag. account_id comes from list_inboxes."""
    return agent._tool_read_inbox(account_id=account_id, limit=limit)


@mcp.tool()
def search_email(account_id: str, query: str, limit: int = 10) -> str:
    """Search an inbox for messages matching a query (sender, subject, or body —
    Gmail search syntax like `is:unread newer_than:2d` works). Returns matching
    message ids + headers. account_id comes from list_inboxes."""
    return agent._tool_search_email(account_id=account_id, query=query, limit=limit)


@mcp.tool()
def read_email(account_id: str, msg_id: str) -> str:
    """Read one full email (headers + body) by its message id within an account.
    msg_id comes from read_inbox/search_email."""
    return agent._tool_read_email(account_id=account_id, msg_id=msg_id)


@mcp.tool()
def draft_email(account_id: str, to: str = "", subject: str = "",
                body: str = "", reply_to: str = "") -> str:
    """Save a DRAFT email (it is never sent — the user reviews and sends it from
    their mail client). Provide either `to` (recipients, comma-separated) for a new
    message, or `reply_to` (a message id) to draft a threaded reply."""
    return agent._tool_draft_email(account_id=account_id, to=to, subject=subject,
                                   body=body, reply_to=reply_to)


@mcp.tool()
def stage_email_draft(account_id: str, to: str = "", subject: str = "",
                      body: str = "", reply_to: str = "") -> str:
    """Propose a draft for a dispatch review gate without saving it yet."""
    return agent._tool_stage_email_draft(
        account_id=account_id, to=to, subject=subject, body=body, reply_to=reply_to,
    )


if __name__ == "__main__":
    mcp.run()  # stdio transport (FastMCP default)
