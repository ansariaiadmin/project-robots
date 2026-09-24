#!/usr/bin/env python3
"""Create a compact routing packet instead of copying whole files."""

from __future__ import annotations

from pathlib import Path

from .common import (
    auto_checks,
    changed_files,
    comment_marker,
    load_config,
    match_any,
    read_text,
    source_state,
    tracked_files,
    write_json,
    write_markdown,
)

TASK_ALIASES = {
    "docs": {"doc", "docs", "document", "documentation", "readme", "roadmap", "module"},
    "ui": {"ui", "ux", "interface", "frontend", "style", "css", "layout"},
    "core": {"core", "backend", "logic", "service", "storage", "data", "api"},
    "release": {"release", "deploy", "package", "docker", "ci", "build"},
    "automation": {"automation", "robot", "agent", "tool", "script"},
}


def _scope_rows(paths: list[str], config: dict, task: str) -> list[dict]:
    rows = []
    task_words = set(task.lower().replace("/", " ").replace("-", " ").split())
    for raw_scope in config.get("routes", []):
        if not isinstance(raw_scope, dict):
            continue
        patterns = [str(item) for item in raw_scope.get("patterns", [])]
        name = str(raw_scope.get("name", "scope"))
        if paths:
            if not any(match_any(path, patterns) for path in paths):
                continue
        else:
            keywords = {
                str(item).lower() for item in raw_scope.get("keywords", [])
            }
            keywords.update(TASK_ALIASES.get(name.lower(), {name.lower()}))
            if not task_words.intersection(keywords):
                continue
        rows.append({
            "name": name,
            "readFirst": [str(item) for item in raw_scope.get("readFirst", [])],
            "checks": [str(item) for item in raw_scope.get("checks", [])],
            "invariants": [str(item) for item in raw_scope.get("invariants", [])],
        })
    return rows


def _ownership_docs(
    project: Path,
    paths: list[str],
    task: str,
    config: dict,
) -> list[str]:
    max_bytes = int(config["limits"]["maxFileBytes"])
    task_words = {
        word for word in task.lower().replace("/", " ").replace("-", " ").split()
        if len(word) >= 3
    }
    matched = []
    for document in tracked_files(project, config):
        if document.suffix.lower() != ".md":
            continue
        relative = document.relative_to(project).as_posix()
        stem = document.stem.lower()
        text = read_text(document, max_bytes)
        if text is None:
            continue
        owns_changed_path = any(f"`{path}`" in text for path in paths)
        named_by_task = stem != "readme" and stem in task_words
        if owns_changed_path or named_by_task:
            matched.append(relative)
        if len(matched) >= 6:
            break
    return matched


