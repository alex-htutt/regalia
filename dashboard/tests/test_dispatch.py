"""Focused tests for custom agents, group planning, and review-gated dispatches."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("REGALIA_UPDATE_CHECK", "0")
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import agent  # noqa: E402
import app as dashboard_app  # noqa: E402
import dispatch_engine  # noqa: E402
import dispatch_workspace  # noqa: E402
import dispatches  # noqa: E402


def _definition(**overrides):
    value = {
        "name": "Test researcher",
        "instructions": "Research the assigned question and cite evidence.",
        "profile": "research",
        "capabilities": ["vault_read", "web"],
        "tier": "fast",
    }
    value.update(overrides)
    return value


class DispatchDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = dispatches.DB_PATH
        dispatches.DB_PATH = Path(self.tmp.name) / "dispatch.sqlite3"
        dispatches._init()
        dashboard_app.app.config["TESTING"] = True
        self.client = dashboard_app.app.test_client()

    def tearDown(self):
        dispatches.DB_PATH = self.old_db
        self.tmp.cleanup()

    def test_custom_agent_round_trip(self):
        created = self.client.post("/api/agent-definitions", json=_definition())
        self.assertEqual(created.status_code, 201)
        agent_id = created.get_json()["id"]
        listed = self.client.get("/api/agent-definitions").get_json()["agents"]
        self.assertEqual([item["id"] for item in listed], [agent_id])
        updated = self.client.put(
            f"/api/agent-definitions/{agent_id}",
            json=_definition(name="Updated researcher"),
        )
        self.assertEqual(updated.get_json()["name"], "Updated researcher")

    def test_priority_is_required(self):
        response = self.client.post(
            "/api/dispatches", json={"kind": "group", "goal": "Large task"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Fast, Balanced, or Best", response.get_json()["error"])

    def test_group_starts_with_clarification(self):
        response = self.client.post(
            "/api/dispatches",
            json={"kind": "group", "goal": "Build and research a feature", "priority": "balanced"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["state"], "clarifying")
        self.assertEqual(data["messages"][-1]["role"], "assistant")

    def test_invalid_single_does_not_leave_orphan_dispatch(self):
        response = self.client.post(
            "/api/dispatches",
            json={"kind": "single", "goal": "Do work", "priority": "fast"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(dispatches.list_dispatches(), [])


class PlanValidationTests(unittest.TestCase):
    def setUp(self):
        self.group = {"kind": "group", "priority": "balanced", "scope": "", "goal": "goal"}

    @mock.patch("dispatch_engine._tier_available", return_value=True)
    def test_group_requires_two_workers(self, _available):
        with self.assertRaisesRegex(dispatch_engine.DispatchError, "2-8"):
            dispatch_engine.normalize_plan(self.group, {
                "workers": [{"id": "only", "objective": "Do everything", "tier": "fast"}],
            })

    @mock.patch("dispatch_engine._tier_available", return_value=True)
    def test_dependency_cycles_are_rejected(self, _available):
        with self.assertRaisesRegex(dispatch_engine.DispatchError, "cycle"):
            dispatch_engine.normalize_plan(self.group, {"workers": [
                {"id": "a", "objective": "A", "depends_on": ["b"], "tier": "fast"},
                {"id": "b", "objective": "B", "depends_on": ["a"], "tier": "fast"},
            ]})

    @mock.patch("dispatch_engine._tier_available", return_value=True)
    def test_mixed_file_and_mail_writes_are_rejected(self, _available):
        with self.assertRaisesRegex(dispatch_engine.DispatchError, "separate workers"):
            dispatch_engine.normalize_plan(self.group, {"workers": [
                {"id": "mixed", "objective": "Write and draft", "tier": "fast",
                 "capabilities": ["code_write", "inbox_draft"]},
                {"id": "review", "objective": "Review", "tier": "fast"},
            ]})

    @mock.patch("dispatch_engine._tier_available", return_value=True)
    def test_file_and_mail_writers_need_separate_dispatches(self, _available):
        with self.assertRaisesRegex(dispatch_engine.DispatchError, "separate dispatches"):
            dispatch_engine.normalize_plan(self.group, {"workers": [
                {"id": "code", "objective": "Edit code", "tier": "fast",
                 "capabilities": ["code_write"]},
                {"id": "mail", "objective": "Draft update", "tier": "fast",
                 "capabilities": ["inbox_draft"]},
            ]})


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = dispatches.DB_PATH
        self.old_work = dispatch_workspace.WORK_ROOT
        dispatches.DB_PATH = Path(self.tmp.name) / "dispatch.sqlite3"
        dispatch_workspace.WORK_ROOT = Path(self.tmp.name) / "work"
        dispatches._init()

    def tearDown(self):
        dispatches.DB_PATH = self.old_db
        dispatch_workspace.WORK_ROOT = self.old_work
        self.tmp.cleanup()

    def test_copy_workspace_changes_only_on_apply(self):
        source = Path(self.tmp.name) / "source"
        source.mkdir()
        (source / "note.txt").write_text("before", encoding="utf-8")
        ws = dispatch_workspace.prepare_worker("d_" + "1" * 32, "worker", source)
        (ws.root / "note.txt").write_text("after", encoding="utf-8")
        artifact = dispatch_workspace.collect_artifact(ws)
        self.assertEqual((source / "note.txt").read_text(encoding="utf-8"), "before")
        dispatch_workspace.apply_artifact(artifact)
        self.assertEqual((source / "note.txt").read_text(encoding="utf-8"), "after")

    def test_copy_workspace_detects_source_conflict(self):
        source = Path(self.tmp.name) / "source"
        source.mkdir()
        target = source / "note.txt"
        target.write_text("before", encoding="utf-8")
        ws = dispatch_workspace.prepare_worker("d_" + "2" * 32, "worker", source)
        (ws.root / "note.txt").write_text("worker", encoding="utf-8")
        artifact = dispatch_workspace.collect_artifact(ws)
        target.write_text("user edit", encoding="utf-8")
        with self.assertRaisesRegex(dispatch_workspace.WorkspaceError, "changed after dispatch"):
            dispatch_workspace.apply_artifact(artifact)

    @mock.patch("dispatch_engine.dispatch_workspace.cleanup_dispatch")
    @mock.patch("dispatch_engine.mailbox.create_draft", return_value={"id": "draft-1"})
    def test_email_draft_is_created_only_when_applied(self, create_draft, _cleanup):
        obj = dispatches.create_dispatch({"kind": "single", "goal": "Draft reply", "priority": "fast"})
        draft = {"account_id": "gmail_x", "to": "person@example.com", "subject": "Hello", "body": "Draft body"}
        dispatches.mutate_dispatch(obj["id"], lambda current: {
            **current, "state": "awaiting_apply",
            "artifacts": [{"kind": "email_drafts", "drafts": [draft], "has_changes": True}],
        })
        self.assertEqual(create_draft.call_count, 0)
        result = dispatch_engine.apply(obj["id"])
        self.assertTrue(result["applied"])
        create_draft.assert_called_once()

    @mock.patch("dispatch_engine._tier_available", return_value=False)
    def test_launch_rejects_unavailable_assignment(self, _available):
        obj = dispatches.create_dispatch({"kind": "single", "goal": "Research", "priority": "fast"})
        with mock.patch("dispatch_engine._choose_worker_tier", return_value="fast"):
            dispatch_engine.configure_single(obj["id"], _definition())
        with self.assertRaisesRegex(dispatch_engine.DispatchError, "unavailable tier"):
            dispatch_engine.launch(obj["id"])


class StagedDraftToolTests(unittest.TestCase):
    @mock.patch("agent.mailbox.create_draft")
    def test_stage_tool_has_no_mailbox_side_effect(self, create_draft):
        result = agent._tool_stage_email_draft(
            account_id="gmail_x", to="person@example.com", subject="Hi", body="Review me",
        )
        self.assertIn("NOT been saved", result)
        create_draft.assert_not_called()

    def test_dispatch_definition_uses_staged_tool(self):
        spec = agent.spec_from_definition({
            "name": "Draft assistant", "instructions": "Prepare drafts.",
            "capabilities": ["inbox_read", "inbox_draft"], "tier": "fast",
        })
        self.assertIn("stage_email_draft", spec["tools"])
        self.assertNotIn("draft_email", spec["tools"])


if __name__ == "__main__":
    unittest.main()
