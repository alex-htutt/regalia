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

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# Make app.py / agent.py importable no matter where the tests run from.
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import agent  # noqa: E402
import app as dashboard_app  # noqa: E402
import chats  # noqa: E402
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


class MailboxMcpBridgeTests(unittest.TestCase):
    """v1.22: the claude tier reaches the mailbox over MCP (mail_mcp.py).

    Offline: router.claude_code_stream is stubbed to capture what the runner
    passes it — nothing spawns the CLI or the MCP server. Proves the wiring:
    email agents get an mcp_config + only mcp__mailbox__* grants; vault agents
    are unchanged; the temp config is cleaned up after the run.
    """

    DONE = [{"type": "result", "subtype": "success", "is_error": False, "result": "ok"}]

    def _run_capturing(self, agent_id):
        seen = {}
        original = router.claude_code_stream

        def fake(prompt, **kw):
            seen.update(kw)
            # The temp config must exist while the CLI would be running.
            cfg = kw.get("mcp_config")
            seen["config_existed_during_run"] = bool(cfg) and Path(cfg).is_file()
            if cfg:
                seen["config_json"] = json.loads(Path(cfg).read_text(encoding="utf-8"))
            return iter(self.DONE)

        router.claude_code_stream = fake
        try:
            agent.run_agent(agent_id, "triage", tier="claude", emit=None)
        finally:
            router.claude_code_stream = original
        return seen

    def test_mailbox_mcp_config_shape(self):
        path = agent._mailbox_mcp_config()
        try:
            cfg = json.loads(Path(path).read_text(encoding="utf-8"))
            server = cfg["mcpServers"]["mailbox"]
            self.assertEqual(server["command"], sys.executable)
            self.assertTrue(server["args"][0].endswith("mail_mcp.py"))
            self.assertTrue(Path(server["args"][0]).is_file())
        finally:
            Path(path).unlink(missing_ok=True)

    def test_email_agent_gets_mcp_and_only_mailbox_tools(self):
        seen = self._run_capturing("inbox_triage")
        self.assertTrue(seen["config_existed_during_run"])
        self.assertIn("mailbox", seen["config_json"]["mcpServers"])
        allowed = seen["allowed_tools"]
        for t in agent.EMAIL_TOOL_NAMES:
            self.assertIn(f"mcp__mailbox__{t}", allowed)
        # Email-only agent: no filesystem tools at all.
        for t in ("Read", "Grep", "Glob", "Write", "Edit", "Bash"):
            self.assertNotIn(t, allowed)
        # Temp config is deleted once the run finishes.
        self.assertFalse(Path(seen["mcp_config"]).exists())

    def test_vault_agent_unchanged_no_mcp(self):
        seen = self._run_capturing("summarizer")
        self.assertIsNone(seen.get("mcp_config"))
        self.assertIn("Read", seen["allowed_tools"])
        self.assertFalse(any(t.startswith("mcp__") for t in seen["allowed_tools"]))

    def test_inbox_triage_defaults_to_claude(self):
        self.assertEqual(agent.AGENTS["inbox_triage"]["tier"], "claude")

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "mcp SDK not installed")
    def test_mail_mcp_imports_and_registers_no_send(self):
        import mail_mcp
        self.assertFalse(hasattr(mail_mcp, "send_email"))
        self.assertFalse(hasattr(mail_mcp, "send"))


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


