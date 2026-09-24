"""Guard — write policy, risk gates, diff previews, central-state helpers."""

from __future__ import annotations

import contextlib
import difflib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

#: Risk above this hard-denies every write regardless of threshold config.
RISK_HARD_DENY = 0.5

#: Target subdirectories known to be robot-generated (safe to migrate).
_KNOWN_TARGET_SUBDIRS = ("evidence", "adrs", "learning", "autonomous")


@dataclass(slots=True)
class WritePolicy:
    """Evaluated permission for one execution batch."""

    decision: str = "deny"  # "allow" | "dry-run" | "deny"
    allowlist: set[str] = field(default_factory=set)
    dry_run: bool = True
    risk: float = 1.0
    threshold: float = 0.3
    reasons: list[str] = field(default_factory=list)


def central_state_dir(project: Path, section: str) -> Path:
    """Central per-project state dir (never inside the target repo)."""
    from robots.common import cache_dir

    return cache_dir(project, section)


def normalize_rel(project: Path, raw: str) -> str | None:
    """Normalize a candidate path; None when it escapes the project."""
    try:
        absolute = (project / raw).resolve()
        return absolute.relative_to(project.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def is_in_scope(project: Path, candidate: Path | str) -> bool:
    """True when a filesystem path resolves inside the project root.

    Blocks symlink escapes and neighbor-directory traversal: every inspected,
    indexed, or executed path must pass this gate.
    """
    try:
        Path(candidate).resolve().relative_to(project.resolve())
        return True
    except (ValueError, OSError):
        return False


def sanitize_changes(changes: object, project: Path) -> list[dict]:
    """Normalize an LLM-produced changes list to in-scope file-change dicts.

    Drops strings, non-dicts, and entries without an in-scope file/path so
    downstream robots never crash on model output shape drift.
    """
    clean: list[dict] = []
    if not isinstance(changes, list):
        return clean
    for change in changes:
        if not isinstance(change, dict):
            continue
        rel = str(change.get("file", change.get("path", ""))).strip()
        if not rel:
            continue
        normalized = normalize_rel(project, rel)
        if normalized is None:
            continue
        entry = dict(change)
        entry["file"] = normalized
        entry["path"] = normalized
        clean.append(entry)
    return clean


def build_allowlist(
    project: Path,
    candidate_paths: list[str] | None = None,
    extra_paths: list[str] | None = None,
) -> set[str]:
    """Explicit file allowlist: existing in-project files only, no globs."""
    allowlist: set[str] = set()
    for raw in (*(candidate_paths or []), *(extra_paths or [])):
        rel = normalize_rel(project, str(raw))
        if rel is None:
            continue
        if "*" in rel or "?" in rel or "[" in rel:
            continue
        if (project / rel).is_file():
            allowlist.add(rel)
    return allowlist


def evaluate_write_policy(
    *,
    risk_overall: float,
    risk_threshold: float = 0.3,
    candidate_paths: list[str] | None = None,
    rag_paths: list[str] | None = None,
    project: Path | None = None,
    config: dict | None = None,
    dry_run_requested: bool = False,
) -> WritePolicy:
    """Decide allow / dry-run / deny for a batch of writes.

    - risk > RISK_HARD_DENY -> deny (unconditional).
    - risk > threshold      -> dry-run preview only.
    - else                  -> allow (still allowlisted; dry_run flag honored).
    Never raises.
    """
    try:
        risk = float(risk_overall)
    except (TypeError, ValueError):
        risk = 1.0
    try:
        threshold = float(risk_threshold)
    except (TypeError, ValueError):
        threshold = 0.3
    reasons: list[str] = []
    allowlist: set[str] = set()
    if project is not None:
        allowlist = build_allowlist(project, candidate_paths, rag_paths)
    if risk > RISK_HARD_DENY:
        reasons.append(f"risk {risk:.2f} exceeds hard-deny {RISK_HARD_DENY:.2f}")
        return WritePolicy(
            decision="deny",
            allowlist=allowlist,
            dry_run=True,
            risk=risk,
            threshold=threshold,
            reasons=reasons,
        )
    forced_dry = bool(dry_run_requested)
    if config is not None:
        auto = config.get("autonomous", {})
        if isinstance(auto, dict) and auto.get("dry_run") is True:
            forced_dry = True
    if risk > threshold:
        reasons.append(f"risk {risk:.2f} exceeds threshold {threshold:.2f}: preview only")
        return WritePolicy(
            decision="dry-run",
            allowlist=allowlist,
            dry_run=True,
            risk=risk,
            threshold=threshold,
            reasons=reasons,
        )
    reasons.append(f"risk {risk:.2f} within threshold {threshold:.2f}")
    if forced_dry:
        reasons.append("dry-run requested by operator config")
    return WritePolicy(
        decision="allow" if not forced_dry else "dry-run",
        allowlist=allowlist,
        dry_run=forced_dry,
        risk=risk,
        threshold=threshold,
        reasons=reasons,
    )


def is_path_allowed(project: Path, rel: str, policy: WritePolicy) -> tuple[bool, str]:
    """Check one relative path against the project boundary + allowlist."""
    normalized = normalize_rel(project, rel)
    if normalized is None:
        return False, "path escapes project boundary"
    if normalized != rel:
        return False, "path not in canonical form"
    if normalized not in policy.allowlist:
        return False, "path not allowlisted for this task"
    return True, ""


def preview_unified_diff(old_text: str, new_text: str, rel: str) -> str:
    """Diff preview without touching the filesystem."""
    lines = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        lineterm="",
    )
    return "\n".join(list(lines)[:200])


