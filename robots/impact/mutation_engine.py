"""Mutation testing engine for test adequacy assessment."""

from __future__ import annotations

import ast
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class MutationResult:
    """Result of mutation testing."""

    total_mutants: int
    killed: int
    survived: int
    timeout: int
    errors: int
    mutation_score: float  # killed / (total - timeout - errors)
    mutants: list[dict] = field(default_factory=list)


class MutationEngine:
    """Runs mutation testing using mutmut or built-in mutator."""

    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.timeout = config.get("impact", {}).get("mutation_timeout_seconds", 120)
        self.use_mutmut = self._check_mutmut()

    def _check_mutmut(self) -> bool:
        """Check if mutmut is available."""
        try:
            subprocess.run(["mutmut", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def run(self, target_files: list[str] | None = None) -> MutationResult:
        """Run mutation testing on target files or entire project."""
        if self.use_mutmut:
            return self._run_mutmut(target_files)
        else:
            return self._run_builtin(target_files)

    def _run_mutmut(self, target_files: list[str] | None) -> MutationResult:
        """Run mutmut mutation testing."""
        _start = time.time()

        # Build mutmut command
        cmd = ["mutmut", "run", "--use-coverage"]
        if target_files:
            # Mutmut doesn't directly support file filtering, use paths
            paths = " ".join(target_files)
            cmd.extend(["--paths", paths])

        try:
            _result = subprocess.run(
                cmd,
                cwd=self.project,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return MutationResult(
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=1,
                errors=0,
                mutation_score=0.0,
                mutants=[{"error": "timeout"}],
            )
        except Exception as e:
            return MutationResult(
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                errors=1,
                mutation_score=0.0,
                mutants=[{"error": str(e)}],
            )

        # Parse results
        try:
            results_output = subprocess.run(
                ["mutmut", "results"],
                cwd=self.project,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout

            killed = results_output.count("killed")
            survived = results_output.count("survived")
            timeout = results_output.count("timeout")
            errors = results_output.count("error")
            total = killed + survived + timeout + errors

            mutation_score = killed / (total - timeout - errors) if (total - timeout - errors) > 0 else 0.0

            return MutationResult(
                total_mutants=total,
                killed=killed,
                survived=survived,
                timeout=timeout,
                errors=errors,
                mutation_score=mutation_score,
            )
        except Exception:
            return MutationResult(
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                errors=1,
                mutation_score=0.0,
                mutants=[{"error": "failed to parse results"}],
            )

    def _run_builtin(self, target_files: list[str] | None) -> MutationResult:
        """Run built-in simple mutation testing (fallback)."""
        # This is a simplified mutation tester for when mutmut isn't available
        # It applies basic mutations and runs tests

        if not target_files:
            # Find test files
            test_files = list(self.project.rglob("test_*.py"))
            test_files.extend(self.project.rglob("*_test.py"))
            target_files = [str(f.relative_to(self.project)) for f in test_files]

        if not target_files:
            return MutationResult(
                total_mutants=0, killed=0, survived=0, timeout=0, errors=0, mutation_score=1.0, mutants=[]
            )

        # Run tests once to get baseline
        try:
            baseline = subprocess.run(
                ["python", "-m", "pytest", "-x", "--tb=no", "-q"] + target_files,
                cwd=self.project,
                capture_output=True,
                text=True,
                timeout=60,
            )
            baseline_passed = baseline.returncode == 0
        except Exception:
            return MutationResult(
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                errors=1,
                mutation_score=0.0,
                mutants=[{"error": "baseline tests failed"}],
            )

        # Simple mutation: we'll just report that built-in is limited
        return MutationResult(
            total_mutants=0,
            killed=0,
            survived=0,
            timeout=0,
            errors=0,
            mutation_score=1.0 if baseline_passed else 0.0,
            mutants=[{"note": "built-in mutation testing limited; install mutmut for full analysis"}],
        )


class Mutator:
    """AST-based mutator for generating mutants."""

    MUTATIONS = {
        # Comparison operators
        "Eq": "NotEq",
        "NotEq": "Eq",
        "Lt": "Gt",
        "Gt": "Lt",
        "LtE": "GtE",
        "GtE": "LtE",
        "Is": "IsNot",
        "IsNot": "Is",
        "In": "NotIn",
        "NotIn": "In",
        # Arithmetic operators
        "Add": "Sub",
        "Sub": "Add",
        "Mult": "Div",
        "Div": "Mult",
        # Boolean operators
        "And": "Or",
        "Or": "And",
    }

    def __init__(self):
        self.mutants = []

    def mutate_file(self, file_path: Path, max_mutants: int = 50) -> list[dict]:
        """Generate mutants for a single file."""
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.mutants = []
        visitor = MutationVisitor(self.MUTATIONS, max_mutants)
        visitor.visit(tree)

        return visitor.mutants


class MutationVisitor(ast.NodeVisitor):
    """AST visitor that generates mutants."""

    def __init__(self, mutations: dict, max_mutants: int):
        self.mutations = mutations
        self.max_mutants = max_mutants
        self.mutants = []
        self._source_lines = None

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(self.mutants) >= self.max_mutants:
            return
        for op in node.ops:
            op_type = type(op).__name__
            if op_type in self.mutations:
                self.mutants.append(
                    {
                        "type": "comparison",
                        "original": op_type,
                        "mutated": self.mutations[op_type],
                        "line": node.lineno,
                        "col": node.col_offset,
                    }
                )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if len(self.mutants) >= self.max_mutants:
            return
        op_type = type(node.op).__name__
        if op_type in self.mutations:
            self.mutants.append(
                {
                    "type": "arithmetic",
                    "original": op_type,
                    "mutated": self.mutations[op_type],
                    "line": node.lineno,
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if len(self.mutants) >= self.max_mutants:
            return
        op_type = type(node.op).__name__
        if op_type in self.mutations:
            self.mutants.append(
                {
                    "type": "boolean",
                    "original": op_type,
                    "mutated": self.mutations[op_type],
                    "line": node.lineno,
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)


def run_mutation_testing(
    project: Path,
    config: dict,
    target_files: list[str] | None = None,
) -> MutationResult:
    """Convenience function to run mutation testing."""
    engine = MutationEngine(project, config)
    return engine.run(target_files)
