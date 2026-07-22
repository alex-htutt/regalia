"""Planning and dependency-aware execution for single/group agent dispatches."""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import agent
import dispatch_workspace
import dispatches
import mailbox
import router


_cancel_events: dict[str, threading.Event] = {}
_runtime_lock = threading.Lock()
_active: set[str] = set()

WRITE_CAPS = frozenset({"vault_write", "code_write", "inbox_draft"})
FILE_WRITE_CAPS = frozenset({"vault_write", "code_write"})
CONCURRENCY = {"fast": 4, "balanced": 3, "best": 2}


class DispatchError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def model_catalog() -> dict:
    status = router.status()
    ollama = router.list_ollama_models()
    entries = {
        "fast": {**status["fast"], "models": ollama or [status["fast"]["model"]]},
        "smart": {**status["smart"], "models": [status["smart"]["model"]]},
        "openai": {**status["openai"], "models": [status["openai"]["model"]]},
        "chatgpt": {**status["chatgpt"], "models": [status["chatgpt"]["model"]]},
        "claude": {**status["claude"], "models": ["haiku", "sonnet", "opus"]},
    }
    return {"tiers": entries, "priorities": list(dispatches.PRIORITIES)}


def _tier_available(tier: str) -> bool:
    try:
        return bool(router.status_for(tier).get("available"))
    except (ValueError, KeyError):
        return False


def _planner_choice(priority: str, requested: dict | None = None) -> tuple[str, str]:
    requested = requested or {}
    tier = str(requested.get("tier") or "").lower()
    model = str(requested.get("model") or "").strip()
    if tier in agent.AGENT_TIERS and _tier_available(tier):
        return tier, model
    order = ("claude", "smart", "openai", "chatgpt", "fast")
    for candidate in order:
        if _tier_available(candidate):
            if candidate == "claude":
                return candidate, "sonnet" if priority == "fast" else "opus"
            return candidate, ""
    raise DispatchError("No agent-capable model backend is ready. Connect one in Settings.", 503)


def _suggest_model(tier: str, complexity: str, priority: str) -> str:
    if tier == "claude":
        if complexity == "simple":
            return "haiku"
        if complexity == "hard" or priority == "best":
            return "opus"
        return "sonnet"
    try:
        value = router.status_for(tier).get("model") or ""
        return "" if "default" in value.lower() else value
    except (ValueError, KeyError):
        return ""


def _choose_worker_tier(complexity: str, priority: str) -> str:
    if complexity == "simple" and _tier_available("fast"):
        return "fast"
    if priority == "fast":
        order = ("claude", "openai", "smart", "chatgpt", "fast")
    else:
        order = ("claude", "smart", "openai", "chatgpt", "fast")
    return next((tier for tier in order if _tier_available(tier)), "fast")


def _json_object(text: str) -> dict:
    text = str(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.I | re.S)
    candidates = [fenced.group(1)] if fenced else []
    first, last = text.find("{"), text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first:last + 1])
    for raw in candidates:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            continue
    raise DispatchError("The planner returned an invalid plan. Try the planning turn again.", 502)


def _fallback_plan(obj: dict) -> dict:
    scope = obj.get("scope") or ""
    return {
        "summary": "Research the request, implement it in isolation, and verify the integrated result.",
        "checks": [],
        "workers": [
            {
                "id": "research", "title": "Research and architecture",
                "objective": f"Investigate the request, relevant workspace context, and implementation risks: {obj['goal']}",
                "complexity": "moderate", "capabilities": ["vault_read", "code_read", "web"],
                "scope": scope, "depends_on": [],
            },
            {
                "id": "implement", "title": "Implementation",
                "objective": f"Implement the approved request and report changed files and checks: {obj['goal']}",
                "complexity": "hard", "capabilities": ["code_read", "code_write", "run_checks"],
                "scope": scope, "depends_on": ["research"],
            },
        ],
    }


