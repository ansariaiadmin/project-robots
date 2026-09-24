#!/usr/bin/env python3
"""Route changes to the smallest safe check set and record bound evidence."""

from __future__ import annotations

import datetime as dt
import shlex
import time
from pathlib import Path

from .common import (
    RobotError,
    auto_checks,
    changed_files,
    load_config,
    match_any,
    run,
    source_state,
    tracked_files,
    write_json,
)
from .docs_robot import inspect as inspect_docs
from .hygiene_robot import inspect as inspect_hygiene

CODE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".go", ".h", ".hpp", ".java", ".js", ".jsx",
    ".mjs", ".py", ".rs", ".ts", ".tsx",
}
UI_PATTERNS = (
    "src/pages/**", "src/components/**", "src/ui/**", "src/styles/**",
    "app/**", "pages/**", "components/**", "styles/**", "*.css",
)
RELEASE_PATTERNS = (
    "Dockerfile", "docker/**", ".github/**", ".gitlab-ci.yml",
    "scripts/release/**", "scripts/deploy/**", "scripts/package*",
    "public/sw.*", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
)


def _configured_route_checks(paths: list[str], config: dict, available: dict) -> list[str]:
    if not paths:
        return []
    selected = []
    for route in config.get("routes", []):
        if not isinstance(route, dict):
            continue
        patterns = [str(item) for item in route.get("patterns", [])]
        if paths and not any(match_any(path, patterns) for path in paths):
            continue
        selected.extend(
            str(name) for name in route.get("checks", [])
            if str(name) in available
        )
    return list(dict.fromkeys(selected))


def _first_available(available: dict, names: tuple[str, ...]) -> str | None:
    return next((name for name in names if name in available), None)


def build_plan(
    project: Path,
    *,
    full: bool = False,
    browser: bool = False,
) -> dict:
    config, config_source = load_config(project)
    available = auto_checks(project, config)
    changes = changed_files(project, config)
    paths = [item["path"] for item in changes]
    selected = _configured_route_checks(paths, config, available)
    if "diff" in available:
        selected.insert(0, "diff")

    if full:
        preferred_groups = (
            ("test:docs",),
            ("lint",),
            ("typecheck",),
            ("test:core", "test", "test:unit"),
            ("build:offline", "build"),
            ("test:release",),
            ("test:layout",),
        )
        for group in preferred_groups:
            found = _first_available(available, group)
            if found:
                selected.append(found)
        if browser and "test:browser" in available:
            selected.append("test:browser")
        for name in available:
            if name.startswith(("cargo-", "go-")):
                selected.append(name)
    elif paths:
        docs_only = all(path.endswith(".md") or path.startswith("docs/") for path in paths)
        code_changed = any(Path(path).suffix.lower() in CODE_SUFFIXES for path in paths)
        ui_changed = any(match_any(path, UI_PATTERNS) for path in paths)
        release_changed = any(match_any(path, RELEASE_PATTERNS) for path in paths)
        manifest_changed = any(
            Path(path).name in {
                "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
                "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
            }
            for path in paths
        )
        if docs_only and "test:docs" in available:
            selected.append("test:docs")
        if code_changed or manifest_changed:
            for group in (("lint",), ("typecheck",), ("test:core", "test", "test:unit")):
                found = _first_available(available, group)
                if found:
                    selected.append(found)
        if ui_changed and "test:layout" in available:
            selected.append("test:layout")
        if browser and ui_changed and "test:browser" in available:
            selected.append("test:browser")
        if release_changed or manifest_changed:
            for group in (("build:offline", "build"), ("test:release",)):
                found = _first_available(available, group)
                if found:
                    selected.append(found)
    selected = list(dict.fromkeys(name for name in selected if name in available))

    python_paths = [
        path for path in paths
        if path.endswith(".py") and (project / path).is_file()
    ]
    if full and not python_paths:
        python_paths = [
            path.relative_to(project).as_posix()
            for path in tracked_files(project, config)
            if path.suffix.lower() == ".py"
        ][:200]
    commands = [
        {"name": name, "argv": available[name]}
        for name in selected
    ]
    if python_paths:
        commands.append({
            "name": "python-syntax",
            "argv": [
                "python3",
                "-c",
                (
                    "import pathlib,sys;"
                    "[compile(pathlib.Path(p).read_text(encoding='utf-8'),p,'exec') "
                    "for p in sys.argv[1:]]"
                ),
                *python_paths[:200],
            ],
        })
    return {
        "project": str(project),
        "configSource": config_source,
        "full": full,
        "includeBrowser": browser,
        "changed": changes,
        "availableChecks": available,
        "commands": commands,
    }


def _command_result(project: Path, name: str, argv: list[str], config: dict) -> dict:
    started = time.monotonic()
    timeout = int(config["limits"]["commandTimeoutSeconds"])
    tail_lines = int(config["limits"]["outputTailLines"])
    try:
        completed = run(argv, cwd=project, timeout=timeout)
        output = completed.stdout.splitlines()
        return {
            "name": name,
            "argv": argv,
            "passed": completed.returncode == 0,
            "returnCode": completed.returncode,
            "durationSeconds": round(time.monotonic() - started, 3),
            "outputTail": output[-tail_lines:],
        }
    except RobotError as error:
        return {
            "name": name,
            "argv": argv,
            "passed": False,
            "returnCode": None,
            "durationSeconds": round(time.monotonic() - started, 3),
            "outputTail": [str(error)],
        }


def execute(project: Path, plan: dict) -> tuple[dict, Path]:
    config, _source = load_config(project)
    before = source_state(project, config)
    docs, _docs_path = inspect_docs(project)
    hygiene, _hygiene_path = inspect_hygiene(project)
    results = [
        {
            "name": "docs-robot",
            "argv": [],
            "passed": docs["ok"],
            "returnCode": 0 if docs["ok"] else 1,
            "durationSeconds": 0,
            "outputTail": [
                f"errors={docs['summary']['errors']} warnings={docs['summary']['warnings']}"
            ],
        },
        {
            "name": "hygiene-robot",
            "argv": [],
            "passed": hygiene["ok"],
            "returnCode": 0 if hygiene["ok"] else 1,
            "durationSeconds": 0,
            "outputTail": [
                f"errors={hygiene['summary']['errors']} warnings={hygiene['summary']['warnings']}"
            ],
        },
    ]
    results.extend(
        _command_result(project, row["name"], row["argv"], config)
        for row in plan["commands"]
    )
    after = source_state(project, config)
    stable = before == after
    payload = {
        **plan,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceState": after,
        "stableSourceState": stable,
        "passed": stable and all(result["passed"] for result in results),
        "results": results,
    }
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output = write_json(project, "checks", f"check-{stamp}.json", payload)
    write_json(project, "checks", "latest.json", payload)
    return payload, output


def compact_plan(plan: dict) -> dict:
    return {
        "project": plan["project"],
        "changedFiles": len(plan["changed"]),
        "full": plan["full"],
        "browser": plan["includeBrowser"],
        "commands": [
            {"name": item["name"], "command": shlex.join(item["argv"])}
            for item in plan["commands"]
        ],
    }
