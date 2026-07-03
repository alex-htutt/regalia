"""Smoke tests — the trust floor for unattended automation.

First tests in the repo (PRODUCT_VISION.md, Horizon 1, Theme ③). Pure stdlib
`unittest` so they add no dependency, per dashboard/CLAUDE.md's no-new-deps rule.
They pin down two things the rest of the roadmap leans on before we let agents
run unattended on a schedule:

  1. Every read-only endpoint still returns 200 with well-formed JSON.
  2. The vault-confined agent tools refuse to escape the vault (path traversal),
     and the folder browser does too.

Run from the dashboard/ folder:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make app.py / agent.py importable no matter where the tests run from.
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import agent  # noqa: E402
import app as dashboard_app  # noqa: E402
import email_sources  # noqa: E402
import mailbox  # noqa: E402
import router  # noqa: E402


class RouteSmokeTests(unittest.TestCase):
    """Every read-only endpoint returns 200 and the expected JSON shape."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def test_index_renders(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_api_tasks_returns_list(self):
        r = self.client.get("/api/tasks")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)

    def test_api_browse_root(self):
        r = self.client.get("/api/browse")
        self.assertEqual(r.status_code, 200)
        self.assertIn("folders", r.get_json())

    def test_api_usage_returns_dict(self):
        r = self.client.get("/api/usage")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), dict)

    def test_api_agents_returns_registry(self):
        r = self.client.get("/api/agents")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json().get("agents"), list)

    def test_api_router_status(self):
        self.assertEqual(self.client.get("/api/router/status").status_code, 200)


class BrowseTraversalTests(unittest.TestCase):
    """The folder browser must not serve anything outside the vault."""

    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def test_parent_escape_rejected(self):
        self.assertEqual(self.client.get("/api/browse?path=../..").status_code, 400)

    def test_backslash_escape_rejected(self):
        # backslashes are normalized to '/', then resolved — must still be caught.
        r = self.client.get("/api/browse?path=..\\..\\..\\Windows")
        self.assertIn(r.status_code, (400, 404))


class AgentToolSafetyTests(unittest.TestCase):
    """Vault tools are confined + traversal-safe (the trust floor for cron agents).

    The traversal cases must fail *before* touching the filesystem, so none of
    these create or read a file outside the vault.
    """

    def test_safe_path_allows_in_vault(self):
        p = agent._safe_path("dashboard/app.py", must_exist=True)
        self.assertTrue(str(p).replace("\\", "/").endswith("dashboard/app.py"))

    def test_safe_path_rejects_parent_traversal(self):
        with self.assertRaises(agent.AgentError):
            agent._safe_path("../../secret.md")

    def test_safe_path_rejects_backslash_traversal(self):
        with self.assertRaises(agent.AgentError):
            agent._safe_path("..\\..\\secret.md")

    def test_safe_path_rejects_empty(self):
        with self.assertRaises(agent.AgentError):
            agent._safe_path("")

    def test_read_note_blocks_escape(self):
        with self.assertRaises(agent.AgentError):
            agent._tool_read_note(path="../../../etc/passwd")

    def test_write_note_blocks_escape(self):
        with self.assertRaises(agent.AgentError):
            agent._tool_write_note(path="../../escape.md", content="should never land")

    def test_write_note_refuses_non_md(self):
        self.assertIn("Error", agent._tool_write_note(path="notes/x.txt", content="x"))

    def test_write_note_refuses_empty(self):
        self.assertIn("Error", agent._tool_write_note(path="notes/x.md", content="   "))


class AgentRegistryTests(unittest.TestCase):
    """The agent registry stays internally consistent."""

    def test_list_agents_shape(self):
        agents = agent.list_agents()
        self.assertGreaterEqual(len(agents), 1)
        for a in agents:
            self.assertEqual({"id", "name", "desc", "tier", "status"}, set(a))

    def test_every_agent_tool_is_registered(self):
        for spec in agent.AGENTS.values():
            for tool in spec["tools"]:
                self.assertIn(tool, agent.TOOL_SCHEMAS, f"{spec['id']}: no schema for {tool}")
                self.assertIn(tool, agent.TOOL_FNS, f"{spec['id']}: no impl for {tool}")


