"""Agent Brain: Context Aggregator and Ollama Loop Connector."""

from __future__ import annotations

import json
import subprocess

from robots.ledger import load_ledger
from robots.telemetry import get_system_metrics


def collect_agent_state() -> dict:
    # 1. Get Hardware Sense
    metrics = get_system_metrics()

    # 2. Get Financial Sense
    ledger = load_ledger()

    # 3. Get Project Health Sense
    docs_res = subprocess.run(
        ["./project-robots", "--project", ".", "docs"],
        capture_output=True,
        text=True,
    )
    hygiene_res = subprocess.run(
        ["./project-robots", "--project", ".", "hygiene"],
        capture_output=True,
        text=True,
    )

    state = {
        "status": "ready",
        "telemetry": metrics,
        "ledger": ledger,
        "health": {
            "docs_ok": "PASS" in docs_res.stdout,
            "hygiene_ok": "PASS" in hygiene_res.stdout,
        },
    }
    return state


if __name__ == "__main__":
    current_state = collect_agent_state()
    print(json.dumps(current_state, indent=2))  # noqa: T201
