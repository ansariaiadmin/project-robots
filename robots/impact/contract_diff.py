"""Contract diff verification for API/schema changes."""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ContractChange:
    """Represents a contract change."""

    type: str  # "added", "removed", "modified", "breaking"
    location: str
    description: str
    severity: str  # "breaking", "non-breaking", "unknown"
    old_signature: str = ""
    new_signature: str = ""


@dataclass(slots=True)
class ContractDiffResult:
    """Result of contract diff analysis."""

    changes: list[ContractChange]
    breaking_changes: int
    non_breaking_changes: int
    risk_score: float  # 0.0 - 1.0


class ContractDiffAnalyzer:
    """Analyzes contract/schema changes between versions."""

    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config

    def analyze(self, base_commit: str = "HEAD~1", head_commit: str = "HEAD") -> ContractDiffResult:
        """Analyze contract changes between two commits."""
        changes = []

        # Get changed Python files
        changed_files = self._get_changed_python_files(base_commit, head_commit)

        for file_path in changed_files:
            file_changes = self._analyze_file_changes(file_path, base_commit, head_commit)
            changes.extend(file_changes)

        breaking = sum(1 for c in changes if c.severity == "breaking")
        non_breaking = sum(1 for c in changes if c.severity == "non-breaking")

        # Risk score based on breaking changes
        total = breaking + non_breaking
        risk_score = breaking / max(total, 1) if total > 0 else 0.0

        return ContractDiffResult(
            changes=changes,
            breaking_changes=breaking,
            non_breaking_changes=non_breaking,
            risk_score=risk_score,
        )

    def _get_changed_python_files(self, base: str, head: str) -> list[str]:
        """Get Python files changed between commits."""
        try:
            output = subprocess.run(
                ["git", "diff", "--name-only", f"{base}..{head}", "*.py"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            return [f.strip() for f in output.splitlines() if f.strip()]
        except Exception:
            return []

    def _analyze_file_changes(self, file_path: str, base: str, head: str) -> list[ContractChange]:
        """Analyze contract changes in a single file."""
        changes = []

        try:
            # Get file content at both commits
            base_content = self._get_file_at_commit(file_path, base)
            head_content = self._get_file_at_commit(file_path, head)

            if not base_content or not head_content:
                return changes

            base_tree = ast.parse(base_content)
            head_tree = ast.parse(head_content)

            base_contracts = self._extract_contracts(base_tree, file_path)
            head_contracts = self._extract_contracts(head_tree, file_path)

            # Compare contracts
            changes.extend(self._compare_contracts(base_contracts, head_contracts, file_path))

        except Exception:
            pass

        return changes

    def _get_file_at_commit(self, file_path: str, commit: str) -> str | None:
        """Get file content at specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit}:{file_path}"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except Exception:
            return None

    def _extract_contracts(self, tree: ast.AST, file_path: str) -> dict[str, dict]:
        """Extract contracts (functions, classes, schemas) from AST."""
        contracts = {}
        visitor = ContractVisitor(file_path)
        visitor.visit(tree)
        for contract in visitor.contracts:
            contracts[contract["name"]] = contract
        return contracts

    def _compare_contracts(
        self,
        base: dict[str, dict],
        head: dict[str, dict],
        file_path: str,
    ) -> list[ContractChange]:
        """Compare contracts between two versions."""
        changes = []
        all_names = set(base.keys()) | set(head.keys())

        for name in all_names:
            if name in base and name not in head:
                changes.append(
                    ContractChange(
                        type="removed",
                        location=f"{file_path}::{name}",
                        description=f"Contract '{name}' was removed",
                        severity="breaking",
                        old_signature=base[name].get("signature", ""),
                    )
                )
            elif name not in base and name in head:
                changes.append(
                    ContractChange(
                        type="added",
                        location=f"{file_path}::{name}",
                        description=f"Contract '{name}' was added",
                        severity="non-breaking",
                        new_signature=head[name].get("signature", ""),
                    )
                )
            else:
                # Modified - check for breaking changes
                diff = self._diff_contracts(base[name], head[name])
                if diff:
                    changes.append(
                        ContractChange(
                            type="modified",
                            location=f"{file_path}::{name}",
                            description=diff["description"],
                            severity=diff["severity"],
                            old_signature=base[name].get("signature", ""),
                            new_signature=head[name].get("signature", ""),
                        )
                    )

        return changes

    def _diff_contracts(self, old: dict, new: dict) -> dict | None:
        """Compare two contract definitions."""
        # Function signature changes
        if old.get("type") == "function" and new.get("type") == "function":
            old_sig = old.get("signature", "")
            new_sig = new.get("signature", "")

            if old_sig != new_sig:
                # Check if breaking
                old_params = self._parse_params(old_sig)
                new_params = self._parse_params(new_sig)

                # Removed required params = breaking
                removed_required = set(old_params["required"]) - set(new_params["required"])
                # Added required params = breaking
                added_required = set(new_params["required"]) - set(old_params["required"])
                # Changed param types = potentially breaking
                type_changes = []
                for param in set(old_params["all"]) & set(new_params["all"]):
                    if old_params["types"].get(param) != new_params["types"].get(param):
                        type_changes.append(param)

                if removed_required or added_required:
                    return {
                        "description": f"Function signature changed: removed required={removed_required}, added required={added_required}, type changes={type_changes}",
                        "severity": "breaking",
                    }
                elif type_changes:
                    return {
                        "description": f"Function parameter types changed: {type_changes}",
                        "severity": "breaking",
                    }
                else:
                    # Only optional params added or defaults changed
                    return {
                        "description": f"Function signature modified (non-breaking): {old_sig} -> {new_sig}",
                        "severity": "non-breaking",
                    }

        # Class changes
        if old.get("type") == "class" and new.get("type") == "class":
            old_methods = set(old.get("methods", []))
            new_methods = set(new.get("methods", []))

            removed_methods = old_methods - new_methods
            if removed_methods:
                return {
                    "description": f"Class methods removed: {removed_methods}",
                    "severity": "breaking",
                }

            # Check for method signature changes
            for method in old_methods & new_methods:
                old_method = old.get("method_details", {}).get(method, {})
                new_method = new.get("method_details", {}).get(method, {})
                if old_method.get("signature") != new_method.get("signature"):
                    return {
                        "description": f"Method '{method}' signature changed",
                        "severity": "breaking",
                    }

        # Schema changes (Pydantic models, TypedDict, dataclasses)
        if old.get("type") in {"pydantic", "dataclass", "typeddict"} and new.get("type") in {
            "pydantic",
            "dataclass",
            "typeddict",
        }:
            old_fields = set(old.get("fields", []))
            new_fields = set(new.get("fields", []))

            removed_fields = old_fields - new_fields
            if removed_fields:
                return {
                    "description": f"Schema fields removed: {removed_fields}",
                    "severity": "breaking",
                }

            # Check field type changes
            for field in old_fields & new_fields:
                old_type = old.get("field_types", {}).get(field)
                new_type = new.get("field_types", {}).get(field)
                if old_type != new_type:
                    return {
                        "description": f"Schema field '{field}' type changed: {old_type} -> {new_type}",
                        "severity": "breaking",
                    }

        return None

    def _parse_params(self, signature: str) -> dict:
        """Parse function signature for parameters."""
        # Simplified parsing
        params = {"required": [], "optional": [], "all": [], "types": {}}
        # This is a placeholder - real implementation would use ast
        return params


class ContractVisitor(ast.NodeVisitor):
    """Extracts contracts from AST."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.contracts = []
        self._current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not self._current_class:  # Only top-level functions
            sig = self._get_signature(node)
            self.contracts.append(
                {
                    "name": node.name,
                    "type": "function",
                    "signature": sig,
                    "line": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                }
            )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_class = self._current_class
        self._current_class = node.name

        methods = []
        method_details = {}
        fields = []
        field_types = {}

        # Check for Pydantic/dataclass/TypedDict
        is_pydantic = any(
            "BaseModel" in ast.unparse(base) if hasattr(ast, "unparse") else "BaseModel" in str(base)
            for base in node.bases
        )
        is_dataclass = any(
            "dataclass" in ast.unparse(d) if hasattr(ast, "unparse") else "dataclass" in str(d)
            for d in node.decorator_list
        )

        contract_type = "class"
        if is_pydantic:
            contract_type = "pydantic"
        elif is_dataclass:
            contract_type = "dataclass"

        # Extract methods and fields
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._get_signature(item)
                methods.append(item.name)
                method_details[item.name] = {"signature": sig}
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Annotated assignment = field
                fields.append(item.target.id)
                if item.annotation:
                    field_types[item.target.id] = (
                        ast.unparse(item.annotation) if hasattr(ast, "unparse") else str(item.annotation)
                    )

        self.contracts.append(
            {
                "name": node.name,
                "type": contract_type,
                "methods": methods,
                "method_details": method_details,
                "fields": fields,
                "field_types": field_types,
                "line": node.lineno,
                "bases": [ast.unparse(b) if hasattr(ast, "unparse") else str(b) for b in node.bases],
            }
        )

        self.generic_visit(node)
        self._current_class = old_class

    def _get_signature(self, node: ast.FunctionDef) -> str:
        """Get function signature as string."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)}"
            args.append(arg_str)

        # Handle defaults
        defaults = node.args.defaults
        _num_defaults = len(defaults)
        _num_args = len(args)

        return f"({', '.join(args)})"




def analyze_contract_diff(
    project: Path,
    config: dict,
    base_commit: str = "HEAD~1",
    head_commit: str = "HEAD",
) -> ContractDiffResult:
    """Convenience function for contract diff analysis."""
    analyzer = ContractDiffAnalyzer(project, config)
    return analyzer.analyze(base_commit, head_commit)
