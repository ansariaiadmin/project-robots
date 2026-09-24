"""Robot Protocol — Composable, testable robot interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RobotResult:
    """Standardized robot output."""

    ok: bool
    summary: dict
    output: Path
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True, slots=True)
class Plan:
    """Execution plan with metadata."""

    name: str
    steps: list[dict]
    risk_score: float = 0.0
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@runtime_checkable
class Robot(Protocol):
    """Base protocol for all robots."""

    name: str
    version: int

    def inspect(self, project: Path, config: dict) -> RobotResult: ...
    def plan(self, project: Path, config: dict) -> Plan: ...
    def execute(self, project: Path, plan: Plan) -> RobotResult: ...


class BaseRobot(ABC):
    """Abstract base with common utilities."""

    name: str = "base"
    version: int = 1

    @abstractmethod
    def inspect(self, project: Path, config: dict) -> RobotResult:
        pass

    @abstractmethod
    def plan(self, project: Path, config: dict) -> Plan:
        pass

    @abstractmethod
    def execute(self, project: Path, plan: Plan) -> RobotResult:
        pass


ROBOT_REGISTRY: dict[str, Robot] = {}


def register_robot(robot: Robot) -> None:
    """Register a robot implementation."""
    ROBOT_REGISTRY[robot.name] = robot


def get_robot(name: str) -> Robot | None:
    """Retrieve robot by name."""
    return ROBOT_REGISTRY.get(name)


def list_robots() -> list[str]:
    """List all registered robot names."""
    return sorted(ROBOT_REGISTRY.keys())
