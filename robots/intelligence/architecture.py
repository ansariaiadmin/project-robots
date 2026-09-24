"""Architectural layer detection and boundary mapping."""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class Layer:
    """Represents an architectural layer."""
    name: str
    patterns: list[str]
    description: str = ""
    strict: bool = True  # If True, violations are errors


@dataclass(slots=True)
class Boundary:
    """Represents a boundary between layers."""
    from_layer: str
    to_layer: str
    allowed: bool = True
    reason: str = ""


@dataclass(slots=True)
class ArchitectureModel:
    """Complete architectural model of the project."""
    layers: list[Layer]
    boundaries: list[Boundary]
    layer_of_file: dict[str, str] = field(default_factory=dict)
    violations: list[dict] = field(default_factory=list)


DEFAULT_LAYERS = [
    Layer(
        name="domain",
        patterns=["**/domain/**", "**/models/**", "**/entities/**", "**/core/**"],
        description="Business logic, entities, value objects",
        strict=True,
    ),
    Layer(
        name="application",
        patterns=["**/application/**", "**/services/**", "**/use_cases/**", "**/handlers/**"],
        description="Application services, use cases, command/query handlers",
        strict=True,
    ),
    Layer(
        name="infrastructure",
        patterns=["**/infrastructure/**", "**/adapters/**", "**/repositories/**", "**/external/**"],
        description="External adapters, database, API clients, frameworks",
        strict=True,
    ),
    Layer(
        name="presentation",
        patterns=["**/presentation/**", "**/api/**", "**/web/**", "**/controllers/**", "**/views/**", "**/cli/**"],
        description="HTTP handlers, CLI, GraphQL, UI components",
        strict=True,
    ),
    Layer(
        name="tests",
        patterns=["**/tests/**", "**/test_*.py", "**/*_test.py", "**/spec/**"],
        description="Test code",
        strict=False,
    ),
    Layer(
        name="shared",
        patterns=["**/shared/**", "**/common/**", "**/utils/**", "**/helpers/**"],
        description="Shared utilities, cross-cutting concerns",
        strict=False,
    ),
]


DEFAULT_BOUNDARIES = [
    # Domain is innermost - nothing should depend on outer layers
    Boundary("domain", "application", allowed=False, reason="Domain must not depend on application"),
    Boundary("domain", "infrastructure", allowed=False, reason="Domain must not depend on infrastructure"),
    Boundary("domain", "presentation", allowed=False, reason="Domain must not depend on presentation"),
    
    # Application can depend on domain, not on outer
    Boundary("application", "domain", allowed=True, reason="Application uses domain"),
    Boundary("application", "infrastructure", allowed=False, reason="Application must not depend on infrastructure"),
    Boundary("application", "presentation", allowed=False, reason="Application must not depend on presentation"),
    
    # Infrastructure can depend on domain and application
    Boundary("infrastructure", "domain", allowed=True, reason="Infrastructure implements domain"),
    Boundary("infrastructure", "application", allowed=True, reason="Infrastructure implements application"),
    Boundary("infrastructure", "presentation", allowed=False, reason="Infrastructure must not depend on presentation"),
    
    # Presentation can depend on all inner layers
    Boundary("presentation", "domain", allowed=True, reason="Presentation uses domain"),
    Boundary("presentation", "application", allowed=True, reason="Presentation uses application"),
    Boundary("presentation", "infrastructure", allowed=True, reason="Presentation uses infrastructure"),
    
    # Tests can depend on anything
    Boundary("tests", "domain", allowed=True, reason="Tests verify domain"),
    Boundary("tests", "application", allowed=True, reason="Tests verify application"),
    Boundary("tests", "infrastructure", allowed=True, reason="Tests verify infrastructure"),
    Boundary("tests", "presentation", allowed=True, reason="Tests verify presentation"),
    
    # Shared can be used by anyone, but shouldn't depend on specific layers
    Boundary("shared", "domain", allowed=False, reason="Shared must not depend on domain"),
    Boundary("shared", "application", allowed=False, reason="Shared must not depend on application"),
    Boundary("shared", "infrastructure", allowed=False, reason="Shared must not depend on infrastructure"),
    Boundary("shared", "presentation", allowed=False, reason="Shared must not depend on presentation"),
]