def normalize_plan(dispatch_obj: dict, raw_plan: dict) -> dict:
    workers_raw = raw_plan.get("workers") if isinstance(raw_plan, dict) else None
    if not isinstance(workers_raw, list):
        raise DispatchError("A dispatch plan needs a workers list.")
    minimum = 2 if dispatch_obj.get("kind") == "group" else 1
    if not minimum <= len(workers_raw) <= 8:
        label = "2-8" if minimum == 2 else "1-8"
        raise DispatchError(
            f"A {dispatch_obj.get('kind', 'single')} dispatch plan must contain {label} workers."
        )
    workers = []
    used = set()
    for index, raw in enumerate(workers_raw):
        if not isinstance(raw, dict):
            raise DispatchError("Every worker must be an object.")
        base_id = re.sub(r"[^a-z0-9_-]", "_", str(raw.get("id") or f"worker_{index + 1}").lower())[:40]
        wid = base_id or f"worker_{index + 1}"
        if wid in used:
            raise DispatchError(f"Duplicate worker id '{wid}'.")
        used.add(wid)
        objective = str(raw.get("objective") or "").strip()
        if not objective:
            raise DispatchError(f"Worker '{wid}' needs an objective.")
        complexity = str(raw.get("complexity") or "moderate").lower()
        if complexity not in ("simple", "moderate", "hard"):
            complexity = "moderate"
        capabilities = []
        for value in raw.get("capabilities") or ["vault_read"]:
            value = str(value).lower()
            if value in dispatches.CAPABILITIES and value not in capabilities:
                capabilities.append(value)
        if not capabilities:
            capabilities = ["vault_read"]
        if "inbox_draft" in capabilities and FILE_WRITE_CAPS.intersection(capabilities):
            raise DispatchError(
                "Keep staged email drafts and filesystem writes in separate workers."
            )
        tier = str(raw.get("tier") or "").lower()
        if tier not in agent.AGENT_TIERS:
            tier = _choose_worker_tier(complexity, dispatch_obj["priority"])
        model = str(raw.get("model") or "").strip() or _suggest_model(
            tier, complexity, dispatch_obj["priority"]
        )
        workers.append({
            "id": wid,
            "title": str(raw.get("title") or wid.replace("_", " ").title()).strip()[:100],
            "objective": objective[:20000],
            "instructions": str(raw.get("instructions") or "").strip()[:12000],
            "complexity": complexity,
            "capabilities": capabilities,
            "scope": str(raw.get("scope") or dispatch_obj.get("scope") or "").replace("\\", "/").strip().strip("/"),
            "tier": tier,
            "model": model[:160],
            "depends_on": [str(x) for x in raw.get("depends_on") or []],
            "approved_checks": [str(x).strip() for x in raw.get("approved_checks") or raw_plan.get("checks") or [] if str(x).strip()][:12],
            "status": "pending", "result": None, "error": None, "artifact": None,
        })
    ids = {w["id"] for w in workers}
    for worker in workers:
        if any(dep not in ids or dep == worker["id"] for dep in worker["depends_on"]):
            raise DispatchError(f"Worker '{worker['id']}' has an invalid dependency.")
    visiting, done = set(), set()

    def visit(wid):
        if wid in visiting:
            raise DispatchError("Worker dependencies contain a cycle.")
        if wid in done:
            return
        visiting.add(wid)
        item = next(w for w in workers if w["id"] == wid)
        for dep in item["depends_on"]:
            visit(dep)
        visiting.remove(wid)
        done.add(wid)

    for worker in workers:
        visit(worker["id"])
    # Non-Git scopes are checked again at execution; keeping writes in one scope
    # makes the final review/apply surface understandable.
    write_scopes = {w["scope"] for w in workers if WRITE_CAPS.intersection(w["capabilities"])}
    if len(write_scopes) > 1:
        raise DispatchError("All write-capable workers in one dispatch must use the same scope.")
    if (any("inbox_draft" in w["capabilities"] for w in workers)
            and any(FILE_WRITE_CAPS.intersection(w["capabilities"]) for w in workers)):
        raise DispatchError(
            "Keep staged email drafts and filesystem writes in separate dispatches."
        )
    return {
        "summary": str(raw_plan.get("summary") or "").strip()[:4000],
        "checks": [str(x).strip() for x in raw_plan.get("checks") or [] if str(x).strip()][:12],
        "workers": workers,
    }


