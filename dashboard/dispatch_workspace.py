"""Isolated workspaces and reviewable artifacts for write-capable dispatches."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import paths


WORK_ROOT = paths.data_dir() / ".dispatch_work"
_IGNORE = shutil.ignore_patterns(
    ".git", ".dispatch_work", "__pycache__", ".pytest_cache", "node_modules",
    "build", "dist", "*.pyc",
)


class WorkspaceError(Exception):
    pass


@dataclass
class WorkerWorkspace:
    dispatch_id: str
    worker_id: str
    source_scope: Path
    root: Path
    kind: str
    git_root: Path | None = None
    rel_scope: str = "."
    baseline: Path | None = None


def _run(argv, cwd: Path, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(x) for x in argv], cwd=str(cwd), input=input_text,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    if check and proc.returncode:
        raise WorkspaceError((proc.stderr or proc.stdout or "Workspace command failed.").strip())
    return proc


def _git_root(scope: Path) -> Path | None:
    try:
        proc = _run(["git", "rev-parse", "--show-toplevel"], scope)
        root = Path(proc.stdout.strip()).resolve()
        return root if root.is_dir() else None
    except (WorkspaceError, OSError, subprocess.SubprocessError):
        return None


def _safe_child(base: Path, name: str) -> Path:
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise WorkspaceError("Invalid isolated workspace id.")
    target = (base / name).resolve()
    if target.parent != base.resolve():
        raise WorkspaceError("Workspace path escapes its dispatch folder.")
    return target


def _copy_untracked(git_root: Path, rel_scope: str, worktree: Path) -> None:
    proc = _run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", rel_scope],
        git_root,
    )
    for raw in proc.stdout.splitlines():
        rel = raw.strip().replace("\\", "/")
        if not rel:
            continue
        source = (git_root / rel).resolve()
        target = (worktree / rel).resolve()
        if git_root not in source.parents or worktree not in target.parents or not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def prepare_worker(dispatch_id: str, worker_id: str, source_scope: Path,
                   dependency_patches: list[str] | None = None) -> WorkerWorkspace:
    source_scope = source_scope.resolve()
    dispatch_root = _safe_child(WORK_ROOT, dispatch_id)
    dispatch_root.mkdir(parents=True, exist_ok=True)
    target = _safe_child(dispatch_root, worker_id)
    if target.exists():
        shutil.rmtree(target)
    git_root = _git_root(source_scope)
    if git_root:
        rel_scope = source_scope.relative_to(git_root).as_posix()
        _run(["git", "worktree", "add", "--detach", str(target), "HEAD"], git_root)
        dirty = _run(["git", "diff", "--binary", "HEAD", "--", rel_scope], git_root).stdout
        if dirty.strip():
            _run(["git", "apply", "--whitespace=nowarn", "-"], target, input_text=dirty)
        _copy_untracked(git_root, rel_scope, target)
        _run(["git", "add", "-A", "--", rel_scope], target)
        _run([
            "git", "-c", "user.name=Regalia Dispatch", "-c",
            "user.email=dispatch@local", "commit", "--allow-empty", "-m",
            "regalia dispatch baseline",
        ], target)
        for patch_path in dependency_patches or []:
            patch = Path(patch_path).read_text(encoding="utf-8")
            if patch.strip():
                _run(["git", "apply", "--whitespace=nowarn", "-"], target, input_text=patch)
        if dependency_patches:
            _run(["git", "add", "-A", "--", rel_scope], target)
            _run([
                "git", "-c", "user.name=Regalia Dispatch", "-c",
                "user.email=dispatch@local", "commit", "--allow-empty", "-m",
                "dependency results",
            ], target)
        return WorkerWorkspace(
            dispatch_id, worker_id, source_scope, (target / rel_scope).resolve(),
            "git", git_root=git_root, rel_scope=rel_scope,
        )

    baseline = _safe_child(dispatch_root, worker_id + "_baseline")
    if baseline.exists():
        shutil.rmtree(baseline)
    shutil.copytree(source_scope, baseline, ignore=_IGNORE)
    shutil.copytree(baseline, target, ignore=_IGNORE)
    return WorkerWorkspace(
        dispatch_id, worker_id, source_scope, target, "copy", baseline=baseline,
    )


def _file_map(root: Path) -> dict[str, Path]:
    out = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and ".git" not in path.parts:
            out[path.relative_to(root).as_posix()] = path
    return out


def _digest(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_artifact(workspace: WorkerWorkspace) -> dict:
    artifact_root = _safe_child(_safe_child(WORK_ROOT, workspace.dispatch_id), "artifacts")
    artifact_root.mkdir(parents=True, exist_ok=True)
    if workspace.kind == "git":
        # Find the actual worktree root rather than assuming a one-level scope.
        worktree_root = Path(_run(["git", "rev-parse", "--show-toplevel"], workspace.root).stdout.strip())
        _run(["git", "add", "-N", "--", workspace.rel_scope], worktree_root)
        patch = _run(["git", "diff", "--binary", "HEAD", "--", workspace.rel_scope], worktree_root).stdout
        out_path = artifact_root / f"{workspace.worker_id}.patch"
        out_path.write_text(patch, encoding="utf-8")
        files = re_paths_from_patch(patch)
        return {
            "kind": "git", "path": str(out_path), "files": files,
            "preview": patch[:100000], "has_changes": bool(patch.strip()),
            "source_root": str(workspace.git_root),
        }

    before = _file_map(workspace.baseline or workspace.root)
    after = _file_map(workspace.root)
    changes = []
    for rel in sorted(set(before) | set(after)):
        old, new = before.get(rel), after.get(rel)
        if _digest(old) == _digest(new):
            continue
        payload = None
        if new:
            payload = base64.b64encode(new.read_bytes()).decode("ascii")
        changes.append({
            "path": rel, "before": _digest(workspace.source_scope / rel),
            "delete": new is None, "content_b64": payload,
        })
    out_path = artifact_root / f"{workspace.worker_id}.json"
    out_path.write_text(json.dumps(changes, ensure_ascii=False), encoding="utf-8")
    preview = "\n".join(("DELETE " if c["delete"] else "WRITE ") + c["path"] for c in changes)
    return {
        "kind": "copy", "path": str(out_path), "files": [c["path"] for c in changes],
        "preview": preview, "has_changes": bool(changes),
        "source_root": str(workspace.source_scope),
    }


def re_paths_from_patch(patch: str) -> list[str]:
    paths_out = []
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            rel = line[6:].strip()
            if rel != "/dev/null" and rel not in paths_out:
                paths_out.append(rel)
        elif line.startswith("--- a/") and line[6:].strip() != "/dev/null":
            rel = line[6:].strip()
            if rel not in paths_out:
                paths_out.append(rel)
    return paths_out


def integrate(dispatch_id: str, source_scope: Path, artifacts: list[dict]) -> dict:
    changed = [a for a in artifacts if a.get("has_changes")]
    if not changed:
        return {"kind": "none", "files": [], "preview": "", "has_changes": False}
    kinds = {a.get("kind") for a in changed}
    if kinds == {"copy"}:
        if len(changed) > 1:
            raise WorkspaceError("Non-Git dispatches allow only one write-capable worker.")
        return dict(changed[0])
    if kinds != {"git"}:
        raise WorkspaceError("Cannot combine Git and non-Git artifacts.")
    ws = prepare_worker(dispatch_id, "integration", source_scope)
    worktree_root = Path(_run(["git", "rev-parse", "--show-toplevel"], ws.root).stdout.strip())
    for artifact in changed:
        patch = Path(artifact["path"]).read_text(encoding="utf-8")
        if patch.strip():
            _run(["git", "apply", "--whitespace=nowarn", "-"], worktree_root, input_text=patch)
    return collect_artifact(ws)


def apply_artifact(artifact: dict) -> dict:
    if not artifact or not artifact.get("has_changes"):
        return {"applied": True, "files": []}
    if artifact.get("kind") == "git":
        root = Path(artifact.get("source_root") or "").resolve()
        patch = Path(artifact["path"]).read_text(encoding="utf-8")
        _run(["git", "apply", "--check", "--whitespace=nowarn", "-"], root, input_text=patch)
        _run(["git", "apply", "--whitespace=nowarn", "-"], root, input_text=patch)
        return {"applied": True, "files": artifact.get("files") or []}
    if artifact.get("kind") == "copy":
        root = Path(artifact.get("source_root") or "").resolve()
        changes = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
        for change in changes:
            target = (root / change["path"]).resolve()
            if target != root and root not in target.parents:
                raise WorkspaceError("Artifact path escapes its source scope.")
            if _digest(target) != change.get("before"):
                raise WorkspaceError(f"'{change['path']}' changed after dispatch; review the conflict.")
        for change in changes:
            target = (root / change["path"]).resolve()
            if change.get("delete"):
                if target.is_file():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(change.get("content_b64") or ""))
        return {"applied": True, "files": [c["path"] for c in changes]}
    raise WorkspaceError("Unknown dispatch artifact type.")


def cleanup_dispatch(dispatch_id: str, git_root: Path | None = None) -> None:
    base = _safe_child(WORK_ROOT, dispatch_id)
    if git_root and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and (child / ".git").exists():
                _run(["git", "worktree", "remove", "--force", str(child)], git_root, check=False)
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
