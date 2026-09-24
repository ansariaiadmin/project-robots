#!/usr/bin/env python3
"""Combine robot outputs into one compact project report."""

from __future__ import annotations

from pathlib import Path

from .checks_robot import build_plan, compact_plan
from .common import write_json, write_markdown
from .context_robot import build as build_context
from .discovery_robot import inspect as inspect_discovery
from .docs_robot import inspect as inspect_docs
from .evidence_robot import inspect as inspect_evidence
from .hygiene_robot import inspect as inspect_hygiene


def build(project: Path, task: str = "", budget: int | None = None) -> tuple[dict, Path, Path]:
    discovery, _ = inspect_discovery(project)
    context, _, context_markdown = build_context(project, task=task, budget=budget)
    docs, _ = inspect_docs(project)
    hygiene, _ = inspect_hygiene(project)
    evidence, _ = inspect_evidence(project)
    plan = compact_plan(build_plan(project))
    blockers = []
    if not docs["ok"]:
        blockers.append(f"documentation errors: {docs['summary']['errors']}")
    if not hygiene["ok"]:
        blockers.append(f"hygiene errors: {hygiene['summary']['errors']}")
    if not evidence["summary"]["current"]:
        blockers.append("no current source-bound check evidence")
    payload = {
        "ok": not blockers,
        "project": str(project),
        "summary": {
            "kinds": sorted(discovery["kinds"]),
            "files": discovery["summary"]["trackedFiles"],
            "changedFiles": context["summary"]["changedFiles"],
            "docsErrors": docs["summary"]["errors"],
            "hygieneErrors": hygiene["summary"]["errors"],
            "evidenceCurrent": evidence["summary"]["current"],
        },
        "blockers": blockers,
        "nextChecks": plan["commands"],
        "contextOutput": str(context_markdown),
    }
    json_path = write_json(project, "report", "latest.json", payload)
    lines = [
        "# Project Robot Report",
        "",
        f"Project: `{project}`",
        f"Status: **{'PASS' if payload['ok'] else 'WORK REQUIRED'}**",
        "",
        "## Snapshot",
        "",
        f"- Kinds: {', '.join(payload['summary']['kinds']) or 'unknown'}",
        f"- Files: {payload['summary']['files']}",
        f"- Changed: {payload['summary']['changedFiles']}",
        f"- Documentation errors: {payload['summary']['docsErrors']}",
        f"- Hygiene errors: {payload['summary']['hygieneErrors']}",
        f"- Current evidence: {payload['summary']['evidenceCurrent']}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in blockers)
    if not blockers:
        lines.append("- None.")
    lines.extend(("", "## Next checks", ""))
    lines.extend(f"- `{item['name']}` — `{item['command']}`" for item in plan["commands"])
    if not plan["commands"]:
        lines.append("- No changed-file check required.")
    markdown_path = write_markdown(project, "report", "latest.md", "\n".join(lines))
    return payload, json_path, markdown_path