PLANNER_SYSTEM = """You are Regalia's dispatch planner. Discuss a large task before execution.
Return ONLY JSON. If important information is still missing, return:
{"kind":"question","question":"one concise clarification"}
Otherwise return {"kind":"plan","summary":"...","checks":["approved command"],"workers":[...]}
Each worker needs id, title, objective, complexity (simple|moderate|hard), capabilities,
scope, tier, model, depends_on, and approved_checks. Capabilities are vault_read,
vault_write, code_read, code_write, run_checks, web, inbox_read, inbox_draft.
Use 2-8 workers for group tasks, parallelize independent work, give smaller models
simple work and stronger models hard/integration work. Never schedule writes outside
the stated scope. Research outputs must cite URLs. The user reviews the plan before launch."""


def submit_planner_message(dispatch_id: str, content: str, planner: dict | None = None) -> dict:
    content = str(content or "").strip()
    if not content:
        raise DispatchError("Write a planning response first.")
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    if obj.get("kind") != "group" or obj.get("state") not in ("clarifying", "ready", "failed"):
        raise DispatchError("This dispatch is not accepting planning messages.", 409)
    tier, model = _planner_choice(obj["priority"], planner or obj.get("planner"))

    def prepare(current):
        current["state"] = "planning"
        current["error"] = None
        current["planner"] = {"tier": tier, "model": model}
        current.setdefault("messages", []).append({"role": "user", "content": content})
        return current

    obj = dispatches.mutate_dispatch(dispatch_id, prepare)
    dispatches.append_event(dispatch_id, {"type": "planning_started", "tier": tier, "model": model})
    threading.Thread(target=_planner_worker, args=(dispatch_id,), daemon=True).start()
    return obj


def _planner_worker(dispatch_id: str) -> None:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        return
    messages = [
        {"role": m.get("role"), "content": m.get("content", "")}
        for m in obj.get("messages") or [] if m.get("role") in ("user", "assistant")
    ]
    try:
        result = router.chat(
            messages, tier=obj["planner"]["tier"], model=obj["planner"].get("model") or None,
            system=PLANNER_SYSTEM + f"\nDispatch priority: {obj['priority']}. Scope: {obj.get('scope') or 'vault root'}.",
            max_tokens=4096,
        )
        parsed = _json_object(result.get("reply"))
        if parsed.get("kind") == "question":
            question = str(parsed.get("question") or "What else should the team know?").strip()

            def ask(current):
                current["state"] = "clarifying"
                current["messages"].append({"role": "assistant", "content": question})
                return current

            dispatches.mutate_dispatch(dispatch_id, ask)
            dispatches.append_event(dispatch_id, {"type": "planner_question", "text": question})
            return
        plan = normalize_plan(obj, parsed)
    except Exception as e:  # noqa: BLE001 - fallback still gives the user an editable proposal
        try:
            plan = normalize_plan(obj, _fallback_plan(obj))
        except Exception:
            dispatches.mutate_dispatch(dispatch_id, lambda current: {
                **current, "state": "failed", "error": str(e),
            })
            dispatches.append_event(dispatch_id, {"type": "error", "text": str(e)})
            return

    def ready(current):
        current["state"] = "ready"
        current["plan"] = plan
        current["plan_revision"] = int(current.get("plan_revision") or 0) + 1
        current["workers"] = plan["workers"]
        current["messages"].append({
            "role": "assistant",
            "content": plan.get("summary") or "The dispatch plan is ready for review.",
        })
        return current

    dispatches.mutate_dispatch(dispatch_id, ready)
    dispatches.append_event(dispatch_id, {"type": "plan_ready", "workers": len(plan["workers"])})


def update_plan(dispatch_id: str, raw_plan: dict) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    if obj.get("state") != "ready":
        raise DispatchError("Only a ready plan can be edited.", 409)
    plan = normalize_plan(obj, raw_plan)

    def update(current):
        current["plan"] = plan
        current["workers"] = plan["workers"]
        current["plan_revision"] = int(current.get("plan_revision") or 0) + 1
        return current

    return dispatches.mutate_dispatch(dispatch_id, update)