class ClaudeAgentTierTests(unittest.TestCase):
    """The subscription `claude` tier routes the Agents view through the streamed
    CLI runner (not the in-process tool loop) and maps its events to step events.

    Offline: router.claude_code_stream is stubbed with canned CLI-shaped events, so
    nothing spawns the real CLI or hits the network.
    """

    # CLI stream-json events, in the shape claude_code_stream yields them.
    FAKE_STREAM = [
        {"type": "system", "subtype": "init", "model": "claude-test"},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "thinking"},
            {"type": "tool_use", "id": "t1", "name": "Glob", "input": {"pattern": "*.md"}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "a.md\nb.md"},
        ]}},
        {"type": "result", "subtype": "success", "is_error": False, "result": "done: 2 notes"},
    ]

    def _run(self):
        original = router.claude_code_stream
        router.claude_code_stream = lambda *a, **k: iter(self.FAKE_STREAM)
        events = []
        try:
            res = agent.run_agent("summarizer", "count notes", tier="claude",
                                  emit=events.append)
        finally:
            router.claude_code_stream = original
        return res, events

    def test_claude_tier_not_coerced(self):
        res, _ = self._run()
        self.assertEqual(res["tier"], "claude")
        self.assertEqual(res["reply"], "done: 2 notes")
        self.assertEqual(res["model"], "claude-test")

    def test_stream_maps_to_step_events(self):
        res, events = self._run()
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "start")
        self.assertIn("tool", types)
        self.assertIn("tool_result", types)
        self.assertEqual(types[-1], "final")
        # The tool_result is labeled with the tool name from its matching tool_use.
        self.assertEqual(res["steps"], [{"tool": "Glob", "input": {}, "output": "a.md\nb.md"}])

    def test_tool_result_text_coerces_blocks(self):
        self.assertEqual(agent._tool_result_text("plain"), "plain")
        self.assertEqual(
            agent._tool_result_text([{"type": "text", "text": "x"}, {"type": "text", "text": "y"}]),
            "x\ny",
        )


class EmailDraftsOnlyTests(unittest.TestCase):
    """Write scope is drafts-only by construction — there is no send path anywhere.

    This is the email trust floor: an agent or a bug can create a draft, but
    nothing in the codebase can put a message in the outbox.
    """

    def test_no_send_function_in_mailbox(self):
        for name in ("send", "send_message", "send_email", "send_draft"):
            self.assertFalse(hasattr(mailbox, name), f"mailbox must not expose {name}()")

    def test_no_send_tool_registered(self):
        for name in ("send", "send_email", "send_message"):
            self.assertNotIn(name, agent.TOOL_FNS)
            self.assertNotIn(name, agent.TOOL_SCHEMAS)

    def test_graph_scopes_omit_mail_send(self):
        # Without Mail.Send the Outlook token literally cannot send.
        self.assertNotIn("Mail.Send", email_sources.MS_SCOPES)

    def test_gmail_scopes_omit_send_scope(self):
        self.assertFalse(any("gmail.send" in s for s in email_sources.GMAIL_SCOPES))

    def test_draft_email_tool_says_not_sent(self):
        # Stub create_draft so no network is touched; the tool must signal "not sent".
        original = mailbox.create_draft
        mailbox.create_draft = lambda *a, **k: {"ok": True, "id": "d1", "provider": "gmail",
                                                "account_id": k.get("account_id", "x"), "link": ""}
        try:
            out = agent._tool_draft_email(account_id="gmail-x", to="a@b.com", body="hi")
        finally:
            mailbox.create_draft = original
        self.assertIn("NOT sent", out)

    def test_draft_email_not_in_readonly_chat_tools(self):
        # A read-only chat turn must never be able to draft. draft_email is a write
        # tool, gated like write_note — only agents that opt in receive it.
        self.assertNotIn("draft_email", agent.CHAT_TOOLS)


