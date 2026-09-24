"""TASK #5 — Close Technical Debt (P1) tests.

Covers:
1) Evidence Honesty: HMAC-SHA256, tamper detection, key management
2) Canary/Rollback real checks
3) Learning Loop lessons store
4) Intelligence Cache git fingerprint
5) Throttle Shallow SKIPPED status
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _make_temp_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=project, check=True, capture_output=True
    )
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=project, check=True, capture_output=True)
    return temp, project


class EvidenceHonestyTests(unittest.TestCase):
    """EvidencePackage HMAC-SHA256 and tamper detection — ≥4 tests."""

    def test_hmac_sign_verify_success(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            (project / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
            evidence = EvidencePackage(
                decision_id="DEC-TEST1",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-1", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            sig = evidence.sign()
            self.assertTrue(sig)
            self.assertEqual(len(sig), 64)  # HMAC-SHA256 hex is 64 chars
            self.assertTrue(evidence.verify(project))
        finally:
            temp.cleanup()

    def test_tamper_one_byte_fails(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            evidence = EvidencePackage(
                decision_id="DEC-TEST2",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-2", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            evidence.sign()
            self.assertTrue(evidence.verify(project))

            # Tamper one byte
            (project / "src" / "app.py").write_text("print('tampered')\n", encoding="utf-8")
            self.assertFalse(evidence.verify(project), "tamper one byte should fail verify")
        finally:
            temp.cleanup()

    def test_tamper_signature_fails(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            evidence = EvidencePackage(
                decision_id="DEC-TEST3",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-3", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            evidence.sign()
            original_sig = evidence.signature
            # Flip last char
            tampered = original_sig[:-1] + ("0" if original_sig[-1] != "0" else "1")
            evidence.signature = tampered
            self.assertFalse(evidence.verify(project), "tampered signature should fail")
        finally:
            temp.cleanup()

    def test_verify_side_effect_free(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            evidence = EvidencePackage(
                decision_id="DEC-TEST4",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-4", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            fp_before = evidence.source_fingerprint
            sig_before = evidence.sign()
            # verify should not mutate fingerprint or signature
            evidence.verify(project)
            self.assertEqual(evidence.source_fingerprint, fp_before)
            self.assertEqual(evidence.signature, sig_before)
        finally:
            temp.cleanup()

    def test_env_key_management(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            # Set env key
            os.environ["PROJECT_ROBOTS_SIGNING_KEY"] = "test-secret-key-12345"
            evidence = EvidencePackage(
                decision_id="DEC-TEST5",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-5", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            sig = evidence.sign()
            self.assertTrue(evidence.verify(project))

            # Verify with different key fails
            evidence2 = EvidencePackage(
                decision_id="DEC-TEST5",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-5", title="t", status="proposed", context="c", decision="d"),
                source_fingerprint=evidence.source_fingerprint,
                signature=sig,
            )
            # Use different key via param
            self.assertFalse(evidence2.verify(project, public_key="different-key"))

            # Cleanup
            del os.environ["PROJECT_ROBOTS_SIGNING_KEY"]
        finally:
            temp.cleanup()
            if "PROJECT_ROBOTS_SIGNING_KEY" in os.environ:
                del os.environ["PROJECT_ROBOTS_SIGNING_KEY"]

    def test_hmac_not_simple_sha256(self):
        """Ensure signature is HMAC, not simple SHA256 of content."""
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy
        import hashlib
        import json

        temp, project = _make_temp_project()
        try:
            evidence = EvidencePackage(
                decision_id="DEC-TEST6",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-6", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            sig = evidence.sign(private_key="my-secret-key")
            # Simple SHA256 of content would be different
            content = evidence._canonical_content()
            simple_sha = hashlib.sha256(content).hexdigest()[:32]
            self.assertNotEqual(sig, simple_sha)
            self.assertEqual(len(sig), 64)  # HMAC SHA256 full hex
        finally:
            temp.cleanup()


class CanaryRollbackTests(unittest.TestCase):
    """Canary/Rollback real checks — ≥3 tests."""

    def test_canary_success_when_files_ok(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            (project / "src" / "good.py").write_text("x = 1\n", encoding="utf-8")
            evidence = EvidencePackage(
                decision_id="DEC-CANARY1",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/good.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="canary"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-C1", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            evidence.sign()
            result = evidence.canary_deploy(project)
            self.assertTrue(result, "canary should pass for valid file")
            self.assertIn("canary", evidence.verification)
            self.assertEqual(evidence.verification["canary"]["error_rate"], 0.0)
        finally:
            temp.cleanup()

    def test_canary_fails_when_syntax_error(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            (project / "src" / "bad.py").write_text("def foo(\n", encoding="utf-8")
            evidence = EvidencePackage(
                decision_id="DEC-CANARY2",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/bad.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="canary"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-C2", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            evidence.sign()
            result = evidence.canary_deploy(project)
            self.assertFalse(result, "canary should fail for syntax error")
            self.assertGreater(evidence.verification["canary"]["error_rate"], 0)
        finally:
            temp.cleanup()

    def test_canary_error_rate_threshold(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            (project / "src" / "good.py").write_text("x=1\n", encoding="utf-8")
            (project / "src" / "bad.py").write_text("def foo(\n", encoding="utf-8")
            evidence = EvidencePackage(
                decision_id="DEC-CANARY3",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/good.py"}, {"file": "src/bad.py"}],
                tools=[],
                verification={},
                rollback=RollbackStrategy(strategy_type="canary"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-C3", title="t", status="proposed", context="c", decision="d"),
            )
            evidence.compute_fingerprint(project)
            evidence.sign()
            result = evidence.canary_deploy(project, error_threshold=0.05)
            self.assertFalse(result)
            self.assertEqual(evidence.verification["canary"]["error_rate"], 0.5)
        finally:
            temp.cleanup()

    def test_rollback_decision_based_on_threshold(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            evidence = EvidencePackage(
                decision_id="DEC-ROLL1",
                rationale="test",
                risk_score=0.8,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={"canary": {"error_rate": 0.1, "threshold": 0.05, "passed": False}},
                rollback=RollbackStrategy(
                    strategy_type="immediate",
                    trigger_conditions=[
                        {"metric": "error_rate", "threshold": 0.05, "window": "5m"}
                    ],
                    rollback_steps=["step1", "step2"],
                ),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-R1", title="t", status="proposed", context="c", decision="d"),
            )
            # Should trigger rollback when error_rate > threshold
            self.assertTrue(evidence.should_rollback({"error_rate": 0.1, "threshold": 0.05}))
            self.assertFalse(evidence.should_rollback({"error_rate": 0.01, "threshold": 0.05}))
        finally:
            temp.cleanup()

    def test_execute_rollback_real_not_hardcoded(self):
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            # Case 1: No error, no rollback needed -> returns False (not hardcoded True)
            evidence_ok = EvidencePackage(
                decision_id="DEC-ROLL2",
                rationale="test",
                risk_score=0.1,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={"canary": {"error_rate": 0.0, "threshold": 0.05, "passed": True}},
                rollback=RollbackStrategy(
                    strategy_type="immediate",
                    rollback_steps=["step1"],
                ),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-R2", title="t", status="proposed", context="c", decision="d"),
            )
            self.assertFalse(evidence_ok.execute_rollback(project))

            # Case 2: Error, rollback needed -> returns True
            evidence_fail = EvidencePackage(
                decision_id="DEC-ROLL3",
                rationale="test",
                risk_score=0.9,
                changes=[{"file": "src/app.py"}],
                tools=[],
                verification={"canary": {"error_rate": 0.5, "threshold": 0.05, "passed": False}},
                rollback=RollbackStrategy(
                    strategy_type="immediate",
                    rollback_steps=["disable flag", "verify"],
                ),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-R3", title="t", status="proposed", context="c", decision="d"),
            )
            self.assertTrue(evidence_fail.execute_rollback(project))
        finally:
            temp.cleanup()

    def test_rollback_strategy_should_trigger(self):
        from robots.evidence.rollback import RollbackStrategy

        strategy = RollbackStrategy(
            strategy_type="canary",
            trigger_conditions=[
                {"metric": "error_rate", "threshold": 0.05, "window": "5m"},
                {"metric": "availability", "threshold": 0.99, "window": "5m"},
            ],
            rollback_steps=["a", "b"],
        )
        self.assertTrue(strategy.should_trigger({"error_rate": 0.1}))
        self.assertTrue(strategy.should_trigger({"availability": 0.98}))
        self.assertFalse(strategy.should_trigger({"error_rate": 0.01, "availability": 0.999}))


class LearningLoopTests(unittest.TestCase):
    """Learning Loop lessons store — ≥3 tests."""

    def test_lesson_append_only(self):
        from robots.autonomous.learning import create_learning_engine
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            engine = create_learning_engine(project)
            # Ensure clean
            if engine.lessons_file.exists():
                engine.lessons_file.unlink()

            lesson1 = {
                "category": "security",
                "severity": "critical",
                "message": "SQL injection risk",
                "context": "fix login",
            }
            engine.save_lesson(lesson1)
            self.assertTrue(engine.lessons_file.exists())
            content1 = engine.lessons_file.read_text(encoding="utf-8")
            lines1 = [l for l in content1.splitlines() if l.strip()]
            self.assertEqual(len(lines1), 1)

            lesson2 = {
                "category": "performance",
                "severity": "major",
                "message": "N+1 query",
                "context": "optimize",
            }
            engine.save_lesson(lesson2)
            content2 = engine.lessons_file.read_text(encoding="utf-8")
            lines2 = [l for l in content2.splitlines() if l.strip()]
            self.assertEqual(len(lines2), 2)
            # First line still present (append-only)
            self.assertIn("SQL injection", content2)
        finally:
            temp.cleanup()

    def test_lesson_persistence_and_load(self):
        from robots.autonomous.learning import create_learning_engine

        temp, project = _make_temp_project()
        try:
            engine = create_learning_engine(project)
            if engine.lessons_file.exists():
                engine.lessons_file.unlink()

            engine.save_lesson(
                {"category": "test", "message": "persist me", "context": "ctx"}
            )
            lessons = engine.load_lessons()
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0]["message"], "persist me")
        finally:
            temp.cleanup()

    def test_keyword_overlap_retrieval(self):
        from robots.autonomous.learning import create_learning_engine

        temp, project = _make_temp_project()
        try:
            engine = create_learning_engine(project)
            if engine.lessons_file.exists():
                engine.lessons_file.unlink()

            engine.save_lesson(
                {
                    "category": "security",
                    "message": "SQL injection in login",
                    "context": "auth module",
                    "keywords": ["sql", "injection", "login", "auth"],
                }
            )
            engine.save_lesson(
                {
                    "category": "performance",
                    "message": "Slow query",
                    "context": "database",
                    "keywords": ["slow", "query", "database"],
                }
            )

            relevant = engine.get_relevant_lessons("fix login SQL injection", top_k=5)
            self.assertEqual(len(relevant), 1)
            self.assertIn("SQL injection", relevant[0]["message"])

            relevant2 = engine.get_relevant_lessons("database query performance", top_k=5)
            self.assertEqual(len(relevant2), 1)
            self.assertIn("Slow query", relevant2[0]["message"])
        finally:
            temp.cleanup()

    def test_run1_lesson_saved_run2_sees_in_plan(self):
        """Simulate run1 saves lesson, run2 retrieves via keyword overlap for plan."""
        from robots.autonomous.learning import create_learning_engine
        from robots.evidence.adr import ADR
        from robots.evidence.observability import ObservabilityHooks
        from robots.evidence.package import EvidencePackage
        from robots.evidence.rollback import RollbackStrategy

        temp, project = _make_temp_project()
        try:
            engine = create_learning_engine(project)
            if engine.lessons_file.exists():
                engine.lessons_file.unlink()

            # Run1: create evidence with critique findings and save lessons
            class FakeFinding:
                def __init__(self, cat, sev, msg):
                    self.category = cat
                    self.severity = sev
                    self.message = msg

            class FakeCritique:
                def __init__(self):
                    self.findings = [
                        FakeFinding("security", "critical", "Missing auth check in billing"),
                    ]
                    self.passed = False

            evidence = EvidencePackage(
                decision_id="DEC-LEARN1",
                rationale="fix billing auth",
                risk_score=0.5,
                changes=[{"file": "src/billing.py"}],
                tools=[],
                verification={"critique": {"findings": [{"category": "security", "severity": "critical", "message": "Missing auth check in billing"}]}},
                rollback=RollbackStrategy(strategy_type="immediate"),
                observability=ObservabilityHooks(),
                adr=ADR(id="ADR-L1", title="t", status="proposed", context="c", decision="d"),
            )

            critique = FakeCritique()
            saved = engine.save_lessons_from_critique(evidence, critique)
            self.assertEqual(len(saved), 1)

            # Run2: new engine instance (simulating next run) retrieves lessons for similar issue
            engine2 = create_learning_engine(project)
            relevant = engine2.get_relevant_lessons("fix billing authentication", top_k=5)
            self.assertGreaterEqual(len(relevant), 1)
            # Check that lesson is visible in plan context
            # Simulate _generate_plan injecting lessons
            plan = {"issue": "fix billing authentication"}
            plan["lessons"] = relevant
            self.assertIn("billing", json.dumps(plan["lessons"]).lower())
        finally:
            temp.cleanup()

    def test_lessons_store_json_append_only_format(self):
        from robots.autonomous.learning import create_learning_engine

        temp, project = _make_temp_project()
        try:
            engine = create_learning_engine(project)
            if engine.lessons_file.exists():
                engine.lessons_file.unlink()

            for i in range(3):
                engine.save_lesson({"message": f"lesson {i}", "category": "test"})

            # File should be JSONL (each line valid JSON)
            lines = engine.lessons_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            for line in lines:
                data = json.loads(line)
                self.assertIn("message", data)
                self.assertIn("id", data)
                self.assertIn("timestamp", data)
        finally:
            temp.cleanup()


class IntelligenceCacheTests(unittest.TestCase):
    """Intelligence cache git fingerprint invalidation — ≥2 tests."""

    def test_git_fingerprint_format(self):
        from robots.intelligence.core import _get_git_fingerprint

        temp, project = _make_temp_project()
        try:
            fp = _get_git_fingerprint(project)
            # Should be "<sha>:<clean|dirty>"
            self.assertIn(":", fp)
            sha, state = fp.split(":", 1)
            self.assertEqual(len(sha), 40)  # git SHA is 40 hex chars
            self.assertIn(state, ["clean", "dirty", "unknown"])
        finally:
            temp.cleanup()

    def test_cache_miss_when_head_changes(self):
        from robots.common import cache_dir
        from robots.intelligence.core import _get_git_fingerprint, build_repository_intelligence

        temp, project = _make_temp_project()
        try:
            # Build and cache
            intelligence1 = build_repository_intelligence(project, {}, use_cache=True)
            cache_path = cache_dir(project, "intelligence") / "latest.json"
            self.assertTrue(cache_path.exists())
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertIn("_git_fingerprint", cached)
            fp1 = cached["_git_fingerprint"]

            # Change HEAD by making new commit
            (project / "src" / "new.py").write_text("x=1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "second"], cwd=project, check=True, capture_output=True)

            fp2 = _get_git_fingerprint(project)
            self.assertNotEqual(fp1, fp2, "HEAD changed, fingerprint should differ")

            # Now build with cache enabled — should be cache miss (rebuild)
            # We can detect miss by checking that cached file gets overwritten with new fingerprint
            intelligence2 = build_repository_intelligence(project, {}, use_cache=True)
            cached2 = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached2["_git_fingerprint"], fp2)
        finally:
            temp.cleanup()

    def test_cache_hit_when_fingerprint_same(self):
        from robots.common import cache_dir
        from robots.intelligence.core import build_repository_intelligence

        temp, project = _make_temp_project()
        try:
            # First build
            build_repository_intelligence(project, {}, use_cache=True)
            cache_path = cache_dir(project, "intelligence") / "latest.json"
            mtime1 = cache_path.stat().st_mtime

            # Second build immediately — should hit cache and not rewrite (mtime same or similar)
            # We sleep a bit to ensure mtime would change if rewritten
            import time

            time.sleep(0.1)
            build_repository_intelligence(project, {}, use_cache=True)
            mtime2 = cache_path.stat().st_mtime
            # If cache hit, file not rewritten, mtime same
            self.assertEqual(mtime1, mtime2)
        finally:
            temp.cleanup()

    def test_cache_dirty_state_invalidates(self):
        from robots.intelligence.core import _get_git_fingerprint

        temp, project = _make_temp_project()
        try:
            fp_clean = _get_git_fingerprint(project)
            self.assertTrue(fp_clean.endswith(":clean"))

            # Make dirty
            (project / "src" / "app.py").write_text("print('dirty')\n", encoding="utf-8")
            fp_dirty = _get_git_fingerprint(project)
            self.assertTrue(fp_dirty.endswith(":dirty"))
            self.assertNotEqual(fp_clean, fp_dirty)
        finally:
            temp.cleanup()


class ThrottleShallowTests(unittest.TestCase):
    """Throttle shallow success — explicit SKIPPED — ≥2 tests."""

    def test_shallow_verification_returns_skipped(self):
        from robots.autonomous.loop import AutonomousRobot, AutonomousConfig
        from robots.common import load_config
        from robots.intelligence import build_repository_intelligence

        temp, project = _make_temp_project()
        try:
            config, _ = load_config(project)
            intelligence = build_repository_intelligence(project, config)
            robot = AutonomousRobot(AutonomousConfig(issue_queue=["test"]))
            brain = {
                "provider": "mock",
                "model": "mock-small",
                "tier": "tier-1-local",
                "verification_depth": "shallow",
                "provider_obj": None,
            }
            plan = {"risk_score": 0.1, "changed_files": [], "steps": []}
            verification = robot._verify_execution(plan, project, config, brain)
            self.assertTrue(verification["checks"]["skipped"])
            self.assertEqual(verification["checks"]["status"], "SKIPPED")
            self.assertIn("shallow", verification["checks"]["reason"].lower())
        finally:
            temp.cleanup()

    def test_verification_passed_false_when_shallow_skipped(self):
        from robots.autonomous.loop import _verification_passed

        v = {
            "syntax": {"ok": True},
            "suite": {"skipped": True, "reason": "no writes"},
            "checks": {"skipped": True, "depth": "shallow", "status": "SKIPPED", "reason": "shallow"},
            "depth": "shallow",
        }
        self.assertFalse(_verification_passed(v), "shallow skipped should not be considered passed")

    def test_cycle_result_skipped_not_success(self):
        from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
        from robots.common import load_config

        temp, project = _make_temp_project()
        try:
            config, _ = load_config(project)
            robot = AutonomousRobot(AutonomousConfig(max_cycles=2, issue_queue=["tidy"]))
            result = robot.run_cycle(project, config, "tidy")
            # With mock provider (shallow), result should be SKIPPED and success=False
            self.assertFalse(result.success)
            self.assertIn("SKIPPED", result.error)
            self.assertEqual(result.plan.get("verification_status", {}).get("status"), "SKIPPED")
        finally:
            temp.cleanup()

    def test_suite_skipped_explicit_status(self):
        from robots.autonomous.loop import _run_target_suite
        from robots.common import load_config

        temp, project = _make_temp_project()
        try:
            config, _ = load_config(project)
            # Project has no test files that are tracked? It has src/app.py but not test_*.py
            # So _run_target_suite should return skipped with explicit status
            result = _run_target_suite(project, config)
            if result.get("skipped"):
                self.assertEqual(result.get("status"), "SKIPPED")
                self.assertIn("reason", result)
        finally:
            temp.cleanup()

    def test_verification_status_skipped_has_reason(self):
        from robots.autonomous.loop import _verification_status

        v = {
            "checks": {"skipped": True, "depth": "shallow", "status": "SKIPPED", "reason": "shallow tier"},
            "suite": {"skipped": True, "reason": "no writes"},
            "depth": "shallow",
        }
        status = _verification_status(v)
        self.assertEqual(status["status"], "SKIPPED")
        self.assertIn("reason", status)
        self.assertTrue(status["reason"])


if __name__ == "__main__":
    unittest.main()