def configure_single(dispatch_id: str, definition: dict) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    spec = agent.spec_from_definition(definition, "worker")
    worker = {
        "id": "worker", "title": spec["name"], "objective": obj["goal"],
        "instructions": spec["system"], "complexity": str(definition.get("complexity") or "moderate"),
        "capabilities": list(definition.get("capabilities") or []),
        "scope": str(definition.get("scope") or obj.get("scope") or ""),
        "tier": str(definition.get("tier") or "") or _choose_worker_tier("moderate", obj["priority"]),
        "model": str(definition.get("model") or ""), "depends_on": [],
        "approved_checks": list(definition.get("approved_checks") or []),
    }
    plan = normalize_plan(obj, {"summary": "Single agent dispatch", "workers": [worker]})
    return dispatches.mutate_dispatch(dispatch_id, lambda current: {
        **current, "state": "ready", "plan": plan, "workers": plan["workers"],
        "plan_revision": 1,
    })


def launch(dispatch_id: str) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    if obj.get("state") not in ("ready", "interrupted", "failed") or not obj.get("plan"):
        raise DispatchError("Review a complete dispatch plan before launching.", 409)
    file_writers: dict[str, list[dict]] = {}
    for worker in obj.get("workers") or []:
        tier = str(worker.get("tier") or "")
        if not _tier_available(tier):
            raise DispatchError(
                f"{worker.get('title') or worker.get('id')} is assigned to unavailable tier '{tier}'. "
                "Connect it or choose another tier before launch.", 503,
            )
        if tier == "chatgpt" and any(
                cap.startswith("inbox_") for cap in worker.get("capabilities") or []):
            raise DispatchError(
                "ChatGPT-account workers cannot access connected inboxes yet; choose Claude, "
                "Local, Anthropic API, or OpenAI API for that worker.", 409,
            )
        scope = agent.resolve_scope(worker.get("scope") or "")
        if FILE_WRITE_CAPS.intersection(worker.get("capabilities") or []):
            file_writers.setdefault(str(scope.root), []).append(worker)
    for source, writers in file_writers.items():
        if len(writers) > 1 and dispatch_workspace._git_root(Path(source)) is None:
            raise DispatchError(
                "Non-Git folders support one write-capable worker per dispatch. "
                "Combine the writing task or initialize Git before launch.", 409,
            )
    with _runtime_lock:
        if dispatch_id in _active:
            raise DispatchError("That dispatch is already running.", 409)
        _active.add(dispatch_id)
        cancel = threading.Event()
        _cancel_events[dispatch_id] = cancel

    def prepare(current):
        current["state"] = "running"
        current["cancel_requested"] = False
        current["error"] = None
        for worker in current.get("workers") or []:
            if worker.get("status") not in ("done",):
                worker.update(status="pending", error=None, result=None, artifact=None)
        return current

    obj = dispatches.mutate_dispatch(dispatch_id, prepare)
    dispatches.append_event(dispatch_id, {"type": "dispatch_started"})
    threading.Thread(target=_orchestrate, args=(dispatch_id, cancel), daemon=True).start()
    return obj


def _worker_definition(worker: dict) -> dict:
    return {
        "name": worker["title"], "objective": worker["objective"],
        "instructions": worker.get("instructions") or (
            f"You are the {worker['title']} worker. Complete only your assigned objective. "
            "Use evidence from the assigned scope. Cite public URLs. Finish with results, "
            "changed files, checks, and unresolved risks."
        ),
        "capabilities": worker["capabilities"], "tier": worker["tier"],
        "approved_checks": worker.get("approved_checks") or [],
    }


def _set_worker(dispatch_id: str, worker_id: str, **changes) -> dict:
    def mutate(current):
        for worker in current.get("workers") or []:
            if worker.get("id") == worker_id:
                worker.update(changes)
                break
        return current
    return dispatches.mutate_dispatch(dispatch_id, mutate)