class MailboxSafetyTests(unittest.TestCase):
    """Token store is traversal-safe and tokens never leak into API output."""

    def test_account_path_rejects_traversal(self):
        for bad in ("../evil", "..\\evil", "a/b", "sub/../x"):
            with self.assertRaises(mailbox.MailboxError):
                mailbox._account_path(bad)

    def test_account_path_stays_in_store(self):
        p = mailbox._account_path("gmail-ok_example_com")
        self.assertEqual(p.parent, mailbox.TOKENS_DIR.resolve())

    def test_tokens_never_leak_in_account_listing(self):
        # Plant a fake account file carrying a secret token, then confirm neither
        # list_accounts nor accounts_overview echoes the token back.
        import json as _json
        mailbox.TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        path = mailbox.TOKENS_DIR / "gmail-leakcheck_example_com.json"
        path.write_text(_json.dumps({
            "id": "gmail-leakcheck_example_com", "provider": "gmail",
            "address": "leakcheck@example.com",
            "google": {"token": "SECRET_DO_NOT_LEAK", "refresh_token": "RT_SECRET"},
        }), encoding="utf-8")
        try:
            accts = mailbox.list_accounts()
            overview = mailbox.accounts_overview()  # refresh fails gracefully (no net)
        finally:
            path.unlink(missing_ok=True)
        blob = _json.dumps(accts) + _json.dumps(overview)
        self.assertNotIn("SECRET_DO_NOT_LEAK", blob)
        self.assertNotIn("RT_SECRET", blob)
        # The planted account is still surfaced (metadata only).
        self.assertTrue(any(a["id"] == "gmail-leakcheck_example_com" for a in accts))


