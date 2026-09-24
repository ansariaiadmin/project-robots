#!/usr/bin/env python3
"""Shared primitives for generic project robots."""

from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = TOOL_ROOT / ".cache"
PROFILE_ROOT = TOOL_ROOT / "profiles"
DEFAULT_IGNORES = (
    ".git/**",
    "**/.git/**",
    ".hg/**",
    "**/.hg/**",
    ".svn/**",
    "**/.svn/**",
    "node_modules/**",
    "**/node_modules/**",
    ".venv/**",
    "**/.venv/**",
    "venv/**",
    "**/venv/**",
    "__pycache__/**",
    "**/__pycache__/**",
    ".pytest_cache/**",
    "**/.pytest_cache/**",
    ".mypy_cache/**",
    "**/.mypy_cache/**",
    ".ruff_cache/**",
    "**/.ruff_cache/**",
    ".next/**",
    "**/.next/**",
    ".nuxt/**",
    "**/.nuxt/**",
    "coverage/**",
    "**/coverage/**",
    "dist/**",
    "**/dist/**",
    "build/**",
    "**/build/**",
    "target/**",
    "**/target/**",
    ".tmp/**",
    "**/.tmp/**",
    ".cache/**",
    "**/.cache/**",
    "tmp/**",
    "**/tmp/**",
)
TEXT_SUFFIXES = {
    ".c", ".cc", ".cpp", ".css", ".go", ".h", ".hpp", ".html", ".java",
    ".js", ".json", ".jsx", ".md", ".mjs", ".py", ".rs", ".sh", ".sql",
    ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
MANIFESTS = {
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "dotnet": ("*.sln", "*.csproj"),
}
DEFAULT_CONFIG = {
    "version": 1,
    "ignore": list(DEFAULT_IGNORES),
    "readFirst": [
        "AGENTS.md",
        "README.md",
        "docs/MASTER.md",
        "docs/README.md",
        "CONTRIBUTING.md",
    ],
    "invariants": [],
    "routes": [],
    "checks": {},
    "limits": {
        "maxFileBytes": 2_000_000,
        "maxFindings": 40,
        "contextTokenBudget": 4000,
        "commandTimeoutSeconds": 900,
        "outputTailLines": 30,
    },
}


class RobotError(RuntimeError):
    """Expected user-facing robot failure."""


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_project(raw: str | Path) -> Path:
    project = Path(raw).expanduser().resolve()
    if not project.is_dir():
        raise RobotError(f"Project directory does not exist: {project}")
    return project


def slug(project: Path) -> str:
    safe_name = "".join(
        char if char.isalnum() or char in "-_" else "-"
        for char in project.name.lower()
    ).strip("-") or "project"
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:10]
    return f"{safe_name}-{digest}"


def cache_dir(project: Path, section: str | None = None) -> Path:
    root = CACHE_ROOT / slug(project)
    path = root / section if section else root
    path.mkdir(parents=True, exist_ok=True)
    return path


def deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def profile_path(project: Path) -> Path:
    return PROFILE_ROOT / f"{slug(project)}.json"


def load_config(project: Path) -> tuple[dict, str]:
    config = dict(DEFAULT_CONFIG)
    candidates = (
        project / ".project-robots.json",
        profile_path(project),
    )
    source = "auto"
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RobotError(f"Invalid robot config {candidate}: {error}") from error
        if not isinstance(payload, dict):
            raise RobotError(f"Robot config must contain a JSON object: {candidate}")
        config = deep_merge(config, payload)
        source = str(candidate)
        break
    config["ignore"] = list(dict.fromkeys((*DEFAULT_IGNORES, *config.get("ignore", []))))
    return config, source


def is_ignored(relative_path: str, patterns: Iterable[str]) -> bool:
    normalized = relative_path.replace(os.sep, "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    return any(
        fnmatch.fnmatch(normalized, pattern)
        or fnmatch.fnmatch(f"{normalized}/", pattern)
        for pattern in patterns
    )


def command_exists(command: str) -> bool:
    return shutil.which(command, path=effective_env()["PATH"]) is not None