def _run_worker(dispatch_id: str, worker: dict, cancel: threading.Event,
                dependency_artifacts: list[dict]) -> tuple[dict, dict | None]:
    _set_worker(dispatch_id, worker["id"], status="running")
    dispatches.append_event(dispatch_id, {
        "type": "worker_started", "worker": worker["id"], "title": worker["title"],
        "tier": worker["tier"], "model": worker.get("model") or "default",
    })
    scope = agent.resolve_scope(worker.get("scope") or "")
    writes = bool(WRITE_CAPS.intersection(worker["capabilities"]))
    workspace = None
    run_scope = scope
    if writes and not any(c.startswith("inbox_") for c in worker["capabilities"]):
        dep_paths = [a["path"] for a in dependency_artifacts
                     if a and a.get("kind") == "git" and a.get("has_changes")]
        workspace = dispatch_workspace.prepare_worker(
            dispatch_id, worker["id"], scope.root, dependency_patches=dep_paths,
        )
        run_scope = agent.AccessScope(
            "external", workspace.root, scope.label or "isolated workspace", True,
            tuple(worker.get("approved_checks") or ()),
        )
    spec = agent.spec_from_definition(_worker_definition(worker), worker["id"])

    def emit(event):
        payload = dict(event)
        tool_input = payload.get("input")
        if workspace and payload.get("type") == "tool" and isinstance(tool_input, dict):
            tool_input = dict(tool_input)

            def workspace_relative(raw):
                if not raw:
                    return raw
                path = Path(str(raw))
                if not path.is_absolute():
                    return raw
                try:
                    return path.resolve().relative_to(workspace.root.resolve()).as_posix()
                except (OSError, ValueError):
                    return raw

            for key in ("path", "file_path", "notebook_path"):
                if key in tool_input:
                    tool_input[key] = workspace_relative(tool_input[key])
            if isinstance(tool_input.get("changes"), list):
                tool_input["changes"] = [
                    {**change, "path": workspace_relative(change.get("path") or change.get("file_path"))}
                    if isinstance(change, dict) else change
                    for change in tool_input["changes"]
                ]
            payload["input"] = tool_input
        dispatches.append_event(dispatch_id, {**payload, "worker": worker["id"]})

    result = agent.run_agent(
        worker["id"], worker["objective"], tier=worker["tier"], model=worker.get("model") or "",
        emit=emit, spec_override=spec, scope_override=run_scope, cancel_event=cancel,
    )
    artifact = dispatch_workspace.collect_artifact(workspace) if workspace else None
    staged_drafts = [
        dict(step.get("input") or {}) for step in result.get("steps") or []
        if step.get("tool") in ("stage_email_draft", "mcp__mailbox__stage_email_draft")
    ]
    if staged_drafts:
        draft_artifact = {
            "kind": "email_drafts", "drafts": staged_drafts,
            "files": [f"Draft: {d.get('subject') or '(no subject)'}" for d in staged_drafts],
            "preview": "\n\n".join(
                f"To: {d.get('to') or '(thread reply)'}\nSubject: {d.get('subject') or ''}\n\n{d.get('body') or ''}"
                for d in staged_drafts
            )[:100000],
            "has_changes": True,
        }
        if artifact and artifact.get("has_changes"):
            raise DispatchError("A single worker cannot stage both files and email drafts.", 409)
        artifact = draft_artifact
    _set_worker(dispatch_id, worker["id"], status="done", result=result, artifact=artifact)
    dispatches.append_event(dispatch_id, {
        "type": "worker_done", "worker": worker["id"], "has_changes": bool(artifact and artifact.get("has_changes")),
    })
    return result, artifact


