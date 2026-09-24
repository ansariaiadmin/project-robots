#!/usr/bin/env python3
"""One low-noise CLI for reusable project robots."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from robots.autonomous.robot import AutonomousMainRobot
from robots.checks_robot import build_plan, compact_plan, execute
from robots.cleanup_robot import inspect as inspect_cleanup
from robots.common import (
    RobotError,
    auto_checks,
    detect_kinds,
    load_config,
    profile_path,
    resolve_project,
)
from robots.context_robot import build as build_context
from robots.discovery_robot import inspect as inspect_discovery
from robots.docs_robot import inspect as inspect_docs
from robots.evidence_robot import inspect as inspect_evidence
from robots.hygiene_robot import inspect as inspect_hygiene
from robots.impact.robot import ImpactRobot

# Level 5 robots
from robots.intelligence.robot import IntelligenceRobot
from robots.reflexion.robot import CritiqueRobot
from robots.report_robot import build as build_report


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))  # noqa: T201
        return
    summary = payload.get("summary", {})
    status = "PASS" if payload.get("ok", True) else "WORK REQUIRED"
    print(f"{status}: {json.dumps(summary, ensure_ascii=False, separators=(',', ':'))}")  # noqa: T201
    for key in ("output", "json", "markdown", "reason"):
        if payload.get(key):
            print(f"{key}: {payload[key]}")  # noqa: T201


def create_profile(project: Path, force: bool) -> tuple[dict, Path]:
    destination = profile_path(project)
    if destination.exists() and not force:
        raise RobotError(f"Profile already exists: {destination}; use --force to replace it.")
    checks = auto_checks(project, {"checks": {}})
    required_docs = [
        name for name in ("AGENTS.md", "README.md", "docs/MASTER.md")
        if (project / name).is_file()
    ]
    profile = {
        "version": 1,
        "name": project.name,
        "requiredDocs": required_docs,
        "readFirst": required_docs,
        "invariants": [],
        "routes": [
            {
                "name": "docs",
                "keywords": ["docs", "documentation", "roadmap", "module"],
                "patterns": ["docs/**", "*.md", "AGENTS.md"],
                "readFirst": required_docs,
                "checks": [name for name in ("test:docs", "lint") if name in checks],
                "invariants": ["Documentation must match current source behavior."],
            },
            {
                "name": "ui",
                "keywords": ["ui", "ux", "interface", "frontend", "layout"],
                "patterns": [
                    "src/pages/**", "src/components/**", "src/ui/**",
                    "src/styles/**", "app/**", "pages/**", "components/**",
                ],
                "readFirst": required_docs,
                "checks": [
                    name for name in ("lint", "typecheck", "test:layout")
                    if name in checks
                ],
                "invariants": [],
            },
            {
                "name": "core",
                "keywords": ["core", "logic", "backend", "service", "storage", "data"],
                "patterns": [
                    "src/services/**", "src/storage/**", "src/data/**",
                    "lib/**", "server/**", "backend/**", "tests/**"
                ],
                "readFirst": required_docs,
                "checks": [
                    name for name in ("lint", "typecheck", "test:core", "test", "test:unit")
                    if name in checks
                ],
                "invariants": [],
            },
            {
                "name": "release",
                "keywords": ["release", "deploy", "package", "docker", "ci", "build"],
                "patterns": [
                    "Dockerfile", "docker/**", ".github/**",
                    "scripts/release/**", "scripts/deploy/**", "scripts/package*",
                    "package.json", "package-lock.json", "pyproject.toml",
                ],
                "readFirst": required_docs,
                "checks": [
                    name for name in ("lint", "build:offline", "build", "test:release")
                    if name in checks
                ],
                "invariants": [],
            },
            {
                "name": "automation",
                "keywords": ["automation", "robot", "agent", "tool", "script"],
                "patterns": ["scripts/**", "tools/**", "package.json", "pyproject.toml"],
                "readFirst": required_docs,
                "checks": [
                    name for name in ("lint", "typecheck", "test")
                    if name in checks
                ],
                "invariants": ["Generated evidence must stay outside product source."],
            },
        ],
        "checks": checks,
        "limits": {
            "contextTokenBudget": 4000,
            "maxFindings": 40,
            "commandTimeoutSeconds": 900,
            "outputTailLines": 30,
        },
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return profile, destination


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="project-robots",
        description="Generic read-mostly robots for compact project work.",
    )
    cli.add_argument("--project", default=".", help="Project directory.")
    cli.add_argument("--json", action="store_true", help="Print full JSON.")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("discover", help="Detect project shape and scripts.")
    context = commands.add_parser("context", help="Build a token-budgeted context pack.")
    context.add_argument("--task", default="")
    context.add_argument("--budget", type=int)
    commands.add_parser("docs", help="Check docs, links, and duplicates.")
    commands.add_parser("hygiene", help="Check conflicts, risky files, and generated clutter.")
    commands.add_parser("clean-plan", help="List cleanup candidates; never delete.")
    plan = commands.add_parser("plan", help="Plan the smallest useful validation set.")
    plan.add_argument("--full", action="store_true")
    plan.add_argument("--browser", action="store_true")
    check = commands.add_parser("check", help="Execute a source-bound check plan.")
    check.add_argument("--full", action="store_true")
    check.add_argument("--browser", action="store_true")
    check.add_argument("--run", action="store_true", help="Required to execute commands.")
    commands.add_parser("evidence", help="Verify that latest evidence matches current source.")
    report = commands.add_parser("report", help="Generate one compact project report.")
    report.add_argument("--task", default="")
    report.add_argument("--budget", type=int)
    init = commands.add_parser("init", help="Create a central profile outside the project.")
    init.add_argument("--force", action="store_true")

    rag_index = commands.add_parser("rag-index", help="Build Code-Graph RAG index.")
    rag_index.add_argument("--force", action="store_true")
    rag_index.add_argument("--no-embed", action="store_true")
    rag_index.add_argument("--chunk-max-lines", type=int, default=120)
    rag_query = commands.add_parser("rag-query", help="Query Code-Graph RAG index.")
    rag_query.add_argument("--task", default="")
    rag_query.add_argument("--k", type=int, default=20)
    rag_query.add_argument("--budget", type=int)

    # Level 5 commands
    commands.add_parser("intelligence", help="Analyze repository architecture and dependencies.")
    impact = commands.add_parser("impact", help="Simulate impact and compute risk score for changes.")
    commands.add_parser("critique", help="Critique plan with senior-engineer heuristics.")
    auto = commands.add_parser("autonomous", help="Run autonomous sense-plan-critique-act-learn cycles.")
    auto.add_argument("--mode", choices=["oneshot", "continuous", "default"], default="default")
    auto.add_argument("--issue", default="")
    auto.add_argument("--max-cycles", type=int, default=10)
    auto.add_argument("--interval", type=int, default=300)
    auto.add_argument("--endpoint", default=None, help="Model endpoint URL (overrides config/env).")
    auto.add_argument("--model", default=None, help="Model name (overrides config/env).")
    auto.add_argument("--dry-run", action="store_true", help="Preview writes.")
    auto.add_argument("--force-probe", action="store_true", help="Bypass cached handshake.")

    solve = commands.add_parser("solve", help="Solve a coding issue with autonomous execution.")
    solve.add_argument("--issue", required=True, help="Issue description to solve.")
    solve.add_argument("--allow-writes", action="store_true", help="Allow file modifications (default: dry-run).")
    solve.add_argument("--dry-run", action="store_true", help="Force dry-run even if --allow-writes is set.")
    solve.add_argument("--endpoint", default=None, help="Model endpoint URL.")
    solve.add_argument("--model", default=None, help="Model name.")
    solve.add_argument("--force-probe", action="store_true", help="Bypass cached handshake.")

    status = commands.add_parser("status", help="Show project status.")
    status.add_argument("--sovereignty", action="store_true", help="Show sovereignty/value status.")

    probe = commands.add_parser("probe-brain", help="Probe model backend and report capabilities.")
    probe.add_argument("--endpoint", default=None)
    probe.add_argument("--model", default=None)
    probe.add_argument("--provider", default=None)
    probe.add_argument("--timeout", type=int, default=10)

    for subparser in commands.choices.values():
        subparser.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Print full JSON.",
        )
    return cli


def main() -> int:
    args = parser().parse_args()
    try:
        project = resolve_project(args.project)
        if args.command == "init":
            profile, destination = create_profile(project, args.force)
            emit({
                "ok": True,
                "summary": {
                    "kinds": sorted(detect_kinds(project)),
                    "checks": len(profile["checks"]),
                },
                "output": str(destination),
            }, args.json)
            return 0
        if args.command == "discover":
            payload, output = inspect_discovery(project)
            emit({**payload, "output": str(output)}, args.json)
            return 0
        if args.command == "context":
            payload, json_path, md_path = build_context(
                project, task=args.task, budget=args.budget
            )
            emit({**payload, "json": str(json_path), "markdown": str(md_path)}, args.json)
            return 0
        if args.command == "docs":
            payload, output = inspect_docs(project)
            emit({**payload, "output": str(output)}, args.json)
            return 0 if payload["ok"] else 1
        if args.command == "hygiene":
            payload, output = inspect_hygiene(project)
            emit({**payload, "output": str(output)}, args.json)
            return 0 if payload["ok"] else 1
        if args.command == "clean-plan":
            payload, output = inspect_cleanup(project)
            emit({**payload, "output": str(output)}, args.json)
            return 0
        if args.command in {"plan", "check"}:
            plan = build_plan(project, full=args.full, browser=args.browser)
            if args.command == "plan" or not args.run:
                payload = {
                    "ok": True,
                    "summary": compact_plan(plan),
                    "note": "Plan only; pass `check --run` to execute.",
                }
                emit(payload, args.json)
                return 0
            payload, output = execute(project, plan)
            emit({
                "ok": payload["passed"],
                "summary": {
                    "passed": payload["passed"],
                    "stable": payload["stableSourceState"],
                    "checks": [
                        {"name": row["name"], "passed": row["passed"]}
                        for row in payload["results"]
                    ],
                },
                "output": str(output),
            }, args.json)
            return 0 if payload["passed"] else 1
        if args.command == "evidence":
            payload, output = inspect_evidence(project)
            emit({**payload, "output": str(output)}, args.json)
            return 0 if payload["ok"] else 1
        if args.command == "report":
            payload, json_path, md_path = build_report(
                project, task=args.task, budget=args.budget
            )
            emit({**payload, "json": str(json_path), "markdown": str(md_path)}, args.json)
            return 0 if payload["ok"] else 1

        # Level 5 commands
        if args.command == "intelligence":
            robot = IntelligenceRobot()
            config, _ = load_config(project)
            result = robot.inspect(project, config)
            emit({"ok": result.ok, "summary": result.summary, "output": str(result.output), "metadata": result.metadata}, args.json)
            return 0 if result.ok else 1

        if args.command == "impact":
            robot = ImpactRobot()
            config, _ = load_config(project)
            result = robot.inspect(project, config)
            emit({"ok": result.ok, "summary": result.summary, "output": str(result.output), "metadata": result.metadata}, args.json)
            return 0 if result.ok else 1

        if args.command == "critique":
            robot = CritiqueRobot()
            config, _ = load_config(project)
            result = robot.inspect(project, config)
            emit({"ok": result.ok, "summary": result.summary, "output": str(result.output), "metadata": result.metadata}, args.json)
            return 0 if result.ok else 1

        if args.command == "autonomous":
            auto_config = {
                "mode": args.mode,
                "issue": args.issue,
                "max_cycles": args.max_cycles,
                "interval_seconds": args.interval,
            }
            config, _ = load_config(project)
            if args.endpoint:
                auto_config["endpoint"] = args.endpoint
            if args.model:
                auto_config["model"] = args.model
            if args.dry_run:
                auto_config["dry_run"] = True
            if args.force_probe:
                auto_config["force_probe"] = True
            config["autonomous"] = auto_config
            robot = AutonomousMainRobot()
            result = robot.inspect(project, config)
            emit({"ok": result.ok, "summary": result.summary, "output": str(result.output), "metadata": result.metadata}, args.json)
            return 0 if result.ok else 1

        if args.command == "probe-brain":
            import time as _time

            from robots.brain import probe_capabilities, provider_from_config
            from robots.brain.resources import snapshot as _host_snapshot
            from robots.common import write_json as _write_json
            from robots.sovereignty import estimate_cost_usd, record_event

            started = _time.monotonic()
            config, _ = load_config(project)
            brain = config.get("brain", {})
            if not isinstance(brain, dict):
                brain = {}
            overrides = dict(brain)
            if args.endpoint:
                overrides["endpoint"] = args.endpoint
            if args.model:
                overrides["model"] = args.model
            if args.provider:
                overrides["provider"] = args.provider
            overrides["timeout"] = args.timeout
            provider = provider_from_config({"brain": overrides})
            model_name = getattr(provider, "model", "") or "mock-small"
            # Explicit probe: always live, refreshes the handshake cache.
            profile = probe_capabilities(
                provider, model_name, {"brain": overrides},
                verify=True, project=project, force_probe=True,
            )
            host = _host_snapshot()
            latency_ms = int((_time.monotonic() - started) * 1000)
            handshake = profile.probes.get("handshake", {})
            payload = {
                "ok": True,
                "summary": {
                    "provider": getattr(provider, "kind", "mock"),
                    "model": model_name,
                    "tier": profile.tier,
                    "model_known": profile.model_known,
                    "context_window": profile.context_window,
                    "handshake_valid": bool(handshake.get("json_valid", False)),
                    "handshake_ms": int(handshake.get("latency_ms", 0)),
                },
                "profile": {
                    "tier": profile.tier,
                    "context_window": profile.context_window,
                    "tool_calling": profile.tool_calling,
                    "reasoning_format": profile.reasoning_format,
                    "structured_output": profile.structured_output,
                    "retrieval_budget": profile.retrieval_budget,
                    "retrieval_k": profile.retrieval_k,
                    "max_cycles": profile.max_cycles,
                    "verification_depth": profile.verification_depth,
                    "write_permission": profile.write_permission,
                    "model_known": profile.model_known,
                    "provider": profile.provider,
                    "model": profile.model,
                    "probes": profile.probes,
                },
                "host": {
                    "cpu_count": host.cpu_count,
                    "load_1m": host.load_1m,
                    "load_per_cpu": host.load_per_cpu,
                    "mem_available_mb": host.mem_available_mb,
                },
            }
            probe_out = _write_json(project, "brain", "probe-latest.json", payload)
            with contextlib.suppress(Exception):
                record_event(
                    "probe",
                    project=str(project),
                    model=model_name,
                    tier=profile.tier,
                    success=True,
                    latency_ms=latency_ms,
                    est_cost_usd=estimate_cost_usd(0, 0, 0.0),
                    note=f"handshake={handshake.get('json_valid', False)}",
                )
            emit({**payload, "output": str(probe_out)}, args.json)
            return 0

        if args.command == "rag-index":
            from robots.rag.robot import build_index_command

            config, _ = load_config(project)
            payload, output = build_index_command(
                project,
                config,
                force=args.force,
                chunk_max_lines=args.chunk_max_lines,
                no_embed=args.no_embed,
            )
            emit({**payload, "output": str(output)}, args.json)
            return 0

        if args.command == "rag-query":
            from robots.rag.robot import query_command

            config, _ = load_config(project)
            payload, output, md_path = query_command(
                project, config, task=args.task, k=args.k, budget=args.budget
            )
            emit({**payload, "output": str(output), "markdown": str(md_path)}, args.json)
            return 0 if payload["ok"] else 1

        if args.command == "solve":
            import time as _time

            from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
            from robots.common import write_json as _write_json
            from robots.common import write_markdown as _write_md
            from robots.sovereignty import diff_stats, estimate_cost_usd, estimate_value_usd

            config, _ = load_config(project)
            auto_config = {"mode": "oneshot", "issue": args.issue}
            if args.allow_writes and not args.dry_run:
                auto_config["allow_writes"] = True
            if args.dry_run:
                auto_config["dry_run"] = True
            if args.endpoint:
                auto_config["endpoint"] = args.endpoint
            if args.model:
                auto_config["model"] = args.model
            if args.force_probe:
                auto_config["force_probe"] = True
            config["autonomous"] = auto_config

            robot = AutonomousRobot(AutonomousConfig(issue_queue=[args.issue]))
            result = robot.run_cycle(project, config, args.issue)

            # Build solve report
            plan = result.plan
            execution = plan.get("execution", {}) or {}
            verification = plan.get("verification", {}) or {}

            # Calculate value
            added = removed = 0
            for entry in execution.get("tool_results", []) or []:
                res = entry.get("result") if isinstance(entry, dict) else None
                if isinstance(res, dict) and res.get("files_changed"):
                    a, r = diff_stats(str(res.get("preview", "")))
                    added += a
                    removed += r
            lines_changed = added + removed
            value = estimate_value_usd(lines_changed=lines_changed, tests_fixed=verification.get("tests_fixed", 0)) if result.success else 0.0

            payload = {
                "ok": result.success,
                "summary": {
                    "issue": args.issue,
                    "cycle_id": result.cycle_id,
                    "success": result.success,
                    "tier": plan.get("brain", {}).get("tier", "unknown"),
                    "model": plan.get("brain", {}).get("model", "unknown"),
                    "policy": execution.get("policy", {}).get("decision", "unknown"),
                    "lines_changed": lines_changed,
                    "tests_fixed": verification.get("tests_fixed", 0),
                    "repairs": len(verification.get("repairs", [])),
                    "tokens_in": plan.get("brain", {}).get("tokens_in", 0),
                    "tokens_out": plan.get("brain", {}).get("tokens_out", 0),
                    "value_usd": value,
                },
                "plan": {
                    "rationale": plan.get("rationale", ""),
                    "steps": plan.get("steps", []),
                    "changes": plan.get("changes", []),
                },
                "verification": verification,
                "policy": execution.get("policy", {}),
                "repairs": verification.get("repairs", []),
            }
            md_lines = [
                "# Solve Report",
                f"**Issue**: {args.issue}",
                f"**Status**: {'PASS' if result.success else 'FAIL'}",
                f"**Tier**: {plan.get('brain', {}).get('tier', 'unknown')}",
                f"**Model**: {plan.get('brain', {}).get('model', 'unknown')}",
                "",
                "## Policy",
                f"- Decision: {execution.get('policy', {}).get('decision', 'unknown')}",
                f"- Allowlisted: {', '.join(execution.get('policy', {}).get('allowlisted', [])) or 'none'}",
                f"- Reasons: {'; '.join(execution.get('policy', {}).get('reasons', []))}",
                "",
                "## Execution",
                f"- Files changed: {lines_changed}",
                f"- Tests fixed: {verification.get('tests_fixed', 0)}",
                f"- Repairs: {len(verification.get('repairs', []))}",
                "",
                "## Verification",
                f"- Syntax OK: {verification.get('syntax', {}).get('ok', 'unknown')}",
                f"- Suite OK: {verification.get('suite', {}).get('ok', verification.get('suite', {}).get('skipped', 'unknown'))}",
                f"- Depth: {verification.get('depth', 'unknown')}",
            ]
            if verification.get("repairs"):
                md_lines.append("")
                md_lines.append("## Repairs")
                for r in verification["repairs"]:
                    md_lines.append(f"- Attempt {r['attempt']}: {len(r['changes'])} changes")
            md_lines.append("")
            md_lines.append("## Economy")
            md_lines.append(f"- Tokens in/out: {plan.get('brain', {}).get('tokens_in', 0)}/{plan.get('brain', {}).get('tokens_out', 0)}")
            md_lines.append(f"- Value: ${value:.4f}")

            json_path = _write_json(project, "solve", "latest.json", payload)
            md_path = _write_md(project, "solve", "latest.md", "\n".join(md_lines))

            emit({**payload, "json": str(json_path), "markdown": str(md_path)}, args.json)
            return 0 if result.success else 1

        if args.command == "status":
            from robots.sovereignty import status_summary

            payload = {
                "ok": True,
                "summary": status_summary(),
            }
            emit(payload, args.json)
            return 0
    except RobotError as error:
        print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
