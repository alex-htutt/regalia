---
date: 2026-07-25
tags: [area/projects, type/reference]
status: active
topic: "networking"
deadline:
related: []
---

# packet-loss-monitor — Context

> Dense, manually maintained snapshot. Prime any Cursor chat with `@file projects/packet-loss-monitor/_context_packet-loss-monitor.md`.

## Current state
- `packet_loss_monitor.py`: pings a host on a loop (default `8.8.8.8`, 1s interval), prints rolling-window and overall packet-loss % per line, and a summary on Ctrl+C.

## Active deliverable(s)
- CLI script only. No packaging/tests yet.

## Open questions
- Log to CSV for later plotting?

## Key people / resources
-

## Next deadline
-
