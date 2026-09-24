"""Autonomous Robot — Main entry point for autonomous operation."""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

from robots.autonomous.loop import (
    AutonomousConfig,
    AutonomousRobot,
    AutonomousScheduler,
    CycleResult,
    run_autonomous,
)
from robots.common import cache_dir, load_config, write_json
from robots.protocol import BaseRobot, Plan, RobotResult, register_robot


class AutonomousMainRobot(BaseRobot):
    """Main autonomous robot for CLI integration."""

    name = "autonomous"
    version = 1

    def __init__(self):
        self.robot = AutonomousRobot()
        self.scheduler = None
        self._last_config: dict = {}

    def _brain_summary(self, config: dict) -> dict:
        """Resolve brain runtime (fail-open) for summaries and cycle caps."""
        try:
            from robots.brain import resolve_runtime

            _, profile, adaptive = resolve_runtime(config, fast=True)
            return {
                "provider": config.get("brain", {}).get("provider", "")
                if isinstance(config.get("brain"), dict)
                else "",
                "tier": profile.tier,
                "model_known": profile.model_known,
                "max_cycles": adaptive["max_cycles"],
                "verification_depth": adaptive["verification_depth"],
            }
        except Exception:
            return {"tier": "tier-1-local", "max_cycles": 2, "verification_depth": "shallow"}

    def inspect(self, project: Path, config: dict) -> RobotResult:
        """Run autonomous mode based on config."""
        self._last_config = config if isinstance(config, dict) else {}
        # Check for autonomous config
        auto_config = config.get("autonomous", {})

        if auto_config.get("mode") == "continuous":
            return self._run_continuous(project, config, auto_config)
        elif auto_config.get("mode") == "oneshot":
            return self._run_oneshot(project, config, auto_config)
        else:
            return self._run_default(project, config, auto_config)

    def _run_default(self, project: Path, config: dict, auto_config: dict) -> RobotResult:
        """Default autonomous run - process issue queue."""
        issues = auto_config.get("issues") or (
            [auto_config["issue"]] if auto_config.get("issue") else ["autonomous maintenance cycle"]
        )
        brain = self._brain_summary(config)
        max_cycles = min(int(auto_config.get("max_cycles", 1)), int(brain["max_cycles"]))

        results = run_autonomous(project, config, issues, max_cycles)

        output = write_json(
            project,
            "autonomous",
            "latest.json",
            {
                "cycles": len(results),
                "results": [
                    {
                        "cycle_id": r.cycle_id,
                        "issue": r.issue,
                        "success": r.success,
                        "evidence_id": r.evidence.decision_id if r.evidence else None,
                        "error": r.error,
                    }
                    for r in results
                ],
            },
        )

        all_success = all(r.success for r in results)

        return RobotResult(
            ok=all_success,
            summary={
                "cycles_completed": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "tier": brain["tier"],
                "verification_depth": brain["verification_depth"],
            },
            output=output,
            metadata={"results": [self._cycle_to_dict(r) for r in results]},
        )

    def _run_oneshot(self, project: Path, config: dict, auto_config: dict) -> RobotResult:
        """Run single cycle for a specific issue."""
        issue = auto_config.get("issue", "autonomous maintenance")

        self.robot.config = AutonomousConfig(
            max_cycles=1,
            issue_queue=[issue],
        )

        result = self.robot.run_cycle(project, config, issue)

        output = write_json(
            project,
            "autonomous",
            "latest.json",
            {
                "cycle_id": result.cycle_id,
                "issue": result.issue,
                "success": result.success,
                "evidence_id": result.evidence.decision_id if result.evidence else None,
                "error": result.error,
            },
        )

        return RobotResult(
            ok=result.success,
            summary={
                "cycle_id": result.cycle_id,
                "success": result.success,
                "evidence": result.evidence.decision_id if result.evidence else None,
                "tier": self._brain_summary(config)["tier"],
            },
            output=output,
            metadata=self._cycle_to_dict(result),
        )

    @staticmethod
    def _normalize_issues(auto_config: dict) -> list[str]:
        """Merge singular issue + plural issues into one in-memory queue.

        Accepts the CLI singular key and a programmatic plural list;
        drops blanks, never raises.
        """
        if not isinstance(auto_config, dict):
            return []
        queue: list[str] = []
        raw_list = auto_config.get("issues")
        if isinstance(raw_list, list):
            queue.extend(s for s in (str(i).strip() for i in raw_list) if s)
        single = auto_config.get("issue")
        if isinstance(single, str) and single.strip():
            queue.append(single.strip())
        return queue

    @staticmethod
    def _queue_path(project: Path) -> Path:
        return cache_dir(project, "autonomous") / "queue.json"

    @staticmethod
    def _load_queue(queue_path: Path) -> list[str]:
        """Read persisted remainder; missing/malformed data means empty."""
        try:
            data = json.loads(queue_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        raw = data.get("issues") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            return []
        return [s for s in (str(i).strip() for i in raw) if s]

    @staticmethod
    def _save_queue(queue_path: Path, pending: list[str]) -> None:
        """Persist remaining queue. Never raises."""
        try:
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(json.dumps({"issues": list(pending)}), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def _clear_queue(queue_path: Path) -> None:
        """Remove queue state on normal completion. Never raises."""
        with contextlib.suppress(OSError):
            queue_path.unlink(missing_ok=True)

    def _run_continuous(self, project: Path, config: dict, auto_config: dict) -> RobotResult:
        """Bounded drain: one cycle per queued issue until empty or capped."""
        brain = self._brain_summary(config)
        max_cycles = min(int(auto_config.get("max_cycles", 10)), int(brain["max_cycles"]))
        try:
            interval = max(0, int(auto_config.get("interval_seconds", 300)))
        except (TypeError, ValueError):
            interval = 0
        queue_path = self._queue_path(project)

        pending = self._load_queue(queue_path)
        for issue in self._normalize_issues(auto_config):
            # Merge fresh input after the persisted remainder; first
            # occurrence wins so no valid persisted issue is ever dropped
            # and duplicates across both sources run only once.
            if issue not in pending:
                pending.append(issue)
        if not pending:
            self._clear_queue(queue_path)
            return RobotResult(
                ok=True,
                summary={"message": "No issues in queue for continuous mode"},
                output=write_json(project, "autonomous", "latest.json", {}),
            )

        self._save_queue(queue_path, pending)

        self.robot.config = AutonomousConfig(
            max_cycles=max_cycles,
            cycle_interval_seconds=interval,
            issue_queue=[],
        )

        self.scheduler = AutonomousScheduler(self.robot, project, config)

        results: list[CycleResult] = []
        completed = 0
        # run_cycle never raises (failures arrive as failed CycleResults),
        # so every issue is attempted and the loop always advances.
        while pending and completed < max_cycles:
            issue = pending.pop(0)
            result = self.robot.run_cycle(project, config, issue)
            results.append(result)
            completed += 1
            self._save_queue(queue_path, pending)
            if pending and completed < max_cycles and interval > 0:
                time.sleep(interval)

        if not pending:
            self._clear_queue(queue_path)

        output = write_json(
            project,
            "autonomous",
            "latest.json",
            {
                "mode": "continuous",
                "cycles": len(results),
                "results": [
                    {
                        "cycle_id": r.cycle_id,
                        "issue": r.issue,
                        "success": r.success,
                        "evidence_id": r.evidence.decision_id if r.evidence else None,
                        "error": r.error,
                    }
                    for r in results
                ],
                "remaining_issues": len(pending),
            },
        )

        all_success = all(r.success for r in results)

        return RobotResult(
            ok=all_success,
            summary={
                "mode": "continuous",
                "cycles_completed": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "remaining": len(pending),
                "tier": brain["tier"],
            },
            output=output,
            metadata={"results": [self._cycle_to_dict(r) for r in results]},
        )

    def _cycle_to_dict(self, cycle: CycleResult) -> dict:
        """Convert CycleResult to dict."""
        evidence_dict = None
        if cycle.evidence:
            evidence_dict = cycle.evidence.to_dict()
        return {
            "cycle_id": cycle.cycle_id,
            "issue": cycle.issue,
            "plan": cycle.plan,
            "critique_passed": cycle.critique_passed,
            "evidence": evidence_dict,
            "success": cycle.success,
            "error": cycle.error,
        }

    def plan(self, project: Path, config: dict) -> Plan:
        return Plan(
            name="autonomous",
            steps=[
                {"action": "sense", "target": "repository"},
                {"action": "plan", "target": "issue"},
                {"action": "critique", "target": "plan"},
                {"action": "execute", "target": "plan"},
                {"action": "verify", "target": "execution"},
                {"action": "learn", "target": "outcome"},
            ],
            risk_score=0.0,
        )

    def execute(self, project: Path, plan: Plan) -> RobotResult:
        return self.inspect(project, self._last_config or {})


# Register on import
register_robot(AutonomousMainRobot())


if __name__ == "__main__":
    import sys

    from robots.common import resolve_project

    project = resolve_project(sys.argv[1] if len(sys.argv) > 1 else ".")
    config, _ = load_config(project)

    robot = AutonomousMainRobot()
    result = robot.inspect(project, config)
    print(f"{'OK' if result.ok else 'FAILED'}: {result.summary}")
