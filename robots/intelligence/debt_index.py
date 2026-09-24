"""Technical debt index — complexity, duplication, age metrics."""

from __future__ import annotations

import ast
import fnmatch
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class FileMetrics:
    """Metrics for a single file."""

    path: str
    lines: int
    complexity: int  # Cyclomatic complexity
    functions: int
    classes: int
    max_nesting: int
    age_days: int
    churn: int  # Number of commits touching this file
    ownership: str  # Primary author
    duplication_score: float = 0.0


@dataclass(slots=True)
class DebtIndex:
    """Complete technical debt index."""

    file_metrics: dict[str, FileMetrics] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    hotspots: list[tuple[str, float]] = field(default_factory=list)  # (file, debt_score)
    trends: dict[str, list[tuple[str, float]]] = field(default_factory=dict)  # metric -> [(date, value)]


class DebtAnalyzer:
    """Analyzes technical debt across the codebase."""

    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.max_file_bytes = config.get("limits", {}).get("maxFileBytes", 2_000_000)

    def analyze(self, import_graph: dict | None = None) -> DebtIndex:
        """Compute complete debt index."""
        index = DebtIndex()

        # Get git history for age and churn
        file_ages = self._get_file_ages()
        file_churn = self._get_file_churn()
        file_ownership = self._get_file_ownership()

        # Analyze each Python file
        for py_file in self._find_python_files():
            if self._is_ignored(py_file):
                continue

            rel_path = py_file.relative_to(self.project).as_posix()
            try:
                metrics = self._analyze_file(
                    py_file,
                    rel_path,
                    file_ages.get(rel_path, 0),
                    file_churn.get(rel_path, 0),
                    file_ownership.get(rel_path, "unknown"),
                )
                index.file_metrics[rel_path] = metrics
            except Exception:
                continue

        # Compute debt scores and hotspots
        index.hotspots = self._compute_hotspots(index.file_metrics)
        index.summary = self._compute_summary(index.file_metrics)

        return index

    def _find_python_files(self) -> list[Path]:
        files = []
        for root, dirs, names in os.walk(self.project):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(root_path / d)]
            for name in names:
                if name.endswith(".py"):
                    file_path = root_path / name
                    if not self._is_ignored_file(file_path):
                        files.append(file_path)
        return files

    def _analyze_file(
        self,
        file_path: Path,
        rel_path: str,
        age_days: int,
        churn: int,
        ownership: str,
    ) -> FileMetrics:
        """Analyze a single Python file for complexity metrics."""
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_path)

        visitor = ComplexityVisitor()
        visitor.visit(tree)

        lines = len(source.splitlines())

        return FileMetrics(
            path=rel_path,
            lines=lines,
            complexity=visitor.complexity,
            functions=visitor.functions,
            classes=visitor.classes,
            max_nesting=visitor.max_nesting,
            age_days=age_days,
            churn=churn,
            ownership=ownership,
        )

    def _compute_hotspots(self, metrics: dict[str, FileMetrics]) -> list[tuple[str, float]]:
        """Compute debt score for each file and return top hotspots."""
        scored = []
        for path, m in metrics.items():
            # Debt score formula: weighted combination of complexity, churn, age, size
            score = (
                0.30 * min(m.complexity / 20.0, 1.0)  # Normalized complexity
                + 0.25 * min(m.churn / 50.0, 1.0)  # Normalized churn
                + 0.20 * min(m.lines / 500.0, 1.0)  # Normalized size
                + 0.15 * min(m.age_days / 365.0, 1.0)  # Normalized age
                + 0.10 * min(m.max_nesting / 10.0, 1.0)  # Normalized nesting
            )
            scored.append((path, score))

        return sorted(scored, key=lambda x: x[1], reverse=True)[:20]

    def _compute_summary(self, metrics: dict[str, FileMetrics]) -> dict:
        """Compute summary statistics."""
        if not metrics:
            return {}

        total_files = len(metrics)
        total_lines = sum(m.lines for m in metrics.values())
        avg_complexity = sum(m.complexity for m in metrics.values()) / total_files
        max_complexity = max(m.complexity for m in metrics.values())
        total_churn = sum(m.churn for m in metrics.values())

        high_complexity = sum(1 for m in metrics.values() if m.complexity > 20)
        high_churn = sum(1 for m in metrics.values() if m.churn > 20)
        large_files = sum(1 for m in metrics.values() if m.lines > 500)

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "avg_complexity": round(avg_complexity, 2),
            "max_complexity": max_complexity,
            "total_churn": total_churn,
            "high_complexity_files": high_complexity,
            "high_churn_files": high_churn,
            "large_files": large_files,
            "debt_ratio": round((high_complexity + high_churn + large_files) / total_files, 3),
        }

    def _get_file_ages(self) -> dict[str, int]:
        """Get file ages in days from git history."""
        ages = {}
        try:
            output = subprocess.run(
                ["git", "log", "--pretty=format:%ct", "--name-only", "-z", "--follow"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            parts = output.split("\0")
            current_hash = None
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if len(part) == 40 and all(c in "0123456789abcdef" for c in part):
                    current_hash = part
                else:
                    # Get commit date for this hash
                    try:
                        date_output = subprocess.run(
                            ["git", "show", "-s", "--format=%ct", current_hash],
                            cwd=self.project,
                            capture_output=True,
                            text=True,
                            check=True,
                        ).stdout.strip()
                        commit_date = datetime.fromtimestamp(int(date_output))
                        age = (datetime.now() - commit_date).days
                        if part not in ages or age < ages[part]:
                            ages[part] = age
                    except Exception:
                        pass
        except Exception:
            pass

        return ages

    def _get_file_churn(self) -> dict[str, int]:
        """Get churn (commit count) per file."""
        churn = defaultdict(int)
        try:
            output = subprocess.run(
                ["git", "log", "--pretty=format:", "--name-only", "-z"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            for part in output.split("\0"):
                part = part.strip()
                if part:
                    churn[part] += 1
        except Exception:
            pass

        return dict(churn)

    def _get_file_ownership(self) -> dict[str, str]:
        """Get primary author for each file."""
        ownership = {}
        try:
            output = subprocess.run(
                ["git", "log", "--pretty=format:%an", "--name-only", "-z"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            parts = output.split("\0")
            current_author = None
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if " " in part or "@" in part:
                    current_author = part
                elif current_author and part not in ownership:
                    ownership[part] = current_author
        except Exception:
            pass

        return ownership

    def _is_ignored_dir(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(f"{rel}/", p) for p in patterns)

    def _is_ignored_file(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(rel, p) for p in patterns)

    def _is_ignored(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(rel, p) for p in patterns)


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor to compute cyclomatic complexity and nesting."""

    def __init__(self):
        self.complexity = 1  # Base complexity
        self.functions = 0
        self.classes = 0
        self.max_nesting = 0
        self._current_nesting = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions += 1
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_Try(self, node: ast.Try) -> None:
        self.complexity += len(node.handlers)
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self._enter_block()
        self.generic_visit(node)
        self._exit_block()

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each and/or adds complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def _enter_block(self):
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)

    def _exit_block(self):
        self._current_nesting -= 1


def analyze_debt(project: Path, config: dict, import_graph: dict | None = None) -> DebtIndex:
    """Convenience function to analyze technical debt."""
    analyzer = DebtAnalyzer(project, config)
    return analyzer.analyze(import_graph)