class ImportantMailTests(unittest.TestCase):
    """v1.23: the overview's Important-mail panel — deterministic scoring + route.

    Offline: list_accounts/fetch_inbox are mocked; the scorer and date parser are
    pure. Proves work/school mail scores in, marketing scores out, the date
    cutoff drops stale mail, and the route degrades with no inbox connected.
    """

    def test_scorer_boosts_school_and_work(self):
        score, why = mailbox._importance_score({
            "subject": "Assignment 3 due Friday", "snippet": "submission deadline",
            "from": "prof@rpi.edu", "unread": True})
        self.assertGreaterEqual(score, email_sources.IMPORTANT_MIN_SCORE)
        self.assertIn("assignment", why)
        self.assertIn(".edu", why)

    def test_scorer_penalizes_marketing(self):
        score, _ = mailbox._importance_score({
            "subject": "50% off sale — free shipping!", "snippet": "unsubscribe here",
            "from": "deals@shop.com", "unread": True})
        self.assertLess(score, email_sources.IMPORTANT_MIN_SCORE)

    def test_parse_msg_date_both_formats(self):
        rfc = mailbox._parse_msg_date("Fri, 10 Jul 2026 09:30:00 -0400")
        iso = mailbox._parse_msg_date("2026-07-10T13:30:00Z")
        self.assertEqual(rfc, iso)
        self.assertIsNone(mailbox._parse_msg_date("not a date"))

    def test_important_messages_filters_and_sorts(self):
        orig_accounts, orig_fetch = mailbox.list_accounts, mailbox.fetch_inbox
        from datetime import datetime, timedelta, timezone
        fresh = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000")
        stale = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000")
        mailbox.list_accounts = lambda: [
            {"id": "gmail-x", "provider": "gmail", "address": "x@gmail.com"}]
        mailbox.fetch_inbox = lambda aid, limit=25, query="": {"messages": [
            {"id": "m1", "subject": "Interview schedule", "snippet": "onboarding",
             "from": "HR <hr@corp.com>", "date": fresh, "unread": True},
            {"id": "m2", "subject": "Exam deadline", "snippet": "",
             "from": "prof@rpi.edu", "date": stale, "unread": True},   # too old
            {"id": "m3", "subject": "Weekend sale", "snippet": "unsubscribe",
             "from": "promo@shop.com", "date": fresh, "unread": False},  # junk
        ]}
        try:
            out = mailbox.important_messages()
        finally:
            mailbox.list_accounts, mailbox.fetch_inbox = orig_accounts, orig_fetch
        self.assertTrue(out["available"])
        self.assertEqual([m["subject"] for m in out["messages"]], ["Interview schedule"])
        self.assertEqual(out["messages"][0]["from"], "HR")
        self.assertEqual(out["messages"][0]["account"], "x")

    def test_route_degrades_with_no_accounts(self):
        dashboard_app.app.config["TESTING"] = True
        client = dashboard_app.app.test_client()
        orig = mailbox.list_accounts
        mailbox.list_accounts = lambda: []
        try:
            r = client.get("/api/mail/important")
        finally:
            mailbox.list_accounts = orig
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["available"])
        self.assertEqual(body["messages"], [])


