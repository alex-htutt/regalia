"""Continually pings a host and reports packet loss over time.

Usage:
    python packet_loss_monitor.py [host] [--interval SECONDS] [--window N]

Prints a running packet-loss percentage over a rolling window, plus a
summary when stopped (Ctrl+C).
"""

import argparse
import platform
import re
import subprocess
import sys
import time
from collections import deque
from datetime import datetime


def build_ping_command(host: str) -> list[str]:
    if platform.system().lower() == "windows":
        return ["ping", "-n", "1", "-w", "1000", host]
    return ["ping", "-c", "1", "-W", "1", host]


def parse_rtt_ms(output: str) -> float | None:
    match = re.search(r"time[=<]([\d.]+)\s*ms", output, re.IGNORECASE)
    return float(match.group(1)) if match else None


def ping_once(host: str) -> tuple[bool, float | None]:
    try:
        result = subprocess.run(
            build_ping_command(host),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return True, parse_rtt_ms(result.stdout)
        return False, None
    except subprocess.TimeoutExpired:
        return False, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor packet loss over time via ping.")
    parser.add_argument("host", nargs="?", default="8.8.8.8", help="Host to ping (default: 8.8.8.8)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between pings (default: 1)")
    parser.add_argument("--window", type=int, default=50, help="Rolling window size for loss %% (default: 50)")
    args = parser.parse_args()

    results: deque[bool] = deque(maxlen=args.window)
    sent = 0
    lost = 0

    print(f"Pinging {args.host} every {args.interval}s (window={args.window}). Ctrl+C to stop.\n")

    try:
        while True:
            ok, rtt = ping_once(args.host)
            sent += 1
            results.append(ok)
            if not ok:
                lost += 1

            window_loss_pct = (1 - sum(results) / len(results)) * 100
            overall_loss_pct = (lost / sent) * 100
            timestamp = datetime.now().strftime("%H:%M:%S")

            status = f"rtt={rtt:.1f}ms" if ok else "TIMEOUT"
            print(
                f"[{timestamp}] {status:<12} "
                f"window_loss={window_loss_pct:5.1f}%  overall_loss={overall_loss_pct:5.1f}%  "
                f"({sent} sent, {lost} lost)"
            )

            time.sleep(args.interval)
    except KeyboardInterrupt:
        overall_loss_pct = (lost / sent) * 100 if sent else 0.0
        print(f"\nStopped. {sent} sent, {lost} lost, {overall_loss_pct:.1f}% overall packet loss.")
        sys.exit(0)


if __name__ == "__main__":
    main()
