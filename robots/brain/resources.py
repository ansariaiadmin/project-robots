"""Resources — host load snapshots and throttling decisions (stdlib only)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class HostSnapshot:
    """Point-in-time host load readings (None where unavailable)."""

    cpu_count: int = 4
    load_1m: float | None = None
    load_per_cpu: float | None = None
    mem_available_mb: int | None = None
    procs: int | None = None


@dataclass(slots=True)
class ThrottleDecision:
    """Throttling verdict for heavy local work."""

    overloaded: bool = False
    max_workers: int = 1
    num_predict_cap: int | None = None
    force_shallow: bool = False
    reasons: list[str] = field(default_factory=list)
    snapshot: HostSnapshot = field(default_factory=HostSnapshot)


def snapshot() -> HostSnapshot:
    """Read host load (Linux /proc preferred, graceful elsewhere)."""
    cpu = os.cpu_count() or 4
    load_1m: float | None = None
    try:
        load_1m = float(os.getloadavg()[0])
    except (OSError, AttributeError):
        load_1m = None
    mem_mb: int | None = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    mem_mb = int(line.split()[1]) // 1024
                    break
    except (OSError, ValueError, IndexError):
        mem_mb = None
    procs: int | None = None
    try:
        procs = sum(1 for entry in os.listdir("/proc") if entry.isdigit())
    except OSError:
        procs = None
    per_cpu = (load_1m / cpu) if load_1m is not None and cpu > 0 else None
    return HostSnapshot(
        cpu_count=cpu, load_1m=load_1m, load_per_cpu=per_cpu,
        mem_available_mb=mem_mb, procs=procs,
    )


def check(config: dict | None = None, snap: HostSnapshot | None = None) -> ThrottleDecision:
    """Decide throttling. Pure apart from the default live snapshot.

    Reserves cores for neighbor projects; degrades to single-worker plus
    capped generation length and shallow verification under load.
    """
    snap = snap or snapshot()
    throttle = {}
    if isinstance(config, dict):
        raw = config.get("throttling", {})
        if isinstance(raw, dict):
            throttle = raw
    try:
        reserve = max(0, int(throttle.get("reserve_cores", 2)))
    except (TypeError, ValueError):
        reserve = 2
    try:
        cap = max(1, int(throttle.get("max_workers", 4)))
    except (TypeError, ValueError):
        cap = 4
    try:
        max_load = float(throttle.get("max_load_per_cpu", 0.75))
    except (TypeError, ValueError):
        max_load = 0.75
    try:
        min_mem = int(throttle.get("min_mem_mb", 1024))
    except (TypeError, ValueError):
        min_mem = 1024
    try:
        predict_cap = max(64, int(throttle.get("throttle_num_predict", 256)))
    except (TypeError, ValueError):
        predict_cap = 256

    workers = max(1, min(snap.cpu_count - reserve, cap))
    reasons: list[str] = [f"reserved {reserve} cores for neighbors"]
    overloaded = False
    if snap.load_per_cpu is not None and snap.load_per_cpu > max_load:
        overloaded = True
        workers = 1
        reasons.append(f"load {snap.load_per_cpu:.2f}/cpu exceeds {max_load:.2f}")
    elif snap.load_per_cpu is not None and snap.load_per_cpu > max_load - 0.25:
        workers = min(workers, 2)
        reasons.append(f"load {snap.load_per_cpu:.2f}/cpu elevated; capped workers")
    if snap.mem_available_mb is not None and snap.mem_available_mb < min_mem:
        overloaded = True
        workers = 1
        reasons.append(f"memory {snap.mem_available_mb}MB below {min_mem}MB")
    return ThrottleDecision(
        overloaded=overloaded,
        max_workers=workers,
        num_predict_cap=predict_cap if overloaded else None,
        force_shallow=overloaded,
        reasons=reasons,
        snapshot=snap,
    )
