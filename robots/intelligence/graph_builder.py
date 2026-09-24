"""Dependency graph builder for repository intelligence."""

from __future__ import annotations

import ast
import fnmatch
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass(slots=True)
class ImportEdge:
    """Represents an import relationship."""
    importer: str
    imported: str
    import_type: str  # "direct", "from", "relative"
    line: int


@dataclass(slots=True)
class ModuleNode:
    """Represents a Python module in the graph."""
    path: str
    imports: list[ImportEdge] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    symbols: dict[str, list[str]] = field(default_factory=dict)  # symbol -> [defined_in]


class ImportGraphBuilder:
    """Builds import dependency graph from Python source files."""
    
    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.graph: dict[str, ModuleNode] = {}
        self._stdlib_modules = self._load_stdlib_modules()
    
    def _load_stdlib_modules(self) -> set[str]:
        """Load known stdlib modules for filtering."""
        import sysconfig
        stdlib_path = Path(sysconfig.get_path("stdlib"))
        if stdlib_path.exists():
            return {p.name for p in stdlib_path.iterdir() if p.is_dir()}
        # Fallback common stdlib modules
        return {
            "os", "sys", "json", "pathlib", "collections", "itertools",
            "functools", "dataclasses", "typing", "datetime", "hashlib",
            "subprocess", "shlex", "shutil", "fnmatch", "re", "ast",
            "argparse", "logging", "unittest", "asyncio", "contextlib",
        }
    
    def build(self) -> dict[str, ModuleNode]:
        """Build complete import graph for project."""
        python_files = self._find_python_files()
        
        for py_file in python_files:
            try:
                self._analyze_file(py_file)
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
        
        self._resolve_reverse_edges()
        return self.graph
    
    def _find_python_files(self) -> list[Path]:
        """Find all Python files in project, respecting ignores."""
        files = []
        for root, dirs, names in os.walk(self.project):
            root_path = Path(root)
            # Filter directories
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(root_path / d)]
            for name in names:
                if name.endswith(".py"):
                    file_path = root_path / name
                    if not self._is_ignored_file(file_path):
                        files.append(file_path)
        return files
    
    def _is_ignored_dir(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(f"{rel}/", p) for p in patterns)
    
    def _is_ignored_file(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(rel, p) for p in patterns)
    
    def _analyze_file(self, file_path: Path) -> None:
        """Extract imports from a single Python file."""
        rel_path = file_path.relative_to(self.project).as_posix()
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_path)
        
        node = ModuleNode(path=rel_path)
        visitor = ImportVisitor(rel_path, self._stdlib_modules)
        visitor.visit(tree)
        
        node.imports = visitor.imports
        node.symbols = visitor.symbols
        self.graph[rel_path] = node
    
    def _resolve_reverse_edges(self) -> None:
        """Build reverse dependency edges."""
        for importer, node in self.graph.items():
            for edge in node.imports:
                if edge.imported in self.graph:
                    self.graph[edge.imported].imported_by.append(importer)
    
    def get_dependents(self, module: str, depth: int = 1) -> set[str]:
        """Get all modules that depend on the given module (transitive)."""
        result = set()
        frontier = {module}
        
        for _ in range(depth):
            next_frontier = set()
            for mod in frontier:
                if mod in self.graph:
                    next_frontier.update(self.graph[mod].imported_by)
            result.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break
        
        return result
    
    def get_dependencies(self, module: str, depth: int = 1) -> set[str]:
        """Get all modules the given module depends on (transitive)."""
        result = set()
        frontier = {module}
        
        for _ in range(depth):
            next_frontier = set()
            for mod in frontier:
                if mod in self.graph:
                    next_frontier.update(e.imported for e in self.graph[mod].imports)
            result.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break
        
        return result
    
    def find_cycles(self) -> list[list[str]]:
        """Detect import cycles using Tarjan's algorithm."""
        index = 0
        stack = []
        indices = {}
        lowlinks = {}
        on_stack = set()
        cycles = []
        
        def strongconnect(node_id: str):
            nonlocal index
            indices[node_id] = index
            lowlinks[node_id] = index
            index += 1
            stack.append(node_id)
            on_stack.add(node_id)
            
            if node_id in self.graph:
                for edge in self.graph[node_id].imports:
                    if edge.imported not in self.graph:
                        continue
                    succ = edge.imported
                    if succ not in indices:
                        strongconnect(succ)
                        lowlinks[node_id] = min(lowlinks[node_id], lowlinks[succ])
                    elif succ in on_stack:
                        lowlinks[node_id] = min(lowlinks[node_id], indices[succ])
            
            if lowlinks[node_id] == indices[node_id]:
                cycle = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    cycle.append(w)
                    if w == node_id:
                        break
                if len(cycle) > 1:
                    cycles.append(cycle)
        
        for node_id in self.graph:
            if node_id not in indices:
                strongconnect(node_id)
        
        return cycles


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract imports and symbol definitions."""
    
    def __init__(self, module_path: str, stdlib_modules: set[str]):
        self.module_path = module_path
        self.stdlib = stdlib_modules
        self.imports: list[ImportEdge] = []
        self.symbols: dict[str, list[str]] = defaultdict(list)
        self._current_class = None
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(ImportEdge(
                importer=self.module_path,
                imported=alias.name.split(".")[0],
                import_type="direct",
                line=node.lineno,
            ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        level = node.level
        
        if level > 0:
            # Relative import
            parts = self.module_path.split("/")
            base = "/".join(parts[:-level]) if level <= len(parts) else ""
            imported = f"{base}.{module}" if module else base
            imported = imported.lstrip(".")
        else:
            imported = module.split(".")[0]
        
        # Skip stdlib
        if imported in self.stdlib:
            self.generic_visit(node)
            return
        
        for alias in node.names:
            self.imports.append(ImportEdge(
                importer=self.module_path,
                imported=imported,
                import_type="from",
                line=node.lineno,
            ))
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = f"{self._current_class}.{node.name}" if self._current_class else node.name
        self.symbols[name].append(self.module_path)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_class = self._current_class
        self._current_class = node.name
        self.symbols[node.name].append(self.module_path)
        self.generic_visit(node)
        self._current_class = old_class


def build_import_graph(project: Path, config: dict) -> dict[str, ModuleNode]:
    """Convenience function to build import graph."""
    builder = ImportGraphBuilder(project, config)
    return builder.build()