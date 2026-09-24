"""P0 milestone regression tests: critique handoff, evidence load, rag-query single path."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
from robots.common import cache_dir
from robots.evidence.package import EvidencePackage, EvidenceStore
from robots.reflexion.robot import CritiqueRobot


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "p0@example.invalid")
    _git(project, "config", "user.name", "P0 Tests")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class CritiqueHandoffTests(unittest.TestCase):
    def test_direct_critiques_current_plan_not_stale_file(self):
        temp, project = _make_project()
        try:
            from robots.common import load_config
            from robots.intelligence import build_repository_intelligence

            config, _ = load_config(project)
            intelligence = build_repository_intelligence(project, config)  # noqa: F841
            # Stale file contains a benign plan; in-memory plan masks symptoms.
            stale = {"issue": "stale", "steps": [{"action": "refactor", "target": "x"}],
                     "changes": []}
            (cache_dir(project, "checks") / "latest.json").write_text(
                json.dumps(stale), encoding="utf-8")
            current = {"issue": "live issue",
                       "steps": [{"action": "catch and suppress", "target": "hotspot"}],
                       "changes": []}
            robot = CritiqueRobot()
            critique, refined, _ = robot.critique_plan_direct(
                current, intelligence, "live issue", project, config)
            self.assertTrue(
                any(f.severity == "critical" for f in critique.findings),
                "symptom-masking plan must yield a critical finding",
            )
            self.assertIsNotNone(refined)
        finally:
            temp.cleanup()

    def test_critical_blocks_writes_in_cycle(self):
        temp, project = _make_project()
        try:
            from robots.common import load_config

            config, _ = load_config(project)
            target = project / "src" / "app.py"
            before = target.read_text(encoding="utf-8")
            robot = AutonomousRobot(AutonomousConfig(
                issue_queue=["critical block test"], risk_threshold=0.3))
            critical_plan = {
                "issue": "critical block test",
                "rationale": "test",
                "steps": [{"action": "catch and ignore errors", "target": "x"}],
                "changes": [{"file": "src/app.py", "path": "src/app.py",
                             "type": "fix", "description": "patch"}],
                "risk_score": {"overall": 0.0},
            }
            robot._generate_plan = lambda *a, **k: dict(critical_plan)  # type: ignore[method-assign]
            result = robot.run_cycle(project, config, "critical block test")
            # TASK #5: Critical blocks writes, but shallow verification may also cause SKIPPED
            # The important assertion is that writes are blocked, not success=True
            self.assertFalse(result.critique_passed)
            self.assertTrue(
                result.plan.get("execution", {}).get("blocked_by_critique", False),
                "critical critique must set blocked_by_critique",
            )
            self.assertEqual(target.read_text(encoding="utf-8"), before,
                             "blocked cycle must not modify target files")
        finally:
            temp.cleanup()

    def test_standalone_inspect_still_file_backed(self):
        temp, project = _make_project()
        try:
            from robots.common import load_config

            config, _ = load_config(project)
            plan = {"issue": "standalone", "steps": [], "changes": []}
            (cache_dir(project, "checks") / "latest.json").write_text(
                json.dumps(plan), encoding="utf-8")
            robot = CritiqueRobot()
            result = robot.inspect(project, config)
            self.assertTrue((cache_dir(project, "critique") / "latest.json").exists())
            self.assertIn("passed", result.summary)
        finally:
            temp.cleanup()


class EvidenceStoreTests(unittest.TestCase):
    def test_missing_returns_none(self):
        temp, project = _make_project()
        try:
            store = EvidenceStore(project)
            self.assertIsNone(store.load("DEC-DOESNOTEXIST"))
        finally:
            temp.cleanup()

    def test_save_load_roundtrip(self):
        temp, project = _make_project()
        try:
            store = EvidenceStore(project)
            pkg = EvidencePackage(
                decision_id="DEC-ROUNDTRIP",
                rationale="r",
                risk_score=0.1,
                changes=[],
                tools=[],
                verification={},
                rollback=__import__(
                    "robots.evidence.rollback", fromlist=["RollbackStrategy"]
                ).RollbackStrategy(strategy_type="immediate"),
            )
            store.save(pkg)
            loaded = store.load("DEC-ROUNDTRIP")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.decision_id, "DEC-ROUNDTRIP")
            self.assertEqual(loaded.rationale, "r")
        finally:
            temp.cleanup()

    def test_legacy_fallback(self):
        temp, project = _make_project()
        try:
            store = EvidenceStore(project)
            legacy = project / ".project-robots" / "evidence"
            legacy.mkdir(parents=True, exist_ok=True)
            pkg = EvidencePackage(
                decision_id="DEC-LEGACY",
                rationale="legacy",
                risk_score=0.2,
                changes=[],
                tools=[],
                verification={},
                rollback=__import__(
                    "robots.evidence.rollback", fromlist=["RollbackStrategy"]
                ).RollbackStrategy(strategy_type="immediate"),
            )
            (legacy / "DEC-LEGACY.json").write_text(
                json.dumps(pkg.to_dict()), encoding="utf-8")
            loaded = store.load("DEC-LEGACY")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.rationale, "legacy")
        finally:
            temp.cleanup()

    def test_corrupt_file_returns_none(self):
        temp, project = _make_project()
        try:
            store = EvidenceStore(project)
            (store.evidence_dir / "DEC-BAD.json").write_text(
                "{not valid json", encoding="utf-8")
            self.assertIsNone(store.load("DEC-BAD"))
        finally:
            temp.cleanup()


class RagQueryPathTests(unittest.TestCase):
    def test_single_parser_and_dispatch(self):
        from project_robots import parser

        cli = parser()
        args = cli.parse_args(["--project", ".", "rag-query", "--task", "t", "--k", "5"])
        self.assertEqual(args.command, "rag-query")
        self.assertEqual(args.task, "t")
        self.assertEqual(args.k, 5)
        src = Path("project_robots.py").read_text(encoding="utf-8")
        # Exactly one canonical dispatch path.
        self.assertEqual(src.count('args.command == "rag-query"'), 1)
        self.assertEqual(src.count('add_parser("rag-query"'), 1)


if __name__ == "__main__":
    unittest.main()
