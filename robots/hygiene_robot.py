#!/usr/bin/env python3
"""Find high-signal repository hygiene risks without exposing file contents."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from .common import (
    TEXT_SUFFIXES,
    comment_marker,
    load_config,
    read_text,
    tracked_files,
    write_json,
)

CONFLICT = re.compile(r"^(<<<<<<<|=======|>>>>>>>)(?:\s|$)")
SUSPICIOUS_NAMES = re.compile(
    r"(^|/)(\.env($|\.)|id_rsa$|.*\.(pem|key|p12|pfx)$|credentials?\.json$)",
    re.IGNORECASE,
)
GENERATED_PARTS = {
    "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "target", ".next", "coverage",
}


def inspect(project: Path) -> tuple[dict, Path]:
    config, config_source = load_config(project)
    limits = config["limits"]
    max_bytes = int(limits["maxFileBytes"])
    limit = int(limits["maxFindings"])
    files = tracked_files(project, config)
    conflicts = []
    todos = []
    large_files = []
    suspicious_files = []
    generated_files = []
    hashes: dict[tuple[int, str], list[str]] = defaultdict(list)

    for path in files:
        relative = path.relative_to(project).as_posix()
        size = path.stat().st_size
        if size > max_bytes:
            large_files.append({"path": relative, "bytes": size})
        if SUSPICIOUS_NAMES.search(relative) and not relative.endswith((".example", ".sample")):
            suspicious_files.append(relative)
        if GENERATED_PARTS.intersection(path.relative_to(project).parts):
            generated_files.append(relative)
        if 1024 <= size <= max_bytes:
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes[(size, digest)].append(relative)
            except OSError:
                pass
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path, max_bytes)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if CONFLICT.search(line):
                conflicts.append({"path": relative, "line": line_number})
            marker = comment_marker(line, path.suffix)
            if marker:
                todos.append({
                    "path": relative,
                    "line": line_number,
                    "marker": marker,
                })
            if len(conflicts) + len(todos) >= limit:
                break

    duplicate_files = [
        paths for paths in hashes.values() if len(paths) > 1
    ]
    errors = len(conflicts) + len(suspicious_files)
    warnings = len(large_files) + len(generated_files) + len(duplicate_files)
    payload = {
        "ok": errors == 0,
        "project": str(project),
        "configSource": config_source,
        "summary": {
            "trackedFiles": len(files),
            "errors": errors,
            "warnings": warnings,
            "todoMarkers": len(todos),
        },
        "mergeConflicts": conflicts[:limit],
        "suspiciousTrackedFiles": suspicious_files[:limit],
        "largeFiles": large_files[:limit],
        "trackedGeneratedFiles": generated_files[:limit],
        "exactDuplicates": duplicate_files[:limit],
        "todoMarkers": todos[:limit],
    }
    output = write_json(project, "hygiene", "latest.json", payload)
    return payload, output
