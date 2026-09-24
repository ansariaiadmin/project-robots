"""Tests for autonomous write guardrails and central-state redirection."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.autonomous.guard import (
    build_allowlist,
    cleanup_stray_target_state,
    evaluate_write_policy,
    guarded_write_text,
    is_path_allowed,
    preview_unified_diff,
)
from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
from robots.common import cache_dir
from robots.evidence.adr import ADR, ADRRegistry
from robots.evidence.package import EvidencePackage, EvidenceStore


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "guard@example.invalid")
    _git(project, "config", "user.name", "Guard Tests")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class PolicyTests(unittest.TestCase):
    def test_low_risk_allows(self):
        policy = evaluate_write_policy(risk_overall=0.1, risk_threshold=0.3)
        self.assertEqual(policy.decision, "allow")
        self.assertFalse(policy.dry_run)

    def test_mid_risk_dry_run(self):
        policy = evaluate_write_policy(risk_overall=0.4, risk_threshold=0.3)
        self.assertEqual(policy.decision, "dry-run")
        self.assertTrue(policy.dry_run)

    def test_high_risk_denies(self):
        policy = evaluate_write_policy(risk_overall=0.9, risk_threshold=0.3)
        self.assertEqual(policy.decision, "deny")

    def test_invalid_risk_denies(self):
        policy = evaluate_write_policy(risk_overall="nonsense", risk_threshold=0.3)
        self.assertEqual(policy.decision, "deny")

    def test_operator_dry_run_forces_preview(self):
        policy = evaluate_write_policy(
            risk_overall=0.05, risk_threshold=0.3, dry_run_requested=True
        )
        self.assertEqual(policy.decision, "dry-run")


class AllowlistTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_existing_file_allowlisted(self):
        allowlist = build_allowlist(self.project, ["src/app.py"])
        self.assertIn("src/app.py", allowlist)

    def test_missing_glob_escape_excluded(self):
        allowlist = build_allowlist(
            self.project, ["nope.py", "*.py", "../escape.py", "src/../src/app.py"]
        )
        self.assertNotIn("nope.py", allowlist)
        self.assertNotIn("*.py", allowlist)
        self.assertNotIn("../escape.py", allowlist)
        # Non-canonical but in-project paths are normalized, not allowlisted raw.
        self.assertIn("src/app.py", allowlist)

    def test_is_path_allowed(self):
        policy = evaluate_write_policy(
            risk_overall=0.0, candidate_paths=["src/app.py"], project=self.project
        )
        allowed, _ = is_path_allowed(self.project, "src/app.py", policy)
        self.assertTrue(allowed)
        allowed, reason = is_path_allowed(self.project, "src/other.py", policy)
        self.assertFalse(allowed)
        self.assertIn("allowlisted", reason)
        allowed, reason = is_path_allowed(self.project, "../escape.py", policy)
        self.assertFalse(allowed)

    def test_guarded_write_allow(self):
        policy = evaluate_write_policy(
            risk_overall=0.0, candidate_paths=["src/app.py"], project=self.project
        )
        result = guarded_write_text(self.project, "src/app.py", "print('new')\n", policy)
        self.assertTrue(result["written"])
        self.assertIn("print", result["preview"])
        self.assertEqual((self.project / "src" / "app.py").read_text(), "print('new')\n")

    def test_guarded_write_dry_run_writes_nothing(self):
        policy = evaluate_write_policy(
            risk_overall=0.4, candidate_paths=["src/app.py"], project=self.project
        )
        result = guarded_write_text(self.project, "src/app.py", "print('new')\n", policy)
        self.assertFalse(result["written"])
        self.assertNotEqual(result["preview"], "")
        self.assertEqual((self.project / "src" / "app.py").read_text(), "print('ok')\n")

    def test_guarded_write_deny(self):
        policy = evaluate_write_policy(risk_overall=0.9, project=self.project)
        result = guarded_write_text(self.project, "src/app.py", "print('new')\n", policy)
        self.assertFalse(result["written"])
        self.assertEqual((self.project / "src" / "app.py").read_text(), "print('ok')\n")

    def test_preview_diff(self):
        preview = preview_unified_diff("a\n", "b\n", "f.py")
        self.assertIn("--- a/f.py", preview)
        self.assertIn("+++ b/f.py", preview)


class CentralStateTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_evidence_store_central(self):
        store = EvidenceStore(self.project)
        self.assertFalse(str(store.evidence_dir).startswith(str(self.project)))
        from robots.evidence.package import create_evidence_package

        evidence = create_evidence_package(
            {"rationale": "r", "changes": [], "risk_score": {"overall": 0.0}},
            self.project, {}, [],
        )
        assert isinstance(evidence, EvidencePackage)
        path = store.save(evidence)
        self.assertTrue(path.is_file())
        self.assertFalse((self.project / ".project-robots").exists())
        self.assertIn(evidence.decision_id, store.list())

    def test_adr_registry_central(self):
        registry = ADRRegistry(self.project)
        self.assertFalse(str(registry.adr_dir).startswith(str(self.project)))
        adr = ADR(id="ADR-1", title="t", status="proposed", context="c", decision="d")
        path = registry.add(adr)
        self.assertTrue(path.is_file())
        self.assertFalse((self.project / ".project-robots").exists())
        self.assertIsNotNone(registry.get("ADR-1"))

    def test_learning_engine_central(self):
        from robots.autonomous.learning import LearningEngine

        engine = LearningEngine(self.project)
        self.assertFalse(str(engine.learning_dir).startswith(str(self.project)))
        engine.record_tool_effectiveness("ast_rewrite", True, 1.0)
        self.assertTrue(engine.state_file.is_file())
        self.assertFalse((self.project / ".project-robots").exists())

    def test_cleanup_migrates_stray_state(self):
        stray = self.project / ".project-robots" / "evidence"
        stray.mkdir(parents=True)
        (stray / "DEC-1.json").write_text("{}", encoding="utf-8")
        (self.project / ".project-robots" / "notes.txt").write_text("keep", encoding="utf-8")
        report = cleanup_stray_target_state(self.project)
        self.assertIn("evidence/DEC-1.json", report["moved"])
        central = cache_dir(self.project, "evidence") / "DEC-1.json"
        self.assertTrue(central.is_file())
        # Unknown files are left alone; stray dir survives because of them.
        self.assertFalse(report["removed"])
        self.assertTrue((self.project / ".project-robots" / "notes.txt").is_file())


class LoopGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_generate_plan_falls_back_on_brain_failure(self):
        from robots.brain.provider import BaseProvider
        from robots.common import load_config
        from robots.intelligence import build_repository_intelligence

        class FailProvider(BaseProvider):
            kind = "mock"

            def generate(self, prompt, options=None):
                raise RuntimeError("boom")

            def probe(self):
                raise RuntimeError("boom")

        config, _ = load_config(self.project)
        intelligence = build_repository_intelligence(self.project, config)
        robot = AutonomousRobot(AutonomousConfig(issue_queue=["fix"]))
        brain = {
            "provider": "mock", "model": "x", "tier": "tier-1-local",
            "budget": 4000, "retrieval_k": 8, "verification_depth": "shallow",
            "write_permission": "supervised", "provider_obj": FailProvider("", "x"),
        }
        plan = robot._generate_plan("fix", intelligence, config, self.project, {}, brain)
        self.assertIn("fallback", plan.get("brain", {}))
        self.assertGreater(len(plan["steps"]), 0)

    def test_run_cycle_offline_no_target_writes(self):
        from robots.common import load_config

        config, _ = load_config(self.project)
        robot = AutonomousRobot(AutonomousConfig(max_cycles=2, issue_queue=["tidy"]))
        result = robot.run_cycle(self.project, config, "tidy")
        self.assertTrue(result.success)
        self.assertEqual(result.plan.get("brain", {}).get("provider"), "mock")
        self.assertFalse((self.project / ".project-robots").exists())
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"], cwd=self.project,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(status, "")

    def test_execute_plan_with_tools_no_crash_no_write(self):
        from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
        from robots.common import load_config
        from robots.tooling.selector import ToolRecommendation

        config, _ = load_config(self.project)
        robot = AutonomousRobot(AutonomousConfig(issue_queue=[]))
        plan = {
            "risk_score": {"overall": 0.0},
            "changes": [{"file": "src/app.py"}],
            "context_chunks": [],
        }
        tools = [
            ToolRecommendation(tool="ast_rewrite", reason="t", confidence=1.0,
                               config={"refactoring_type": "general"}),
            ToolRecommendation(tool="semantic_patch", reason="t", confidence=1.0,
                               config={"pattern": "print", "replacement": "print",
                                       "file_pattern": "*.py"}),
        ]
        brain = {"write_permission": "supervised", "tier": "tier-1-local"}
        result = robot._execute_plan(plan, tools, self.project, config, brain)
        self.assertIn("policy", result)
        self.assertEqual(len(result["tool_results"]), 2)
        for entry in result["tool_results"]:
            self.assertIsInstance(entry["result"], dict)
        self.assertEqual((self.project / "src" / "app.py").read_text(), "print('ok')\n")

    def test_issue_singular_respected(self):
        from robots.autonomous.robot import AutonomousMainRobot
        from robots.common import load_config

        config, _ = load_config(self.project)
        config["autonomous"] = {"mode": "default", "issue": "singular issue", "max_cycles": 2}
        robot = AutonomousMainRobot()
        result = robot.inspect(self.project, config)
        self.assertTrue(result.ok)
        issues = [r["issue"] for r in result.metadata["results"]]
        self.assertEqual(issues, ["singular issue"])


if __name__ == "__main__":
    unittest.main()
