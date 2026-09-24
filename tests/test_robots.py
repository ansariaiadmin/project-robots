from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.checks_robot import build_plan, execute
from robots.common import cache_dir
from robots.context_robot import build as build_context
from robots.docs_robot import inspect as inspect_docs
from robots.evidence_robot import inspect as inspect_evidence


class RobotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(
            ["git", "config", "user.email", "robots@example.invalid"],
            cwd=self.project,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Project Robots"],
            cwd=self.project,
            check=True,
        )
        (self.project / "README.md").write_text(
            "# Demo\n\nSee [guide](docs/guide.md).\n",
            encoding="utf-8",
        )
        (self.project / "docs").mkdir()
        (self.project / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (self.project / "src").mkdir()
        (self.project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        config = {
            "version": 1,
            "requiredDocs": ["README.md", "docs/guide.md"],
            "readFirst": ["README.md"],
            "routes": [
                {
                    "name": "code",
                    "patterns": ["src/**"],
                    "readFirst": ["docs/guide.md"],
                    "checks": ["smoke"],
                    "invariants": ["Smoke check must pass."],
                }
            ],
            "checks": {
                "diff": ["git", "diff", "--check", "--", "."],
                "smoke": ["python3", "-c", "print('smoke passed')"],
            },
            "limits": {"contextTokenBudget": 1000},
        }
        (self.project / ".project-robots.json").write_text(
            json.dumps(config),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.project, check=True)

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_docs_detects_broken_local_link(self):
        payload, _ = inspect_docs(self.project)
        self.assertTrue(payload["ok"])
        (self.project / "docs" / "guide.md").unlink()
        payload, _ = inspect_docs(self.project)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["summary"]["errors"], 2)

    def test_context_stays_inside_budget_and_routes_scope(self):
        (self.project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
        payload, _json_path, _markdown_path = build_context(
            self.project,
            task="change app",
            budget=1000,
        )
        self.assertEqual(payload["scopes"], ["code"])
        self.assertLessEqual(payload["summary"]["estimatedFirstReadTokens"], 1000)
        self.assertIn("smoke", payload["recommendedChecks"])

    def test_context_maps_changed_source_to_owning_doc(self):
        (self.project / "docs" / "guide.md").write_text(
            "# Guide\n\nOwned source: `src/app.py`\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "ownership"], cwd=self.project, check=True)
        (self.project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
        payload, _json_path, _markdown_path = build_context(self.project, task="")
        first_read = {
            row["path"] for row in payload["files"] if row["open"] == "first"
        }
        self.assertIn("docs/guide.md", first_read)

    def test_check_evidence_becomes_stale_after_source_change(self):
        (self.project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
        plan = build_plan(self.project)
        payload, _ = execute(self.project, plan)
        self.assertTrue(payload["passed"])
        evidence, _ = inspect_evidence(self.project)
        self.assertTrue(evidence["ok"])
        (self.project / "src" / "app.py").write_text("print('newer')\n", encoding="utf-8")
        evidence, _ = inspect_evidence(self.project)
        self.assertFalse(evidence["ok"])
        self.assertFalse(evidence["summary"]["current"])

    def test_plan_is_minimal_and_deterministic(self):
        (self.project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
        first = build_plan(self.project)
        second = build_plan(self.project)
        self.assertEqual(first["commands"], second["commands"])
        self.assertEqual(
            [row["name"] for row in first["commands"]],
            ["diff", "smoke", "python-syntax"],
        )

    def test_nested_generated_cache_is_ignored(self):
        cache = self.project / "src" / "__pycache__"
        cache.mkdir()
        (cache / "app.pyc").write_bytes(b"generated")
        payload, _json_path, _markdown_path = build_context(self.project)
        self.assertNotIn(
            "src/__pycache__/app.pyc",
            {row["path"] for row in payload["changed"]},
        )

    def test_hidden_tool_cache_is_ignored(self):
        cache = self.project / ".cache"
        cache.mkdir()
        (cache / "evidence.json").write_text("{}\n", encoding="utf-8")
        payload, _json_path, _markdown_path = build_context(self.project)
        self.assertNotIn(
            ".cache/evidence.json",
            {row["path"] for row in payload["changed"]},
        )

    def test_clean_project_runs_only_baseline_check(self):
        plan = build_plan(self.project)
        self.assertEqual(
            [row["name"] for row in plan["commands"]],
            ["diff"],
        )


if __name__ == "__main__":
    unittest.main()
