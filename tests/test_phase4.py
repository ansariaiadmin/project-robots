"""Tests for Phase 4: verify-with-repair, ledger valuation, solve CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from robots.autonomous.loop import (
    AutonomousRobot,
    _run_target_suite,
    _syntax_check_files,
    _verification_passed,
    _written_files,
)
from robots.common import cache_dir
from robots.sovereignty import (
    diff_stats,
    estimate_cost_usd,
    estimate_energy_usd,
    estimate_value_usd,
    hardware_goal,
    record_event,
    set_test_db,
    status_summary,
)


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "phase4@example.invalid")
    _git(project, "config", "user.name", "Phase4")
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "__init__.py").touch()
    (project / "src" / "__init__.py").touch()
    (project / "src" / "billing.py").write_text(
        "def calculate_total(items):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += item[\"price\"]\n"
        "    return total\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_billing.py").write_text(
        "from src.billing import calculate_total\n"
        "def test_basic():\n"
        "    assert calculate_total([{'price': 10}, {'price': 20}]) == 30\n",
        encoding="utf-8",
    )
    (project / ".project-robots.json").write_text(
        json.dumps({
            "version": 1,
            "limits": {"contextTokenBudget": 4000},
            "sovereignty": {"rate_per_mtok": 0.0, "cpu_watts": 65.0, "energy_usd_per_kwh": 0.15},
        }),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class LedgerValuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "ledger.sqlite"
        set_test_db(self.db)

    def tearDown(self):
        set_test_db(None)
        self.temp.cleanup()

    def test_diff_stats_counts_added_removed(self):
        diff = "--- a/file.py\n+++ b/file.py\n-old\n+new\n"
        added, removed = diff_stats(diff)
        self.assertEqual(added, 1)  # "+new"
        self.assertEqual(removed, 1)  # "-old"

    def test_diff_stats_empty(self):
        self.assertEqual(diff_stats(""), (0, 0))

    def test_estimate_value_usd_lines(self):
        # 10 lines changed at $75/hr * 1.5 min/line = $18.75
        value = estimate_value_usd(lines_changed=10)
        self.assertAlmostEqual(value, 18.75, places=2)

    def test_estimate_value_usd_tests(self):
        # 2 tests fixed at $75/hr * 10 min/test = $25
        value = estimate_value_usd(tests_fixed=2)
        self.assertAlmostEqual(value, 25.0, places=2)

    def test_estimate_value_usd_combined(self):
        value = estimate_value_usd(lines_changed=4, tests_fixed=1)
        expected = (4 * 1.5 + 1 * 10) / 60 * 75
        self.assertAlmostEqual(value, expected, places=2)

    def test_estimate_energy_usd(self):
        # 60000ms at 65W and $0.15/kWh
        # 60s * 65W = 3900J = 3900/3600000 kWh * 0.15
        cost = estimate_energy_usd(60000, 65.0, 0.15)
        expected = 60000 / 3_600_000 * 65.0 / 1000 * 0.15
        self.assertAlmostEqual(cost, expected, places=6)

    def test_estimate_cost_usd_local(self):
        self.assertEqual(estimate_cost_usd(1000, 500, 0.0), 0.0)

    def test_hardware_goal_default(self):
        goal = hardware_goal()
        self.assertIn("item", goal)
        self.assertIn("cost_usd", goal)

    def test_status_summary(self):
        record_event("cycle", issue="t1", success=True, lines_changed=5, value_usd=1.5)
        result = status_summary(self.db)
        self.assertIn("events", result)
        self.assertIn("goal_item", result)
        self.assertIn("progress", result)
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["total_lines_changed"], 5)


class VerifyHelpersTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_syntax_check_valid(self):
        result = _syntax_check_files(self.project, ["src/billing.py"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["errors"], [])

    def test_syntax_check_invalid(self):
        (self.project / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
        result = _syntax_check_files(self.project, ["broken.py"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(len(result["errors"]), 1)

    def test_run_target_suite_passing(self):
        result = _run_target_suite(self.project, {"limits": {"commandTimeoutSeconds": 60}})
        # If pytest not installed, skipped=True
        if not result.get("skipped"):
            self.assertTrue(result.get("ok"))

    def test_verification_passed_with_suite_skipped(self):
        v = {"syntax": {"ok": True}, "suite": {"skipped": True}, "checks": {"passed": True}}
        self.assertTrue(_verification_passed(v))

    def test_verification_passed_fails_on_bad_syntax(self):
        v = {"syntax": {"ok": False}, "suite": {"skipped": True}, "checks": {"passed": True}}
        self.assertFalse(_verification_passed(v))

    def test_written_files_from_execution(self):
        exec_result = {
            "tool_results": [{
                "tool": "direct_edit",
                "result": {
                    "success": True,
                    "files_changed": 1,
                    "preview": "--- a/src/billing.py\n+++ b/src/billing.py\n-old\n+new\n",
                    "changes": [{"file": "src/billing.py"}],
                },
            }],
        }
        files = _written_files(exec_result, self.project)
        self.assertIn("src/billing.py", files)

    def test_repair_error_context_syntax(self):
        ctx = AutonomousRobot()._repair_error_context({"syntax": {"ok": False, "errors": [
            {"file": "f.py", "line": 3, "error": "unexpected indent"}
        ]}})
        self.assertIn("syntax f.py:3", ctx)
        self.assertIn("unexpected indent", ctx)

    def test_repair_error_context_suite(self):
        ctx = AutonomousRobot()._repair_error_context({
            "syntax": {"ok": True},
            "suite": {"ok": False, "failed": 2, "returncode": 1,
                      "tail": ["FAILED test_x", "AssertionError: 1 != 2"]},
        })
        self.assertIn("pytest failed", ctx)
        self.assertIn("FAILED", ctx)


class StatusCLITests(unittest.TestCase):
    def test_status_flag_works(self):
        import sys

        from project_robots import main
        old_argv = sys.argv
        try:
            with tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                sys.argv = ["project-robots", "--project", str(project), "status", "--sovereignty"]
                rc = main()
                self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv


class SolveCLITests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()
        # Use a test DB to avoid polluting production ledger
        self.db = Path(self.temp.name) / "test_ledger.sqlite"
        set_test_db(self.db)

    def tearDown(self):
        set_test_db(None)
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_solve_dry_run_creates_report(self):
        import sys

        from project_robots import main
        old_argv = sys.argv
        try:
            sys.argv = ["project-robots", "--project", str(self.project),
                        "solve", "--issue", "verify billing",
                        "--dry-run"]
            rc = main()
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv
        # Check solve report was written
        solve_dir = cache_dir(self.project, "solve")
        self.assertTrue((solve_dir / "latest.json").is_file())
        report = json.loads((solve_dir / "latest.json").read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["issue"], "verify billing")
        self.assertIn("summary", report)

    def test_solve_no_target_writes(self):
        import sys

        from project_robots import main
        old_argv = sys.argv
        try:
            sys.argv = ["project-robots", "--project", str(self.project),
                        "solve", "--issue", "verify billing",
                        "--dry-run"]
            main()
        finally:
            sys.argv = old_argv
        # Target should be unchanged
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=no"],
            cwd=self.project, capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(status, "")


if __name__ == "__main__":
    unittest.main()
