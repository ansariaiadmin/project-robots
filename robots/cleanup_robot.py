#!/usr/bin/env python3
"""Create a non-destructive cleanup plan for generated project data."""

from __future__ import annotations

import os
from pathlib import Path

from .common import load_config, write_json

CANDIDATE_NAMES = {
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
    ".ruff_cache": "Ruff cache",
    ".cache": "tool cache",
    "coverage": "coverage output",
    "dist": "generated distribution",
    "build": "generated build",
    "target": "Rust build output",
    ".next": "Next.js build output",
    ".nuxt": "Nuxt build output",
    ".tmp": "project temporary output",
    "node_modules": "installed dependencies reproducible from a lockfile",
}


def _size(path: Path) -> tuple[int, int]:
    total = 0
    files = 0
    try:
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                files += 1
                total += child.stat().st_size
    except OSError:
        return total, files
    return total, files


def inspect(project: Path) -> tuple[dict, Path]:
    config, config_source = load_config(project)
    candidates = []
    visited: set[Path] = set()
    for root, directories, _files in os.walk(project):
        root_path = Path(root)
        if root_path.name == ".git":
            directories[:] = []
            continue
        for name in list(directories):
            path = root_path / name
            if path.is_symlink():
                directories.remove(name)
                continue
            if name == ".git":
                directories.remove(name)
                continue
            if name not in CANDIDATE_NAMES:
                continue
            directories.remove(name)
            if any(parent in visited for parent in path.parents):
                continue
            visited.add(path)
            size, files = _size(path)
            candidates.append({
                "path": path.relative_to(project).as_posix(),
                "bytes": size,
                "files": files,
                "reason": CANDIDATE_NAMES[name],
                "action": "review-before-removal",
            })
    candidates.sort(key=lambda item: item["bytes"], reverse=True)
    payload = {
        "ok": True,
        "project": str(project),
        "configSource": config_source,
        "summary": {
            "candidates": len(candidates),
            "potentialBytes": sum(item["bytes"] for item in candidates),
            "deleted": 0,
        },
        "candidates": candidates[: int(config["limits"]["maxFindings"])],
        "note": "Plan only. This robot never deletes files.",
    }
    output = write_json(project, "cleanup", "latest.json", payload)
    return payload, output
