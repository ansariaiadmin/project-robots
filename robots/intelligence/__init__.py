"""Repository Intelligence Package."""

from robots.intelligence.architecture import (
    ArchitectureDetector,
    ArchitectureModel,
    Boundary,
    Layer,
    detect_architecture,
)
from robots.intelligence.core import RepositoryIntelligence, build_repository_intelligence, get_intelligence_summary
from robots.intelligence.coupling import CouplingAnalyzer, CouplingEntry, CouplingMatrix, analyze_coupling
from robots.intelligence.debt_index import DebtAnalyzer, DebtIndex, FileMetrics, analyze_debt
from robots.intelligence.graph_builder import ImportEdge, ImportGraphBuilder, ModuleNode, build_import_graph
from robots.intelligence.invariants import Invariant, InvariantExtractor, InvariantRegistry, extract_invariants
from robots.intelligence.robot import IntelligenceRobot

__all__ = [
    "build_import_graph",
    "ImportGraphBuilder",
    "ModuleNode",
    "ImportEdge",
    "detect_architecture",
    "ArchitectureDetector",
    "ArchitectureModel",
    "Layer",
    "Boundary",
    "analyze_coupling",
    "CouplingAnalyzer",
    "CouplingMatrix",
    "CouplingEntry",
    "extract_invariants",
    "InvariantExtractor",
    "InvariantRegistry",
    "Invariant",
    "analyze_debt",
    "DebtAnalyzer",
    "DebtIndex",
    "FileMetrics",
    "build_repository_intelligence",
    "RepositoryIntelligence",
    "get_intelligence_summary",
    "IntelligenceRobot",
]