class EmailRouteTests(unittest.TestCase):
    """The email endpoints return the right shapes; mailbox is stubbed (no network)."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        self._orig = {n: getattr(mailbox, n) for n in
                      ("accounts_overview", "fetch_inbox", "read_message", "create_draft")}

    def tearDown(self):
        for n, fn in self._orig.items():
            setattr(mailbox, n, fn)

    def test_api_inboxes_shape(self):
        mailbox.accounts_overview = lambda: {"accounts": [
            {"id": "gmail-x", "provider": "gmail", "address": "x@y.com", "unread": 3, "status": "ok"}],
            "errors": []}
        r = self.client.get("/api/inboxes")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["accounts"][0]["unread"], 3)

    def test_api_inbox_lists_messages(self):
        mailbox.fetch_inbox = lambda account_id, limit=25, query="": {
            "account": {"id": account_id}, "query": query,
            "messages": [{"id": "m1", "from": "a@b.com", "subject": "Hi", "unread": True}]}
        r = self.client.get("/api/inbox/gmail-x")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["messages"][0]["id"], "m1")

    def test_api_inbox_propagates_error_status(self):
        def boom(*a, **k):
            raise mailbox.MailboxError("reconnect needed", 401)
        mailbox.fetch_inbox = boom
        r = self.client.get("/api/inbox/gmail-x")
        self.assertEqual(r.status_code, 401)
        self.assertIn("error", r.get_json())

    def test_api_draft_requires_account(self):
        r = self.client.post("/api/email/draft", json={"to": "a@b.com"})
        self.assertEqual(r.status_code, 400)

    def test_api_draft_creates(self):
        seen = {}
        def fake(account_id, to="", subject="", body="", reply_to_msg_id=""):
            seen.update(account_id=account_id, to=to, reply=reply_to_msg_id)
            return {"ok": True, "id": "d9", "provider": "gmail", "account_id": account_id, "link": ""}
        mailbox.create_draft = fake
        r = self.client.post("/api/email/draft",
                             json={"account_id": "gmail-x", "to": "a@b.com", "body": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["id"], "d9")
        self.assertEqual(seen["account_id"], "gmail-x")


class HermesRetrievalTests(unittest.TestCase):
    """M3: the Hermes email-skill retrieval path maps JSON onto the frozen shapes.

    The Hermes subprocess is never spawned — we exercise the pure mappers and
    `_extract_json` directly, and mock the `_hermes_skill` seam to prove fetch/read
    route through Hermes (and keep the same message dicts) when the backend flips.
    """

    SEARCH_ITEM = {
        "id": "m1", "threadId": "t1", "from": "a@b.com", "to": "me@x.com",
        "subject": "Hi", "date": "Mon, 30 Jun 2026", "snippet": "hello there",
        "labels": ["INBOX", "UNREAD"],
    }

    def test_extract_json_raw_array(self):
        self.assertEqual(mailbox._extract_json('[{"id": "m1"}]'), [{"id": "m1"}])

    def test_extract_json_tolerates_fence_and_prose(self):
        reply = 'Sure, here it is:\n```json\n[{"id": "m1"}]\n```\nDone.'
        self.assertEqual(mailbox._extract_json(reply), [{"id": "m1"}])

    def test_extract_json_empty_raises(self):
        with self.assertRaises(mailbox.MailboxError):
            mailbox._extract_json("   ")

    def test_extract_json_no_json_raises(self):
        with self.assertRaises(mailbox.MailboxError):
            mailbox._extract_json("no json here at all")

    def test_summary_mapping_shape_and_unread(self):
        msg = mailbox._hermes_msg(self.SEARCH_ITEM)
        self.assertEqual(set(msg),
                         {"id", "thread_id", "from", "subject", "date", "snippet", "unread"})
        self.assertEqual(msg["thread_id"], "t1")
        self.assertTrue(msg["unread"])  # derived from the UNREAD label

    def test_summary_mapping_read_when_no_unread_label(self):
        item = {**self.SEARCH_ITEM, "labels": ["INBOX"]}
        self.assertFalse(mailbox._hermes_msg(item)["unread"])

    def test_full_mapping_adds_to_and_body(self):
        item = {**self.SEARCH_ITEM, "body": "full body text"}
        msg = mailbox._hermes_msg(item, full=True)
        self.assertEqual(msg["to"], "me@x.com")
        self.assertEqual(msg["body"], "full body text")

    def test_missing_subject_defaults(self):
        self.assertEqual(mailbox._hermes_msg({"id": "m1"})["subject"], "(no subject)")

    def test_fetch_inbox_routes_to_hermes(self):
        orig_backend, orig_skill = email_sources.MAILBOX_BACKEND, mailbox._hermes_skill
        email_sources.MAILBOX_BACKEND = "hermes"
        mailbox._hermes_skill = lambda cmd: [self.SEARCH_ITEM]
        mailbox._CACHE.clear()
        try:
            out = mailbox.fetch_inbox("gmail", limit=5)
        finally:
            email_sources.MAILBOX_BACKEND = orig_backend
            mailbox._hermes_skill = orig_skill
            mailbox._CACHE.clear()
        self.assertEqual(len(out["messages"]), 1)
        self.assertEqual(out["messages"][0]["id"], "m1")
        self.assertTrue(out["messages"][0]["unread"])

    def test_read_message_routes_to_hermes(self):
        orig_backend, orig_skill = email_sources.MAILBOX_BACKEND, mailbox._hermes_skill
        email_sources.MAILBOX_BACKEND = "hermes"
        mailbox._hermes_skill = lambda cmd: {**self.SEARCH_ITEM, "body": "B"}
        try:
            msg = mailbox.read_message("gmail", "m1")
        finally:
            email_sources.MAILBOX_BACKEND = orig_backend
            mailbox._hermes_skill = orig_skill
        self.assertEqual(msg["body"], "B")
        self.assertEqual(msg["to"], "me@x.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)
