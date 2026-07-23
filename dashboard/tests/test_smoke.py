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
import os
import sys
import unittest
from unittest import mock
from pathlib import Path

# Keep the launch-time update check off during tests — importing app runs it, and
# it must never make a real network call from the smoke suite. (Set before the
# app import below so updater.startup() sees it.)
os.environ.setdefault("REGALIA_UPDATE_CHECK", "0")

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
import updater  # noqa: E402
import version  # noqa: E402


class RouteSmokeTests(unittest.TestCase):
    """Every read-only endpoint returns 200 and the expected JSON shape."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def test_index_renders(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_index_includes_vault_graph_shell_and_local_d3(self):
        body = self.client.get("/").get_data(as_text=True)
        for marker in ('id="vault-graph"', 'id="vault-tree"', 'id="vault-inspector"',
                       '/static/d3.v7.9.0.min.js', '/static/icon-anthropic.svg',
                       '/static/icon-openai.svg', "fetch('/api/vault-activity')",
                       '.vault-graph-state[hidden]', 'vaultSetFolderExpanded', '📁'):
            self.assertIn(marker, body)
        for path in ("/static/d3.v7.9.0.min.js", "/static/icon-anthropic.svg", "/static/icon-openai.svg"):
            asset = self.client.get(path)
            self.assertEqual(asset.status_code, 200)
            asset.close()

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

    def test_api_update_shape(self):
        r = self.client.get("/api/update")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        for key in ("checked", "current", "latest", "out_of_date",
                    "can_self_update", "releases_url", "apply"):
            self.assertIn(key, d)
        self.assertEqual(d["current"], version.__version__)
        self.assertIn(d["apply"].get("state"), ("idle", "running", "done", "error"))
        # No 'asset_url' must leak out of the internal state into the API shape.
        self.assertNotIn("asset_url", d)


class VersionCompareTests(unittest.TestCase):
    """The release comparison drives the whole 'out of date' decision."""

    def test_newer_and_older(self):
        self.assertTrue(version.is_newer("v1.30", "1.29"))
        self.assertTrue(version.is_newer("1.29.1", "1.29"))
        self.assertFalse(version.is_newer("v1.28", "1.29"))
        self.assertFalse(version.is_newer("v1.29", "1.29"))     # equal, not newer
        self.assertFalse(version.is_newer("1.29.0", "1.29"))    # zero-pads equal

    def test_garbage_never_raises(self):
        # A malformed tag must degrade to a comparison, never an exception.
        self.assertFalse(version.is_newer("", "1.29"))
        self.assertFalse(version.is_newer("not-a-version", "1.29"))


class UpdateApplyFromSourceTests(unittest.TestCase):
    """From source there is no binary to swap — apply() must be a safe no-op."""

    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def test_apply_from_source_is_noop(self):
        # The test process is not frozen, so this must not try to touch any file.
        self.assertFalse(updater.is_frozen())
        r = self.client.post("/api/update/apply")
        self.assertEqual(r.status_code, 409)          # nothing started
        d = r.get_json()
        self.assertFalse(d.get("started"))
        self.assertEqual(d.get("reason"), "source")
        self.assertEqual(d["update"]["apply"]["state"], "error")


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


class VaultMapTests(unittest.TestCase):
    """The visual browser maps every relevant type without escaping the vault."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        self._orig_root = dashboard_app.VAULT_ROOT
        self._tmp = tempfile.TemporaryDirectory()
        dashboard_app.VAULT_ROOT = Path(self._tmp.name)
        root = Path(self._tmp.name)
        (root / "Projects" / "App").mkdir(parents=True)
        (root / "Notes").mkdir()
        (root / ".hidden").mkdir()
        (root / "dashboard").mkdir()
        (root / "Home.md").write_text(
            "# Home\n[[Projects/App/context|App]]\n", encoding="utf-8"
        )
        (root / "Projects" / "App" / "context.md").write_text(
            "# App\n![Diagram](diagram.png)\n[[unique]]\n", encoding="utf-8"
        )
        (root / "Projects" / "App" / "diagram.png").write_bytes(b"\x89PNG\r\n")
        (root / "Projects" / "App" / "data.json").write_text('{"ok": true}', encoding="utf-8")
        (root / "Projects" / "App" / "manual.pdf").write_bytes(b"%PDF-1.4")
        (root / "Notes" / "unique.md").write_text("# Unique", encoding="utf-8")
        (root / "Notes" / "CLAUDE.md").write_text("ignored", encoding="utf-8")
        (root / ".hidden" / "secret.txt").write_text("hidden", encoding="utf-8")
        (root / "dashboard" / "app.py").write_text("ignored", encoding="utf-8")

    def tearDown(self):
        dashboard_app.VAULT_ROOT = self._orig_root
        self._tmp.cleanup()

    def test_map_has_home_hierarchy_non_markdown_and_authored_links(self):
        response = self.client.get("/api/vault-map")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["root"], "file:Home.md")
        nodes = {node["path"]: node for node in data["nodes"]}
        self.assertEqual(nodes["Home.md"]["kind"], "home")
        self.assertEqual(nodes["Projects/App/diagram.png"]["preview_kind"], "image")
        self.assertEqual(nodes["Projects/App/data.json"]["preview_kind"], "text")
        self.assertIn("Projects/App/manual.pdf", nodes)
        self.assertNotIn("Notes/CLAUDE.md", nodes)
        self.assertNotIn(".hidden/secret.txt", nodes)
        self.assertNotIn("dashboard/app.py", nodes)

        edges = {(edge["source"], edge["target"], edge["kind"]) for edge in data["edges"]}
        self.assertIn(("file:Home.md", "folder:Projects", "branch"), edges)
        self.assertIn(("folder:Projects/App", "file:Projects/App/data.json", "contains"), edges)
        self.assertIn(("file:Home.md", "file:Projects/App/context.md", "link"), edges)
        self.assertIn(("file:Projects/App/context.md", "file:Projects/App/diagram.png", "link"), edges)
        self.assertIn(("file:Projects/App/context.md", "file:Notes/unique.md", "link"), edges)

    def test_ambiguous_bare_wikilink_is_omitted(self):
        root = Path(self._tmp.name)
        (root / "Projects" / "duplicate.md").write_text("# One", encoding="utf-8")
        (root / "Notes" / "duplicate.md").write_text("# Two", encoding="utf-8")
        (root / "Home.md").write_text("[[duplicate]]", encoding="utf-8")
        links = [e for e in self.client.get("/api/vault-map").get_json()["edges"] if e["kind"] == "link"]
        self.assertFalse(any(e["source"] == "file:Home.md" for e in links))

    def test_preview_text_image_unsupported_and_traversal(self):
        text = self.client.get("/api/vault-preview?path=Projects/App/data.json")
        self.assertEqual(text.status_code, 200)
        self.assertEqual(text.get_data(as_text=True), '{"ok": true}')
        self.assertEqual(text.headers["X-Preview-Truncated"], "0")
        image = self.client.get("/api/vault-preview?path=Projects/App/diagram.png")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/png")
        image.close()
        self.assertEqual(self.client.get("/api/vault-preview?path=Projects/App/manual.pdf").status_code, 415)
        self.assertEqual(self.client.get("/api/vault-preview?path=../../outside.txt").status_code, 400)
        self.assertEqual(self.client.get("/api/vault-preview?path=.hidden/secret.txt").status_code, 404)

    def test_text_preview_is_bounded(self):
        big = Path(self._tmp.name) / "Projects" / "App" / "large.txt"
        big.write_text("x" * (dashboard_app.BROWSER_PREVIEW_BYTES + 10), encoding="utf-8")
        response = self.client.get("/api/vault-preview?path=Projects/App/large.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), dashboard_app.BROWSER_PREVIEW_BYTES)
        self.assertEqual(response.headers["X-Preview-Truncated"], "1")


class VaultActivityTests(unittest.TestCase):
    """Running agents expose only normalized active-vault folders and edits."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        self._orig_root = dashboard_app.VAULT_ROOT
        self._orig_runs = dict(dashboard_app._RUNS)
        self._tmp = tempfile.TemporaryDirectory()
        dashboard_app.VAULT_ROOT = Path(self._tmp.name)
        (dashboard_app.VAULT_ROOT / "Projects" / "App").mkdir(parents=True)
        (dashboard_app.VAULT_ROOT / "Projects" / "App" / "main.py").write_text("pass", encoding="utf-8")
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS.clear()

    def tearDown(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS.clear()
            dashboard_app._RUNS.update(self._orig_runs)
        dashboard_app.VAULT_ROOT = self._orig_root
        self._tmp.cleanup()

    def test_classic_run_reports_scope_provider_and_edited_file(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS["r1"] = {
                "id": "r1", "agent": "researcher", "name": "Research Agent",
                "tier": "smart", "folder": "Projects/App", "status": "running",
                "steps": [
                    {"type": "tool", "tool": "write_file", "input": {"path": "main.py"}},
                    {"type": "tool", "tool": "write_file", "input": {"path": "../../escape.py"}},
                ],
            }
        with mock.patch.object(dashboard_app.dispatches, "list_dispatches", return_value=[]):
            response = self.client.get("/api/vault-activity")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["poll_ms"], 1200)
        self.assertEqual(len(data["activities"]), 1)
        activity = data["activities"][0]
        self.assertEqual(activity["provider"], "anthropic")
        self.assertEqual(activity["scope"], "Projects/App")
        self.assertEqual(activity["editing_paths"], ["Projects/App/main.py"])

    def test_local_run_is_not_mislabeled_as_a_cloud_provider(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS["r2"] = {
                "id": "r2", "agent": "summarizer", "name": "Daily Summarizer",
                "tier": "fast", "folder": "Projects", "status": "running", "steps": [],
            }
        with mock.patch.object(dashboard_app.dispatches, "list_dispatches", return_value=[]):
            activity = self.client.get("/api/vault-activity").get_json()["activities"][0]
        self.assertEqual(activity["provider"], "local")

    def test_running_dispatch_worker_reports_openai_edit(self):
        summary = [{"id": "d_test", "state": "running"}]
        dispatch = {
            "id": "d_test", "scope": "Projects/App", "workers": [{
                "id": "build", "title": "Builder", "status": "running",
                "tier": "chatgpt", "scope": "Projects/App", "capabilities": ["code_write"],
            }],
        }
        events = {"events": [{
            "type": "tool", "worker": "build", "tool": "file_change",
            "input": {"changes": [{"path": "main.py"}]},
        }]}
        with mock.patch.object(dashboard_app.dispatches, "list_dispatches", return_value=summary), \
             mock.patch.object(dashboard_app.dispatches, "get_dispatch", return_value=dispatch), \
             mock.patch.object(dashboard_app.dispatches, "events", return_value=events):
            activities = self.client.get("/api/vault-activity").get_json()["activities"]
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["provider"], "openai")
        self.assertEqual(activities[0]["editing_paths"], ["Projects/App/main.py"])

    def test_external_and_non_filesystem_runs_are_omitted(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS.update({
                "r3": {"id": "r3", "agent": "researcher", "name": "External",
                       "tier": "smart", "folder": "ext:client", "status": "running", "steps": []},
                "r4": {"id": "r4", "agent": "inbox_triage", "name": "Inbox",
                       "tier": "claude", "folder": "", "status": "running", "steps": []},
            })
        with mock.patch.object(dashboard_app.dispatches, "list_dispatches", return_value=[]):
            activities = self.client.get("/api/vault-activity").get_json()["activities"]
        self.assertEqual(activities, [])


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
            self.assertEqual(
                {"id", "name", "desc", "tier", "status", "presets", "folder_capable"},
                set(a),
            )
            self.assertIsInstance(a["presets"], list)
            self.assertIsInstance(a["folder_capable"], bool)

    def test_every_agent_tool_is_registered(self):
        for spec in agent.AGENTS.values():
            for tool in spec["tools"]:
                self.assertIn(tool, agent.TOOL_SCHEMAS, f"{spec['id']}: no schema for {tool}")
                self.assertIn(tool, agent.TOOL_FNS, f"{spec['id']}: no impl for {tool}")


class AgentRunUxTests(unittest.TestCase):
    """v1.28 Agents-tab UX backend: run listing, folder assignment, presets."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def test_agent_runs_listing_shape(self):
        r = self.client.get("/api/agent/runs")
        self.assertEqual(r.status_code, 200)
        runs = r.get_json()["runs"]
        self.assertIsInstance(runs, list)
        for run in runs:
            self.assertEqual(
                {"id", "agent", "name", "task", "tier", "folder", "status", "started"},
                set(run))
            self.assertNotIn("steps", run)

    def test_run_rejects_bad_folder(self):
        for bad in ("../..", "..\\..", "no_such_folder_xyz", "dashboard/app.py"):
            r = self.client.post("/api/agent/run",
                                 json={"agent": "summarizer", "task": "x", "folder": bad})
            self.assertEqual(r.status_code, 400, f"folder {bad!r} should be rejected")

    def test_folder_scope_reaches_the_model(self):
        # Stub the CLI stream and capture the prompt run_agent builds — the
        # assigned folder must be injected as a scope line ahead of the task.
        # Runs against a temp vault so the assertion is filesystem-independent.
        import tempfile
        seen = {}
        original = router.claude_code_stream

        def fake(prompt, **kw):
            seen["prompt"] = prompt
            return iter([{"type": "result", "subtype": "success",
                          "is_error": False, "result": "ok"}])

        router.claude_code_stream = fake
        orig_root = dashboard_app.VAULT_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "projects").mkdir()
            dashboard_app.VAULT_ROOT = Path(tmp)
            try:
                agent.run_agent("summarizer", "count notes", tier="claude",
                                folder="projects")
            finally:
                dashboard_app.VAULT_ROOT = orig_root
                router.claude_code_stream = original
        self.assertIn("only vault folder 'projects'", seen["prompt"])
        self.assertIn("count notes", seen["prompt"])

    def test_folder_traversal_rejected_in_run_agent(self):
        with self.assertRaises(agent.AgentError):
            agent.run_agent("summarizer", "x", tier="claude", folder="../../etc")

    def test_registry_presets_are_strings(self):
        for spec in agent.AGENTS.values():
            for p in spec.get("presets", []):
                self.assertIsInstance(p, str)
                self.assertTrue(p.strip())

    def test_email_only_agent_rejects_folder_scope(self):
        self.assertFalse(agent.supports_folder("inbox_triage"))
        r = self.client.post(
            "/api/agent/run",
            json={"agent": "inbox_triage", "task": "triage", "folder": "dashboard"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("no filesystem tools", r.get_json()["error"])


class AgentRunStoreTests(unittest.TestCase):
    """Run history keeps active work and supports incremental polling."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        with dashboard_app._RUNS_LOCK:
            self._original = dict(dashboard_app._RUNS)
            dashboard_app._RUNS.clear()

    def tearDown(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS.clear()
            dashboard_app._RUNS.update(self._original)

    @staticmethod
    def _run(run_id, status, number, steps=None):
        return {
            "id": run_id, "agent": "summarizer", "name": "Daily Summarizer",
            "task": "x", "tier": "fast", "folder": "", "status": status,
            "steps": list(steps or []), "result": None, "error": None,
            "started": f"2026-07-17T00:00:{number:02d}-07:00",
        }

    def test_trim_retains_all_active_and_newest_finished(self):
        with dashboard_app._RUNS_LOCK:
            for i in range(55):
                run_id = f"active{i}"
                dashboard_app._RUNS[run_id] = self._run(run_id, "running", i)
            for i in range(51):
                run_id = f"done{i}"
                dashboard_app._RUNS[run_id] = self._run(run_id, "done", i)
            dashboard_app._trim_runs_locked()
            ids = set(dashboard_app._RUNS)
        self.assertTrue({f"active{i}" for i in range(55)} <= ids)
        self.assertNotIn("done0", ids)
        self.assertTrue({f"done{i}" for i in range(1, 51)} <= ids)

    def test_status_cursor_returns_only_new_steps(self):
        events = [{"type": "think", "text": str(i)} for i in range(3)]
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS["cursor"] = self._run("cursor", "running", 1, events)
        r = self.client.get("/api/agent/run/cursor?after=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["steps"], events[1:])
        self.assertEqual(r.get_json()["cursor"], 3)
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS["cursor"]["steps"].append(
                {"type": "final", "text": "done"})
        r = self.client.get("/api/agent/run/cursor?after=3")
        self.assertEqual(len(r.get_json()["steps"]), 1)
        self.assertEqual(r.get_json()["cursor"], 4)
        self.assertEqual(self.client.get("/api/agent/run/cursor?after=4").get_json()["steps"], [])

    def test_status_cursor_rejects_invalid_values(self):
        with dashboard_app._RUNS_LOCK:
            dashboard_app._RUNS["cursor"] = self._run("cursor", "running", 1)
        for value in ("-1", "nope"):
            self.assertEqual(
                self.client.get(f"/api/agent/run/cursor?after={value}").status_code, 400)

    def test_client_has_terminal_404_and_incremental_polling(self):
        html = (Path(__file__).parents[1] / "templates" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("status === 404", html)
        self.assertIn("?after=", html)
        self.assertIn("This run expired or the app restarted.", html)


class ExternalFolderTests(unittest.TestCase):
    """v1.28 external folders: registry validation, vault-side context scaffolding,
    ext: path resolution, and the no-scaffolding-in-the-external-folder contract.
    Runs against a temp registry + temp vault + temp external dir throughout."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        import externals
        self.externals = externals
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        (base / "vault").mkdir()
        (base / "outside" / "proj").mkdir(parents=True)
        (base / "outside" / "other").mkdir()
        self._orig_store = externals.EXTERNALS_PATH
        self._orig_root = dashboard_app.VAULT_ROOT
        externals.EXTERNALS_PATH = base / ".external.json"
        dashboard_app.VAULT_ROOT = base / "vault"
        self.vault = base / "vault"
        self.outside = base / "outside" / "proj"
        self.other = base / "outside" / "other"

    def tearDown(self):
        self.externals.EXTERNALS_PATH = self._orig_store
        dashboard_app.VAULT_ROOT = self._orig_root
        self._tmp.cleanup()

    def test_add_validates(self):
        for name, path in (
            ("bad/name", str(self.outside)),
            ("ok", "relative/path"),
            ("ok", str(self.outside / "missing")),
            ("ok", str(self.vault)),          # inside the vault → pointless
            ("ok", str(self.vault.parent)),   # contains the vault → over-broad
            ("", str(self.outside)),
        ):
            with self.assertRaises(ValueError, msg=f"({name!r}, {path!r})"):
                self.externals.add(name, path, self.vault)
        self.assertEqual(self.externals.load(), {})

    def test_connect_scaffolds_vault_context_only(self):
        r = self.client.post("/api/external",
                             json={"name": "proj", "path": str(self.outside)})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["context_created"])
        context = self.vault / "external" / "proj" / "_context_proj.md"
        self.assertTrue(context.is_file())
        text = context.read_text(encoding="utf-8")
        self.assertIn("area/external", text)
        self.assertNotIn(str(self.outside), text)
        fm, _ = dashboard_app._parse_frontmatter(text)
        self.assertEqual(fm["topic"], "Connected external workspace")
        # The contract: nothing was written into the external folder itself.
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_connect_rejects_non_object_json(self):
        for body in (["proj", str(self.outside)], "proj", 7, None):
            if body is None:
                r = self.client.post(
                    "/api/external", data="null", content_type="application/json")
            else:
                r = self.client.post("/api/external", json=body)
            self.assertEqual(r.status_code, 400)
            self.assertIn("JSON object", r.get_json()["error"])
        self.assertEqual(self.externals.load(), {})

    def test_overlapping_external_roots_rejected(self):
        self.externals.add("proj", str(self.outside), self.vault)
        nested = self.outside / "nested"
        nested.mkdir()
        for name, path in (("same", self.outside), ("nested", nested),
                           ("parent", self.outside.parent)):
            with self.assertRaises(ValueError, msg=name):
                self.externals.add(name, str(path), self.vault)
        self.assertEqual(set(self.externals.load()), {"proj"})

    def test_context_symlink_escape_is_not_written(self):
        outside_context = self.other / "redirected"
        outside_context.mkdir()
        (self.vault / "external").mkdir()
        link = self.vault / "external" / "proj"
        try:
            link.symlink_to(outside_context, target_is_directory=True)
        except OSError as e:
            self.skipTest(f"directory symlinks unavailable: {e}")
        r = self.client.post("/api/external",
                             json={"name": "proj", "path": str(self.outside)})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["context_created"])
        self.assertIn("outside the vault", r.get_json()["warning"])
        self.assertEqual(list(outside_context.iterdir()), [])

    def test_duplicate_conflicts_and_delete_keeps_context(self):
        self.client.post("/api/external", json={"name": "proj", "path": str(self.outside)})
        r = self.client.post("/api/external", json={"name": "PROJ", "path": str(self.outside)})
        self.assertEqual(r.status_code, 409)
        r = self.client.delete("/api/external/proj")
        self.assertTrue(r.get_json()["kept_context"])
        self.assertEqual(self.externals.load(), {})
        self.assertTrue((self.vault / "external" / "proj").is_dir())

    def test_resolve_and_safe_path(self):
        self.externals.add("proj", str(self.outside), self.vault)
        (self.outside / "notes.md").write_text("hi", encoding="utf-8")
        self.assertEqual(self.externals.resolve("ext:proj/notes.md"),
                         (self.outside / "notes.md").resolve())
        self.assertIsNone(self.externals.resolve("plain/vault/path.md"))
        with self.assertRaises(ValueError):
            self.externals.resolve("ext:proj/../../escape")
        with self.assertRaises(ValueError):
            self.externals.resolve("ext:nope/x")
        # Through the agent tool layer: readable, and traversal still fails.
        scope = agent.resolve_scope("ext:proj")
        self.assertEqual(agent._tool_read_note(path="ext:proj/notes.md", _scope=scope), "hi")
        with self.assertRaises(agent.AgentError):
            agent._tool_read_note(path="ext:proj/notes.md")
        with self.assertRaises(agent.AgentError):
            agent._safe_path("ext:proj/../../escape")

    def test_run_scope_and_add_dirs(self):
        self.externals.add("proj", str(self.outside), self.vault)
        self.externals.add("other", str(self.other), self.vault)
        seen = {}
        original = router.claude_code_stream
        router.claude_code_stream = lambda prompt, **kw: (
            seen.update(prompt=prompt, **kw),
            iter([{"type": "result", "subtype": "success", "is_error": False, "result": "ok"}]),
        )[1]
        try:
            agent.run_agent("summarizer", "look around", tier="claude", folder="ext:proj")
        finally:
            router.claude_code_stream = original
        self.assertIn("external folder 'proj'", seen["prompt"])
        self.assertEqual(Path(seen["cwd"]), self.outside.resolve())
        self.assertEqual(seen["builtin_tools"], ["Read", "Grep", "Glob", "Write", "Edit"])
        self.assertEqual(seen["allowed_tools"], ["Read(./**)", "Edit(./**)"])
        self.assertNotIn("extra_dirs", seen)
        self.assertNotIn("ext:other", seen["prompt"].lower())
        self.assertNotIn(str(self.other), seen["prompt"])

    def test_selected_external_is_the_only_tool_scope(self):
        self.externals.add("proj", str(self.outside), self.vault)
        self.externals.add("other", str(self.other), self.vault)
        (self.outside / "a.md").write_text("alpha-only", encoding="utf-8")
        (self.other / "b.md").write_text("beta-only", encoding="utf-8")
        (self.vault / "vault.md").write_text("vault-only", encoding="utf-8")
        scope = agent.resolve_scope("ext:proj")
        self.assertEqual(agent._tool_read_note("a.md", _scope=scope), "alpha-only")
        self.assertIn("alpha-only", agent._tool_search_vault("only", _scope=scope))
        self.assertNotIn("beta", agent._tool_search_vault("only", _scope=scope))
        for path in ("ext:other/b.md", "../other/b.md", str(self.vault / "vault.md")):
            with self.assertRaises(agent.AgentError, msg=path):
                agent._safe_path(path, must_exist=True, scope=scope)

    def test_selected_vault_folder_rejects_siblings_and_externals(self):
        (self.vault / "one").mkdir()
        (self.vault / "two").mkdir()
        (self.vault / "one" / "a.md").write_text("a", encoding="utf-8")
        (self.vault / "two" / "b.md").write_text("b", encoding="utf-8")
        self.externals.add("proj", str(self.outside), self.vault)
        scope = agent.resolve_scope("one")
        self.assertEqual(agent._tool_read_note("a.md", _scope=scope), "a")
        for path in ("../two/b.md", "two/b.md", "ext:proj/x.md"):
            with self.assertRaises(agent.AgentError, msg=path):
                agent._safe_path(path, must_exist=True, scope=scope)