class ArchitectureDetector:
    """Detects architectural layers and validates boundaries."""
    
    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.custom_layers = self._load_custom_layers()
        self.custom_boundaries = self._load_custom_boundaries()
    
    def _load_custom_layers(self) -> list[Layer]:
        """Load custom layers from config."""
        layers = list(DEFAULT_LAYERS)
        for layer_config in self.config.get("architecture", {}).get("layers", []):
            layers.append(Layer(
                name=layer_config["name"],
                patterns=layer_config.get("patterns", []),
                description=layer_config.get("description", ""),
                strict=layer_config.get("strict", True),
            ))
        return layers
    
    def _load_custom_boundaries(self) -> list[Boundary]:
        """Load custom boundaries from config."""
        boundaries = list(DEFAULT_BOUNDARIES)
        for boundary_config in self.config.get("architecture", {}).get("boundaries", []):
            boundaries.append(Boundary(
                from_layer=boundary_config["from"],
                to_layer=boundary_config["to"],
                allowed=boundary_config.get("allowed", True),
                reason=boundary_config.get("reason", ""),
            ))
        return boundaries
    
    def detect(self, import_graph: dict) -> ArchitectureModel:
        """Detect architecture from import graph."""
        model = ArchitectureModel(
            layers=self.custom_layers,
            boundaries=self.custom_boundaries,
        )
        
        # Assign each file to a layer
        for file_path in import_graph:
            model.layer_of_file[file_path] = self._classify_file(file_path)
        
        # Check boundaries using import graph
        model.violations = self._check_boundaries(import_graph, model.layer_of_file)
        
        return model
    
    def _classify_file(self, file_path: str) -> str:
        """Classify a file into an architectural layer."""
        for layer in self.custom_layers:
            for pattern in layer.patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    return layer.name
        # Default to shared for unclassified
        return "shared"
    
    def _check_boundaries(
        self,
        import_graph: dict,
        layer_of_file: dict[str, str],
    ) -> list[dict]:
        """Check architectural boundary violations."""
        violations = []
        
        # Build boundary lookup
        boundary_map = {}
        for b in self.custom_boundaries:
            boundary_map[(b.from_layer, b.to_layer)] = b
        
        for importer, node in import_graph.items():
            from_layer = layer_of_file.get(importer, "shared")
            
            for edge in node.imports:
                imported = edge.imported
                if imported not in layer_of_file:
                    continue  # External dependency
                to_layer = layer_of_file[imported]
                
                if from_layer == to_layer:
                    continue  # Same layer is fine
                
                boundary = boundary_map.get((from_layer, to_layer))
                if boundary and not boundary.allowed:
                    violations.append({
                        "importer": importer,
                        "imported": imported,
                        "from_layer": from_layer,
                        "to_layer": to_layer,
                        "reason": boundary.reason,
                        "line": edge.line,
                        "severity": "error" if self._layer_strict(from_layer) else "warning",
                    })
        
        return violations
    
    def _layer_strict(self, layer_name: str) -> bool:
        for layer in self.custom_layers:
            if layer.name == layer_name:
                return layer.strict
        return True
    
    def get_layer_metrics(self, model: ArchitectureModel) -> dict[str, dict]:
        """Compute metrics per layer."""
        metrics = {}
        for layer in self.custom_layers:
            files = [f for f, l in model.layer_of_file.items() if l == layer.name]
            violations = [v for v in model.violations if v["from_layer"] == layer.name]
            metrics[layer.name] = {
                "file_count": len(files),
                "violation_count": len(violations),
                "coupling": self._compute_coupling(files, import_graph, layer_of_file),
            }
        return metrics
    
    def _compute_coupling(
        self,
        files: list[str],
        import_graph: dict,
        layer_of_file: dict[str, str],
    ) -> dict[str, int]:
        """Compute coupling between layers."""
        coupling = defaultdict(int)
        for file in files:
            if file in import_graph:
                for edge in import_graph[file].imports:
                    if edge.imported in layer_of_file:
                        to_layer = layer_of_file[edge.imported]
                        if to_layer != layer_of_file[file]:
                            coupling[to_layer] += 1
        return dict(coupling)


def detect_architecture(
    project: Path,
    config: dict,
    import_graph: dict,
) -> ArchitectureModel:
    """Convenience function to detect architecture."""
    detector = ArchitectureDetector(project, config)
    return detector.detect(import_graph)