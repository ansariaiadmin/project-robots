"""Observability Hooks — Metrics, traces, and structured logs for production validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class MetricDefinition:
    """Defines a metric to emit."""
    name: str
    type: str  # "counter", "gauge", "histogram", "summary"
    description: str
    labels: list[str] = field(default_factory=list)
    unit: str = ""


@dataclass(slots=True)
class TraceDefinition:
    """Defines a trace span."""
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    parent: str | None = None


@dataclass(slots=True)
class LogDefinition:
    """Defines a structured log entry."""
    level: str  # "debug", "info", "warning", "error"
    message: str
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ObservabilityHooks:
    """Collection of observability hooks for a change."""
    metrics: list[MetricDefinition] = field(default_factory=list)
    traces: list[TraceDefinition] = field(default_factory=list)
    logs: list[LogDefinition] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)  # Alert rules
    dashboards: list[dict] = field(default_factory=list)  # Dashboard references
    
    def to_dict(self) -> dict:
        return {
            "metrics": [{"name": m.name, "type": m.type, "description": m.description, "labels": m.labels, "unit": m.unit} for m in self.metrics],
            "traces": [{"name": t.name, "attributes": t.attributes, "parent": t.parent} for t in self.traces],
            "logs": [{"level": l.level, "message": l.message, "fields": l.fields} for l in self.logs],
            "alerts": self.alerts,
            "dashboards": self.dashboards,
        }
    
    @classmethod
    def from_plan(cls, plan: dict) -> "ObservabilityHooks":
        """Generate observability hooks from a plan."""
        hooks = cls()
        
        changed_files = plan.get("changed_files", [])
        steps = plan.get("steps", [])
        
        # Add metrics for each changed file
        for file_path in changed_files:
            base_name = file_path.replace("/", "_").replace(".", "_")
            hooks.metrics.extend([
                MetricDefinition(
                    name=f"{base_name}_calls_total",
                    type="counter",
                    description=f"Total calls to {file_path}",
                    labels=["status"],
                ),
                MetricDefinition(
                    name=f"{base_name}_duration_seconds",
                    type="histogram",
                    description=f"Latency of {file_path} operations",
                    labels=["operation"],
                    unit="seconds",
                ),
                MetricDefinition(
                    name=f"{base_name}_errors_total",
                    type="counter",
                    description=f"Errors in {file_path}",
                    labels=["error_type"],
                ),
            ])
        
        # Add traces for key operations
        for step in steps:
            action = step.get("action", "")
            target = step.get("target", "")
            if action in ("execute", "call", "query", "mutation"):
                hooks.traces.append(TraceDefinition(
                    name=f"{action}.{target}",
                    attributes={"component": target, "action": action},
                ))
        
        # Add structured logs for key events
        hooks.logs.extend([
            LogDefinition(
                level="info",
                message="Change deployed",
                fields={"plan_id": plan.get("decision_id", ""), "files": str(changed_files)},
            ),
            LogDefinition(
                level="info",
                message="Health check passed",
                fields={"component": "system"},
            ),
        ])
        
        # Add alert rules for critical changes
        if any("critical" in str(s).lower() for s in steps):
            hooks.alerts.append({
                "name": "high_error_rate",
                "condition": "rate(errors_total[5m]) > 0.1",
                "severity": "critical",
                "description": "Error rate exceeded threshold after deployment",
            })
        
        return hooks
    
    def to_prometheus_rules(self) -> str:
        """Generate Prometheus alerting rules."""
        lines = ["groups:"]
        for alert in self.alerts:
            lines.extend([
                f"  - name: {alert.get('name', 'unknown')}",
                f"    rules:",
                f"      - alert: {alert.get('name', 'UnknownAlert')}",
                f"        expr: {alert.get('condition', 'true')}",
                f"        for: 2m",
                f"        labels:",
                f"          severity: {alert.get('severity', 'warning')}",
                f"        annotations:",
                f"          summary: {alert.get('description', 'Alert triggered')}",
                f"          description: {alert.get('description', '')}",
            ])
        return "\n".join(lines)
    
    def to_otel_instrumentation(self) -> str:
        """Generate OpenTelemetry instrumentation code snippet."""
        nl = "\n"
        metrics_code = nl.join(f'{m.name} = meter.create_{m.type}("{m.name}", description="{m.description}", unit="{m.unit}")' for m in self.metrics)
        traces_code = nl.join(f'with tracer.start_as_current_span("{t.name}") as span:\n    span.set_attributes({t.attributes})' for t in self.traces)
        logs_code = nl.join(f'logger.{l.level}("{l.message}", extra={l.fields})' for l in self.logs)
        
        return f"""
# OpenTelemetry instrumentation for this change
# Auto-generated - integrate into application

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
{metrics_code}

# Traces
{traces_code}

# Structured logging
import logging
logger = logging.getLogger(__name__)
{logs_code}
"""


def create_observability_hooks(plan: dict) -> ObservabilityHooks:
    """Convenience function to create observability hooks from a plan."""
    return ObservabilityHooks.from_plan(plan)