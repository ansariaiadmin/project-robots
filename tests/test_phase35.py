"""Tests for Phase 3.5: handshake cache, ledger isolation, markers, writes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from robots.brain import (
    MockProvider,
    load_cached_handshake,
    save_cached_handshake,
    secret_marker,
)
from robots.brain.provider import ModelResponse, ProbeInfo
from robots.common import cache_dir, load_config
from robots.sovereignty import db_path, in_test_mode, record_event, set_test_db, summary


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "phase35@example.invalid")
    _git(project, "config", "user.name", "Phase35")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("def answer():\n    return None\n", encoding="utf-8")
    (project / ".env").write_text("OPENAI_API_KEY=sk-test-123\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class CountingProvider:
    """Stub Ollama-shaped provider (no network, no model_facts)."""

    kind = "ollama"

    def __init__(self) -> None:
        self.model = "test-model"
        self.endpoint = "http://stub:11434"
        self.timeout = 5
        self.calls = 0

    def probe(self) -> ProbeInfo:
        return ProbeInfo(ok=True, provider="ollama", models=["test-model"], model_known=True)

    def generate(self, prompt: str, options=None) -> ModelResponse:
        _ = (prompt, options)
        self.calls += 1
        return ModelResponse(text='{"ok":true,"n":1}', model=self.model,
                             provider="ollama", latency_ms=5)


class HandshakeCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.provider = CountingProvider()
        self.result = {"verified": True, "json_valid": True, "latency_ms": 5,
                       "error": "", "source": "ollama", "text": ""}

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_save_load_roundtrip(self):
        self.assertTrue(save_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", self.result))
        loaded = load_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", {})
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(loaded["json_valid"])
        self.assertEqual(loaded["latency_ms"], 5)

    def test_key_mismatch_misses(self):
        save_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", self.result)
        self.assertIsNone(load_cached_handshake(
            self.project, "ollama", "http://stub:11434", "other-model", {}))
        self.assertIsNone(load_cached_handshake(
            self.project, "ollama", "http://other:11434", "test-model", {}))
        self.assertIsNone(load_cached_handshake(
            self.project, "openai", "http://stub:11434", "test-model", {}))

    def test_stale_entry_misses(self):
        from robots.brain.capabilities import handshake_cache_path

        save_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", self.result)
        path = handshake_cache_path(self.project)
        assert path is not None
        cached = json.loads(path.read_text(encoding="utf-8"))
        cached["ts"] -= 7200
        path.write_text(json.dumps(cached), encoding="utf-8")
        self.assertIsNone(load_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", {}))

    def test_invalid_results_never_cached(self):
        bad = dict(self.result, json_valid=False)
        save_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", bad)
        self.assertIsNone(load_cached_handshake(
            self.project, "ollama", "http://stub:11434", "test-model", {}))

    def test_probe_reuses_cache(self):
        from robots.brain import probe_capabilities

        config: dict = {}
        first = probe_capabilities(self.provider, "test-model", config,
                                   verify=True, project=self.project)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(first.probes["handshake"]["source"], "ollama")
        second = probe_capabilities(self.provider, "test-model", config,
                                    verify=True, project=self.project)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(second.probes["handshake"]["source"], "cache")
        self.assertTrue(second.probes["handshake"]["json_valid"])

    def test_force_probe_bypasses_cache(self):
        from robots.brain import probe_capabilities

        config: dict = {}
        probe_capabilities(self.provider, "test-model", config,
                           verify=True, project=self.project)
        probe_capabilities(self.provider, "test-model", config,
                           verify=True, project=self.project, force_probe=True)
        self.assertEqual(self.provider.calls, 2)

    def test_mock_never_touches_cache(self):
        from robots.brain import probe_capabilities
        from robots.brain.capabilities import handshake_cache_path

        probe_capabilities(MockProvider("", "mock-small"), "mock-small", {},
                           verify=True, project=self.project)
        path = handshake_cache_path(self.project)
        self.assertTrue(path is None or not path.is_file())


class LedgerIsolationTests(unittest.TestCase):
    def tearDown(self):
        set_test_db(None)

    def test_explicit_override(self):
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "iso.sqlite"
        try:
            set_test_db(target)
            self.assertEqual(db_path(), target)
            self.assertTrue(in_test_mode())
            rowid = record_event("cycle", issue="iso", success=True)
            self.assertGreater(rowid, 0)
            result = summary()
            self.assertEqual(result["events"], 1)
            self.assertTrue(target.is_file())
        finally:
            set_test_db(None)
            temp.cleanup()

    def test_pytest_session_isolated_from_production(self):
        from robots.sovereignty.ledger import ledger_dir

        production = ledger_dir() / "ledger.sqlite"
        self.assertNotEqual(db_path(), production)

    def test_env_flag_routes_to_temp(self):
        with mock.patch.dict(os.environ, {"PROJECT_ROBOTS_TEST": "1"}):
            path = db_path()
            self.assertNotEqual(path, Path("/nonexistent") / "x")
            self.assertIn("project-robots-sov-test", path.name)


class SecretMarkerTests(unittest.TestCase):
    def test_marker_format_stable_opaque(self):
        first = secret_marker(".env")
        self.assertEqual(first, secret_marker(".env"))
        self.assertTrue(first.startswith("<redacted-secret:"))
        self.assertTrue(first.endswith(">"))
        self.assertNotIn(".env", first)
        self.assertNotEqual(first, secret_marker("other.env"))

    def test_query_seeds_sanitized(self):
        from robots.rag.robot import query_command
        from robots.rag.store import build_index

        temp, project = _make_project()
        try:
            config, _ = load_config(project)
            build_index(project, config)
            (project / ".env").write_text("OPENAI_API_KEY=rotated\n", encoding="utf-8")
            build_index(project, config, force=True)
            payload, _, _ = query_command(project, config, task="rotate keys", k=5)
            self.assertTrue(payload["ok"])
            self.assertNotIn(".env", json.dumps(payload["seeds"]))
            self.assertGreaterEqual(payload.get("secretsSeeds", 0), 1)
        finally:
            shutil.rmtree(cache_dir(project), ignore_errors=True)
            temp.cleanup()


class ChangeShapeTests(unittest.TestCase):
    def test_sanitize_changes_drops_malformed(self):
        from robots.autonomous.guard import sanitize_changes

        temp = tempfile.TemporaryDirectory()
        project = Path(temp.name)
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("x\n", encoding="utf-8")
        try:
            cleaned = sanitize_changes(
                [
                    {"file": "src/app.py", "description": "fix"},
                    "just a string",
                    42,
                    {"description": "no file"},
                    {"file": "../escape.py"},
                    {"path": "src/app.py"},
                ],
                project,
            )
            self.assertEqual(len(cleaned), 2)
            self.assertTrue(all(c["file"] == "src/app.py" for c in cleaned))
            self.assertEqual(cleaned[0]["description"], "fix")
        finally:
            temp.cleanup()

    def test_selector_skips_non_dicts(self):
        from robots.tooling.selector import ToolSelector

        selector = ToolSelector({})
        # Must not raise on model shape drift; needs no intelligence for skips.
        self.assertEqual(selector.select(["oops", 7, None], None), [])  # type: ignore[arg-type]


class RealWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_allowlisted_write_applies_diff_and_passes_checks(self):
        from robots.autonomous.guard import evaluate_write_policy
        from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
        from robots.tooling.selector import ToolRecommendation

        target = self.project / "src" / "app.py"
        config, _ = load_config(self.project)
        policy = evaluate_write_policy(
            risk_overall=0.05, risk_threshold=0.3,
            candidate_paths=["src/app.py"], project=self.project, config=config,
        )
        self.assertEqual(policy.decision, "allow")
        self.assertIn("src/app.py", policy.allowlist)
        plan = {
            "risk_score": {"overall": 0.05},
            "changes": [{"file": "src/app.py"}],
            "context_chunks": [],
        }
        tools = [ToolRecommendation(
            tool="semantic_patch", reason="t", confidence=0.9,
            config={"pattern": "return None", "replacement": "return 42",
                    "file_pattern": "*.py"},
        )]
        brain = {"write_permission": "standard", "tier": "tier-2-mid"}
        robot = AutonomousRobot(AutonomousConfig(issue_queue=[]))
        result = robot._execute_plan(plan, tools, self.project, config, brain)
        self.assertEqual(result["policy"]["decision"], "allow")
        self.assertFalse(result["policy"]["dry_run"])
        # File modified per diff.
        content = target.read_text(encoding="utf-8")
        self.assertIn("return 42", content)
        self.assertNotIn("return None", content)
        preview = result["tool_results"][0]["result"].get("preview", "")
        self.assertIn("-    return None", preview)
        self.assertIn("+    return 42", preview)
        # Git status reflects the change.
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"], cwd=self.project,
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("src/app.py", status)
        # Post-write checks pass: syntax valid, targeted file compiles.
        compile(content, "src/app.py", "exec")


if __name__ == "__main__":
    unittest.main()
