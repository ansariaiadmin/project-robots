"""Tests for Code-Graph RAG subsystem (RFC-001). Stdlib only."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from robots.common import cache_dir, load_config
from robots.context_robot import build as build_context
from robots.rag.budget import allocate
from robots.rag.chunker import chunk_file, chunk_python_symbols, chunk_sliding
from robots.rag.lexical import fts_search, like_fallback, tokenize_query
from robots.rag.rank import fuse_with_details, rrf_fuse
from robots.rag.robot import build_index_command, query_command
from robots.rag.store import build_index, is_fresh, load_chunks
from robots.rag.structural import bfs_distances, build_adjacency, file_scores
from robots.rag.vectors import build_idf, cosine, text_to_vector


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True,
                   capture_output=True)


def _make_project() -> tuple[tempfile.TemporaryDirectory, Path]:
    temp = tempfile.TemporaryDirectory()
    project = Path(temp.name)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "rag@example.invalid")
    _git(project, "config", "user.name", "RAG Tests")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text(
        "import os\n\n"
        "def process_payment(amount):\n"
        "    \"\"\"Process a payment with retry.\"\"\"\n"
        "    return amount * 2\n\n"
        "def refund_payment(amount):\n"
        "    return amount\n",
        encoding="utf-8",
    )
    (project / "src" / "util.py").write_text(
        "def helper():\n    return 42\n", encoding="utf-8"
    )
    (project / "docs").mkdir()
    (project / "docs" / "guide.md").write_text(
        "# Guide\n\nPayment retry logic lives in src/app.py.\n", encoding="utf-8"
    )
    (project / "README.md").write_text("# Demo\n", encoding="utf-8")
    (project / ".project-robots.json").write_text(
        json.dumps({"version": 1, "limits": {"contextTokenBudget": 4000}}),
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    return temp, project


class ChunkerTests(unittest.TestCase):
    def test_python_symbol_boundaries(self):
        text = (
            "import os\n\n"
            "def foo():\n    return 1\n\n"
            "def bar():\n    return 2\n\n"
            "class Baz:\n    def method(self):\n        return 3\n"
        )
        chunks = chunk_python_symbols("src/app.py", text)
        assert chunks is not None
        symbols = {c["symbol"] for c in chunks}
        self.assertIn("foo", symbols)
        self.assertIn("bar", symbols)
        for chunk in chunks:
            self.assertLessEqual(chunk["end_line"] - chunk["start_line"] + 1, 120)
            self.assertGreater(chunk["token_est"], 0)
            self.assertEqual(len(chunk["id"]), 16)

    def test_oversized_symbol_splits(self):
        body = "\n".join(f"    x{idx} = {idx}" for idx in range(200))
        text = f"def big():\n{body}\n"
        chunks = chunk_python_symbols("src/big.py", text, max_lines=120)
        assert chunks is not None
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk["end_line"] - chunk["start_line"] + 1, 120)

    def test_sliding_fallback_counts(self):
        lines = [f"line {idx}" for idx in range(1, 201)]
        chunks = chunk_sliding("docs/guide.md", "\n".join(lines))
        self.assertEqual(len(chunks), 3)
        self.assertEqual((chunks[0]["start_line"], chunks[0]["end_line"]), (1, 80))
        self.assertEqual((chunks[1]["start_line"], chunks[1]["end_line"]), (61, 140))
        self.assertEqual((chunks[2]["start_line"], chunks[2]["end_line"]), (121, 200))

    def test_chunk_file_dispatch(self):
        py_chunks = chunk_file("a.py", "def f():\n    return 1\n", True)
        self.assertTrue(any(c["symbol"] == "f" for c in py_chunks))
        md_chunks = chunk_file("b.md", "# hi\n", False)
        self.assertEqual(len(md_chunks), 1)


class RankBudgetTests(unittest.TestCase):
    def test_rrf_exact(self):
        fused = rrf_fuse([["a", "b", "c"], ["b", "a"], ["c"]], k=60)
        self.assertAlmostEqual(fused["a"], 1 / 61 + 1 / 62)
        self.assertAlmostEqual(fused["b"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(fused["c"], 1 / 63 + 1 / 61)
        details = fuse_with_details(["a", "b"], ["b", "a"], ["a"])
        self.assertEqual(details[0]["id"], "a")
        self.assertEqual(details[0]["rank_L"], 1)
        self.assertEqual(details[0]["rank_S"], 2)
        self.assertEqual(details[0]["rank_V"], 1)

    def test_budget_first_always_kept(self):
        items = [
            {"id": "a", "token_est": 3000},
            {"id": "b", "token_est": 2000},
            {"id": "c", "token_est": 500},
        ]
        first, on_demand, estimated = allocate(items, 4000)
        # Greedy fit: a (3000) first, b exceeds -> on-demand, c fits -> first.
        self.assertEqual([i["id"] for i in first], ["a", "c"])
        self.assertEqual([i["id"] for i in on_demand], ["b"])
        self.assertEqual(estimated, 3500)
        first2, _, est2 = allocate([{"id": "x", "token_est": 5000}], 4000)
        self.assertEqual(len(first2), 1)
        self.assertEqual(est2, 5000)

    def test_lexical_tokenizer(self):
        self.assertIn("payment", tokenize_query("Payment retry logic!"))
        self.assertNotIn("the", tokenize_query("the payment"))

    def test_vectors_cosine(self):
        idf = build_idf(["hello world", "hello world", "unrelated zebra"])
        vec_a = text_to_vector("hello world", idf)
        vec_b = text_to_vector("hello world", idf)
        self.assertAlmostEqual(cosine(vec_a, vec_b), 1.0, places=5)

    def test_structural_bfs(self):
        from types import SimpleNamespace

        graph = {
            "a.py": SimpleNamespace(
                imports=[SimpleNamespace(imported="b.py")], imported_by=[]
            ),
            "b.py": SimpleNamespace(imports=[], imported_by=["a.py"]),
        }
        adj = build_adjacency(graph)
        self.assertIn("b.py", adj["a.py"])
        dist = bfs_distances(adj, ["a.py"], depth=2)
        self.assertEqual(dist["a.py"], 0)
        self.assertEqual(dist["b.py"], 1)
        scores = file_scores(graph, {"b.py": 20}, ["a.py"])
        self.assertGreater(scores["b.py"][0], 0)


class RagIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.project = _make_project()

    def tearDown(self):
        shutil.rmtree(cache_dir(self.project), ignore_errors=True)
        self.temp.cleanup()

    def test_index_and_query(self):
        config, _ = load_config(self.project)
        payload, _ = build_index_command(self.project, config)
        self.assertTrue(payload["ok"])
        self.assertGreater(payload["summary"]["chunks"], 3)
        fresh, _, _ = is_fresh(self.project, config)
        self.assertTrue(fresh)
        chunks = load_chunks(self.project)
        self.assertTrue(all(c["token_est"] > 0 for c in chunks))
        qpayload, _, _ = query_command(self.project, config, task="payment retry", k=10)
        self.assertTrue(qpayload["ok"])
        self.assertGreater(qpayload["summary"]["hits"], 0)
        self.assertLessEqual(
            qpayload["summary"]["firstTokens"], qpayload["summary"]["budget"]
        )
        paths = [h["path"] for h in qpayload["hits"]]
        self.assertIn("src/app.py", paths)
        # Lexical path works against the real index.
        lex = fts_search(self.project, "payment retry", limit=10)
        self.assertGreater(len(lex), 0)
        like = like_fallback(self.project, ["payment"], limit=10)
        self.assertGreater(len(like), 0)

    def test_stale_after_source_change(self):
        config, _ = load_config(self.project)
        build_index(self.project, config)
        fresh, _, _ = is_fresh(self.project, config)
        self.assertTrue(fresh)
        (self.project / "src" / "app.py").write_text(
            "def changed():\n    return 0\n", encoding="utf-8"
        )
        fresh2, _, _ = is_fresh(self.project, config)
        self.assertFalse(fresh2)
        qpayload, _, _ = query_command(self.project, config, task="payment")
        self.assertFalse(qpayload["ok"])
        self.assertIn("rag-index", qpayload["reason"])

    def test_reindex_recovers(self):
        config, _ = load_config(self.project)
        build_index(self.project, config)
        (self.project / "src" / "app.py").write_text(
            "def changed():\n    return 0\n", encoding="utf-8"
        )
        info = build_index(self.project, config, force=True)
        self.assertFalse(info["reused"])
        fresh, _, _ = is_fresh(self.project, config)
        self.assertTrue(fresh)

    def test_context_enrichment_respects_budget(self):
        config, _ = load_config(self.project)
        build_index(self.project, config)
        (self.project / "src" / "app.py").write_text(
            "def process_payment(amount):\n    return amount * 3\n", encoding="utf-8"
        )
        payload, _, _ = build_context(self.project, task="payment retry", budget=4000)
        summary = payload["summary"]
        total = summary["estimatedFirstReadTokens"] + summary["ragFirstTokens"]
        self.assertLessEqual(total, 4000)
        self.assertIn("rag", payload)

    def test_zero_side_effects(self):
        config, _ = load_config(self.project)
        build_index(self.project, config)
        query_command(self.project, config, task="payment")
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=self.project, capture_output=True, text=True, check=True,
        ).stdout.strip()
        # Only allowed: nothing tracked modified (index lives in central .cache).
        tracked_modified = [
            line for line in status.splitlines()
            if line and not line.endswith(".pyc") and "??" not in line[:2]
        ]
        self.assertEqual(tracked_modified, [])
        self.assertFalse((self.project / ".cache").exists())
        self.assertFalse((self.project / ".project-robots").exists())


if __name__ == "__main__":
    unittest.main()
