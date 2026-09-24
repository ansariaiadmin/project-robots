"""Repository Intelligence core functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .graph_builder import build_import_graph, ModuleNode
from .architecture import detect_architecture, ArchitectureModel
from .coupling import analyze_coupling, CouplingMatrix
from .invariants import extract_invariants, InvariantRegistry
from .debt_index import analyze_debt, DebtIndex


@dataclass(slots=True)
class RepositoryIntelligence:
    """Complete repository intelligence model."""
    import_graph: dict[str, ModuleNode]
    architecture: ArchitectureModel
    coupling: CouplingMatrix
    invariants: InvariantRegistry
    debt_index: DebtIndex
    generated_at: str = field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for caching."""
        return {
            "import_graph": {
                path: {
                    "path": node.path,
                    "imports": [
                        {"importer": e.importer, "imported": e.imported, "type": e.import_type, "line": e.line}
                        for e in node.imports
                    ],
                    "imported_by": node.imported_by,
                    "symbols": node.symbols,
                }
                for path, node in self.import_graph.items()
            },
            "architecture": {
                "layers": [
                    {"name": l.name, "patterns": l.patterns, "description": l.description, "strict": l.strict}
                    for l in self.architecture.layers
                ],
                "boundaries": [
                    {"from": b.from_layer, "to": b.to_layer, "allowed": b.allowed, "reason": b.reason}
                    for b in self.architecture.boundaries
                ],
                "layer_of_file": self.architecture.layer_of_file,
                "violations": self.architecture.violations,
            },
            "coupling": {
                "entries": {
                    f"{k[0]}|{k[1]}": {"file_a": v.file_a, "file_b": v.file_b, "count": v.count, "last_seen": v.last_seen, "avg_days_between": v.avg_days_between}
                    for k, v in self.coupling.entries.items()
                },
                "file_frequency": self.coupling.file_frequency,
                "window_start": self.coupling.window_start,
                "window_end": self.coupling.window_end,
                "total_commits": self.coupling.total_commits,
            },
            "invariants": {
                "invariants": {
                    k: {"id": v.id, "type": v.type, "description": v.description, "location": v.location, "validator": v.validator, "severity": v.severity, "metadata": v.metadata}
                    for k, v in self.invariants.invariants.items()
                }
            },
            "debt_index": {
                "file_metrics": {
                    k: {"path": v.path, "lines": v.lines, "complexity": v.complexity, "functions": v.functions, "classes": v.classes, "max_nesting": v.max_nesting, "age_days": v.age_days, "churn": v.churn, "ownership": v.ownership, "duplication_score": v.duplication_score}
                    for k, v in self.debt_index.file_metrics.items()
                },
                "summary": self.debt_index.summary,
                "hotspots": self.debt_index.hotspots,
            },
            "generated_at": self.generated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RepositoryIntelligence":
        """Deserialize from dictionary."""
        # Reconstruct import graph
        import_graph = {}
        for path, node_data in data.get("import_graph", {}).items():
            from .graph_builder import ModuleNode, ImportEdge
            imports = [ImportEdge(**e) for e in node_data.get("imports", [])]
            node = ModuleNode(
                path=node_data["path"],
                imports=imports,
                imported_by=node_data.get("imported_by", []),
                symbols=node_data.get("symbols", {}),
            )
            import_graph[path] = node
        
        # Reconstruct architecture
        from .architecture import ArchitectureModel, Layer, Boundary
        arch_data = data.get("architecture", {})
        architecture = ArchitectureModel(
            layers=[Layer(**l) for l in arch_data.get("layers", [])],
            boundaries=[Boundary(**b) for b in arch_data.get("boundaries", [])],
            layer_of_file=arch_data.get("layer_of_file", {}),
            violations=arch_data.get("violations", []),
        )
        
        # Reconstruct coupling
        from .coupling import CouplingMatrix, CouplingEntry
        coup_data = data.get("coupling", {})
        coupling = CouplingMatrix(
            entries={
                tuple(k.split("|")): CouplingEntry(**v)
                for k, v in coup_data.get("entries", {}).items()
            },
            file_frequency=coup_data.get("file_frequency", {}),
            window_start=coup_data.get("window_start", ""),
            window_end=coup_data.get("window_end", ""),
            total_commits=coup_data.get("total_commits", 0),
        )
        
        # Reconstruct invariants
        from .invariants import InvariantRegistry, Invariant
        inv_data = data.get("invariants", {})
        invariants = InvariantRegistry(
            invariants={k: Invariant(**v) for k, v in inv_data.get("invariants", {}).items()}
        )
        
        # Reconstruct debt index
        from .debt_index import DebtIndex, FileMetrics
        debt_data = data.get("debt_index", {})
        debt_index = DebtIndex(
            file_metrics={k: FileMetrics(**v) for k, v in debt_data.get("file_metrics", {}).items()},
            summary=debt_data.get("summary", {}),
            hotspots=debt_data.get("hotspots", []),
        )
        
        return cls(
            import_graph=import_graph,
            architecture=architecture,
            coupling=coupling,
            invariants=invariants,
            debt_index=debt_index,
            generated_at=data.get("generated_at", ""),
        )


def build_repository_intelligence(
    project: Path,
    config: dict,
    use_cache: bool = True,
) -> RepositoryIntelligence:
    """Build complete repository intelligence model."""
    from robots.common import cache_dir, write_json, slug
    import json
    
    cache_path = cache_dir(project, "intelligence") / "latest.json"
    
    # Try cache first
    if use_cache and cache_path.exists():
        try:
            with cache_path.open() as f:
                cached = json.load(f)
            # Check if cache is fresh (less than 1 hour old)
            import time
            if time.time() - cache_path.stat().st_mtime < 3600:
                return RepositoryIntelligence.from_dict(cached)
        except Exception:
            pass
    
    # Build fresh
    import_graph = build_import_graph(project, config)
    architecture = detect_architecture(project, config, import_graph)
    coupling = analyze_coupling(project, config)
    invariants = extract_invariants(project, config)
    debt_index = analyze_debt(project, config, import_graph)
    
    intelligence = RepositoryIntelligence(
        import_graph=import_graph,
        architecture=architecture,
        coupling=coupling,
        invariants=invariants,
        debt_index=debt_index,
    )
    
    # Cache result
    try:
        write_json(project, "intelligence", "latest.json", intelligence.to_dict())
    except Exception:
        pass
    
    return intelligence


def get_intelligence_summary(intelligence: RepositoryIntelligence) -> dict:
    """Get a concise summary for context packing."""
    return {
        "modules": len(intelligence.import_graph),
        "import_edges": sum(len(n.imports) for n in intelligence.import_graph.values()),
        "cycles": len([c for c in intelligence.architecture.violations if "cycle" in str(c).lower()]),
        "architecture_violations": len(intelligence.architecture.violations),
        "coupling_pairs": len(intelligence.coupling.entries),
        "top_coupled": intelligence.coupling.get_hotspots(intelligence.coupling, 5) if hasattr(intelligence.coupling, 'get_hotspots') else [],
        "invariants": len(intelligence.invariants.invariants),
        "debt_hotspots": intelligence.debt_index.hotspots[:5],
        "debt_summary": intelligence.debt_index.summary,
    }