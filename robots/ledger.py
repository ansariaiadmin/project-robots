"""Financial & Growth Ledger Robot for Autonomous Upgrades."""

from __future__ import annotations

import json
from pathlib import Path

LEDGER_FILE = Path(__file__).resolve().parents[1] / "profiles" / "ledger.json"


def load_ledger() -> dict:
    if not LEDGER_FILE.exists():
        default_data = {
            "balance_usd": 0.0,
            "target_hardware": {
                "item": "1TB NVMe PCIe 4.0 SSD",
                "cost_usd": 85.0,
                "achieved": False,
            },
            "transactions": [],
        }
        save_ledger(default_data)
        return default_data
    with open(LEDGER_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ledger(data: dict) -> None:
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    data = load_ledger()
    print(json.dumps(data, indent=2))  # noqa: T201
