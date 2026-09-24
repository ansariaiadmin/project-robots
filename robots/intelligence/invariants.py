"""Invariant registry — contracts, schemas, SLOs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Invariant:
    """A single invariant (contract, schema, SLO)."""
    id: str
    type: str  # "contract", "schema", "slo", "custom"
    description: str
    location: str  # file path or "global"
    validator: str  # Python expression or reference to validator function
    severity: str = "error"  # "error", "warning", "info"
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class InvariantRegistry:
    """Registry of all project invariants."""
    invariants: dict[str, Invariant] = field(default_factory=dict)
    
    def add(self, invariant: Invariant) -> None:
        self.invariants[invariant.id] = invariant
    
    def get(self, invariant_id: str) -> Invariant | None:
        return self.invariants.get(invariant_id)
    
    def by_type(self, invariant_type: str) -> list[Invariant]:
        return [i for i in self.invariants.values() if i.type == invariant_type]
    
    def by_location(self, location: str) -> list[Invariant]:
        return [i for i in self.invariants.values() if i.location == location]


class InvariantExtractor:
    """Extracts invariants from source code and config."""
    
    CONTRACT_PATTERNS = [
        (r"@contract\s+(.+)", "contract"),
        (r"@invariant\s+(.+)", "contract"),
        (r"@requires\s+(.+)", "precondition"),
        (r"@ensures\s+(.+)", "postcondition"),
        (r"assert\s+(.+)", "assertion"),
    ]
    
    SCHEMA_PATTERNS = [
        (r"class\s+(\w+)\s*\(\s*BaseModel\s*\)", "pydantic"),
        (r"class\s+(\w+)\s*:\s*\n\s*\"\"\"[^\"\"\"]*schema", "dataclass"),
        (r"TypedDict\s*\(\s*[\"'](\w+)[\"']", "typeddict"),
    ]
    
    SLO_PATTERNS = [
        (r"SLO\s*:\s*(.+)", "slo"),
        (r"latency.*<.*(\d+)", "latency"),
        (r"throughput.*>.*(\d+)", "throughput"),
        (r"availability.*>.*(\d+)", "availability"),
    ]
    
    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.registry = InvariantRegistry()
    
    def extract(self) -> InvariantRegistry:
        """Extract all invariants from project."""
        # From source code
        self._extract_from_source()
        
        # From config files
        self._extract_from_config()
        
        # From documentation
        self._extract_from_docs()
        
        return self.registry
    
    def _extract_from_source(self) -> None:
        """Extract invariants from source code comments and annotations."""
        for py_file in self.project.rglob("*.py"):
            if self._is_ignored(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                rel_path = py_file.relative_to(self.project).as_posix()
                self._scan_content(content, rel_path)
            except (OSError, UnicodeDecodeError):
                continue
    
    def _scan_content(self, content: str, file_path: str) -> None:
        """Scan content for invariant patterns."""
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # Contract patterns
            for pattern, inv_type in self.CONTRACT_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    inv_id = f"{file_path}:{i+1}:{inv_type}"
                    self.registry.add(Invariant(
                        id=inv_id,
                        type=inv_type,
                        description=match.group(1).strip(),
                        location=file_path,
                        validator=f"line_{i+1}",
                        severity="error" if inv_type in ("contract", "precondition", "postcondition") else "warning",
                        metadata={"line": i+1, "raw": line.strip()},
                    ))
            
            # Schema patterns
            for pattern, schema_type in self.SCHEMA_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    inv_id = f"{file_path}:{i+1}:schema:{schema_type}"
                    self.registry.add(Invariant(
                        id=inv_id,
                        type="schema",
                        description=f"{schema_type} schema: {match.group(1)}",
                        location=file_path,
                        validator=f"schema_{match.group(1)}",
                        severity="info",
                        metadata={"line": i+1, "schema_type": schema_type, "name": match.group(1)},
                    ))
            
            # SLO patterns
            for pattern, slo_type in self.SLO_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    inv_id = f"{file_path}:{i+1}:slo:{slo_type}"
                    self.registry.add(Invariant(
                        id=inv_id,
                        type="slo",
                        description=f"{slo_type} SLO: {match.group(1) if match.groups() else line.strip()}",
                        location=file_path,
                        validator=f"slo_{slo_type}",
                        severity="warning",
                        metadata={"line": i+1, "slo_type": slo_type},
                    ))
    
    def _extract_from_config(self) -> None:
        """Extract invariants from config files."""
        # pyproject.toml - tool configurations
        pyproject = self.project / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                self._extract_from_toml(data, "pyproject.toml")
            except Exception:
                pass
        
        # package.json - scripts, engines
        package_json = self.project / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                self._extract_from_package_json(data)
            except Exception:
                pass
    
    def _extract_from_toml(self, data: dict, file_path: str) -> None:
        """Extract invariants from TOML config."""
        # Type checking config
        if "tool" in data:
            tools = data["tool"]
            if "mypy" in tools:
                self.registry.add(Invariant(
                    id=f"{file_path}:mypy:strict",
                    type="contract",
                    description="mypy strict mode enabled",
                    location=file_path,
                    validator="mypy_strict",
                    severity="error",
                    metadata=tools["mypy"],
                ))
            if "ruff" in tools:
                ruff = tools["ruff"]
                if "select" in ruff:
                    self.registry.add(Invariant(
                        id=f"{file_path}:ruff:rules",
                        type="contract",
                        description=f"Ruff rules: {', '.join(ruff['select'][:10])}",
                        location=file_path,
                        validator="ruff_rules",
                        severity="warning",
                        metadata=ruff,
                    ))
    
    def _extract_from_package_json(self, data: dict) -> None:
        """Extract invariants from package.json."""
        if "engines" in data:
            self.registry.add(Invariant(
                id="package.json:engines",
                type="contract",
                description=f"Node engine requirement: {data['engines'].get('node', 'any')}",
                location="package.json",
                validator="node_version",
                severity="error",
                metadata=data["engines"],
            ))
    
    def _extract_from_docs(self) -> None:
        """Extract invariants from documentation."""
        for md_file in self.project.rglob("*.md"):
            if self._is_ignored(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                rel_path = md_file.relative_to(self.project).as_posix()
                
                # Look for SLO/requirement sections
                if any(kw in content.lower() for kw in ["slo", "requirement", "invariant", "contract", "guarantee"]):
                    self.registry.add(Invariant(
                        id=f"{rel_path}:doc:invariants",
                        type="custom",
                        description="Documentation contains invariants/SLOs",
                        location=rel_path,
                        validator="doc_review",
                        severity="info",
                        metadata={"has_invariants": True},
                    ))
            except Exception:
                continue
    
    def _is_ignored(self, path: Path) -> bool:
        rel = path.relative_to(self.project).as_posix()
        patterns = self.config.get("ignore", [])
        return any(fnmatch.fnmatch(rel, p) for p in patterns)


import fnmatch


def extract_invariants(project: Path, config: dict) -> InvariantRegistry:
    """Convenience function to extract invariants."""
    extractor = InvariantExtractor(project, config)
    return extractor.extract()