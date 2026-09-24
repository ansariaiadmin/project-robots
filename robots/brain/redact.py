"""Redact — secret path detection and value redaction (stdlib only)."""

from __future__ import annotations

import fnmatch
import hashlib
import re

#: Basename/path patterns never indexed or auto-read (secrets, keys, env).
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "id_ed25519*",
    "*credentials*.json",
    "*secret*",
    "secrets.*",
    "*.p12",
    "*.pfx",
    ".aws/credentials",
    "*/.aws/credentials",
)

_SENSITIVE_NAME = re.compile(r"(?i)(api[_-]?key|secret|token|passwd|password|private[_-]?key)")

_ENV_ASSIGN = re.compile(r"(?m)^(\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*)(.+?)(\s*)$")

_PEM_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----")

_TOKEN_RES = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[bpas]-[A-Za-z0-9-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


def is_secret_path(rel: str) -> bool:
    """True when a project-relative path looks like secrets/keys/env."""
    normalized = (rel or "").replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    if parts[0] in (".env",) or normalized == ".env":
        return True
    for pattern in SECRET_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(parts[-1], pattern):
            return True
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def _redact_env_assignments(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match) -> str:
        nonlocal count
        name = match.group(0).split("=", 1)[0]
        if _SENSITIVE_NAME.search(name):
            count += 1
            return f"{match.group(1)}[REDACTED]{match.group(3)}"
        return match.group(0)

    return _ENV_ASSIGN.sub(replace, text), count


def redact_text(text: str) -> tuple[str, int]:
    """Redact secret values in text. Returns (redacted_text, redactions)."""
    if not text:
        return text, 0
    total = 0
    redacted, pem_count = _PEM_BLOCK.subn("-----BEGIN REDACTED PRIVATE KEY-----", text)
    total += pem_count
    redacted, env_count = _redact_env_assignments(redacted)
    total += env_count

    def generic_replace(match: re.Match) -> str:
        nonlocal total
        total += 1
        return "[REDACTED]"

    for pattern in _TOKEN_RES:
        redacted = pattern.sub(generic_replace, redacted)
    # Generic key=value with sensitive names (non-env files, JSON-ish, YAML-ish).
    keyed = re.compile(
        r'(?i)(["\']?(?:api[_-]?key|secret|token|password|private[_-]?key)["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)'
    )

    def keyed_replace(match: re.Match) -> str:
        nonlocal total
        total += 1
        return f"{match.group(1)}[REDACTED]"

    redacted = keyed.sub(keyed_replace, redacted)
    return redacted, total


def secret_marker(rel: str) -> str:
    """Stable opaque marker for a skipped secret path (no path disclosure).

    Reports counts plus markers in metadata instead of exact secret paths,
    so prompt traces and diagnostic summaries never leak secret locations.
    """
    digest = hashlib.sha256((rel or "").encode("utf-8")).hexdigest()[:8]
    return f"<redacted-secret:{digest}>"
