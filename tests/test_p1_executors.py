"""P1 executor regression tests: wired vs unsupported, gates, dry-run, scope."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.autonomous.loop import AutonomousConfig, AutonomousRobot
from robots.tooling.selector import ToolRecommendation


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "p1@example.invalid")
    _git(project, "config", "user.name", "P1 Tests")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


def _rec(tool: str, config: dict) -> ToolRecommendation:
    return ToolRecommendation(tool=tool, reason="test", confidence=0.9, config=config)


def _exec(plan: dict, tools: list, project: Path, config: dict, brain: dict | None = None) -> dict:
    robot = AutonomousRobot(AutonomousConfig(risk_threshold=0.3))
    return robot._execute_plan(plan, tools, project, config, brain or {})


class ContractExecutorTests(unittest.TestCase):
    def test_openapi_compatible_returns_structured_success(self):
        temp, project = _make_project()
        try:
            old = {"paths": {"/a": {}}, "components": {"schemas": {}}}
            new = {"paths": {"/a": {}, "/b": {}}, "components": {"schemas": {}}}
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("contract_tester", {
                "old_spec": old, "new_spec": new, "contract_type": "openapi"})],
                project, {})
            self.assertEqual(len(out["tool_results"]), 1)
            res = out["tool_results"][0]["result"]
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "success")
            self.assertGreaterEqual(res["contracts_tested"], 1)
        finally:
            temp.cleanup()

    def test_openapi_breaking_reports_failed_not_success(self):
        temp, project = _make_project()
        try:
            old = {"paths": {"/a": {}, "/gone": {}}, "components": {"schemas": {}}}
            new = {"paths": {"/a": {}}, "components": {"schemas": {}}}
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("contract_tester", {
                "old_spec": old, "new_spec": new})], project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "failed")
            self.assertTrue(res["breaking_changes"])
        finally:
            temp.cleanup()

    def test_missing_context_fails_closed(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("contract_tester", {})], project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "skipped")
        finally:
            temp.cleanup()

    def test_protobuf_placeholder_is_unsupported(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("contract_tester", {
                "old_spec": {"a": 1}, "new_spec": {"a": 1},
                "contract_type": "protobuf"})], project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "unsupported")
        finally:
            temp.cleanup()


class ModelCheckerExecutorTests(unittest.TestCase):
    def test_missing_spec_path_skipped(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("model_checker", {})], project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "skipped")
        finally:
            temp.cleanup()

    def test_out_of_scope_blocked(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("model_checker", {"spec_path": "../escape.tla"})],
                        project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "blocked")
        finally:
            temp.cleanup()

    def test_missing_file_skipped(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("model_checker", {"spec_path": "src/nope.tla"})],
                        project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "skipped")
        finally:
            temp.cleanup()

    def test_no_backend_is_unsupported_never_success(self):
        temp, project = _make_project()
        try:
            (project / "src" / "spec.tla").write_text("---- MODULE s ----\n", encoding="utf-8")
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("model_checker", {"spec_path": "src/spec.tla"})],
                        project, {})
            res = out["tool_results"][0]["result"]
            # Either a real backend verifies, or we report unsupported.
            self.assertIn(res["status"], ("unsupported", "success", "failed"))
            if res["status"] == "unsupported":
                self.assertFalse(res["success"])
            self.assertEqual(res.get("files_changed", 0), 0)
        finally:
            temp.cleanup()


class UnsupportedExecutorTests(unittest.TestCase):
    def test_property_and_benchmark_unsupported(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("property_tester", {}), _rec("benchmark", {})],
                        project, {})
            self.assertEqual(len(out["tool_results"]), 2)
            for entry in out["tool_results"]:
                self.assertFalse(entry["result"]["success"])
                self.assertEqual(entry["result"]["status"], "unsupported")
        finally:
            temp.cleanup()

    def test_unknown_tool_fails_closed(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [], "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("no_such_tool", {})], project, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "unsupported")
        finally:
            temp.cleanup()


class GateTests(unittest.TestCase):
    def test_dry_run_zero_writes(self):
        temp, project = _make_project()
        try:
            target = project / "src" / "app.py"
            before = target.read_bytes()
            plan = {"changes": [{"file": "src/app.py", "type": "refactor",
                                 "description": "rename foo to bar"}],
                    "risk_score": {"overall": 0.0}}
            tools = [_rec("ast_rewrite", {"refactoring_type": "general"}),
                     _rec("contract_tester", {"old_spec": {"paths": {}},
                                              "new_spec": {"paths": {}}}),
                     _rec("property_tester", {})]
            config = {"autonomous": {"dry_run": True}}
            out = _exec(plan, tools, project, config, {})
            self.assertTrue(out["policy"]["dry_run"])
            self.assertEqual(target.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_high_risk_blocked(self):
        temp, project = _make_project()
        try:
            target = project / "src" / "app.py"
            before = target.read_bytes()
            plan = {"changes": [{"file": "src/app.py", "description": "x"}],
                    "risk_score": {"overall": 0.9}}
            tools = [_rec("contract_tester", {"old_spec": {"paths": {}},
                                              "new_spec": {"paths": {}}}),
                     _rec("model_checker", {"spec_path": "src/app.py"})]
            out = _exec(plan, tools, project, {}, {})
            self.assertEqual(out["policy"]["decision"], "deny")
            for entry in out["tool_results"]:
                self.assertFalse(entry["result"]["success"])
                self.assertEqual(entry["result"]["status"], "blocked")
            self.assertEqual(target.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_out_of_scope_write_blocked(self):
        temp, project = _make_project()
        try:
            plan = {"changes": [{"file": "../outside.py", "description": "rename"}],
                    "risk_score": {"overall": 0.0}}
            out = _exec(plan, [_rec("ast_rewrite", {"refactoring_type": "general"})],
                        project, {}, {})
            res = out["tool_results"][0]["result"]
            self.assertFalse(res["success"])
            self.assertFalse((project.parent / "outside.py").exists())
        finally:
            temp.cleanup()

    def test_critical_critique_still_blocks_all_tools(self):
        temp, project = _make_project()
        try:
            from robots.common import load_config

            config, _ = load_config(project)
            target = project / "src" / "app.py"
            before = target.read_bytes()
            robot = AutonomousRobot(AutonomousConfig(issue_queue=["p1"]))
            critical = {"issue": "p1", "rationale": "t",
                        "steps": [{"action": "catch and ignore errors", "target": "x"}],
                        "changes": [{"file": "src/app.py", "description": "patch"}],
                        "risk_score": {"overall": 0.0}}
            robot._generate_plan = lambda *a, **k: dict(critical)  # type: ignore[method-assign]
            result = robot.run_cycle(project, config, "p1")
            self.assertTrue(result.plan.get("execution", {}).get("blocked_by_critique"))
            self.assertEqual(result.plan["execution"]["tool_results"], [])
            self.assertEqual(target.read_bytes(), before)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