def _orchestrate(dispatch_id: str, cancel: threading.Event) -> None:
    try:
        obj = dispatches.get_dispatch(dispatch_id)
        workers = {w["id"]: dict(w) for w in obj.get("workers") or []}
        results = {wid: w.get("result") for wid, w in workers.items() if w.get("status") == "done"}
        artifacts = {wid: w.get("artifact") for wid, w in workers.items()
                     if w.get("status") == "done" and w.get("artifact")}
        failed = set()
        pending = {wid for wid in workers if wid not in results}
        concurrency = CONCURRENCY.get(obj.get("priority"), 3)
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="dispatch") as pool:
            running = {}
            while pending or running:
                if cancel.is_set():
                    raise DispatchError("Dispatch cancelled.", 409)
                blocked = [wid for wid in pending if any(dep in failed for dep in workers[wid]["depends_on"])]
                for wid in blocked:
                    pending.remove(wid)
                    failed.add(wid)
                    _set_worker(dispatch_id, wid, status="blocked", error="A dependency failed.")
                ready = [wid for wid in pending
                         if all(dep in results for dep in workers[wid]["depends_on"])]
                for wid in ready[:max(0, concurrency - len(running))]:
                    pending.remove(wid)
                    deps = [artifacts.get(dep) for dep in workers[wid]["depends_on"] if artifacts.get(dep)]
                    running[pool.submit(_run_worker, dispatch_id, workers[wid], cancel, deps)] = wid
                if not running:
                    if pending:
                        raise DispatchError("No runnable workers remain; check the dependency plan.")
                    break
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in done:
                    wid = running.pop(future)
                    try:
                        result, artifact = future.result()
                        results[wid] = result
                        if artifact:
                            artifacts[wid] = artifact
                    except Exception as e:  # noqa: BLE001 - one worker failure should not erase siblings
                        failed.add(wid)
                        _set_worker(dispatch_id, wid, status="failed", error=str(e))
                        dispatches.append_event(dispatch_id, {"type": "worker_failed", "worker": wid, "text": str(e)})
        if cancel.is_set():
            raise DispatchError("Dispatch cancelled.", 409)
        if failed:
            raise DispatchError(f"{len(failed)} worker(s) failed or were blocked. Retry or reassign them.")
        obj = dispatches.get_dispatch(dispatch_id)
        synthesis = _synthesize(obj, results)
        integrated = []
        by_scope: dict[str, list[dict]] = {}
        for wid, artifact in artifacts.items():
            if artifact and artifact.get("has_changes"):
                if artifact.get("kind") == "email_drafts":
                    integrated.append(artifact)
                    continue
                scope = workers[wid].get("scope") or ""
                by_scope.setdefault(scope, []).append(artifact)
        for scope_label, group in by_scope.items():
            source = agent.resolve_scope(scope_label).root
            integrated.append(dispatch_workspace.integrate(dispatch_id, source, group))
        has_changes = any(a.get("has_changes") for a in integrated)

        def finish(current):
            current["result"] = synthesis
            current["artifacts"] = integrated
            current["state"] = "awaiting_apply" if has_changes else "completed"
            return current

        dispatches.mutate_dispatch(dispatch_id, finish)
        dispatches.append_event(dispatch_id, {
            "type": "awaiting_apply" if has_changes else "dispatch_completed",
            "files": sum(len(a.get("files") or []) for a in integrated),
        })
    except Exception as e:  # noqa: BLE001
        state = "cancelled" if cancel.is_set() or getattr(e, "status", None) == 409 else "failed"
        dispatches.mutate_dispatch(dispatch_id, lambda current: {
            **current, "state": state, "error": str(e),
        })
        dispatches.append_event(dispatch_id, {"type": state, "text": str(e)})
    finally:
        with _runtime_lock:
            _active.discard(dispatch_id)
            _cancel_events.pop(dispatch_id, None)


def _synthesize(obj: dict, results: dict) -> dict:
    worker_text = "\n\n".join(
        f"## {wid}\n{(result or {}).get('reply', '')}" for wid, result in results.items()
    )
    prompt = (
        f"Synthesize the completed dispatch for this goal:\n{obj['goal']}\n\n"
        f"Worker outputs:\n{worker_text}\n\nReturn one decision-ready answer with findings, "
        "source URLs, changed files, checks, and unresolved risks. Do not invent evidence."
    )
    try:
        tier, model = _planner_choice(obj["priority"], obj.get("planner"))
        answer = router.chat([{"role": "user", "content": prompt}], tier=tier,
                             model=model or None, max_tokens=4096).get("reply", "")
        if obj.get("priority") == "best":
            review_prompt = (
                "Critically review and improve this synthesis against the worker evidence. "
                "Correct unsupported claims and preserve citations.\n\n" + answer + "\n\nEvidence:\n" + worker_text
            )
            answer = router.chat([{"role": "user", "content": review_prompt}], tier=tier,
                                 model=model or None, max_tokens=4096).get("reply", answer)
        return {"reply": answer, "tier": tier, "model": model or "default", "workers": len(results)}
    except Exception:
        return {"reply": worker_text, "tier": "fallback", "model": "none", "workers": len(results)}