class WorkflowRulesTests(unittest.TestCase):
    """v1.29 adaptive workflow rules: vault runs keep the Regalia conventions;
    external runs get the folder's OWN detected conventions (CLAUDE.md/AGENTS.md/
    cursor rules/README) or a neutral no-scaffolding fallback — never _VAULT_RULES.
    Same temp-registry/vault/external fixture as ExternalFolderTests."""

    def setUp(self):
        import tempfile
        import externals
        self.externals = externals
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        (base / "vault").mkdir()
        (base / "outside" / "proj" / "sub").mkdir(parents=True)
        self._orig_store = externals.EXTERNALS_PATH
        self._orig_root = dashboard_app.VAULT_ROOT
        externals.EXTERNALS_PATH = base / ".external.json"
        dashboard_app.VAULT_ROOT = base / "vault"
        self.vault = base / "vault"
        self.outside = base / "outside" / "proj"
        externals.add("proj", str(self.outside), self.vault)

    def tearDown(self):
        self.externals.EXTERNALS_PATH = self._orig_store
        dashboard_app.VAULT_ROOT = self._orig_root
        self._tmp.cleanup()

    def test_vault_scope_gets_vault_rules(self):
        for folder in ("", "sub"):
            if folder:
                (self.vault / folder).mkdir(exist_ok=True)
            rules = agent._workflow_rules(agent.resolve_scope(folder))
            self.assertIn(agent._VAULT_RULES, rules, msg=folder or "(root)")
            self.assertIn("[[wikilinks]]", rules)

    def test_external_scope_never_gets_vault_rules(self):
        rules = agent._workflow_rules(agent.resolve_scope("ext:proj"))
        self.assertNotIn(agent._VAULT_RULES, rules)
        self.assertNotIn("Obsidian", rules)
        # Empty folder → the neutral anti-imposition fallback.
        self.assertIn("Do NOT add YAML frontmatter", rules)

    def test_detects_folder_claude_md(self):
        (self.outside / "CLAUDE.md").write_text(
            "Use tabs. Tests live in spec/.", encoding="utf-8")
        rules = agent._workflow_rules(agent.resolve_scope("ext:proj"))
        self.assertIn("Use tabs. Tests live in spec/.", rules)
        self.assertIn("own working conventions", rules)
        self.assertIn("CLAUDE.md", rules)
        self.assertNotIn(agent._VAULT_RULES, rules)

    def test_subfolder_scope_finds_connection_root_conventions(self):
        (self.outside / "CLAUDE.md").write_text("root conventions", encoding="utf-8")
        rules = agent._workflow_rules(agent.resolve_scope("ext:proj/sub"))
        self.assertIn("root conventions", rules)

    def test_priority_and_readme_fallback(self):
        (self.outside / "README.md").write_text("just a readme", encoding="utf-8")
        rules = agent._detect_external_workflow(agent.resolve_scope("ext:proj"))
        self.assertIn("just a readme", rules)
        self.assertIn("Context about this folder", rules)   # softer wrap
        self.assertNotIn("Follow them instead", rules)
        # A CLAUDE.md outranks the README.
        (self.outside / "CLAUDE.md").write_text("the real rules", encoding="utf-8")
        rules = agent._detect_external_workflow(agent.resolve_scope("ext:proj"))
        self.assertIn("the real rules", rules)
        self.assertNotIn("just a readme", rules)

    def test_detected_content_is_capped(self):
        (self.outside / "CLAUDE.md").write_text("x" * 20000, encoding="utf-8")
        rules = agent._detect_external_workflow(agent.resolve_scope("ext:proj"))
        self.assertLess(len(rules), agent._WORKFLOW_CHAR_CAP + 200)

    def test_email_only_agents_get_no_workflow_rules(self):
        # inbox_triage has no vault tools: the run_agent gate must never append
        # vault rules to it (it had none before the v1.29 refactor either).
        self.assertFalse(agent.supports_folder("inbox_triage"))
        self.assertNotIn("Obsidian", agent.AGENTS["inbox_triage"]["system"])
        self.assertNotIn("frontmatter", agent.AGENTS["inbox_triage"]["system"])

    def test_claude_tier_external_run_system_is_adapted(self):
        (self.outside / "CLAUDE.md").write_text("house style: kebab-case",
                                                encoding="utf-8")
        seen = {}
        original = router.claude_code_stream
        router.claude_code_stream = lambda prompt, **kw: (
            seen.update(prompt=prompt, **kw),
            iter([{"type": "result", "subtype": "success",
                   "is_error": False, "result": "ok"}]),
        )[1]
        try:
            agent.run_agent("summarizer", "look around", tier="claude",
                            folder="ext:proj")
        finally:
            router.claude_code_stream = original
        self.assertIn("house style: kebab-case", seen["system"])
        self.assertNotIn(agent._VAULT_RULES, seen["system"])
        self.assertNotIn("Home.md", seen["system"])         # no vault scaffolding steps
        self.assertIn("matching the folder's existing formats", seen["system"])

    def test_claude_tier_vault_run_system_unchanged(self):
        seen = {}
        original = router.claude_code_stream
        router.claude_code_stream = lambda prompt, **kw: (
            seen.update(prompt=prompt, **kw),
            iter([{"type": "result", "subtype": "success",
                   "is_error": False, "result": "ok"}]),
        )[1]
        try:
            agent.run_agent("summarizer", "look around", tier="claude")
        finally:
            router.claude_code_stream = original
        self.assertIn(agent._VAULT_RULES, seen["system"])
        self.assertIn(agent._CLAUDE_AGENT_RULES, seen["system"])


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

    def test_model_override_reaches_claude_cli(self):
        seen = {}
        original = router.claude_code_stream

        def fake_stream(*args, **kwargs):
            seen.update(kwargs)
            return iter(self.FAKE_STREAM)

        router.claude_code_stream = fake_stream
        try:
            agent.run_agent("summarizer", "count notes", tier="claude", model="sonnet")
        finally:
            router.claude_code_stream = original
        self.assertEqual(seen["model"], "sonnet")

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
        self.assertEqual(seen["builtin_tools"], [])
        self.assertEqual(Path(seen["cwd"]), dashboard_app.VAULT_ROOT.resolve())
        for t in agent.EMAIL_TOOL_NAMES:
            self.assertIn(f"mcp__mailbox__{t}", allowed)
        # Email-only agent: no filesystem tools at all.
        for t in ("Read", "Grep", "Glob", "Write", "Edit", "Bash"):
            self.assertNotIn(t, allowed)
        self.assertNotIn("CONNECTED EXTERNAL", seen.get("system", ""))
        # Temp config is deleted once the run finishes.
        self.assertFalse(Path(seen["mcp_config"]).exists())

    def test_vault_agent_unchanged_no_mcp(self):
        seen = self._run_capturing("summarizer")
        self.assertIsNone(seen.get("mcp_config"))
        self.assertIn("Read", seen["builtin_tools"])
        self.assertIn("Read(./**)", seen["allowed_tools"])
        self.assertNotIn("Read", seen["allowed_tools"])
        self.assertFalse(any(t.startswith("mcp__") for t in seen["allowed_tools"]))

    def test_inbox_triage_defaults_to_claude(self):
        self.assertEqual(agent.AGENTS["inbox_triage"]["tier"], "claude")

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "mcp SDK not installed")
    def test_mail_mcp_imports_and_registers_no_send(self):
        import mail_mcp
        self.assertTrue(hasattr(mail_mcp, "stage_email_draft"))
        self.assertFalse(hasattr(mail_mcp, "send_email"))
        self.assertFalse(hasattr(mail_mcp, "send"))


