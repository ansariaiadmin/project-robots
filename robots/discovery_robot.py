#!/usr/bin/env python3
"""Discover project shape without loading source content into context."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .common import (
    TEXT_SUFFIXES,
    compact_path,
    detect_kinds,
    git_root,
    load_config,
    package_scripts,
    source_state,
    tracked_files,
    write_json,
)


def inspect(project: Path) -> tuple[dict, Path]:
    config, config_source = load_config(project)
    files = tracked_files(project, config)
    suffixes = Counter(path.suffix.lower() or "<none>" for path in files)
    largest = sorted(files, key=lambda path: path.stat().st_size, reverse=True)[:10]
    payload = {
        "ok": True,
        "project": str(project),
        "gitRoot": str(git_root(project)) if git_root(project) else None,
        "configSource": config_source,
        "sourceState": source_state(project, config),
        "kinds": detect_kinds(project),
        "packageScripts": sorted(package_scripts(project)),
        "summary": {
            "trackedFiles": len(files),
            "textLikeFiles": sum(path.suffix.lower() in TEXT_SUFFIXES for path in files),
            "projectKinds": len(detect_kinds(project)),
        },
        "extensions": dict(suffixes.most_common(20)),
        "largestFiles": [
            {
                "path": compact_path(path, project),
                "bytes": path.stat().st_size,
            }
            for path in largest
        ],
    }
    output = write_json(project, "discover", "latest.json", payload)
    return payload, output