def guarded_write_text(
    project: Path,
    rel: str,
    new_text: str,
    policy: WritePolicy,
) -> dict:
    """Allowlisted write with dry-run support. Returns a result dict, never raises."""
    try:
        allowed, reason = is_path_allowed(project, rel, policy)
        if policy.decision == "deny":
            denied = "; ".join([*policy.reasons, "denied"])
            return {"written": False, "preview": "", "reason": denied}
        if not allowed:
            return {"written": False, "preview": "", "reason": reason}
        old_text = (project / rel).read_text(encoding="utf-8")
        preview = preview_unified_diff(old_text, new_text, rel)
        if policy.decision == "dry-run" or policy.dry_run:
            return {"written": False, "preview": preview, "reason": "dry-run preview"}
        (project / rel).write_text(new_text, encoding="utf-8")
        return {"written": True, "preview": preview, "reason": "applied"}
    except (OSError, UnicodeError) as error:
        return {"written": False, "preview": "", "reason": f"write failed: {error}"}


def cleanup_stray_target_state(project: Path) -> dict:
    """Migrate known robot-generated files out of <project>/.project-robots/.

    Moves evidence/adrs/learning/autonomous payloads to the central cache and
    removes the stray directory when empty. Unknown files are left untouched.
    Never raises.
    """
    report: dict = {"moved": [], "left": [], "removed": False}
    try:
        stray = project / ".project-robots"
        if not stray.is_dir():
            return report
        for sub in _KNOWN_TARGET_SUBDIRS:
            source = stray / sub
            if not source.is_dir():
                continue
            dest = central_state_dir(project, sub)
            for item in sorted(source.iterdir()):
                try:
                    target = dest / item.name
                    if target.exists():
                        report["left"].append(f"{sub}/{item.name}")
                        continue
                    shutil.move(str(item), str(target))
                    report["moved"].append(f"{sub}/{item.name}")
                except (OSError, shutil.Error):
                    report["left"].append(f"{sub}/{item.name}")
            with contextlib.suppress(OSError):
                source.rmdir()
        leftovers = [p for p in stray.rglob("*") if p.is_file()]
        if not leftovers:
            for child in sorted(stray.iterdir()):
                if child.is_dir():
                    with contextlib.suppress(OSError):
                        child.rmdir()
                else:
                    report["left"].append(child.name)
        try:
            stray.rmdir()
            report["removed"] = True
        except OSError:
            report["removed"] = False
        return report
    except (OSError, ValueError) as error:
        report["left"].append(f"cleanup failed: {error}")
        return report