def cancel(dispatch_id: str) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    with _runtime_lock:
        event = _cancel_events.get(dispatch_id)
    if event:
        event.set()
    return dispatches.mutate_dispatch(dispatch_id, lambda current: {
        **current, "cancel_requested": True,
    })


def apply(dispatch_id: str) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    if obj.get("state") != "awaiting_apply":
        raise DispatchError("This dispatch has no reviewed changes awaiting apply.", 409)
    applied = []
    try:
        for artifact_index, artifact in enumerate(obj.get("artifacts") or []):
            if artifact.get("kind") == "email_drafts":
                for draft_index, draft in enumerate(artifact.get("drafts") or []):
                    if draft.get("applied_id"):
                        applied.append(f"Email draft {draft['applied_id']}")
                        continue
                    result = mailbox.create_draft(
                        str(draft.get("account_id") or ""), to=str(draft.get("to") or ""),
                        subject=str(draft.get("subject") or ""), body=str(draft.get("body") or ""),
                        reply_to_msg_id=str(draft.get("reply_to") or ""),
                    )
                    draft_id = str(result.get("id") or "")
                    if not draft_id:
                        raise DispatchError("The mailbox saved a draft but did not return its id; review the mailbox before retrying.", 409)
                    applied.append(f"Email draft {draft_id}".strip())

                    def record_draft(current, ai=artifact_index, di=draft_index, did=draft_id):
                        current["artifacts"][ai]["drafts"][di]["applied_id"] = did
                        return current

                    dispatches.mutate_dispatch(dispatch_id, record_draft)
            else:
                applied.extend(dispatch_workspace.apply_artifact(artifact).get("files") or [])
    except (dispatch_workspace.WorkspaceError, mailbox.MailboxError, OSError, ValueError) as e:
        raise DispatchError(str(getattr(e, "message", e)), 409)
    dispatches.mutate_dispatch(dispatch_id, lambda current: {
        **current, "state": "completed", "applied": True,
    })
    dispatches.append_event(dispatch_id, {"type": "changes_applied", "files": applied})
    roots = [Path(a["source_root"]) for a in obj.get("artifacts") or [] if a.get("source_root")]
    dispatch_workspace.cleanup_dispatch(dispatch_id, roots[0] if roots else None)
    return {"applied": True, "files": applied}


def discard(dispatch_id: str) -> dict:
    obj = dispatches.get_dispatch(dispatch_id)
    if not obj:
        raise DispatchError("No such dispatch.", 404)
    if obj.get("state") != "awaiting_apply":
        raise DispatchError("This dispatch has no staged changes to discard.", 409)
    dispatches.mutate_dispatch(dispatch_id, lambda current: {
        **current, "state": "completed", "applied": False, "artifacts": [],
    })
    dispatches.append_event(dispatch_id, {"type": "changes_discarded"})
    roots = [Path(a["source_root"]) for a in obj.get("artifacts") or [] if a.get("source_root")]
    dispatch_workspace.cleanup_dispatch(dispatch_id, roots[0] if roots else None)
    return {"discarded": True}


def public_dispatch(obj: dict) -> dict:
    if not obj:
        return obj
    clean = json.loads(json.dumps(obj))
    for artifact in clean.get("artifacts") or []:
        artifact.pop("path", None)
        artifact.pop("source_root", None)
    for worker in clean.get("workers") or []:
        if isinstance(worker.get("artifact"), dict):
            worker["artifact"].pop("path", None)
            worker["artifact"].pop("source_root", None)
    return clean
