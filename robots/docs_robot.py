#!/usr/bin/env python3
"""Validate documentation shape and local links without changing files."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from .common import load_config, read_text, tracked_files, write_json

LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    elif ' "' in value:
        value = value.split(' "', 1)[0]
    elif " '" in value:
        value = value.split(" '", 1)[0]
    return unquote(value.split("#", 1)[0].split("?", 1)[0].strip())


def inspect(project: Path) -> tuple[dict, Path]:
    config, config_source = load_config(project)
    max_bytes = int(config["limits"]["maxFileBytes"])
    limit = int(config["limits"]["maxFindings"])
    docs = [path for path in tracked_files(project, config) if path.suffix.lower() == ".md"]
    broken_links = []
    duplicate_headings = []
    oversized = []
    hashes: dict[str, list[str]] = defaultdict(list)

    for path in docs:
        relative = path.relative_to(project).as_posix()
        size = path.stat().st_size
        if size > max_bytes:
            oversized.append({"path": relative, "bytes": size})
            continue
        text = read_text(path, max_bytes)
        if text is None:
            continue
        hashes[hashlib.sha256(text.encode("utf-8")).hexdigest()].append(relative)
        seen_headings: set[tuple[int, str]] = set()
        for level, title in HEADING_PATTERN.findall(text):
            normalized = re.sub(r"\s+", " ", title.strip().lower())
            key = (len(level), normalized)
            if key in seen_headings:
                duplicate_headings.append(
                    {
                        "path": relative,
                        "level": len(level),
                        "heading": title.strip(),
                    }
                )
            seen_headings.add(key)

        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_PATTERN.finditer(line):
                raw_target = match.group(1)
                target = _target(raw_target)
                if not target or target.startswith(("/", "http://", "https://", "mailto:", "data:")):
                    continue
                candidate = (path.parent / target).resolve()
                try:
                    candidate.relative_to(project)
                except ValueError:
                    broken_links.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "target": target,
                            "reason": "escapes project",
                        }
                    )
                    continue
                if not candidate.exists():
                    broken_links.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "target": target,
                            "reason": "missing",
                        }
                    )
                if len(broken_links) >= limit:
                    break

    duplicate_documents = [paths for paths in hashes.values() if len(paths) > 1]
    required = [str(item) for item in config.get("requiredDocs", [])]
    missing_required = [path for path in required if not (project / path).is_file()]
    errors = len(broken_links) + len(missing_required)
    warnings = len(duplicate_headings) + len(duplicate_documents) + len(oversized)
    payload = {
        "ok": errors == 0,
        "project": str(project),
        "configSource": config_source,
        "summary": {
            "documents": len(docs),
            "errors": errors,
            "warnings": warnings,
        },
        "missingRequired": missing_required,
        "brokenLinks": broken_links[:limit],
        "duplicateHeadings": duplicate_headings[:limit],
        "duplicateDocuments": duplicate_documents[:limit],
        "oversizedDocuments": oversized[:limit],
    }
    output = write_json(project, "docs", "latest.json", payload)
    return payload, output