def effective_env() -> dict[str, str]:
    env = dict(os.environ)
    paths = [item for item in env.get("PATH", "").split(os.pathsep) if item]
    optional = (Path("/snap/bin"), Path("/usr/local/bin"))
    for candidate in optional:
        if candidate.is_dir() and str(candidate) not in paths:
            paths.append(str(candidate))
    home = Path.home()
    discovered = []
    fnm_root = home / ".local" / "share" / "fnm" / "node-versions"
    if fnm_root.is_dir():
        discovered.extend(
            path / "installation" / "bin"
            for path in fnm_root.iterdir()
            if (path / "installation" / "bin" / "node").is_file()
        )
    nvm_root = home / ".nvm" / "versions" / "node"
    if nvm_root.is_dir():
        discovered.extend(
            path / "bin"
            for path in nvm_root.iterdir()
            if (path / "bin" / "node").is_file()
        )
    for candidate in sorted(discovered, reverse=True):
        if str(candidate) not in paths:
            paths.insert(0, str(candidate))
    env["PATH"] = os.pathsep.join(paths)
    return env


def run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 60,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=effective_env(),
        )
    except FileNotFoundError as error:
        raise RobotError(f"Command not found: {argv[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RobotError(f"Command timed out after {timeout}s: {shlex.join(argv)}") from error
    if check and completed.returncode != 0:
        raise RobotError(completed.stdout.strip() or f"Command failed: {shlex.join(argv)}")
    return completed


def git_root(project: Path) -> Path | None:
    if not command_exists("git"):
        return None
    completed = run(["git", "rev-parse", "--show-toplevel"], cwd=project)
    if completed.returncode != 0:
        return None
    root = Path(completed.stdout.strip()).resolve()
    return root if root.is_dir() else None


def git_pathspec(project: Path, root: Path) -> str:
    relative = project.relative_to(root).as_posix()
    return "." if relative == "." else relative


def git_output(project: Path, *args: str, binary: bool = False):
    root = git_root(project)
    if root is None:
        raise RobotError("Project is not inside a Git repository.")
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    if completed.returncode != 0:
        error = completed.stderr if not binary else completed.stderr.decode("utf-8", "replace")
        raise RobotError(error.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def _in_scope(project: Path, candidate: Path) -> bool:
    """True when a path resolves inside the project root (no symlink escape)."""
    try:
        candidate.resolve().relative_to(project.resolve())
        return True
    except (ValueError, OSError):
        return False


def tracked_files(project: Path, config: dict) -> list[Path]:
    root = git_root(project)
    if root is not None:
        pathspec = git_pathspec(project, root)
        raw = git_output(
            project,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            pathspec,
            binary=True,
        )
        files = []
        for item in raw.split(b"\0"):
            if not item:
                continue
            candidate = root / item.decode("utf-8", "surrogateescape")
            if candidate.is_file() and _in_scope(project, candidate):
                relative = candidate.relative_to(project).as_posix()
                if not is_ignored(relative, config["ignore"]):
                    files.append(candidate)
        return sorted(files)

    files = []
    for root, directories, names in os.walk(project, followlinks=False):
        root_path = Path(root)
        kept_directories = []
        for name in directories:
            candidate = root_path / name
            relative = candidate.relative_to(project).as_posix()
            if not is_ignored(f"{relative}/placeholder", config["ignore"]):
                kept_directories.append(name)
        directories[:] = kept_directories
        for name in names:
            candidate = root_path / name
            relative = candidate.relative_to(project).as_posix()
            if not is_ignored(relative, config["ignore"]) and _in_scope(project, candidate):
                files.append(candidate)
    return sorted(files)


def changed_files(project: Path, config: dict) -> list[dict[str, str]]:
    root = git_root(project)
    if root is None:
        return []
    pathspec = git_pathspec(project, root)
    output = git_output(
        project,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        pathspec,
    )
    changes = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:].strip().strip('"')
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        absolute = (root / raw_path).resolve()
        try:
            relative = absolute.relative_to(project).as_posix()
        except ValueError:
            continue
        if not is_ignored(relative, config["ignore"]):
            changes.append({"status": line[:2].strip() or "M", "path": relative})
    return changes


def source_state(project: Path, config: dict) -> dict[str, object]:
    root = git_root(project)
    digest = hashlib.sha256()
    state_config = {**config, "ignore": list(DEFAULT_IGNORES)}
    if root is not None:
        pathspec = git_pathspec(project, root)
        commit = git_output(project, "rev-parse", "HEAD").strip()
        changes = changed_files(project, state_config)
        for change in sorted(changes, key=lambda item: (item["path"], item["status"])):
            raw_path = change["path"].encode("utf-8")
            digest.update(change["status"].encode("utf-8"))
            digest.update(b"\0")
            digest.update(raw_path)
            digest.update(b"\0")
            candidate = project / change["path"]
            digest.update(candidate.read_bytes() if candidate.is_file() else b"<missing>")
            digest.update(b"\0")
        digest.update(
            git_output(
                project,
                "diff",
                "--cached",
                "--binary",
                "--",
                pathspec,
                binary=True,
            )
        )
        return {
            "kind": "git",
            "commit": commit,
            "worktreeDigest": digest.hexdigest(),
        }

    for candidate in tracked_files(project, state_config):
        relative = candidate.relative_to(project).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    return {"kind": "filesystem", "contentDigest": digest.hexdigest()}


def detect_kinds(project: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for kind, patterns in MANIFESTS.items():
        matches = []
        for pattern in patterns:
            matches.extend(
                path.relative_to(project).as_posix()
                for path in project.glob(pattern)
                if path.is_file()
            )
        if matches:
            found[kind] = sorted(set(matches))
    return found


def package_scripts(project: Path) -> dict[str, str]:
    manifest = project / "package.json"
    if not manifest.is_file():
        return {}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = payload.get("scripts", {})
    return {
        str(name): str(command)
        for name, command in scripts.items()
        if isinstance(name, str) and isinstance(command, str)
    }


def auto_checks(project: Path, config: dict) -> dict[str, list[str]]:
    configured = {
        str(name): [str(part) for part in argv]
        for name, argv in config.get("checks", {}).items()
        if isinstance(argv, list) and argv
    }
    if configured:
        return configured

    checks: dict[str, list[str]] = {}
    if git_root(project) is not None:
        checks["diff"] = ["git", "diff", "--check", "--", "."]
    scripts = package_scripts(project)
    preferred = (
        "test:docs",
        "lint",
        "typecheck",
        "check",
        "test:core",
        "test",
        "test:unit",
        "build",
        "build:offline",
        "test:release",
        "test:layout",
        "test:browser",
    )
    for name in preferred:
        if name in scripts:
            checks[name] = ["npm", "run", name]

    kinds = detect_kinds(project)
    if "rust" in kinds and command_exists("cargo"):
        checks.setdefault("cargo-check", ["cargo", "check"])
        checks.setdefault("cargo-test", ["cargo", "test"])
    if "go" in kinds and command_exists("go"):
        checks.setdefault("go-test", ["go", "test", "./..."])
    return checks


def match_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def comment_marker(line: str, suffix: str) -> str | None:
    upper_suffix = suffix.lower()
    if upper_suffix in {".json", ".webmanifest"}:
        return None
    comment = line
    if upper_suffix == ".py":
        if "#" not in line:
            return None
        comment = line.split("#", 1)[1]
    elif upper_suffix in {".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rs"}:
        stripped = line.lstrip()
        if "//" in line:
            comment = line.split("//", 1)[1]
        elif stripped.startswith(("/*", "*")):
            comment = stripped
        else:
            return None
    elif upper_suffix in {".css", ".scss", ".less"}:
        stripped = line.lstrip()
        if not stripped.startswith(("/*", "*")):
            return None
        comment = stripped
    for marker in ("TODO", "FIXME", "WIP", "XXX"):
        if marker in comment.upper():
            return marker
    return None


def read_text(path: Path, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def write_json(project: Path, section: str, name: str, payload: dict) -> Path:
    destination = cache_dir(project, section) / name
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def write_markdown(project: Path, section: str, name: str, text: str) -> Path:
    destination = cache_dir(project, section) / name
    destination.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
    return destination


def compact_path(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def summarize_result(payload: dict, output: Path) -> dict:
    return {
        "ok": payload.get("ok", True),
        "summary": payload.get("summary", {}),
        "output": str(output),
    }
