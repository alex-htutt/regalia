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


if __name__ == "__main__":
    unittest.main(verbosity=2)