def build(project: Path, task: str = "", budget: int | None = None) -> tuple[dict, Path, Path]:
    config, config_source = load_config(project)
    limits = config["limits"]
    token_budget = int(budget or limits["contextTokenBudget"])
    changes = changed_files(project, config)
    changed_paths = [item["path"] for item in changes]
    scopes = _scope_rows(changed_paths, config, task)
    read_first = [
        path for path in config.get("readFirst", [])
        if (project / path).is_file()
    ]
    for scope in scopes:
        read_first.extend(
            path for path in scope["readFirst"]
            if (project / path).is_file()
        )
    read_first.extend(_ownership_docs(project, changed_paths, task, config))
    read_first = list(dict.fromkeys(read_first))
    selected = list(dict.fromkeys((*changed_paths, *read_first)))

    estimated = 0
    selected_rows = []
    max_bytes = int(limits["maxFileBytes"])
    from robots.brain.redact import is_secret_path, secret_marker

    for relative in selected:
        path = project / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        token_estimate = max(1, size // 4)
        # Secrets/keys are never first-read: counted by marker, on-demand only.
        if is_secret_path(relative):
            selected_rows.append({
                "path": secret_marker(relative),
                "bytes": size,
                "estimatedTokens": token_estimate,
                "open": "on-demand",
            })
            continue
        if selected_rows and estimated + token_estimate > token_budget:
            selected_rows.append({
                "path": relative,
                "bytes": size,
                "estimatedTokens": token_estimate,
                "open": "on-demand",
            })
            continue
        estimated += token_estimate
        selected_rows.append({
            "path": relative,
            "bytes": size,
            "estimatedTokens": token_estimate,
            "open": "first",
        })

    markers = []
    for change in changes:
        path = project / change["path"]
        text = read_text(path, max_bytes)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            marker = comment_marker(line, path.suffix)
            if stripped.startswith(("<<<<<<<", "=======", ">>>>>>>")) or marker:
                markers.append({
                    "path": change["path"],
                    "line": number,
                    "text": stripped[:160],
                })
                if len(markers) >= int(limits["maxFindings"]):
                    break

    all_checks = auto_checks(project, config)
    routed_checks = list(dict.fromkeys(
        check
        for scope in scopes
        for check in scope["checks"]
        if check in all_checks
    ))
    if not routed_checks and not changed_paths and not task:
        routed_checks = ["diff"] if "diff" in all_checks else []
    elif not routed_checks:
        routed_checks = list(all_checks)[:4]
    invariants = list(dict.fromkeys((
        *[str(item) for item in config.get("invariants", [])],
        *(item for scope in scopes for item in scope["invariants"]),
    )))
    # RAG enrichment (fail-open, strictly within remaining budget).
    rag_info: dict = {"hits": [], "firstTokens": 0, "stale": True}
    try:
        from robots.rag.robot import query_for_context

        remaining = token_budget - estimated
        rag_task = task or " ".join(changed_paths[:3])
        if remaining > 0 and (task or changed_paths):
            rag_info = query_for_context(project, config, rag_task, remaining, k=15)
    except Exception:
        rag_info = {"hits": [], "firstTokens": 0, "stale": True}
    payload = {
        "ok": True,
        "project": str(project),
        "task": task,
        "configSource": config_source,
        "sourceState": source_state(project, config),
        "summary": {
            "changedFiles": len(changes),
            "selectedFiles": len(selected_rows),
            "estimatedFirstReadTokens": estimated,
            "tokenBudget": token_budget,
            "ragHits": len(rag_info.get("hits", [])),
            "ragFirstTokens": int(rag_info.get("firstTokens", 0)),
        },
        "scopes": [scope["name"] for scope in scopes],
        "changed": changes,
        "files": selected_rows,
        "rag": rag_info,
        "invariants": invariants,
        "recommendedChecks": routed_checks,
        "riskMarkers": markers,
    }
    json_path = write_json(project, "context", "latest.json", payload)
    lines = [
        "# Compact Project Context",
        "",
        f"Project: `{project}`",
        f"Task: {task or 'Not supplied'}",
        f"Changed files: {len(changes)}",
        f"First-read estimate: {estimated}/{token_budget} tokens",
        "",
        "## Read first",
        "",
    ]
    first_rows = [row for row in selected_rows if row["open"] == "first"]
    lines.extend(f"- `{row['path']}`" for row in first_rows)
    if not first_rows:
        lines.append("- None; inspect on demand.")
    lines.extend(("", "## Changed", ""))
    lines.extend(f"- `{item['status']}` `{item['path']}`" for item in changes)
    if not changes:
        lines.append("- Clean working tree.")
    lines.extend(("", "## Invariants", ""))
    lines.extend(f"- {item}" for item in invariants)
    if not invariants:
        lines.append("- Use project instructions and source as authority.")
    lines.extend(("", "## Checks", ""))
    lines.extend(f"- `{name}`" for name in routed_checks)
    if not routed_checks:
        lines.append("- No safe check auto-detected.")
    rag_hits = rag_info.get("hits", [])
    if rag_hits:
        lines.extend(("", "## RAG hits", ""))
        for hit in rag_hits:
            if hit.get("open") == "first":
                lines.append(f"- `{hit['path']}:{hit['start']}-{hit['end']}` {hit['symbol']}")
    lines.extend(("", "## Context rule", ""))
    lines.append(
        "Open on-demand files only when a finding requires them; "
        "never preload directories."
    )
    markdown_path = write_markdown(project, "context", "latest.md", "\n".join(lines))
    return payload, json_path, markdown_path
