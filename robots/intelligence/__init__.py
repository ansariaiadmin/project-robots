"""Repository Intelligence Package."""

from robots.intelligence.graph_builder import build_import_graph, ImportGraphBuilder, ModuleNode, ImportEdge
from robots.intelligence.architecture import detect_architecture, ArchitectureDetector, ArchitectureModel, Layer, Boundary
from robots.intelligence.coupling import analyze_coupling, CouplingAnalyzer, CouplingMatrix, CouplingEntry
from robots.intelligence.invariants import extract_invariants, InvariantExtractor, InvariantRegistry, Invariant
from robots.intelligence.debt_index import analyze_debt, DebtAnalyzer, DebtIndex, FileMetrics
from robots.intelligence.core import build_repository_intelligence, RepositoryIntelligence, get_intelligence_summary
from robots.intelligence.robot import IntelligenceRobot

__all__ = [
    "build_import_graph", "ImportGraphBuilder", "ModuleNode", "ImportEdge",
    "detect_architecture", "ArchitectureDetector", "ArchitectureModel", "Layer", "Boundary",
    "analyze_coupling", "CouplingAnalyzer", "CouplingMatrix", "CouplingEntry",
    "extract_invariants", "InvariantExtractor", "InvariantRegistry", "Invariant",
    "analyze_debt", "DebtAnalyzer", "DebtIndex", "FileMetrics",
    "build_repository_intelligence", "RepositoryIntelligence", "get_intelligence_summary",
    "IntelligenceRobot",
]