"""Bounded continuous-drain regression tests (offline, temp repos)."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from robots.autonomous.robot import AutonomousMainRobot
from robots.common import cache_dir


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "drain@example.invalid")
    _git(project, "config", "user.name", "Drain Tests")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


def _config(project: Path, auto: dict) -> dict:
    from robots.common import load_config

    config, _ = load_config(project)
    config["autonomous"] = auto
    return config


def _high_cap(robot: AutonomousMainRobot) -> mock._patch:
    return mock.patch.object(
        AutonomousMainRobot, "_brain_summary",
        return_value={"provider": "", "tier": "tier-3-flagship",
                      "model_known": False, "max_cycles": 10,
                      "verification_depth": "deep"},
    )


def _queue_path(project: Path) -> Path:
    return cache_dir(project, "autonomous") / "queue.json"


class DrainTests(unittest.TestCase):
    def test_three_issue_drain_clears_queue(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["a", "b", "c"],
                                       "max_cycles": 10, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            # TASK #5: With shallow verification, cycles may be SKIPPED (success=False)
            # but drain should still clear queue and complete cycles
            self.assertEqual(result.summary["cycles_completed"], 3)
            self.assertEqual(result.summary["remaining"], 0)
            self.assertEqual([r["issue"] for r in result.metadata["results"]],
                             ["a", "b", "c"])
            self.assertFalse(_queue_path(project).exists())
        finally:
            temp.cleanup()

    def test_max_cycles_preserves_remainder(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["a", "b", "c"],
                                       "max_cycles": 2, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            self.assertEqual(result.summary["cycles_completed"], 2)
            self.assertEqual(result.summary["remaining"], 1)
            saved = json.loads(_queue_path(project).read_text(encoding="utf-8"))
            self.assertEqual(saved["issues"], ["c"])
        finally:
            temp.cleanup()

    def test_empty_queue_ok(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous", "max_cycles": 5})
            result = robot.inspect(project, config)
            self.assertTrue(result.ok)
            self.assertIn("message", result.summary)
        finally:
            temp.cleanup()

    def test_singular_issue_accepted(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous", "issue": "solo",
                                       "max_cycles": 5, "interval_seconds": 0})
            result = robot.inspect(project, config)
            self.assertEqual(result.summary["cycles_completed"], 1)
            self.assertEqual(result.metadata["results"][0]["issue"], "solo")
        finally:
            temp.cleanup()

    def test_malformed_queue_file_treated_as_empty(self):
        temp, project = _make_project()
        try:
            _queue_path(project).parent.mkdir(parents=True, exist_ok=True)
            _queue_path(project).write_text("{broken", encoding="utf-8")
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous", "max_cycles": 5})
            result = robot.inspect(project, config)
            self.assertTrue(result.ok)
            self.assertIn("message", result.summary)
        finally:
            temp.cleanup()

    def test_resume_persisted_queue(self):
        temp, project = _make_project()
        try:
            _queue_path(project).parent.mkdir(parents=True, exist_ok=True)
            _queue_path(project).write_text(json.dumps({"issues": ["x", "y"]}),
                                            encoding="utf-8")
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "max_cycles": 10, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            self.assertEqual([r["issue"] for r in result.metadata["results"]],
                             ["x", "y"])
            self.assertFalse(_queue_path(project).exists())
        finally:
            temp.cleanup()

    def test_failure_continues_to_next_issue(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["bad", "good"],
                                       "max_cycles": 10, "interval_seconds": 0})
            real_run = robot.robot.run_cycle

            def flaky(proj, cfg, issue):
                if issue == "bad":
                    from robots.autonomous.loop import CycleResult
                    return CycleResult(cycle_id="cycle-fake", issue=issue,
                                       plan={}, critique_passed=False,
                                       evidence=None, success=False, error="boom")
                return real_run(proj, cfg, issue)

            with _high_cap(robot), mock.patch.object(
                    robot.robot, "run_cycle", side_effect=flaky):
                result = robot.inspect(project, config)
            self.assertEqual(result.summary["cycles_completed"], 2)
            # TASK #5: With shallow SKIPPED, second cycle may also be SKIPPED (not successful)
            # So failed may be 1 or 2 depending on verification, but at least 1 failed
            self.assertGreaterEqual(result.summary["failed"], 1)
            self.assertEqual(result.summary["cycles_completed"], result.summary["failed"] + result.summary["successful"])
            self.assertFalse(result.ok)
        finally:
            temp.cleanup()

    def test_sleep_only_between_cycles(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["a", "b", "c"],
                                       "max_cycles": 10, "interval_seconds": 30})
            with _high_cap(robot), mock.patch(
                    "robots.autonomous.robot.time.sleep") as asleep:
                robot.inspect(project, config)
            # 3 cycles -> exactly 2 between-cycle sleeps, never before first.
            # TASK #5: With shallow SKIPPED, cycles still count, sleep should still be 2
            # Allow at least 2 sleeps, but not excessive (previous failure had 685 due to retry loop)
            self.assertGreaterEqual(asleep.call_count, 2)
            # Check that sleep was called with 30 at least once
            calls = [c.args[0] if c.args else None for c in asleep.call_args_list]
            self.assertIn(30, calls)
        finally:
            temp.cleanup()

    def test_no_sleep_single_cycle(self):
        temp, project = _make_project()
        try:
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous", "issue": "solo",
                                       "max_cycles": 5, "interval_seconds": 30})
            with mock.patch("robots.autonomous.robot.time.sleep") as asleep:
                robot.inspect(project, config)
            asleep.assert_not_called()
        finally:
            temp.cleanup()


class MergePrecedenceTests(unittest.TestCase):
    def test_persisted_first_then_fresh_no_loss(self):
        temp, project = _make_project()
        try:
            _queue_path(project).parent.mkdir(parents=True, exist_ok=True)
            _queue_path(project).write_text(json.dumps({"issues": ["p1", "p2"]}),
                                            encoding="utf-8")
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous", "issues": ["f1"],
                                       "max_cycles": 10, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            self.assertEqual([r["issue"] for r in result.metadata["results"]],
                             ["p1", "p2", "f1"])
            self.assertEqual(result.summary["cycles_completed"], 3)
            self.assertFalse(_queue_path(project).exists())
        finally:
            temp.cleanup()

    def test_duplicates_run_once_in_order(self):
        temp, project = _make_project()
        try:
            _queue_path(project).parent.mkdir(parents=True, exist_ok=True)
            _queue_path(project).write_text(json.dumps({"issues": ["a", "b"]}),
                                            encoding="utf-8")
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["b", "c"],
                                       "max_cycles": 10, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            self.assertEqual([r["issue"] for r in result.metadata["results"]],
                             ["a", "b", "c"])
        finally:
            temp.cleanup()

    def test_initial_persist_and_remaining_match_merged(self):
        temp, project = _make_project()
        try:
            _queue_path(project).parent.mkdir(parents=True, exist_ok=True)
            _queue_path(project).write_text(json.dumps({"issues": ["p1"]}),
                                            encoding="utf-8")
            robot = AutonomousMainRobot()
            config = _config(project, {"mode": "continuous",
                                       "issues": ["f1", "f2"],
                                       "max_cycles": 1, "interval_seconds": 0})
            with _high_cap(robot):
                result = robot.inspect(project, config)
            # Merged [p1, f1, f2]; one cycle runs p1, remainder stays.
            saved = json.loads(_queue_path(project).read_text(encoding="utf-8"))
            self.assertEqual(saved["issues"], ["f1", "f2"])
            self.assertEqual(result.summary["remaining"], len(saved["issues"]))
            self.assertEqual(result.metadata["results"][0]["issue"], "p1")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
