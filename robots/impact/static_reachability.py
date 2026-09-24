"""Static reachability analysis for impact simulation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from robots.intelligence import RepositoryIntelligence, build_repository_intelligence


@dataclass(slots=True)
class ReachabilityResult:
    """Result of reachability analysis."""

    affected_files: set[str]
    affected_symbols: set[str]
    blast_radius: int  # Number of files transitively affected
    entry_points: list[str]  # Files directly changed
    paths: dict[str, list[str]]  # file -> path from entry point


class ReachabilityAnalyzer:
    """Analyzes static reachability from changed files."""

    def __init__(self, intelligence: RepositoryIntelligence):
        self.intelligence = intelligence
        self.graph = intelligence.import_graph

    def analyze(self, changed_files: list[str]) -> ReachabilityResult:
        """Compute all files reachable from changed files."""
        affected = set()
        affected_symbols = set()
        paths = {}
        entry_points = []

        for changed in changed_files:
            if changed not in self.graph:
                continue
            entry_points.append(changed)
            # BFS from changed file through reverse dependencies (dependents)
            visited = set()
            queue = deque([(changed, [changed])])

            while queue:
                current, path = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                affected.add(current)
                paths[current] = path

                # Add symbols from this file
                if current in self.graph:
                    affected_symbols.update(self.graph[current].symbols.keys())

                # Traverse to dependents (files that import this)
                for dependent in self.graph[current].imported_by:
                    if dependent not in visited:
                        queue.append((dependent, path + [dependent]))

        return ReachabilityResult(
            affected_files=affected,
            affected_symbols=affected_symbols,
            blast_radius=len(affected),
            entry_points=entry_points,
            paths=paths,
        )

    def analyze_symbol(self, symbol: str) -> ReachabilityResult:
        """Find all files that use a specific symbol."""
        affected = set()
        paths = {}

        # Find files defining this symbol
        definers = []
        for path, node in self.graph.items():
            if symbol in node.symbols:
                definers.append(path)

        for definer in definers:
            # BFS to dependents
            visited = set()
            queue = deque([(definer, [definer])])

            while queue:
                current, path = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                affected.add(current)
                paths[current] = path

                for dependent in self.graph[current].imported_by:
                    if dependent not in visited:
                        queue.append((dependent, path + [dependent]))

        return ReachabilityResult(
            affected_files=affected,
            affected_symbols={symbol},
            blast_radius=len(affected),
            entry_points=definers,
            paths=paths,
        )

    def compute_coupling_impact(self, changed_files: list[str]) -> dict[str, float]:
        """Compute impact scores based on historical coupling."""
        # Use the coupling analyzer from the intelligence module

        # The intelligence has the coupling matrix but not the analyzer
        # We need to recreate the analyzer with the project path
        # Since we don't have the project path here, we'll use the coupling matrix directly
        coupling = self.intelligence.coupling

        impact_scores = {}
        for changed in changed_files:
            # Find files coupled to this one
            for (f1, f2), entry in coupling.entries.items():
                if f1 == changed:
                    if f2 not in changed_files:
                        impact_scores[f2] = impact_scores.get(f2, 0) + entry.count
                elif f2 == changed:
                    if f1 not in changed_files:
                        impact_scores[f1] = impact_scores.get(f1, 0) + entry.count

        # Normalize
        max_score = max(impact_scores.values()) if impact_scores else 1
        return {f: s / max_score for f, s in impact_scores.items()}


def analyze_reachability(
    project: Path,
    config: dict,
    changed_files: list[str],
) -> ReachabilityResult:
    """Convenience function for reachability analysis."""
    intelligence = build_repository_intelligence(project, config)
    analyzer = ReachabilityAnalyzer(intelligence)
    return analyzer.analyze(changed_files)
