"""Tests for Phase 3: live facts, handshake, throttling, redaction, ledger."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.autonomous.guard import is_in_scope
from robots.brain import (
    TIER_1_LOCAL,
    TIER_2_MID,
    TIER_3_FLAGSHIP,
    MockProvider,
    OllamaProvider,
    apply_live_facts,
    classify_model,
    is_secret_path,
    parse_model_facts,
    parse_param_count,
    probe_capabilities,
    redact_text,
    step_down_tier,
    tier_for_params,
    validate_handshake_text,
    verify_generation,
)
from robots.brain.resources import HostSnapshot
from robots.brain.resources import check as throttle_check
from robots.common import cache_dir, load_config
from robots.sovereignty import estimate_cost_usd, record_event, summary

LIVE_SHOW_SAMPLE = {
    "details": {
        "parent_model": "",
        "format": "gguf",
        "family": "qwen2",
        "parameter_size": "7.6B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {"general.parameter_count": 7615616512},
    "capabilities": ["completion", "tools", "insert"],
}
LIVE_TAGS_ENTRY = {
    "name": "qwen2.5-coder:7b",
    "details": {"parameter_size": "7.6B", "quantization_level": "Q4_K_M", "context_length": 32768},
}


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project(with_secret: bool = False) -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "phase3@example.invalid")
    _git(project, "config", "user.name", "Phase3")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    if with_secret:
        (project / ".env").write_text("OPENAI_API_KEY=sk-secret123\nPORT=8080\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class LiveFactsTests(unittest.TestCase):
    def test_parse_param_count(self):
        self.assertEqual(parse_param_count("7.6B"), 7600000000)
        self.assertEqual(parse_param_count(7615616512), 7615616512)
        self.assertIsNone(parse_param_count("Q4_K_M"))
        self.assertIsNone(parse_param_count(""))
        self.assertIsNone(parse_param_count(True))

    def test_parse_model_facts(self):
        facts = parse_model_facts(LIVE_TAGS_ENTRY, LIVE_SHOW_SAMPLE)
        self.assertEqual(facts["param_count"], 7615616512)
        self.assertEqual(facts["context_length"], 32768)
        self.assertEqual(facts["quantization"], "Q4_K_M")
        self.assertIn("tools", facts["capabilities"])

    def test_apply_live_facts_upgrades_context_and_tools(self):
        profile = classify_model("mystery-model")
        self.assertEqual(profile.tier, TIER_1_LOCAL)
        profile = apply_live_facts(profile, parse_model_facts(LIVE_TAGS_ENTRY, LIVE_SHOW_SAMPLE))
        self.assertEqual(profile.tier, TIER_1_LOCAL)  # 7.6B stays local tier
        self.assertEqual(profile.context_window, 32768)  # live value beats 4k matrix
        self.assertTrue(profile.tool_calling)  # verified, not guessed

    def test_tier_thresholds(self):
        self.assertEqual(tier_for_params(7_615_616_512), TIER_1_LOCAL)
        self.assertEqual(tier_for_params(20_000_000_000), TIER_2_MID)
        self.assertEqual(tier_for_params(70_000_000_000), TIER_3_FLAGSHIP)
        self.assertIsNone(tier_for_params(None))
        self.assertEqual(step_down_tier(TIER_3_FLAGSHIP), TIER_2_MID)
        self.assertEqual(step_down_tier(TIER_2_MID), TIER_1_LOCAL)
        self.assertEqual(step_down_tier(TIER_1_LOCAL), TIER_1_LOCAL)


class HandshakeTests(unittest.TestCase):
    def test_valid_exact(self):
        valid, number = validate_handshake_text('{"ok":true,"n":1}')
        self.assertTrue(valid)
        self.assertEqual(number, 1)

    def test_valid_fenced(self):
        valid, _ = validate_handshake_text('noise\n```json\n{"ok": true}\n```')
        self.assertTrue(valid)

    def test_invalid(self):
        self.assertFalse(validate_handshake_text('{"ok":false}')[0])
        self.assertFalse(validate_handshake_text("hello world")[0])
        self.assertFalse(validate_handshake_text("")[0])

    def test_mock_short_circuits(self):
        result = verify_generation(MockProvider("", "mock-small"), "mock-small")
        self.assertTrue(result["verified"])
        self.assertEqual(result["source"], "mock")

    def test_unreachable_does_not_raise(self):
        provider = OllamaProvider("http://127.0.0.1:1", "qwen2.5:7b", timeout=1)
        result = verify_generation(provider, "qwen2.5:7b", timeout=1)
        self.assertFalse(result["verified"])
        self.assertFalse(result["json_valid"])

    def test_probe_verify_mock_no_stepdown(self):
        profile = probe_capabilities(MockProvider("", "mock-small"), "mock-small", {}, verify=True)
        self.assertEqual(profile.tier, TIER_1_LOCAL)
        self.assertEqual(profile.probes["handshake"]["source"], "mock")


class ThrottleTests(unittest.TestCase):
    def test_overloaded_host(self):
        snap = HostSnapshot(cpu_count=12, load_1m=12.0, load_per_cpu=1.0,
                            mem_available_mb=9000, procs=200)
        decision = throttle_check({}, snap)
        self.assertTrue(decision.overloaded)
        self.assertEqual(decision.max_workers, 1)
        self.assertTrue(decision.force_shallow)
        self.assertIsNotNone(decision.num_predict_cap)

    def test_healthy_host(self):
        snap = HostSnapshot(cpu_count=12, load_1m=1.5, load_per_cpu=0.125,
                            mem_available_mb=9000, procs=200)
        decision = throttle_check({}, snap)
        self.assertFalse(decision.overloaded)
        self.assertGreater(decision.max_workers, 1)
        self.assertIsNone(decision.num_predict_cap)

    def test_low_memory_overloads(self):
        snap = HostSnapshot(cpu_count=12, load_1m=1.0, load_per_cpu=0.08,
                            mem_available_mb=100, procs=200)
        decision = throttle_check({}, snap)
        self.assertTrue(decision.overloaded)

    def test_reserve_cores_config(self):
        snap = HostSnapshot(cpu_count=4, load_1m=0.1, load_per_cpu=0.025,
                            mem_available_mb=9000, procs=50)
        decision = throttle_check({"throttling": {"reserve_cores": 3}}, snap)
        self.assertEqual(decision.max_workers, 1)


class RedactTests(unittest.TestCase):
    def test_secret_paths(self):
        self.assertTrue(is_secret_path(".env"))
        self.assertTrue(is_secret_path(".env.local"))
        self.assertTrue(is_secret_path("config/.env"))
        self.assertTrue(is_secret_path("id_rsa"))
        self.assertTrue(is_secret_path("deploy/key.pem"))
        self.assertTrue(is_secret_path("credentials.json"))
        self.assertFalse(is_secret_path("src/app.py"))
        self.assertFalse(is_secret_path("docs/guide.md"))

    def test_redact_env_assignment(self):
        redacted, count = redact_text("OPENAI_API_KEY=sk-secret123\nPORT=8080\n")
        self.assertGreater(count, 0)
        self.assertNotIn("sk-secret123", redacted)
        self.assertIn("PORT=8080", redacted)

    def test_redact_pem_and_tokens(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nABC\n-----END RSA PRIVATE KEY-----\n"
        redacted, count = redact_text(text)
        self.assertGreater(count, 0)
        self.assertNotIn("ABC", redacted)
        redacted, _ = redact_text("key=ghp_abcdef1234567890")
        self.assertNotIn("ghp_abcdef", redacted)

    def test_scope_gate(self):
        temp = tempfile.TemporaryDirectory()
        project = Path(temp.name)
        (project / "inside.txt").write_text("x", encoding="utf-8")
        try:
            self.assertTrue(is_in_scope(project, project / "inside.txt"))
            self.assertFalse(is_in_scope(project, "/etc/hostname"))
            self.assertFalse(is_in_scope(project, project / ".." / "escape.txt"))
        finally:
            temp.cleanup()


class IndexRedactionTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project(with_secret=True)

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_secret_files_skipped(self):
        from robots.rag.store import build_index, load_chunks

        config, _ = load_config(self.project)
        info = build_index(self.project, config)
        self.assertGreaterEqual(info["secretsSkipped"], 1)
        paths = {c["path"] for c in load_chunks(self.project)}
        self.assertNotIn(".env", paths)
        self.assertIn("src/app.py", paths)

    def test_context_secret_on_demand(self):
        from robots.brain.redact import secret_marker
        from robots.context_robot import build as build_context

        (self.project / ".env").write_text("OPENAI_API_KEY=changed\n", encoding="utf-8")
        payload, _, _ = build_context(self.project, task="rotate keys", budget=4000)
        rows = {row["path"]: row["open"] for row in payload["files"]}
        self.assertNotIn(".env", rows)
        marker = secret_marker(".env")
        self.assertIn(marker, rows)
        self.assertEqual(rows[marker], "on-demand")


class SovereigntyLedgerTests(unittest.TestCase):
    def test_append_and_summary(self):
        temp = tempfile.TemporaryDirectory()
        db = Path(temp.name) / "ledger.sqlite"
        try:
            first = record_event("cycle", project="p", model="m", tier="t", issue="i",
                                 success=True, latency_ms=2000, tokens_in=1000,
                                 tokens_out=500, db=db)
            self.assertGreater(first, 0)
            record_event("probe", project="p", success=False, latency_ms=100, db=db)
            result = summary(db)
            self.assertEqual(result["events"], 2)
            self.assertEqual(result["success_rate"], 0.5)
            self.assertEqual(result["total_tokens"], 1500)
            self.assertIn("cycle", result["by_kind"])
        finally:
            temp.cleanup()

    def test_cost_estimation(self):
        self.assertEqual(estimate_cost_usd(1000, 500), 0.0)
        self.assertEqual(estimate_cost_usd(1_500_000, 500_000, 3.0), 6.0)

    def test_never_raises(self):
        self.assertEqual(record_event("x", db=Path("/nonexistent-dir-xyz/ledger.sqlite")), -1)
        self.assertIn("events", summary(Path("/nonexistent-dir-xyz/ledger.sqlite")))


class ShallowVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_shallow_skips_checks(self):
        from robots.autonomous.loop import AutonomousConfig, AutonomousRobot

        config, _ = load_config(self.project)
        robot = AutonomousRobot(AutonomousConfig(issue_queue=[]))
        brain = {"verification_depth": "shallow"}
        verification = robot._verify_execution({}, self.project, config, brain)
        self.assertTrue(verification["checks"]["skipped"])
        self.assertEqual(verification["depth"], "shallow")


if __name__ == "__main__":
    unittest.main()
