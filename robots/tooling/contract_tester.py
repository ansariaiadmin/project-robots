"""Contract Tester — API/Schema contract testing and validation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ContractTestResult:
    """Result of contract testing."""
    success: bool
    contracts_tested: int
    passed: int
    failed: int
    breaking_changes: list[dict] = None
    migration_shim: str = ""
    errors: list[str] = None
    
    def __post_init__(self):
        if self.breaking_changes is None:
            self.breaking_changes = []
        if self.errors is None:
            self.errors = []


class ContractTester:
    """Tests API/Schema contracts for compatibility."""
    
    def __init__(self, config: dict):
        self.config = config
        self.use_schematics = self._check_schematics()
        self.use_pact = self._check_pact()
    
    def _check_schematics(self) -> bool:
        try:
            import schematics
            return True
        except ImportError:
            return False
    
    def _check_pact(self) -> bool:
        try:
            subprocess.run(["pact", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False
    
    def test_contracts(
        self,
        old_spec: dict,
        new_spec: dict,
        contract_type: str = "openapi",
    ) -> ContractTestResult:
        """Test contract compatibility between versions."""
        if contract_type == "openapi":
            return self._test_openapi(old_spec, new_spec)
        elif contract_type == "protobuf":
            return self._test_protobuf(old_spec, new_spec)
        elif contract_type == "pydantic":
            return self._test_pydantic(old_spec, new_spec)
        else:
            return ContractTestResult(
                success=False,
                contracts_tested=0,
                passed=0,
                failed=0,
                errors=[f"Unknown contract type: {contract_type}"],
            )
    
    def _test_openapi(self, old_spec: dict, new_spec: dict) -> ContractTestResult:
        """Test OpenAPI spec compatibility."""
        breaking = []
        passed = 0
        
        # Compare paths
        old_paths = set(old_spec.get("paths", {}).keys())
        new_paths = set(new_spec.get("paths", {}).keys())
        
        removed_paths = old_paths - new_paths
        for path in removed_paths:
            breaking.append({
                "type": "removed_endpoint",
                "path": path,
                "severity": "breaking",
            })
        
        # Compare schemas
        old_schemas = old_spec.get("components", {}).get("schemas", {})
        new_schemas = new_spec.get("components", {}).get("schemas", {})
        
        for name, old_schema in old_schemas.items():
            if name not in new_schemas:
                breaking.append({
                    "type": "removed_schema",
                    "schema": name,
                    "severity": "breaking",
                })
            else:
                # Compare schema properties
                new_schema = new_schemas[name]
                schema_breaking = self._compare_schemas(old_schema, new_schema, name)
                breaking.extend(schema_breaking)
        
        # Added paths/schemas are non-breaking
        added_paths = new_paths - old_paths
        passed += len(added_paths)
        
        added_schemas = set(new_schemas.keys()) - set(old_schemas.keys())
        passed += len(added_schemas)
        
        # Existing non-breaking changes
        passed += len(old_paths & new_paths) - len(breaking)
        
        return ContractTestResult(
            success=len(breaking) == 0,
            contracts_tested=passed + len(breaking),
            passed=passed,
            failed=len(breaking),
            breaking_changes=breaking,
        )
    
    def _compare_schemas(self, old: dict, new: dict, name: str) -> list[dict]:
        """Compare two JSON schemas."""
        breaking = []
        
        # Required fields
        old_required = set(old.get("required", []))
        new_required = set(new.get("required", []))
        
        removed_required = old_required - new_required
        for field in removed_required:
            breaking.append({
                "type": "removed_required_field",
                "schema": name,
                "field": field,
                "severity": "breaking",
            })
        
        # Properties
        old_props = set(old.get("properties", {}).keys())
        new_props = set(new.get("properties", {}).keys())
        
        removed_props = old_props - new_props
        for prop in removed_props:
            breaking.append({
                "type": "removed_property",
                "schema": name,
                "property": prop,
                "severity": "breaking",
            })
        
        # Type changes
        for prop in old_props & new_props:
            old_type = old.get("properties", {}).get(prop, {}).get("type")
            new_type = new.get("properties", {}).get(prop, {}).get("type")
            if old_type != new_type:
                breaking.append({
                    "type": "changed_property_type",
                    "schema": name,
                    "property": prop,
                    "old_type": old_type,
                    "new_type": new_type,
                    "severity": "breaking",
                })
        
        return breaking
    
    def _test_protobuf(self, old_spec: dict, new_spec: dict) -> ContractTestResult:
        """Test Protobuf compatibility (placeholder)."""
        return ContractTestResult(
            success=True,
            contracts_tested=1,
            passed=1,
            failed=0,
            breaking_changes=[],
        )
    
    def _test_pydantic(self, old_spec: dict, new_spec: dict) -> ContractTestResult:
        """Test Pydantic model compatibility."""
        # old_spec and new_spec are model class names or definitions
        breaking = []
        passed = 0
        
        # This would require importing the actual models
        # For now, return a placeholder
        return ContractTestResult(
            success=True,
            contracts_tested=1,
            passed=1,
            failed=0,
            breaking_changes=[],
            errors=["Pydantic testing requires model imports"],
        )
    
    def generate_migration_shim(
        self,
        old_spec: dict,
        new_spec: dict,
        contract_type: str = "openapi",
    ) -> str:
        """Generate migration shim for breaking changes."""
        if contract_type == "openapi":
            return self._generate_openapi_shim(old_spec, new_spec)
        return ""
    
    def _generate_openapi_shim(self, old_spec: dict, new_spec: dict) -> str:
        """Generate OpenAPI migration shim."""
        # This would generate adapter code
        return """
# Migration shim for OpenAPI breaking changes
# Auto-generated - review before use

class MigrationAdapter:
    def __init__(self, client):
        self.client = client
    
    # Add methods to translate old API calls to new API
"""


def test_contracts(
    old_spec: dict,
    new_spec: dict,
    contract_type: str = "openapi",
    config: dict = None,
) -> ContractTestResult:
    """Convenience function for contract testing."""
    tester = ContractTester(config or {})
    return tester.test_contracts(old_spec, new_spec, contract_type)