class ClaudeCommandSafetyTests(unittest.TestCase):
    """Automated Claude runs expose an exact tool/config boundary."""

    def test_automation_flags_preserve_empty_arguments(self):
        flags = router._claude_automation_flags([], [])
        self.assertEqual(flags[flags.index("--setting-sources") + 1], "")
        self.assertEqual(flags[flags.index("--tools") + 1], "")
        self.assertEqual(flags[flags.index("--allowedTools") + 1], "")
        self.assertEqual(flags[flags.index("--permission-mode") + 1], "dontAsk")
        self.assertIn("--strict-mcp-config", flags)

    def _chat_command(self, allow_write=False, attachment=False):
        import tempfile
        seen = {}
        original_path = router._claude_cli_path
        original_run = router.subprocess.run
        original_cwd = router.CLAUDE_CLI_CWD

        class FakeProc:
            returncode = 0
            stdout = json.dumps({"result": "ok", "modelUsage": {"test-model": {}}})
            stderr = ""

        def fake_run(cmd, **kwargs):
            seen.update(cmd=cmd, **kwargs)
            if attachment:
                staged = Path(next(
                    line[2:] for line in kwargs["input"].splitlines()
                    if line.startswith("- ")
                ))
                seen["staged"] = staged
                self.assertTrue(staged.is_file())
                self.assertEqual(staged.read_text(encoding="utf-8"), "attachment")
                if "--add-dir" in cmd:
                    self.assertEqual(staged.parent, Path(cmd[cmd.index("--add-dir") + 1]))
                else:
                    self.assertEqual(staged.parent, Path(kwargs["cwd"]))
            return FakeProc()

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "upload.txt"
            source.write_text("attachment", encoding="utf-8")
            router._claude_cli_path = lambda: "claude"
            router.subprocess.run = fake_run
            router.CLAUDE_CLI_CWD = tmp
            try:
                router._claude_code_chat(
                    [{"role": "user", "content": "hello"}], None, 100, None,
                    [{"path": str(source), "name": source.name, "mime": "text/plain"}]
                    if attachment else [],
                    allow_write,
                )
            finally:
                router._claude_cli_path = original_path
                router.subprocess.run = original_run
                router.CLAUDE_CLI_CWD = original_cwd
        return seen

    def test_text_chat_has_no_builtins_or_ambient_configuration(self):
        seen = self._chat_command()
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "")
        self.assertNotIn("--add-dir", cmd)
        self.assertEqual(seen["env"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")
        for forbidden in ("Bash", "Agent", "WebFetch", "WebSearch"):
            self.assertNotIn(forbidden, cmd)

    def test_edit_chat_exposes_only_file_tools(self):
        seen = self._chat_command(allow_write=True)
        cmd = seen["cmd"]
        self.assertEqual(
            cmd[cmd.index("--tools") + 1], "Read,Edit,Write,Glob,Grep")
        self.assertEqual(
            cmd[cmd.index("--allowedTools") + 1], "Read(./**),Edit(./**)")
        self.assertNotIn("Bash", cmd)

    def test_attachment_is_staged_and_removed(self):
        seen = self._chat_command(attachment=True)
        self.assertFalse(seen["staged"].parent.exists())
        self.assertEqual(seen["cmd"][seen["cmd"].index("--tools") + 1], "Read")


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
            "from": "prof@example.edu", "unread": True})
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
             "from": "prof@example.edu", "date": stale, "unread": True},   # too old
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

    def test_concurrent_saves_never_leave_partial_json(self):
        import threading

        obj = chats.create_chat()
        errors = []

        def write(index):
            try:
                chats.save_chat({**obj, "messages": [
                    {"role": "user", "content": f"message {index}"}
                ]})
            except Exception as exc:  # noqa: BLE001 — collected for the assertion
                errors.append(exc)

        workers = [threading.Thread(target=write, args=(i,)) for i in range(12)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertEqual(errors, [])
        loaded = chats.load_chat(obj["id"])
        self.assertRegex(loaded["messages"][0]["content"], r"^message \d+$")
        self.assertEqual(list(chats.CHATS_DIR.glob("*.tmp")), [])


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
        self.assertEqual(
            self.client.post("/api/settings", json={"default_tier": "banana"}).status_code, 400)

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
        self.assertIn("chatgpt", d)
        self.assertEqual(d["chatgpt"]["backend"], "codex-cli")
        self.assertIn("available", d["chatgpt"])
        self.assertIn("auth_state", d["chatgpt"])
        self.assertIn("auth_reason", d["chatgpt"])

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
        self.client.post("/api/settings", json={"default_tier": "chatgpt"})
        cid = None
        try:
            d = self.client.post("/api/chats").get_json()
            cid = d["id"]
            self.assertEqual(d["tier"], "chatgpt")
            self.assertEqual(d["cliModel"], {})
        finally:
            if cid:
                self.client.delete(f"/api/chats/{cid}")


class UiConfigTests(unittest.TestCase):
    """v1.25 — every backend knob is settable from the UI; env still wins."""

    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        import config
        self._config = config
        self._orig_path = config.CONFIG_PATH
        self._tmp = tempfile.TemporaryDirectory()
        config.CONFIG_PATH = Path(self._tmp.name) / ".config.json"

    def tearDown(self):
        self._config.CONFIG_PATH = self._orig_path
        self._tmp.cleanup()

    def test_backend_knobs_round_trip(self):
        r = self.client.post("/api/settings", json={
            "ollama_model": "qwen3:8b", "claude_cli_timeout": "90",
            "ms_oauth_client_id": "0000-1111", "ms_oauth_tenant": "common",
        })
        self.assertEqual(r.status_code, 200)
        d = self.client.get("/api/settings").get_json()["settings"]
        self.assertEqual(d["ollama_model"], "qwen3:8b")
        self.assertEqual(d["claude_cli_timeout"], "90")
        self.assertEqual(d["ms_oauth_client_id"], "0000-1111")
        self.assertEqual(d["ms_oauth_tenant"], "common")

    def test_int_and_url_knobs_validated(self):
        self.assertEqual(
            self.client.post("/api/settings", json={"claude_cli_timeout": "soon"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"news_ttl": "-5"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"codex_cli_timeout": "0"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"news_ttl": "86401"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"ollama_host": "localhost:11434"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings", json={"openai_base": "ftp://x"}).status_code, 400)

    def test_gmail_client_json_validated_and_masked(self):
        self.assertEqual(
            self.client.post("/api/settings",
                             json={"gmail_oauth_client_json": "not json"}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/settings",
                             json={"gmail_oauth_client_json": '{"web_wrong": {}}'}).status_code, 400)
        good = '{"installed": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "shh42"}}'
        r = self.client.post("/api/settings", json={"gmail_oauth_client_json": good})
        self.assertEqual(r.status_code, 200)
        raw = self.client.get("/api/settings").get_data(as_text=True)
        self.assertNotIn("shh42", raw)
        self.assertEqual(json.loads(raw)["settings"]["gmail_oauth_client_json"], {"set": True})

    def test_env_wins_over_store(self):
        import os
        old = os.environ.pop("OLLAMA_MODEL", None)
        try:
            self._config.update({"ollama_model": "from-store"})
            self.assertEqual(router._ollama_model(), "from-store")
            os.environ["OLLAMA_MODEL"] = "from-env"
            self.assertEqual(router._ollama_model(), "from-env")
        finally:
            if old is None:
                os.environ.pop("OLLAMA_MODEL", None)
            else:
                os.environ["OLLAMA_MODEL"] = old
        # unset everywhere -> built-in default
        old = os.environ.pop("OLLAMA_MODEL", None)
        self._config.update({"ollama_model": ""})
        try:
            self.assertEqual(router._ollama_model(), "llama3.2")
        finally:
            if old is not None:
                os.environ["OLLAMA_MODEL"] = old

    def test_pasted_gmail_client_materializes_to_file(self):
        import os
        if os.environ.get("GMAIL_OAUTH_CLIENT"):
            self.skipTest("environment already carries a Gmail client path")
        import email_sources
        import paths
        good = '{"installed": {"client_id": "abc"}}'
        self._config.update({"gmail_oauth_client_json": good})
        orig = paths.data_dir
        paths.data_dir = lambda: Path(self._tmp.name)
        try:
            p = email_sources.gmail_client_secret_file()
            self.assertTrue(p and Path(p).exists())
            self.assertEqual(Path(p).read_text(encoding="utf-8"), good)
        finally:
            paths.data_dir = orig

    def test_ollama_pull_validates_model(self):
        self.assertEqual(self.client.post("/api/ollama/pull", json={}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/ollama/pull", json={"model": "bad name!"}).status_code, 400)
        r = self.client.get("/api/ollama/pull/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.get_json()["state"], ("idle", "running", "done", "error"))

    def test_claude_test_status_route(self):
        r = self.client.get("/api/claude/test/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.get_json()["state"], ("idle", "running", "done", "error"))

    def test_no_ui_string_points_at_cli_setup(self):
        # The UI must never tell the user to edit .env or run connect_email.py.
        html = (Path(dashboard_app.__file__).parent / "templates" / "index.html").read_text(
            encoding="utf-8")
        self.assertNotIn("connect_email.py", html)
        self.assertNotIn("GMAIL_OAUTH_CLIENT", html)

    # ── Personalization (v1.33) ──
    def test_personalization_defaults_and_catalog(self):
        d = self.client.get("/api/settings").get_json()
        p = d["settings"]["personalization"]
        self.assertEqual(p["job_interests"], [])
        self.assertEqual(p["career_stage"], "any")
        self.assertTrue(p["show_jobs"])
        # The catalog rides along so the UI can render the choices.
        self.assertIn("interests", d["catalog"])
        self.assertIn("AI/ML", d["catalog"]["interests"])
        self.assertEqual(list(self._config.CAREER_STAGES), d["catalog"]["career_stages"])

    def test_personalization_round_trips(self):
        payload = {"personalization": {
            "job_interests": ["Quant", "AI/ML", "bogus-bucket"],
            "career_stage": "student",
            "job_locations": ["New York", " Remote "],
            "job_boards": ["anthropic", "ramp"],
            "news_feeds": ["https://example.com/rss",
                           {"name": "Blog", "url": "https://b.com/atom"}],
            "show_jobs": True, "show_news": False,
        }}
        r = self.client.post("/api/settings", json=payload)
        self.assertEqual(r.status_code, 200)
        p = self.client.get("/api/settings").get_json()["settings"]["personalization"]
        self.assertEqual(p["job_interests"], ["Quant", "AI/ML", "bogus-bucket"])
        self.assertEqual(p["career_stage"], "student")
        self.assertEqual(p["job_locations"], ["New York", "Remote"])  # trimmed
        self.assertEqual(p["news_feeds"][0], {"name": "", "url": "https://example.com/rss"})
        self.assertEqual(p["news_feeds"][1], {"name": "Blog", "url": "https://b.com/atom"})
        self.assertFalse(p["show_news"])

    def test_personalization_rejects_bad_values(self):
        self.assertEqual(self.client.post(
            "/api/settings", json={"personalization": {"career_stage": "wizard"}}).status_code, 400)
        self.assertEqual(self.client.post(
            "/api/settings", json={"personalization": {"news_feeds": ["ftp://x"]}}).status_code, 400)
        self.assertEqual(self.client.post(
            "/api/settings", json={"personalization": {"nope": 1}}).status_code, 400)
        self.assertEqual(self.client.post(
            "/api/settings", json={"personalization": "not-an-object"}).status_code, 400)

    def test_resolve_profile_and_scoring_honor_personalization(self):
        # No personalization -> full interest catalog, "any" stage.
        prof = dashboard_app._resolve_profile()
        self.assertEqual(set(prof["interests"]), set(dashboard_app.news_sources.INTEREST_KEYWORDS))
        # Narrow to Quant + student stage; an ML internship should now MISS the
        # interest buckets (Quant only) but still ride the early-career boost.
        self._config.update({"personalization": {
            "job_interests": ["Quant"], "career_stage": "student"}})
        prof = dashboard_app._resolve_profile()
        self.assertEqual(list(prof["interests"]), ["Quant"])
        quant_score, quant_tags = dashboard_app._score_job(
            "Quantitative Trading Intern", "New York", prof)
        self.assertIn("Quant", quant_tags)
        self.assertGreater(quant_score, 0)
        # A senior role is penalized for a student profile.
        senior_score, _ = dashboard_app._score_job("Senior Staff Engineer", "Remote", prof)
        self.assertLessEqual(senior_score, 0)


class ChatGptAccountTierTests(unittest.TestCase):
    """ChatGPT account tier is backed by Codex CLI, not the OpenAI API key path."""

    def test_chatgpt_chat_uses_codex_exec_and_account_env(self):
        import os
        import tempfile

        seen = {}
        original_path = router._codex_cli_path
        original_run = router.subprocess.run
        original_cwd = router.CODEX_CLI_CWD
        original_health = dict(router._CODEX_HEALTH)
        secret_names = (
            "OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN",
            "AWS_SECRET_ACCESS_KEY", "DATABASE_PASSWORD",
        )
        original_secrets = {name: os.environ.get(name) for name in secret_names}

        class FakeProc:
            returncode = 0
            stdout = "hello from chatgpt"
            stderr = ""

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["input"] = kwargs.get("input")
            seen["env"] = kwargs.get("env") or {}
            seen["cwd"] = kwargs.get("cwd")
            seen["add_dir"] = Path(cmd[cmd.index("--add-dir") + 1])
            seen["staged"] = Path(next(
                line[2:] for line in seen["input"].splitlines()
                if line.startswith("- ")
            ))
            self.assertTrue(seen["staged"].is_file())
            self.assertEqual(seen["staged"].read_text(encoding="utf-8"), "attachment")
            return FakeProc()

        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as uploads:
            source = Path(uploads) / "outside vault.txt"
            source.write_text("attachment", encoding="utf-8")
            router._codex_cli_path = lambda: "codex"
            router.subprocess.run = fake_run
            router.CODEX_CLI_CWD = cwd  # intentionally not a Git repository
            for name in secret_names:
                os.environ[name] = f"sentinel-{name.lower()}"
            try:
                res = router.chat(
                    [{"role": "user", "content": "hi"}], tier="chatgpt",
                    system="be terse",
                    model="gpt-test",
                    attachments=[{"path": str(source), "name": source.name,
                                  "mime": "text/plain"}],
                )
            finally:
                router._codex_cli_path = original_path
                router.subprocess.run = original_run
                router.CODEX_CLI_CWD = original_cwd
                router._CODEX_HEALTH.clear()
                router._CODEX_HEALTH.update(original_health)
                for name, value in original_secrets.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value

        self.assertEqual(res["tier"], "chatgpt")
        self.assertEqual(res["reply"], "hello from chatgpt")
        self.assertEqual(seen["cmd"][:2], ["codex", "exec"])
        self.assertIn("read-only", seen["cmd"])
        self.assertIn("--skip-git-repo-check", seen["cmd"])
        self.assertIn("--ignore-user-config", seen["cmd"])
        self.assertIn("--ignore-rules", seen["cmd"])
        self.assertIn('forced_login_method="chatgpt"', seen["cmd"])
        self.assertEqual(seen["cmd"][seen["cmd"].index("-m") + 1], "gpt-test")
        self.assertNotIn("--ask-for-approval", seen["cmd"])
        self.assertTrue(seen["input"].startswith("System instructions:"))
        for name in secret_names:
            self.assertNotIn(name, seen["env"])
        self.assertTrue(seen["cwd"])
        self.assertEqual(seen["staged"].parent, seen["add_dir"])
        self.assertFalse(seen["add_dir"].exists())

    def test_health_rejects_api_key_login_and_marks_tier_unavailable(self):
        import tempfile

        original_path = router._codex_cli_path
        original_run = router.subprocess.run
        original_cwd = router.CODEX_CLI_CWD
        original_health = dict(router._CODEX_HEALTH)

        class FakeProc:
            returncode = 0
            stdout = "Logged in using an API key"
            stderr = ""

        with tempfile.TemporaryDirectory() as cwd:
            router._codex_cli_path = lambda: "codex"
            router.subprocess.run = lambda *args, **kwargs: FakeProc()
            router.CODEX_CLI_CWD = cwd
            try:
                ok, reason = router.codex_cli_health()
                status = router.status_for("chatgpt")
            finally:
                router._codex_cli_path = original_path
                router.subprocess.run = original_run
                router.CODEX_CLI_CWD = original_cwd
                router._CODEX_HEALTH.clear()
                router._CODEX_HEALTH.update(original_health)

        self.assertFalse(ok)
        self.assertIn("API key", reason)
        self.assertFalse(status["authenticated"])
        self.assertEqual(status["auth_state"], "wrong_method")
        self.assertFalse(status["available"])

    def _health_result(self, stdout, returncode=0, stderr=""):
        import tempfile

        original_path = router._codex_cli_path
        original_run = router.subprocess.run
        original_cwd = router.CODEX_CLI_CWD
        original_health = dict(router._CODEX_HEALTH)

        class FakeProc:
            pass

        FakeProc.returncode = returncode
        FakeProc.stdout = stdout
        FakeProc.stderr = stderr
        with tempfile.TemporaryDirectory() as cwd:
            router._codex_cli_path = lambda: "codex"
            router.subprocess.run = lambda *args, **kwargs: FakeProc()
            router.CODEX_CLI_CWD = cwd
            try:
                ok, reason = router.codex_cli_health()
                status = router.status_for("chatgpt")
            finally:
                router._codex_cli_path = original_path
                router.subprocess.run = original_run
                router.CODEX_CLI_CWD = original_cwd
                router._CODEX_HEALTH.clear()
                router._CODEX_HEALTH.update(original_health)
        return ok, reason, status

    def test_health_confirms_explicit_chatgpt_login(self):
        ok, reason, status = self._health_result("Logged in using ChatGPT")
        self.assertTrue(ok)
        self.assertIn("ChatGPT", reason)
        self.assertTrue(status["authenticated"])
        self.assertEqual(status["auth_state"], "chatgpt")
        self.assertIsNotNone(status["auth_checked_at"])

    def test_health_recognizes_signed_out_output(self):
        ok, reason, status = self._health_result("Not logged in", returncode=1)
        self.assertFalse(ok)
        self.assertIn("not signed in", reason)
        self.assertEqual(status["auth_state"], "signed_out")

    def test_health_does_not_guess_on_unknown_success_output(self):
        ok, reason, status = self._health_result("Login status available")
        self.assertFalse(ok)
        self.assertIn("could not confirm", reason)
        self.assertEqual(status["auth_state"], "unknown")

    def test_chatgpt_tool_loop_rejected(self):
        with self.assertRaises(router.RouterError) as ctx:
            router.chat_tools([{"role": "user", "content": "hi"}], [],
                              tier="chatgpt")
        self.assertEqual(ctx.exception.status, 400)


class BackendRegressionTests(unittest.TestCase):
    """Cross-feature regressions around targeted checks and agent tier routing."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def test_router_check_rejects_non_object_without_probing(self):
        original_ollama = router._ollama_up
        router._ollama_up = lambda: self.fail("unrelated Ollama probe ran")
        try:
            response = self.client.post("/api/router/check", json=["chatgpt"])
        finally:
            router._ollama_up = original_ollama
        self.assertEqual(response.status_code, 400)

    def test_mutating_routes_reject_non_object_json(self):
        cases = (
            ("post", "/api/project"),
            ("post", "/api/connect/email"),
            ("post", "/api/ollama/pull"),
            ("post", "/api/email/draft"),
            ("put", "/api/chats/c_00000000000000000000000000000000"),
        )
        for method, url in cases:
            response = getattr(self.client, method)(url, json=["not", "an", "object"])
            self.assertEqual(response.status_code, 400, url)

    def test_chatgpt_check_does_not_probe_other_backends(self):
        original_health = router.codex_cli_health
        original_path = router._codex_cli_path
        original_ollama = router._ollama_up
        original_cache = dict(router._CODEX_HEALTH)

        def healthy():
            router._CODEX_HEALTH.update(exe="codex", ok=True, reason="ready")
            return True, "ready"

        router.codex_cli_health = healthy
        router._codex_cli_path = lambda: "codex"
        router._ollama_up = lambda: self.fail("unrelated Ollama probe ran")
        try:
            response = self.client.post("/api/router/check", json={"tier": "chatgpt"})
        finally:
            router.codex_cli_health = original_health
            router._codex_cli_path = original_path
            router._ollama_up = original_ollama
            router._CODEX_HEALTH.clear()
            router._CODEX_HEALTH.update(original_cache)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["status"]["available"])

    def test_openai_agent_tier_is_preserved(self):
        original_thread = dashboard_app.threading.Thread

        class FakeThread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                pass

        dashboard_app.threading.Thread = FakeThread
        run_id = None
        try:
            response = self.client.post(
                "/api/agent/run",
                json={"agent": "summarizer", "task": "Summarize today", "tier": "openai"},
            )
            body = response.get_json()
            run_id = body.get("run_id")
        finally:
            dashboard_app.threading.Thread = original_thread
            if run_id:
                with dashboard_app._RUNS_LOCK:
                    dashboard_app._RUNS.pop(run_id, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["tier"], "openai")

    def test_chat_model_override_is_scoped_to_supported_tiers(self):
        seen = []
        original_chat = router.chat

        def fake_chat(messages, **kwargs):
            seen.append((kwargs["tier"], kwargs.get("model")))
            return {"reply": "ok", "model": kwargs.get("model") or "default",
                    "tier": kwargs["tier"]}

        router.chat = fake_chat
        try:
            chatgpt = self.client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "hi"}],
                "tier": "chatgpt", "model": "gpt-account-model",
            })
            smart = self.client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "hi"}],
                "tier": "smart", "model": "must-not-cross-backends",
            })
        finally:
            router.chat = original_chat

        self.assertEqual(chatgpt.status_code, 200)
        self.assertEqual(smart.status_code, 200)
        self.assertEqual(seen, [("chatgpt", "gpt-account-model"), ("smart", None)])

    def test_cli_model_overrides_reach_claude_workers(self):
        original_thread = dashboard_app.threading.Thread
        launched = []

        class FakeThread:
            def __init__(self, **kwargs):
                launched.append(kwargs)

            def start(self):
                pass

        dashboard_app.threading.Thread = FakeThread
        agent_run_id = chat_run_id = None
        try:
            agent_response = self.client.post("/api/agent/run", json={
                "agent": "summarizer", "task": "Summarize", "tier": "claude",
                "model": "sonnet",
            })
            agent_run_id = agent_response.get_json().get("run_id")
            chat_response = self.client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "opus",
            })
            chat_run_id = chat_response.get_json().get("run_id")
        finally:
            dashboard_app.threading.Thread = original_thread
            if agent_run_id:
                with dashboard_app._RUNS_LOCK:
                    dashboard_app._RUNS.pop(agent_run_id, None)
            if chat_run_id:
                with dashboard_app._CHAT_STREAMS_LOCK:
                    dashboard_app._CHAT_STREAMS.pop(chat_run_id, None)

        by_target = {item["target"].__name__: item["args"] for item in launched}
        self.assertEqual(by_target["_run_worker"][5], "sonnet")
        self.assertEqual(by_target["_chat_stream_worker"][3], "opus")

    def test_unsupported_agent_tier_is_explicit_error(self):
        response = self.client.post(
            "/api/agent/run",
            json={"agent": "summarizer", "task": "Summarize", "tier": "chatgpt"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot run agents", response.get_json()["error"])

    def test_chat_and_agent_routes_reject_non_object_json(self):
        self.assertEqual(self.client.post("/api/chat", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/agent/run", json=[]).status_code, 400)

    def test_chat_route_rejects_unknown_tier_instead_of_falling_back(self):
        response = self.client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "tier": "mystery"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown tier", response.get_json()["error"])


class ProjectScaffoldTests(unittest.TestCase):
    """v1.26: project areas are dynamic — any top-level vault folder, created on
    demand, validated before any filesystem write. Runs against a temp vault so
    the real one is never touched."""

    @classmethod
    def setUpClass(cls):
        dashboard_app.app.config["TESTING"] = True
        cls.client = dashboard_app.app.test_client()

    def setUp(self):
        import tempfile
        self._orig_root = dashboard_app.VAULT_ROOT
        self._tmp = tempfile.TemporaryDirectory()
        dashboard_app.VAULT_ROOT = Path(self._tmp.name)

    def tearDown(self):
        dashboard_app.VAULT_ROOT = self._orig_root
        self._tmp.cleanup()

    def _context_text(self, rel_context):
        return (Path(self._tmp.name) / rel_context).read_text(encoding="utf-8")

    def test_create_in_empty_vault(self):
        res = dashboard_app.create_project_core("My App", "projects")
        self.assertEqual(set(res), {"ok", "path", "context_file", "subdirs", "home_linked"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["path"], "projects/my_app")
        for sub in dashboard_app.PROJECT_SUBDIRS:
            self.assertTrue((Path(self._tmp.name) / "projects" / "my_app" / sub).is_dir())
        self.assertIn("area/projects", self._context_text(res["context_file"]))

    def test_custom_area_created_with_slug_tag(self):
        res = dashboard_app.create_project_core("Thing", "My Stuff")
        self.assertEqual(res["path"], "My Stuff/thing")
        self.assertIn("area/my-stuff", self._context_text(res["context_file"]))

    def test_legacy_internship_alias(self):
        res = dashboard_app.create_project_core("Intern Work", "internship")
        self.assertEqual(res["path"], "Internship-Projects/intern_work")
        # Tag continuity: existing notes tag area/internship, not the folder slug.
        self.assertIn("area/internship", self._context_text(res["context_file"]))

    def test_existing_folder_reused_case_insensitively(self):
        (Path(self._tmp.name) / "Projects").mkdir()
        res = dashboard_app.create_project_core("App", "projects")
        self.assertEqual(res["path"], "Projects/app")

    def test_bad_areas_rejected_before_any_write(self):
        for bad in ("../x", "..\\x", "a/b", ".obsidian", "dashboard", "templates",
                    "external", ""):
            with self.assertRaises(ValueError, msg=f"area {bad!r} should be rejected"):
                dashboard_app.create_project_core("App", bad)
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_duplicate_is_conflict(self):
        dashboard_app.create_project_core("App", "projects")
        with self.assertRaises(ValueError) as ctx:
            dashboard_app.create_project_core("App", "projects")
        self.assertIn("already exists", str(ctx.exception))
        r = self.client.post("/api/project", json={"name": "App", "area": "projects"})
        self.assertEqual(r.status_code, 409)

    def test_route_shapes(self):
        r = self.client.post("/api/project", json={"name": "Web App", "area": "projects"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        r = self.client.post("/api/project", json={"name": "X", "area": "../evil"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_browse_root_lists_new_area(self):
        dashboard_app.create_project_core("App", "Side Quests")
        names = [f["name"] for f in self.client.get("/api/browse").get_json()["folders"]]
        self.assertIn("Side Quests", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
