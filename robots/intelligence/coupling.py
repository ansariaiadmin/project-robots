"""Change coupling analysis from git history."""

from __future__ import annotations

import fnmatch
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(slots=True)
class CouplingEntry:
    """Represents a co-change relationship between two files."""

    file_a: str
    file_b: str
    count: int
    last_seen: str
    avg_days_between: float


@dataclass(slots=True)
class CouplingMatrix:
    """Complete change coupling matrix."""

    entries: dict[tuple[str, str], CouplingEntry] = field(default_factory=dict)
    file_frequency: dict[str, int] = field(default_factory=dict)
    window_start: str = ""
    window_end: str = ""
    total_commits: int = 0


class CouplingAnalyzer:
    """Analyzes git history to build change coupling matrix."""

    def __init__(self, project: Path, config: dict):
        self.project = project
        self.config = config
        self.window_days = config.get("intelligence", {}).get("coupling_window_days", 90)
        self.min_coupling = config.get("intelligence", {}).get("min_coupling_threshold", 2)

    def analyze(self) -> CouplingMatrix:
        """Build coupling matrix from git history."""
        since = (datetime.now() - timedelta(days=self.window_days)).strftime("%Y-%m-%d")

        # Get commit history with file changes
        try:
            output = subprocess.run(
                ["git", "log", f"--since={since}", "--pretty=format:%H", "--name-only", "-z"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return CouplingMatrix()

        matrix = CouplingMatrix(
            window_start=since,
            window_end=datetime.now().strftime("%Y-%m-%d"),
        )

        # Parse git log output
        commits = self._parse_git_log(output)
        matrix.total_commits = len(commits)

        # Build coupling from commits
        for commit_files in commits:
            # Filter to tracked files only
            tracked = [f for f in commit_files if self._is_tracked(f)]
            if len(tracked) < 2:
                continue

            # Update file frequency
            for f in tracked:
                matrix.file_frequency[f] = matrix.file_frequency.get(f, 0) + 1

            # Update pair couplings
            for i, f1 in enumerate(tracked):
                for f2 in tracked[i + 1 :]:
                    key = tuple(sorted((f1, f2)))
                    entry = matrix.entries.get(key)
                    if entry:
                        entry.count += 1
                        entry.last_seen = datetime.now().isoformat()
                    else:
                        matrix.entries[key] = CouplingEntry(
                            file_a=f1,
                            file_b=f2,
                            count=1,
                            last_seen=datetime.now().isoformat(),
                            avg_days_between=0.0,
                        )

        # Compute average days between co-changes
        self._compute_avg_days(matrix, commits)

        # Filter by minimum threshold
        matrix.entries = {k: v for k, v in matrix.entries.items() if v.count >= self.min_coupling}

        return matrix

    def _parse_git_log(self, output: str) -> list[list[str]]:
        """Parse git log --name-only -z output."""
        commits = []
        current_files = []

        parts = output.split("\0")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part) == 40 and all(c in "0123456789abcdef" for c in part):
                # Commit hash
                if current_files:
                    commits.append(current_files)
                current_files = []
            else:
                # File path
                current_files.append(part)

        if current_files:
            commits.append(current_files)

        return commits

    def _is_tracked(self, file_path: str) -> bool:
        """Check if file is tracked (not ignored)."""
        ignores = self.config.get("ignore", [])
        return not any(fnmatch.fnmatch(file_path, p) for p in ignores)

    def _compute_avg_days(
        self,
        matrix: CouplingMatrix,
        commits: list[list[str]],
    ) -> None:
        """Compute average days between co-changes for each pair."""
        # Build commit date map
        try:
            dates_output = subprocess.run(
                ["git", "log", f"--since={matrix.window_start}", "--pretty=format:%H %ct", "-z"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return

        commit_dates = {}
        for line in dates_output.strip().split("\0"):
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commit_dates[parts[0]] = int(parts[1])

        # For each pair, compute intervals
        pair_dates = defaultdict(list)
        for commit_hash, files in zip(commit_dates.keys(), commits):
            tracked = [f for f in files if self._is_tracked(f)]
            for i, f1 in enumerate(tracked):
                for f2 in tracked[i + 1 :]:
                    key = tuple(sorted((f1, f2)))
                    if key in matrix.entries:
                        pair_dates[key].append(commit_dates[commit_hash])

        for key, dates in pair_dates.items():
            if len(dates) > 1:
                dates.sort()
                intervals = [(dates[i] - dates[i - 1]) / 86400 for i in range(1, len(dates))]
                matrix.entries[key].avg_days_between = sum(intervals) / len(intervals)

    def get_coupled_files(self, matrix: CouplingMatrix, file: str, threshold: int = 2) -> list[tuple[str, int]]:
        """Get files coupled to the given file, sorted by coupling strength."""
        coupled = []
        for (f1, f2), entry in matrix.entries.items():
            if f1 == file:
                coupled.append((f2, entry.count))
            elif f2 == file:
                coupled.append((f1, entry.count))
        return sorted(coupled, key=lambda x: x[1], reverse=True)

    def get_hotspots(self, matrix: CouplingMatrix, top_n: int = 10) -> list[tuple[str, int]]:
        """Get most frequently changed files."""
        return sorted(matrix.file_frequency.items(), key=lambda x: x[1], reverse=True)[:top_n]




def analyze_coupling(project: Path, config: dict) -> CouplingMatrix:
    """Convenience function to analyze coupling."""
    analyzer = CouplingAnalyzer(project, config)
    return analyzer.analyze()