class ChatStoreTests(unittest.TestCase):
    """Multi-chat store (v1.20): CRUD round-trip + traversal-guarded ids.

    The store is pointed at a temp dir so tests never touch real transcripts.
    """

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        self._orig_dir = chats.CHATS_DIR
        self._tmp = tempfile.TemporaryDirectory()
        chats.CHATS_DIR = Path(self._tmp.name)

    def tearDown(self):
        chats.CHATS_DIR = self._orig_dir
        self._tmp.cleanup()

    def test_list_chats_shape(self):
        r = self.client.get("/api/chats")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json().get("chats"), list)

    def test_crud_round_trip(self):
        # create
        r = self.client.post("/api/chats")
        self.assertEqual(r.status_code, 200)
        obj = r.get_json()
        cid = obj["id"]
        self.assertRegex(cid, r"^c_[0-9a-f]{32}$")
        # save with messages → title derived from the first user turn
        obj["messages"] = [{"role": "user", "content": "hello store"},
                           {"role": "assistant", "content": "hi", "model": "m"}]
        r = self.client.put(f"/api/chats/{cid}", json=obj)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["title"], "hello store")
        # load
        r = self.client.get(f"/api/chats/{cid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["messages"]), 2)
        # listed, most recent first, metadata only
        listed = self.client.get("/api/chats").get_json()["chats"]
        self.assertEqual(listed[0]["id"], cid)
        self.assertEqual(listed[0]["messages"], 2)   # count, not bodies
        # delete
        r = self.client.delete(f"/api/chats/{cid}")
        self.assertTrue(r.get_json()["deleted"])
        self.assertEqual(self.client.get(f"/api/chats/{cid}").status_code, 404)

    def test_missing_chat_404(self):
        self.assertEqual(self.client.get("/api/chats/c_" + "0" * 32).status_code, 404)

    def test_bad_id_rejected(self):
        # anything that isn't a minted c_<hex32> id is refused before touching disk
        for bad in ("..", "../../etc", "c_short", "C_" + "A" * 32, "c_" + "g" * 32):
            with self.assertRaises(chats.ChatStoreError) as ctx:
                chats._chat_path(bad)
            self.assertEqual(ctx.exception.status, 400)
        # and through the route: a bad id on PUT is a 400, never a write
        r = self.client.put("/api/chats/c_evil", json={"messages": []})
        self.assertEqual(r.status_code, 400)

    def test_put_body_id_cannot_redirect_write(self):
        cid = self.client.post("/api/chats").get_json()["id"]
        other = "c_" + "f" * 32
        self.client.put(f"/api/chats/{cid}",
                        json={"id": other, "messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(self.client.get(f"/api/chats/{other}").status_code, 404)
        self.assertEqual(len(self.client.get(f"/api/chats/{cid}").get_json()["messages"]), 1)


class SettingsTests(unittest.TestCase):
    """The settings store round-trips, rejects junk, and never leaks secrets."""

    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        # Isolate every test from the real (gitignored) store.
        import tempfile
        import config
        self._config = config
        self._orig_path = config.CONFIG_PATH
        self._tmp = tempfile.TemporaryDirectory()
        config.CONFIG_PATH = Path(self._tmp.name) / ".config.json"

    def tearDown(self):
        self._config.CONFIG_PATH = self._orig_path
        self._tmp.cleanup()

    def test_get_returns_defaults_and_vault_root(self):
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["settings"]["theme"], "dark")
        self.assertTrue(d["vault_root"])

    def test_post_round_trips(self):
        r = self.client.post("/api/settings", json={"theme": "light", "accent": "#a06a24",
                                                    "default_tier": "claude",
                                                    "landing_enabled": False})
        self.assertEqual(r.status_code, 200)
        d = self.client.get("/api/settings").get_json()["settings"]
        self.assertEqual(d["theme"], "light")
        self.assertEqual(d["accent"], "#a06a24")
        self.assertEqual(d["default_tier"], "claude")
        self.assertFalse(d["landing_enabled"])

    def test_unknown_key_rejected(self):
        r = self.client.post("/api/settings", json={"evil": 1})
        self.assertEqual(r.status_code, 400)

    def test_bad_values_rejected(self):
        self.assertEqual(
            self.client.post("/api/settings", json={"theme": "solarized"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"accent": "red"}).status_code, 400)

    def test_secrets_are_never_returned(self):
        self.client.post("/api/settings", json={"anthropic_api_key": "sk-ant-secret123"})
        raw = self.client.get("/api/settings").get_data(as_text=True)
        self.assertNotIn("secret123", raw)
        d = json.loads(raw)["settings"]
        self.assertEqual(d["anthropic_api_key"], {"set": True})
        # ...but the store itself resolves it (env, then file)
        self.assertEqual(
            self._config.secret("anthropic_api_key", "NO_SUCH_ENV_VAR__"), "sk-ant-secret123")

    def test_secret_clears_with_empty_string(self):
        self.client.post("/api/settings", json={"openai_api_key": "sk-x"})
        self.client.post("/api/settings", json={"openai_api_key": ""})
        d = self.client.get("/api/settings").get_json()["settings"]
        self.assertEqual(d["openai_api_key"], {"set": False})

    def test_router_status_includes_openai(self):
        d = self.client.get("/api/router/status").get_json()
        self.assertIn("openai", d)
        self.assertEqual(d["openai"]["backend"], "openai")
        self.assertIn("available", d["openai"])

    def test_openai_key_from_store_flips_availability(self):
        import os
        if os.environ.get("OPENAI_API_KEY"):
            self.skipTest("environment already carries an OpenAI key")
        self.assertFalse(self.client.get("/api/router/status").get_json()["openai"]["available"])
        self.client.post("/api/settings", json={"openai_api_key": "sk-test"})
        self.assertTrue(self.client.get("/api/router/status").get_json()["openai"]["available"])

    def test_connect_email_validates_provider(self):
        r = self.client.post("/api/connect/email", json={"provider": "carrier-pigeon"})
        self.assertEqual(r.status_code, 400)
        r = self.client.get("/api/connect/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.get_json()["state"], ("idle", "running", "done", "error"))

    def test_openai_chat_requires_key(self):
        import os
        if os.environ.get("OPENAI_API_KEY"):
            self.skipTest("environment already carries an OpenAI key")
        with self.assertRaises(router.RouterError) as ctx:
            router.chat([{"role": "user", "content": "hi"}], tier="openai")
        self.assertEqual(ctx.exception.status, 401)

    def test_new_chat_uses_default_tier(self):
        self.client.post("/api/settings", json={"default_tier": "claude"})
        cid = None
        try:
            d = self.client.post("/api/chats").get_json()
            cid = d["id"]
            self.assertEqual(d["tier"], "claude")
        finally:
            if cid:
                self.client.delete(f"/api/chats/{cid}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
