"""Autonomous Loop --- Continuous sense-plan-critique-act-learn cycle."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from robots.evidence.package import EvidencePackage, create_evidence_package
from robots.impact import ImpactRobot
from robots.intelligence import RepositoryIntelligence, build_repository_intelligence
from robots.protocol import BaseRobot, Plan, RobotResult
from robots.reflexion.robot import CritiqueRobot
from robots.tooling.selector import ToolRecommendation, select_tools

# Energy valuation constants (configurable via config["sovereignty"])
CPU_WATTS_DEFAULT = 65.0
ENERGY_USD_PER_KWH = 0.15


@dataclass(slots=True)
class AutonomousConfig:
    """Configuration for autonomous operation."""

    max_cycles: int = 10
    risk_threshold: float = 0.3
    critique_iterations: int = 3
    learning_enabled: bool = True
    cycle_interval_seconds: int = 300  # 5 minutes
    issue_queue: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CycleResult:
    """Result of a single autonomous cycle."""

    cycle_id: str
    issue: str
    plan: dict
    critique_passed: bool
    evidence: EvidencePackage | None
    success: bool
    error: str | None = None


def _tool_dict(obj: object) -> dict:
    """Slots-safe dataclass serialization for tool results (never raises)."""
    try:
        from dataclasses import asdict, is_dataclass

        if is_dataclass(obj):
            result = asdict(obj)
            return result if isinstance(result, dict) else {"repr": repr(obj)[:200]}
    except Exception:
        pass
    try:
        result = dict(vars(obj))
        return result if isinstance(result, dict) else {"repr": repr(obj)[:200]}
    except (TypeError, ValueError):
        return {"repr": repr(obj)[:200]}


def _capped_predict(brain: dict, provider_timeout: object) -> int:
    """Generation length: tier default, capped under host load."""
    base = 512 if str(brain.get("tier", "tier-1-local")) == "tier-1-local" else 1024
    cap = brain.get("num_predict_cap")
    try:
        return max(64, min(base, int(cap))) if cap is not None else base
    except (TypeError, ValueError):
        return base


def _written_files(execution_result: dict, project: Path) -> list[str]:
    """Project-relative files actually modified (policy-approved writes)."""
    files: list[str] = []
    entries = (execution_result or {}).get("tool_results", []) or []
    for entry in entries:
        res = entry.get("result", {}) if isinstance(entry, dict) else {}
        if not isinstance(res, dict) or not res.get("success"):
            continue
        if not res.get("files_changed"):
            continue
        for change in res.get("changes", []) or []:
            raw = change.get("file") if isinstance(change, dict) else None
            if not raw:
                continue
            candidate = Path(str(raw))
            if candidate.is_absolute():
                try:
                    rel = candidate.resolve().relative_to(project.resolve()).as_posix()
                except (ValueError, OSError):
                    continue
            else:
                rel = str(raw)
            if rel not in files and (project / rel).is_file():
                files.append(rel)
    return files


def _syntax_check_files(project: Path, rel_paths: list[str]) -> dict:
    """AST/syntax validation for changed Python files (stdlib compile)."""
    errors: list[dict] = []
    checked = 0
    for rel in rel_paths:
        if not rel.endswith(".py"):
            continue
        try:
            compile((project / rel).read_text(encoding="utf-8"), rel, "exec")
            checked += 1
        except SyntaxError as error:
            errors.append({"file": rel, "line": error.lineno or 0, "error": f"{error.msg} (line {error.lineno})"[:300]})
        except (OSError, ValueError) as error:
            errors.append({"file": rel, "line": 0, "error": str(error)[:300]})
    return {"checked": checked, "ok": not errors, "errors": errors}


def _run_target_suite(project: Path, config: dict, timeout: int = 180) -> dict:
    """Run the target project's pytest suite without touching its tree.

    Uses -p no:cacheprovider and PYTHONDONTWRITEBYTECODE so no
    .pytest_cache/__pycache__ is written into the target repository.
    Returns explicit SKIPPED status with reason when no tests or discovery fails.
    """
    from robots.common import command_exists, tracked_files

    try:
        limits = config.get("limits", {}) if isinstance(config, dict) else {}
        timeout = min(int(limits.get("commandTimeoutSeconds", timeout)), 300)
    except (TypeError, ValueError):
        timeout = 180
    tests: list[str] = []
    try:
        for path in tracked_files(project, config if isinstance(config, dict) else {}):
            if path.suffix != ".py":
                continue
            rel = path.relative_to(project).as_posix()
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                tests.append(rel)
    except Exception as error:
        return {
            "skipped": True,
            "status": "SKIPPED",
            "reason": f"test discovery failed: {error}",
            "ok": False,
        }
    if not tests:
        return {
            "skipped": True,
            "status": "SKIPPED",
            "reason": "no test files",
            "ok": False,
        }
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests[:50]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        completed = subprocess.run(argv, cwd=project, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError:
        return {
            "skipped": True,
            "status": "SKIPPED",
            "reason": "python interpreter not found",
            "ok": False,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "FAILED", "reason": f"timeout after {timeout}s", "tail": []}
    output = completed.stdout + "\n" + completed.stderr
    tail = output.splitlines()[-30:]
    counts = {"passed": 0, "failed": 0}
    for match in re.finditer(r"(\d+)\s+(passed|failed)", output):
        counts[match.group(2)] = int(match.group(1))
    if not command_exists("pytest") and "No module named pytest" in output:
        return {
            "skipped": True,
            "status": "SKIPPED",
            "reason": "pytest not installed for target",
            "ok": False,
        }
    return {
        "ok": completed.returncode == 0,
        "status": "PASSED" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "tail": tail,
    }


def _verification_passed(verification: dict) -> bool:
    """Aggregate pass flag — shallow skipped is NOT passed, no-writes skipped is ok."""
    checks = verification.get("checks", {})
    suite = verification.get("suite", {})
    depth = verification.get("depth", checks.get("depth", ""))

    # Shallow depth: explicit SKIPPED, not passed
    if depth == "shallow" or checks.get("depth") == "shallow":
        if checks.get("skipped"):
            return False

    # If checks skipped due to shallow, not passed
    if checks.get("skipped") and depth == "shallow":
        return False

    syntax_ok = verification.get("syntax", {}).get("ok", True)

    # Suite handling
    if suite.get("skipped"):
        if depth == "shallow":
            # Shallow + suite skipped = not passed (explicit SKIPPED)
            suite_ok = False
        else:
            # No-writes or generic skipped but not shallow: treat as ok for backward compat
            # TASK #5 requires SKIPPED only for shallow throttle, not for no-writes
            suite_ok = True
    else:
        suite_ok = suite.get("ok", True)

    # Checks handling
    if checks.get("skipped"):
        if depth == "shallow":
            checks_ok = False
        else:
            # For no-writes, checks may still be present (not skipped) or skipped due to no writes
            # If checks skipped but not shallow, allow as ok for backward compat
            checks_ok = True
    else:
        checks_ok = checks.get("passed", True)

    return bool(syntax_ok and suite_ok and checks_ok)


def _verification_status(verification: dict) -> dict:
    """Return explicit status: PASSED, FAILED, or SKIPPED with reason.

    TASK #5: Shallow verification returns SKIPPED + reason, not success=True.
    No-writes case returns PASSED for backward compat, but still explicit.
    """
    checks = verification.get("checks", {})
    suite = verification.get("suite", {})
    depth = verification.get("depth", checks.get("depth", ""))

    # Shallow depth is explicit SKIPPED
    if depth == "shallow":
        if checks.get("skipped") or suite.get("skipped"):
            return {
                "status": "SKIPPED",
                "reason": f"verification depth shallow — checks skipped (depth={depth})",
                "depth": depth,
            }

    # No-writes case: suite skipped due to no writes — treat as PASSED for backward compat
    # but still with explicit reason, not SKIPPED failure
    if suite.get("skipped"):
        reason = suite.get("reason", "")
        if "no writes" in str(reason).lower():
            return {
                "status": "PASSED",
                "reason": "no written files — suite skipped (no verification needed)",
                "depth": depth,
            }
        if "no test" in str(reason).lower():
            return {
                "status": "PASSED",
                "reason": f"suite skipped: {reason}",
                "depth": depth,
            }

    # Generic skipped (non-shallow) — check if it's shallow-related
    if checks.get("skipped"):
        if depth == "shallow":
            reason = checks.get("reason", "checks skipped due to shallow depth")
            return {"status": "SKIPPED", "reason": str(reason), "depth": depth}
        # For non-shallow, if checks skipped for other reason, treat as PASSED for backward compat
        # unless explicitly marked as SKIPPED with status
        if checks.get("status") == "SKIPPED" and depth == "shallow":
            return {"status": "SKIPPED", "reason": checks.get("reason", "checks skipped"), "depth": depth}

    # Not skipped — check if passed
    if _verification_passed(verification):
        return {"status": "PASSED", "reason": "all checks passed", "depth": depth}
    else:
        return {"status": "FAILED", "reason": "verification failed", "depth": depth}


def _wants_dry_run(brain: dict, config: dict) -> bool:
    """Supervised tiers preview by default; explicit allow_writes opts in.

    An operator `dry_run: true` always wins over `allow_writes: true`.
    """
    auto = config.get("autonomous", {}) if isinstance(config, dict) else {}
    auto = auto if isinstance(auto, dict) else {}
    if auto.get("dry_run") is True:
        return True
    if auto.get("allow_writes") is True:
        return False
    return str((brain or {}).get("write_permission", "")) == "supervised"


class AutonomousRobot(BaseRobot):
    """Robot for autonomous continuous operation."""

    name = "autonomous"
    version = 1

    def __init__(self, config: AutonomousConfig = None):
        self.config = config or AutonomousConfig()
        self.cycle_count = 0
        self._last_config: dict = {}
        self._last_brain: dict = {}
        self.learning_data = {
            "coupling_adjustments": {},
            "risk_weight_adjustments": {},
            "critique_refinements": [],
        }

    def inspect(self, project: Path, config: dict) -> RobotResult:
        """Run a single autonomous cycle on the highest priority issue."""
        from robots.common import cache_dir

        out_dir = cache_dir(project, "autonomous")
        if not self.config.issue_queue:
            return RobotResult(
                ok=True,
                summary={"message": "No issues in queue"},
                output=out_dir / "latest.json",
            )

        issue = self.config.issue_queue.pop(0)
        result = self.run_cycle(project, config, issue)

        return RobotResult(
            ok=result.success,
            summary={
                "cycle_id": result.cycle_id,
                "issue": result.issue,
                "success": result.success,
                "evidence_id": result.evidence.decision_id if result.evidence else None,
            },
            output=out_dir / f"{result.cycle_id}.json",
            metadata={
                "cycle_id": result.cycle_id,
                "issue": result.issue,
                "success": result.success,
                "evidence_id": result.evidence.decision_id if result.evidence else None,
                "critique_passed": result.critique_passed,
                "error": result.error,
            },
        )

    def plan(self, project: Path, config: dict) -> Plan:
        return Plan(
            name="autonomous",
            steps=[
                {"action": "sense", "target": "repository"},
                {"action": "plan", "target": "issue"},
                {"action": "critique", "target": "plan"},
                {"action": "refine", "target": "plan", "condition": "critique_failed"},
                {"action": "select_tools", "target": "changes"},
                {"action": "execute", "target": "plan"},
                {"action": "verify", "target": "execution"},
                {"action": "package_evidence", "target": "results"},
                {"action": "learn", "target": "outcome"},
            ],
            risk_score=0.0,
        )

    def execute(self, project: Path, plan: Plan) -> RobotResult:
        return self.inspect(project, self._last_config or {})

    def run_cycle(self, project: Path, config: dict, issue: str) -> CycleResult:
        """Execute a single sense-plan-critique-act-learn cycle."""
        import time as _time

        started = _time.monotonic()
        cycle_id = f"cycle-{self.cycle_count:04d}-{uuid.uuid4().hex[:8]}"
        self.cycle_count += 1
        self._last_config = config if isinstance(config, dict) else {}
        brain: dict = {}

        try:
            # 0. CENTRALIZE - migrate stray target-repo robot state (fail-open).
            target_cleanup: dict = {"moved": [], "left": [], "removed": False}
            try:
                from robots.autonomous.guard import cleanup_stray_target_state

                target_cleanup = cleanup_stray_target_state(project)
            except Exception:
                pass

            # 0b. BRAIN - resolve provider/profile/adaptive params (fail-open).
            brain = self._resolve_brain(config, project)
            self._last_brain = {
                "provider": brain["provider"],
                "model": brain["model"],
                "tier": brain["tier"],
            }

            # 0c. THROTTLE - respect host load and neighbor projects (fail-open).
            try:
                from robots.brain.resources import check as throttle_check

                throttle = throttle_check(config if isinstance(config, dict) else None)
                brain["throttled"] = bool(throttle.overloaded)
                brain["throttle_reasons"] = list(throttle.reasons)
                brain["host_workers"] = int(throttle.max_workers)
                if throttle.overloaded:
                    brain["verification_depth"] = "shallow"
                    if throttle.num_predict_cap is not None:
                        brain["num_predict_cap"] = int(throttle.num_predict_cap)
            except Exception:
                pass

            # 1. SENSE - Build repository intelligence
            intelligence = build_repository_intelligence(project, config)

            # 1b. RAG retrieval (fail-open, between SENSE and PLAN).
            rag_context: dict = {"hits": [], "firstTokens": 0, "stale": True}
            try:
                from robots.common import load_config as _load_config
                from robots.rag.robot import query_for_context

                _cfg = config if isinstance(config, dict) else _load_config(project)[0]
                budget = int(_cfg.get("limits", {}).get("contextTokenBudget", 4000))
                rag_context = query_for_context(project, _cfg, issue, budget, k=int(brain.get("retrieval_k", 15)))
            except Exception:
                rag_context = {"hits": [], "firstTokens": 0, "stale": True}

            # 2. PLAN - Dynamic LLM generation via Brain (static fallback).
            plan = self._generate_plan(issue, intelligence, config, project, rag_context, brain)
            plan["decision_id"] = cycle_id
            plan["issue"] = issue
            plan["context_chunks"] = rag_context.get("hits", [])
            plan["target_cleanup"] = target_cleanup
            try:
                from robots.autonomous.guard import sanitize_changes

                plan["changes"] = sanitize_changes(plan.get("changes", []), project)
            except Exception:
                plan["changes"] = []

            # 3. CRITIQUE - direct in-memory handoff (never reads stale files).
            # Critical findings block all writes below.
            critique_robot = CritiqueRobot()
            critique_result, refined_plan, critique_robot_result = critique_robot.critique_plan_direct(
                plan, intelligence, issue, project, config
            )
            _ = critique_robot_result  # Artifacts written for inspectability.
            critique_passed = bool(critique_result.passed)
            has_critical = any(getattr(f, "severity", "") == "critical" for f in (critique_result.findings or []))
            if has_critical:
                critique_passed = False

            # 4. TOOL SELECTION
            tools = select_tools(refined_plan.get("changes", []), intelligence, config)
            refined_plan["tools"] = [_tool_dict(t) for t in tools]

            # 5. EXECUTE - blocked on critical critique; else guarded writes.
            if has_critical:
                execution_result = {
                    "tool_results": [],
                    "policy": {
                        "decision": "deny",
                        "dry_run": True,
                        "risk": 1.0,
                        "threshold": float(self.config.risk_threshold),
                        "allowlisted": [],
                        "reasons": ["critique critical failure blocks writes"],
                    },
                    "blocked_by_critique": True,
                }
            else:
                execution_result = self._execute_plan(refined_plan, tools, project, config, brain)

            # 6. VERIFY - syntax + suite + self-repair loop (max 2 retries).
            verification = self._verify_with_repair(
                refined_plan, execution_result, intelligence, project, config, brain
            )
            refined_plan["execution"] = execution_result
            verification["critique"] = {
                "passed": bool(critique_result.passed),
                "critical": bool(has_critical),
                "findings": [
                    {
                        "severity": getattr(f, "severity", ""),
                        "category": getattr(f, "category", ""),
                        "message": getattr(f, "message", ""),
                    }
                    for f in (critique_result.findings or [])
                ],
            }

            # 7. PACKAGE EVIDENCE
            evidence = create_evidence_package(
                refined_plan,
                project,
                verification,
                [_tool_dict(t) for t in tools],
            )

            # 8. LEARN - Update models
            if self.config.learning_enabled:
                self._learn(evidence, intelligence, critique_result, project=project)

            # TASK #5: Explicit SKIPPED handling — success=True forbidden when skipped
            ver_status = _verification_status(verification)
            refined_plan["verification_status"] = ver_status
            verification["verification_status"] = ver_status

            if ver_status["status"] == "SKIPPED":
                # When checks skipped, success must be False, explicit status SKIPPED
                self._record_ledger(
                    project, config, issue, False, started, refined_plan, brain, note=ver_status["reason"]
                )
                return CycleResult(
                    cycle_id=cycle_id,
                    issue=issue,
                    plan=refined_plan,
                    critique_passed=critique_passed,
                    evidence=evidence,
                    success=False,
                    error=f"SKIPPED: {ver_status['reason']}",
                )

            is_passed = _verification_passed(verification)
            # Success only if verification passed
            final_success = bool(is_passed and critique_passed)

            self._record_ledger(project, config, issue, final_success, started, refined_plan, brain)
            return CycleResult(
                cycle_id=cycle_id,
                issue=issue,
                plan=refined_plan,
                critique_passed=critique_passed,
                evidence=evidence,
                success=final_success,
                error=None if final_success else f"FAILED: {ver_status['reason']}",
            )

        except Exception as e:
            self._record_ledger(project, config, issue, False, started, {}, brain, note=str(e))
            return CycleResult(
                cycle_id=cycle_id,
                issue=issue,
                plan={},
                critique_passed=False,
                evidence=None,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _record_ledger(
        project: Path,
        config: dict,
        issue: str,
        success: bool,
        started: float,
        plan: dict,
        brain: dict,
        note: str = "",
    ) -> None:
        """Append a cycle event to the sovereignty ledger (fail-open)."""
        try:
            import time as _time

            from robots.sovereignty import (
                diff_stats,
                estimate_cost_usd,
                estimate_energy_usd,
                estimate_value_usd,
                record_event,
            )

            brain_meta = plan.get("brain", {}) if isinstance(plan, dict) else {}
            latency = int((_time.monotonic() - started) * 1000)
            tokens_in = int(brain_meta.get("tokens_in", 0))
            tokens_out = int(brain_meta.get("tokens_out", 0))

            # Add repair tokens from verification
            verification = plan.get("verification", {}) if isinstance(plan, dict) else {}
            for repair in verification.get("repairs", []):
                brain = repair.get("brain", {})
                if isinstance(brain, dict):
                    tokens_in += int(brain.get("tokens_in", 0))
                    tokens_out += int(brain.get("tokens_out", 0))

            # Calculate lines changed from execution previews
            added = removed = 0
            execution = plan.get("execution", {}) if isinstance(plan, dict) else {}
            for entry in execution.get("tool_results", []) or []:
                res = entry.get("result") if isinstance(entry, dict) else None
                if isinstance(res, dict) and res.get("files_changed"):
                    a, r = diff_stats(str(res.get("preview", "")))
                    added += a
                    removed += r
            lines_changed = added + removed

            # Value calculation
            verification = plan.get("verification", {}) if isinstance(plan, dict) else {}
            tests_fixed = int(verification.get("tests_fixed", 0) or 0)

            rate = 0.0
            cpu_watts = CPU_WATTS_DEFAULT
            energy_rate = ENERGY_USD_PER_KWH
            if isinstance(config, dict):
                raw = config.get("sovereignty", {})
                if isinstance(raw, dict):
                    try:
                        rate = float(raw.get("rate_per_mtok", 0.0))
                    except (TypeError, ValueError):
                        rate = 0.0
                    try:
                        cpu_watts = float(raw.get("cpu_watts", CPU_WATTS_DEFAULT))
                    except (TypeError, ValueError):
                        cpu_watts = CPU_WATTS_DEFAULT
                    try:
                        energy_rate = float(raw.get("energy_usd_per_kwh", ENERGY_USD_PER_KWH))
                    except (TypeError, ValueError):
                        energy_rate = ENERGY_USD_PER_KWH

            token_cost = estimate_cost_usd(tokens_in, tokens_out, rate)
            energy_cost = estimate_energy_usd(latency, cpu_watts, energy_rate)
            value = estimate_value_usd(lines_changed=lines_changed, tests_fixed=tests_fixed) if success else 0.0

            record_event(
                "cycle",
                project=str(project),
                model=str(brain.get("model", "")),
                tier=str(brain.get("tier", "")),
                issue=str(issue)[:512],
                success=success,
                latency_ms=latency,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                est_cost_usd=round(token_cost + energy_cost, 6),
                value_usd=value,
                lines_changed=lines_changed,
                note=str(note)[:1024],
            )
        except Exception:
            pass

    def _resolve_brain(self, config: dict, project: Path | None = None) -> dict:
        """Resolve provider/profile/adaptive params. Never raises."""
        try:
            from robots.brain import resolve_runtime

            provider, profile, adaptive = resolve_runtime(
                config if isinstance(config, dict) else {}, verify=True, project=project
            )
            return {
                "provider": getattr(provider, "kind", "mock"),
                "model": getattr(provider, "model", "") or "mock-small",
                "tier": profile.tier,
                "retrieval_k": adaptive["retrieval_k"],
                "verification_depth": adaptive["verification_depth"],
                "max_cycles": adaptive["max_cycles"],
                "budget": adaptive["budget"],
                "write_permission": adaptive["write_permission"],
                "context_window": adaptive["context_window"],
                "model_known": profile.model_known,
                "handshake_source": str(profile.probes.get("handshake", {}).get("source", "")),
                "provider_obj": provider,
                "profile_obj": profile,
            }
        except Exception:
            return {
                "provider": "mock",
                "model": "mock-small",
                "tier": "tier-1-local",
                "retrieval_k": 8,
                "verification_depth": "shallow",
                "max_cycles": 2,
                "budget": 4000,
                "write_permission": "supervised",
                "context_window": 4000,
                "model_known": False,
                "handshake_source": "",
                "provider_obj": None,
                "profile_obj": None,
            }

    def _static_plan(self, issue: str, impact_metadata: dict) -> dict:
        """Deterministic fallback plan (pre-RFC-002 behavior)."""
        return {
            "decision_id": "",
            "issue": issue,
            "rationale": f"Autonomous resolution of: {issue}",
            "risk_score": impact_metadata.get("risk_score", {}),
            "changed_files": impact_metadata.get("changed_files", []),
            "steps": [
                {"action": "analyze", "target": "impact"},
                {"action": "fix", "target": "root_cause"},
                {"action": "test", "target": "verification"},
                {"action": "deploy", "target": "canary"},
            ],
        }

    def _generate_plan(
        self,
        issue: str,
        intelligence: RepositoryIntelligence,
        config: dict,
        project: Path,
        rag_context: dict | None = None,
        brain: dict | None = None,
    ) -> dict:
        """Dynamic LLM plan generation via Brain with schema-repair fallback."""
        # Use impact robot to analyze (blast-radius evidence for the prompt).
        impact_robot = ImpactRobot()
        impact_result = impact_robot.inspect(project, config)
        impact_metadata = impact_result.metadata or {}
        static = self._static_plan(issue, impact_metadata)

        # --- Learning Loop: retrieve relevant lessons via keyword overlap ---
        try:
            from robots.autonomous.learning import create_learning_engine

            learning_engine = create_learning_engine(project)
            relevant_lessons = learning_engine.get_relevant_lessons(issue, top_k=5)
            if relevant_lessons:
                static["lessons"] = relevant_lessons
                impact_metadata["lessons"] = relevant_lessons
        except Exception:
            pass

        brain = brain or {}
        provider = brain.get("provider_obj")
        if provider is None:
            static["brain"] = {"provider": "none", "fallback": "no-provider"}
            return static
        try:
            from robots.brain import ModelOptions, build_prompt, repair_plan
            from robots.intelligence import get_intelligence_summary
            from robots.rag.store import load_chunks

            hits = (rag_context or {}).get("hits", [])
            by_id = {}
            try:
                by_id = {c["id"]: c for c in load_chunks(project)}
            except Exception:
                by_id = {}
            prompt_chunks = []
            for hit in hits:
                chunk = dict(hit)
                stored = by_id.get(hit.get("id", ""))
                if stored and not chunk.get("text"):
                    chunk["text"] = stored.get("text", "")
                prompt_chunks.append(chunk)

            # Append lessons as additional context chunks for prompt
            try:
                from robots.autonomous.learning import create_learning_engine

                le = create_learning_engine(project)
                lessons = le.get_relevant_lessons(issue, top_k=5)
                for les in lessons:
                    prompt_chunks.append(
                        {
                            "id": les.get("id", ""),
                            "text": f"Lesson [{les.get('category', '')}]: {les.get('message', '')} Context: {les.get('context', '')}",
                            "path": "lessons",
                            "score": 0.9,
                        }
                    )
            except Exception:
                pass

            summary = get_intelligence_summary(intelligence)
            prompt = build_prompt(
                task=issue,
                rag_chunks=prompt_chunks,
                intelligence_summary=summary if isinstance(summary, dict) else {},
                tier=str(brain.get("tier", "tier-1-local")),
                budget=int(brain.get("budget", 4000)),
            )
            options = ModelOptions(
                temperature=0.2,
                num_predict=_capped_predict(brain, getattr(provider, "timeout", 60)),
                timeout=min(60, int(getattr(provider, "timeout", 60))),
            )
            response = provider.generate(prompt, options)
            tokens_in = max(1, len(prompt.encode("utf-8")) // 4)
            tokens_out = max(1, len(response.text.encode("utf-8")) // 4)
            if response.error or not response.text:
                static["brain"] = {
                    "provider": brain.get("provider"),
                    "model": brain.get("model"),
                    "tier": brain.get("tier"),
                    "fallback": response.error or "empty",
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": response.latency_ms,
                }
                return static
            plan, repaired, repair_error = repair_plan(response.text, issue)
            plan["decision_id"] = ""
            plan["issue"] = issue
            plan["risk_score"] = impact_metadata.get("risk_score", {})
            plan["changed_files"] = impact_metadata.get("changed_files", [])
            plan["brain"] = {
                "provider": brain.get("provider"),
                "model": brain.get("model"),
                "tier": brain.get("tier"),
                "repaired": repaired,
                "repair_error": repair_error,
                "latency_ms": response.latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model_known": brain.get("model_known", False),
                "throttled": bool(brain.get("throttled", False)),
                "handshake_source": brain.get("handshake_source", ""),
            }
            return plan
        except Exception as error:
            static["brain"] = {
                "provider": brain.get("provider"),
                "model": brain.get("model"),
                "tier": brain.get("tier"),
                "fallback": f"exception: {error}",
            }
            return static

    def _apply_direct_edits(self, plan: dict, project: Path, policy, dry_run: bool) -> list[dict]:
        """Apply LLM-specified file/pattern/replacement edits under the policy.

        Entries without edit content are skipped (other tools may handle the
        file). Every application is allowlisted and preview-recorded.
        """
        from robots.autonomous.guard import is_path_allowed
        from robots.tooling.semantic_patch import SemanticPatcher

        out: list[dict] = []
        patcher = SemanticPatcher({})
        for change in plan.get("changes", []) or []:
            if not isinstance(change, dict):
                continue
            rel = str(change.get("file", change.get("path", "")))
            pattern = change.get("pattern", change.get("old", ""))
            replacement = change.get("replacement", change.get("new", ""))
            if not rel or not isinstance(pattern, str) or not pattern:
                continue
            if not isinstance(replacement, str):
                continue
            allowed, reason = is_path_allowed(project, rel, policy)
            if policy.decision == "deny" or not allowed:
                out.append(
                    {
                        "tool": "direct_edit",
                        "result": {
                            "success": False,
                            "files_changed": 0,
                            "file": rel,
                            "reason": reason or "; ".join(policy.reasons),
                        },
                    }
                )
                continue
            file_pattern = str(change.get("file_pattern", "*.py"))
            result = patcher.apply_patch(
                pattern,
                replacement,
                file_pattern,
                project,
                dry_run=dry_run,
                allowed_files={rel},
            )
            entry = _tool_dict(result)
            entry["file"] = rel
            out.append({"tool": "direct_edit", "result": entry})
        return out

    def _execute_plan(
        self,
        plan: dict,
        tools: list[ToolRecommendation],
        project: Path,
        config: dict,
        brain: dict | None = None,
    ) -> dict:
        """Execute plan through the write policy gate (risk + allowlist + dry-run)."""
        from robots.autonomous.guard import evaluate_write_policy, is_path_allowed

        brain = brain or {}
        risk_score = plan.get("risk_score", 0.0)
        if isinstance(risk_score, dict):
            risk_overall = risk_score.get("overall", 0.0)
        else:
            risk_overall = risk_score
        candidates = [
            str(change.get("file", change.get("path", "")))
            for change in plan.get("changes", [])
            if isinstance(change, dict)
        ]
        rag_paths = [str(hit.get("path", "")) for hit in plan.get("context_chunks", []) if isinstance(hit, dict)]
        policy = evaluate_write_policy(
            risk_overall=risk_overall,
            risk_threshold=self.config.risk_threshold,
            candidate_paths=[c for c in candidates if c],
            rag_paths=[p for p in rag_paths if p],
            project=project,
            config=config,
            dry_run_requested=_wants_dry_run(brain, config),
        )
        if brain.get("write_permission") == "denied":
            policy.decision = "deny"
            policy.dry_run = True
            policy.reasons.append("model tier denies writes")
        dry_run = policy.decision != "allow"
        results = []
        results.extend(self._apply_direct_edits(plan, project, policy, dry_run))

        for tool_rec in tools:
            tool_name = tool_rec.tool

            if tool_name == "ast_rewrite":
                from robots.tooling.ast_rewrite import rewrite_ast

                for change in plan.get("changes", []):
                    if not isinstance(change, dict):
                        continue
                    rel = str(change.get("file", ""))
                    allowed, reason = is_path_allowed(project, rel, policy)
                    if policy.decision == "deny" or not allowed:
                        results.append(
                            {
                                "tool": tool_name,
                                "result": {
                                    "success": False,
                                    "files_changed": 0,
                                    "reason": reason or "; ".join(policy.reasons),
                                },
                            }
                        )
                        continue
                    result = rewrite_ast(
                        project / rel,
                        tool_rec.config.get("refactoring_type", "general"),
                        tool_rec.config,
                        config,
                        dry_run,
                    )
                    results.append({"tool": tool_name, "result": _tool_dict(result)})

            elif tool_name == "semantic_patch":
                from robots.tooling.semantic_patch import apply_semantic_patch

                if policy.decision == "deny" or not policy.allowlist:
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "files_changed": 0,
                                "reason": "; ".join(policy.reasons) or "no allowlisted files",
                            },
                        }
                    )
                    continue
                result = apply_semantic_patch(
                    tool_rec.config.get("pattern", ""),
                    tool_rec.config.get("replacement", ""),
                    tool_rec.config.get("file_pattern", "*.py"),
                    project,
                    config,
                    dry_run,
                    set(policy.allowlist),
                )
                results.append({"tool": tool_name, "result": _tool_dict(result)})

            elif tool_name == "model_checker":
                # Read-only formal verification. Never writes; scope-checked read.
                from robots.autonomous.guard import is_in_scope, normalize_rel

                if policy.decision == "deny":
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "blocked",
                                "files_changed": 0,
                                "dry_run": True,
                                "reason": "; ".join(policy.reasons) or "denied",
                            },
                        }
                    )
                    continue
                cfg = tool_rec.config if isinstance(tool_rec.config, dict) else {}
                rel = str(cfg.get("spec_path", cfg.get("file", cfg.get("path", "")))).strip()
                if not rel:
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "skipped",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "reason": "missing execution context: spec_path required",
                            },
                        }
                    )
                    continue
                if normalize_rel(project, rel) is None or not is_in_scope(project, project / rel):
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "blocked",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "reason": "path escapes project boundary",
                            },
                        }
                    )
                    continue
                if not (project / rel).is_file():
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "skipped",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "reason": f"spec file not found: {rel}",
                            },
                        }
                    )
                    continue
                from robots.tooling.model_checker import ModelChecker

                props = cfg.get("properties", cfg.get("property", []))
                properties = list(props) if isinstance(props, list) else []
                spec_type = str(cfg.get("spec_type", "tla"))
                checked = ModelChecker(config).check(project / rel, properties, spec_type)
                payload = _tool_dict(checked)
                errors = " ".join(str(e) for e in (payload.get("errors") or []))
                if "No model checker available" in errors or "not fully implemented" in errors:
                    # Backend missing: explicit unsupported, never success.
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "unsupported",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "spec": rel,
                                "spec_type": spec_type,
                                "reason": errors or "model checker backend unavailable",
                                "errors": payload.get("errors", []),
                            },
                        }
                    )
                    continue
                payload["status"] = "success" if payload.get("success") else "failed"
                payload["dry_run"] = bool(dry_run)
                payload["spec"] = rel
                results.append({"tool": tool_name, "result": payload})

            elif tool_name == "contract_tester":
                # Pure-compute contract diff. Never writes.
                if policy.decision == "deny":
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "blocked",
                                "files_changed": 0,
                                "dry_run": True,
                                "reason": "; ".join(policy.reasons) or "denied",
                            },
                        }
                    )
                    continue
                cfg = tool_rec.config if isinstance(tool_rec.config, dict) else {}
                old_spec = cfg.get("old_spec", cfg.get("old", None))
                new_spec = cfg.get("new_spec", cfg.get("new", None))
                contract_type = str(cfg.get("contract_type", "openapi"))
                if not isinstance(old_spec, dict) or not isinstance(new_spec, dict):
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "skipped",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "reason": ("missing execution context: old_spec/new_spec dicts required"),
                            },
                        }
                    )
                    continue
                if contract_type in ("protobuf", "pydantic"):
                    # Placeholder implementations report fake success; refuse that.
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "unsupported",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "contract_type": contract_type,
                                "reason": f"{contract_type} verification not implemented",
                            },
                        }
                    )
                    continue
                from robots.tooling.contract_tester import ContractTester

                tested = ContractTester(config).test_contracts(old_spec, new_spec, contract_type)
                payload = _tool_dict(tested)
                errors = " ".join(str(e) for e in (payload.get("errors") or []))
                if "requires model imports" in errors:
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "unsupported",
                                "files_changed": 0,
                                "dry_run": bool(dry_run),
                                "contract_type": contract_type,
                                "reason": errors,
                                "errors": payload.get("errors", []),
                            },
                        }
                    )
                    continue
                payload["status"] = "success" if payload.get("success") else "failed"
                payload["dry_run"] = bool(dry_run)
                results.append({"tool": tool_name, "result": payload})

            elif tool_name in ("property_tester", "benchmark"):
                # No executor module exists (selector-only labels). Explicit
                # unsupported; deny takes precedence as blocked.
                if policy.decision == "deny":
                    results.append(
                        {
                            "tool": tool_name,
                            "result": {
                                "success": False,
                                "status": "blocked",
                                "files_changed": 0,
                                "dry_run": True,
                                "reason": "; ".join(policy.reasons) or "denied",
                            },
                        }
                    )
                    continue
                results.append(
                    {
                        "tool": tool_name,
                        "result": {
                            "success": False,
                            "status": "unsupported",
                            "files_changed": 0,
                            "dry_run": bool(dry_run),
                            "reason": f"no executor module for {tool_name}",
                        },
                    }
                )
                continue

            else:
                # Unknown selector label: fail closed, never success.
                results.append(
                    {
                        "tool": tool_name,
                        "result": {
                            "success": False,
                            "status": "unsupported",
                            "files_changed": 0,
                            "dry_run": bool(dry_run),
                            "reason": f"unknown tool: {tool_name}",
                        },
                    }
                )
                continue

        return {
            "tool_results": results,
            "policy": {
                "decision": policy.decision,
                "dry_run": dry_run,
                "risk": policy.risk,
                "threshold": policy.threshold,
                "allowlisted": sorted(policy.allowlist),
                "reasons": policy.reasons,
            },
        }

    def _verify_execution(self, plan: dict, project: Path, config: dict, brain: dict | None = None) -> dict:
        """Verify execution results (depth adapts to model tier).

        TASK #5: When depth shallow, return explicit SKIPPED status + reason,
        never success=True.
        """
        # Run impact analysis again to verify
        impact_robot = ImpactRobot()
        impact_result = impact_robot.inspect(project, config)

        depth = (brain or {}).get("verification_depth", "deep")
        if depth == "shallow":
            return {
                "impact": impact_result.metadata,
                "checks": {
                    "skipped": True,
                    "depth": depth,
                    "status": "SKIPPED",
                    "reason": f"verification depth shallow — checks skipped (tier={brain.get('tier', 'unknown')})",
                    "passed": False,
                },
                "depth": depth,
                "verification_status": {
                    "status": "SKIPPED",
                    "reason": f"shallow verification — checks skipped for tier {brain.get('tier', 'unknown')}",
                    "depth": depth,
                },
            }

        # Run tests
        from robots.checks_robot import build_plan, execute

        check_plan = build_plan(project)
        check_result, _ = execute(project, check_plan)

        return {
            "impact": impact_result.metadata,
            "checks": check_result,
            "depth": depth,
        }

    def _verify_with_repair(
        self,
        plan: dict,
        execution_result: dict,
        intelligence: RepositoryIntelligence,
        project: Path,
        config: dict,
        brain: dict | None = None,
    ) -> dict:
        """Verify execution with syntax check, suite run, and up to 2 self-repair attempts."""
        brain = brain or {}
        depth = str(brain.get("verification_depth", "deep"))
        written = _written_files(execution_result, project)

        # Initial verification (impact + checks)
        verification = self._verify_execution(plan, project, config, brain)
        verification["written_files"] = written
        verification["repairs"] = []

        # Syntax check on written files
        verification["syntax"] = {"ok": True, "checked": 0, "errors": []}
        if written:
            verification["syntax"] = _syntax_check_files(project, written)

        # Suite run — explicit status with reason
        # For no-writes, we return ok=True for backward compat (no verification needed)
        # Shallow case is handled separately in _verify_execution
        first_suite = {
            "skipped": True,
            "status": "PASSED",
            "reason": "no writes — suite skipped (no verification needed)",
            "ok": True,
        }
        if written or depth != "shallow":
            verification["suite"] = _run_target_suite(project, config)
            first_suite = dict(verification["suite"])
        else:
            verification["suite"] = first_suite

        # Self-repair loop (max 2 attempts)
        provider = brain.get("provider_obj")
        attempts = 0
        while written and not _verification_passed(verification) and attempts < 2 and provider is not None:
            attempts += 1
            repair = self._generate_repair(plan, verification, project, config, brain)
            repair_changes = repair.get("changes", [])
            if not repair_changes:
                verification["repairs"].append(
                    {
                        "attempt": attempts,
                        "skipped": "no usable changes",
                        **repair.get("brain", {}),
                    }
                )
                break

            repair_plan_full = {
                "issue": plan.get("issue", ""),
                "risk_score": plan.get("risk_score", 0.0),
                "changes": repair_changes,
                "context_chunks": plan.get("context_chunks", []),
                "brain": repair.get("brain", {}),
            }
            repair_execution = self._execute_plan(repair_plan_full, [], project, config, brain)
            written = _written_files(repair_execution, project)
            verification["repairs"].append(
                {
                    "attempt": attempts,
                    "changes": repair_changes,
                    "execution": {
                        "policy": repair_execution.get("policy", {}),
                        "results": [
                            {
                                "tool": e.get("tool"),
                                "files_changed": (e.get("result") or {}).get("files_changed", 0),
                            }
                            for e in repair_execution.get("tool_results", [])
                        ],
                    },
                    "brain": repair.get("brain", {}),
                }
            )
            if written:
                verification["syntax"] = _syntax_check_files(project, written)
                verification["suite"] = _run_target_suite(project, config)
            if _verification_passed(verification):
                break

        # Track tests fixed (failed -> passing)
        if (
            first_suite.get("failed")
            and verification.get("suite", {}).get("ok")
            and not verification.get("suite", {}).get("skipped")
        ):
            verification["tests_fixed"] = int(first_suite.get("failed", 0))
        else:
            verification["tests_fixed"] = 0

        verification["depth"] = depth
        return verification

    def _repair_error_context(self, verification: dict, limit: int = 1200) -> str:
        """Extract a concise error summary for the repair prompt."""
        parts: list[str] = []
        syntax = verification.get("syntax", {})
        for error in syntax.get("errors", []) or []:
            if isinstance(error, dict):
                parts.append(f"syntax {error.get('file')}:{error.get('line')} {error.get('error')}")
        suite = verification.get("suite", {})
        if suite and not suite.get("skipped") and not suite.get("ok"):
            parts.append(f"pytest failed ({suite.get('failed', '?')} failed, rc={suite.get('returncode')})")
            for line in (suite.get("tail") or [])[-15:]:
                if any(k in line for k in ("FAILED", "Error", "error", "assert")):
                    parts.append(line[:200])
        text = "\n".join(parts)
        return text[:limit] or "verification failed (no details)"

    def _generate_repair(
        self,
        plan: dict,
        verification: dict,
        project: Path,
        config: dict,
        brain: dict,
    ) -> dict:
        """Ask the Brain for a corrected change set from verification failures."""
        provider = brain.get("provider_obj")
        empty = {"changes": [], "brain": {"fallback": "no-provider"}}
        if provider is None:
            return empty
        try:
            import json

            from robots.brain import ModelOptions, build_prompt, repair_plan

            error_context = self._repair_error_context(verification)
            task = (
                f"{plan.get('issue', '')}\n\n"
                "The previous change set failed verification.\n"
                f"Previous changes: {json.dumps(plan.get('changes', []))[:600]}\n"
                f"Verification failures:\n{error_context}\n"
                "Produce a corrected minimal change set that makes verification pass."
            )
            prompt = build_prompt(
                task=task,
                rag_chunks=plan.get("context_chunks", [])[:6],
                intelligence_summary={},
                tier=str(brain.get("tier", "tier-1-local")),
                budget=int(brain.get("budget", 4000)),
            )
            options = ModelOptions(
                temperature=0.0,
                num_predict=_capped_predict(brain, getattr(provider, "timeout", 60)),
                timeout=min(60, int(getattr(provider, "timeout", 60))),
            )
            response = provider.generate(prompt, options)
            tokens_in = max(1, len(prompt.encode("utf-8")) // 4)
            tokens_out = max(1, len(response.text.encode("utf-8")) // 4)
            if response.error or not response.text:
                return {
                    "changes": [],
                    "brain": {
                        "fallback": response.error or "empty",
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "latency_ms": response.latency_ms,
                    },
                }
            repaired_plan, repaired_flag, repair_error = repair_plan(response.text, plan.get("issue", ""))
            try:
                from robots.autonomous.guard import sanitize_changes

                changes = sanitize_changes(repaired_plan.get("changes", []), project)
            except Exception:
                changes = []
            return {
                "changes": changes,
                "brain": {
                    "repaired": repaired_flag,
                    "repair_error": repair_error,
                    "latency_ms": response.latency_ms,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                },
            }
        except Exception as error:
            return {"changes": [], "brain": {"fallback": f"exception: {error}"}}

    def _learn(
        self,
        evidence: EvidencePackage,
        intelligence: RepositoryIntelligence,
        critique_result,
        project=None,
    ):
        """Learn from execution outcome — persists lessons append-only."""
        # Update coupling matrix based on actual vs predicted impact.

        # Adjust risk weights
        if "risk_score" in evidence.verification:
            predicted_risk = evidence.risk_score
            actual_risk = evidence.verification.get("actual_risk", predicted_risk)
            error = abs(predicted_risk - actual_risk)

            if error > 0.1:
                self.learning_data["risk_weight_adjustments"][evidence.decision_id] = error

        # Record critique refinements (accepts CritiqueResult.passed or RobotResult.ok).
        critique_failed = bool(getattr(critique_result, "passed", getattr(critique_result, "ok", True)) is False)
        if critique_failed:
            self.learning_data["critique_refinements"].append(
                {
                    "decision_id": evidence.decision_id,
                    "findings": evidence.verification.get("critique", {}).get("findings", []),
                }
            )

        # --- Learning Loop: persist critic/reflexion lessons in lessons store JSON append-only ---
        try:
            from pathlib import Path

            from robots.autonomous.learning import create_learning_engine

            proj = project
            if proj is None:
                proj = Path(".")
            if isinstance(proj, str):
                proj = Path(proj)

            engine = create_learning_engine(proj)
            engine.save_lessons_from_critique(evidence, critique_result)
        except Exception:
            pass

    def _measure_actual_impact(self, evidence: EvidencePackage) -> dict:
        """Measure actual impact after deployment."""
        # Placeholder - would measure real production metrics
        return {}


class AutonomousScheduler:
    """Schedules and runs autonomous cycles."""

    def __init__(self, robot: AutonomousRobot, project: Path, config: dict):
        self.robot = robot
        self.project = project
        self.config = config
        self.running = False

    def add_issue(self, issue: str) -> None:
        """Add issue to queue."""
        self.robot.config.issue_queue.append(issue)

    def run_continuous(self) -> None:
        """Run continuous autonomous cycles."""
        self.running = True

        while self.running and self.robot.cycle_count < self.robot.config.max_cycles:
            if self.robot.config.issue_queue:
                issue = self.robot.config.issue_queue.pop(0)
                result = self.robot.run_cycle(self.project, self.config, issue)

                status = "SUCCESS" if result.success else "FAILED"
                print(f"Cycle {result.cycle_id}: {status} - {result.issue}")  # noqa: T201

                if not result.success and result.error:
                    print(f"  Error: {result.error}")  # noqa: T201
            else:
                print("No issues in queue, waiting...")  # noqa: T201
                time.sleep(self.robot.config.cycle_interval_seconds)

    def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False


def run_autonomous(
    project: Path,
    config: dict,
    issues: list[str],
    max_cycles: int = 10,
) -> list[CycleResult]:
    """Run autonomous cycles for given issues."""
    auto_config = AutonomousConfig(
        max_cycles=max_cycles,
        issue_queue=issues,
    )

    robot = AutonomousRobot(auto_config)

    results = []
    for issue in issues:
        result = robot.run_cycle(project, config, issue)
        results.append(result)

    return results
