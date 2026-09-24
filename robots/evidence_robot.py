#!/usr/bin/env python3
"""Reject stale check evidence and summarize the latest current result."""

from __future__ import annotations

import json
from pathlib import Path

from .common import cache_dir, load_config, source_state, write_json


def inspect(project: Path) -> tuple[dict, Path]:
    config, _source = load_config(project)
    current = source_state(project, config)
    latest = cache_dir(project, "checks") / "latest.json"
    if not latest.is_file():
        payload = {
            "ok": False,
            "project": str(project),
            "summary": {"current": False, "passed": False},
            "reason": "No recorded check evidence.",
            "sourceState": current,
        }
    else:
        try:
            evidence = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            evidence = {}
        bound = (
            evidence.get("stableSourceState") is True
            and evidence.get("sourceState") == current
        )
        passed = bound and evidence.get("passed") is True
        payload = {
            "ok": passed,
            "project": str(project),
            "summary": {
                "current": bound,
                "passed": passed,
                "checks": len(evidence.get("results", [])),
            },
            "reason": (
                "Current source-bound evidence passed."
                if passed
                else "Evidence is missing, stale, unstable, or failed."
            ),
            "sourceState": current,
            "evidenceCreatedAt": evidence.get("createdAt"),
            "failedChecks": [
                row.get("name")
                for row in evidence.get("results", [])
                if row.get("passed") is not True
            ],
        }
    output = write_json(project, "evidence", "latest.json", payload)
    return payload, output
