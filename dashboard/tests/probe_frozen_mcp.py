"""Black-box probe for Regalia's frozen ``--mail-mcp`` entrypoint.

Usage: ``python tests/probe_frozen_mcp.py path/to/Regalia.exe``
The probe performs an MCP initialize + tools/list handshake over stdio and
asserts the packaged server remains drafts-only. It uses only the stdlib so the
release workflow can run it immediately after PyInstaller.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: probe_frozen_mcp.py <Regalia executable>")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"frozen executable not found: {executable}")

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "regalia-release-probe", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    payload = "".join(json.dumps(message) + "\n" for message in messages)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    proc = subprocess.run(
        [str(executable), "--mail-mcp"],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        creationflags=creationflags,
    )
    if proc.returncode:
        raise SystemExit(f"MCP process failed ({proc.returncode}): {proc.stderr.strip()}")

    responses = []
    for line in proc.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            responses.append(value)
    by_id = {response.get("id"): response for response in responses if "id" in response}
    if 1 not in by_id or "result" not in by_id[1]:
        raise SystemExit("MCP initialize response was missing")
    tools = ((by_id.get(2, {}).get("result") or {}).get("tools") or [])
    names = {str(tool.get("name")) for tool in tools if isinstance(tool, dict)}
    expected = {"list_inboxes", "read_inbox", "search_email", "read_email", "draft_email"}
    if names != expected:
        raise SystemExit(f"unexpected packaged MCP tools: {sorted(names)}")
    if any("send" in name.lower() for name in names):
        raise SystemExit("packaged MCP unexpectedly exposes a send tool")
    print("Frozen mailbox MCP probe passed: " + ", ".join(sorted(names)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
