"""Ledger — append-only SQLite record of compute debt vs value produced.

Lives strictly under central ``.cache/sovereignty/`` (never in a target
repo). Append-only by design: this module exposes INSERT and SELECT only,
no UPDATE or DELETE paths.
"""

from __future__ import annotations

import atexit
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# Energy valuation constants (configurable via config["sovereignty"])
CPU_WATTS_DEFAULT = 65.0
ENERGY_USD_PER_KWH = 0.15

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL,"
    " project TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',"
    " tier TEXT NOT NULL DEFAULT '', issue TEXT NOT NULL DEFAULT '',"
    " success INTEGER NOT NULL DEFAULT 1, latency_ms INTEGER NOT NULL DEFAULT 0,"
    " tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0,"
    " est_cost_usd REAL NOT NULL DEFAULT 0.0, note TEXT NOT NULL DEFAULT '')"
)


_TEST_DB: Path | None = None
_TEST_TMP: Path | None = None


def set_test_db(path: Path | str | None) -> None:
    """Pin the ledger database (tests). None restores automatic routing."""
    global _TEST_DB
    _TEST_DB = Path(path) if path is not None else None


def in_test_mode() -> bool:
    """True under pytest, PROJECT_ROBOTS_TEST=1, or an explicit test db."""
    if _TEST_DB is not None:
        return True
    if os.environ.get("PROJECT_ROBOTS_TEST", "") == "1":
        return True
    return "pytest" in sys.modules


def ledger_dir() -> Path:
    """Central sovereignty state dir (tool-global, outside every target)."""
    from robots.common import CACHE_ROOT

    path = CACHE_ROOT / "sovereignty"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Production ledger, or an isolated per-process file under test mode."""
    global _TEST_TMP
    if _TEST_DB is not None:
        return _TEST_DB
    if not in_test_mode():
        return ledger_dir() / "ledger.sqlite"
    if _TEST_TMP is None:
        name = f"project-robots-sov-test-{os.getpid()}.sqlite"
        _TEST_TMP = Path(tempfile.gettempdir()) / name
        atexit.register(_cleanup_test_db)
    return _TEST_TMP


def _cleanup_test_db() -> None:
    try:
        if _TEST_TMP is not None and _TEST_TMP.is_file():
            _TEST_TMP.unlink()
    except OSError:
        pass


# Valuation model: developer time saved vs compute spent. Constants are
# documented estimates, overridable via config["sovereignty"].
DEV_RATE_USD_PER_HOUR = 75.0
MINUTES_PER_LINE_CHANGED = 1.5
MINUTES_PER_TEST_FIXED = 10.0
CPU_WATTS_DEFAULT = 65.0
ENERGY_USD_PER_KWH = 0.15
HARDWARE_GOAL_DEFAULT_USD = 85.0


def _connect(db: Path | None) -> sqlite3.Connection:
    path = db or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute(_SCHEMA)
    # Value columns added in Phase 4; migrate older ledgers idempotently.
    for column in ("value_usd REAL NOT NULL DEFAULT 0.0", "lines_changed INTEGER NOT NULL DEFAULT 0"):
        try:
            con.execute(f"ALTER TABLE events ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass
    return con


def estimate_cost_usd(tokens_in: int, tokens_out: int, rate_per_mtok: float = 0.0) -> float:
    """Cost estimate; 0.0 default reflects local (self-hosted) inference."""
    try:
        rate = float(rate_per_mtok)
    except (TypeError, ValueError):
        rate = 0.0
    return round((int(tokens_in) + int(tokens_out)) / 1_000_000 * rate, 6)


def estimate_energy_usd(
    latency_ms: int,
    cpu_watts: float = CPU_WATTS_DEFAULT,
    energy_rate: float = ENERGY_USD_PER_KWH,
) -> float:
    """Local CPU energy cost for an event (estimate, never metered)."""
    try:
        kwh = (max(0, int(latency_ms)) / 3_600_000) * float(cpu_watts) / 1000.0
        return round(kwh * float(energy_rate), 6)
    except (TypeError, ValueError):
        return 0.0


def estimate_value_usd(
    lines_changed: int = 0,
    tests_fixed: int = 0,
    dev_rate: float = DEV_RATE_USD_PER_HOUR,
) -> float:
    """Developer-time saved, in USD, for delivered changes."""
    try:
        minutes = max(0, int(lines_changed)) * MINUTES_PER_LINE_CHANGED
        minutes += max(0, int(tests_fixed)) * MINUTES_PER_TEST_FIXED
        return round(minutes / 60 * float(dev_rate), 4)
    except (TypeError, ValueError):
        return 0.0


def diff_stats(preview_text: str) -> tuple[int, int]:
    """Count added/removed lines in unified-diff previews (pure)."""
    added = removed = 0
    for line in (preview_text or "").splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def record_event(
    kind: str,
    *,
    project: str = "",
    model: str = "",
    tier: str = "",
    issue: str = "",
    success: bool = True,
    latency_ms: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    est_cost_usd: float = 0.0,
    value_usd: float = 0.0,
    lines_changed: int = 0,
    note: str = "",
    db: Path | None = None,
) -> int:
    """Append one event. Returns the row id. Never raises."""
    try:
        con = _connect(db)
        try:
            cur = con.execute(
                "INSERT INTO events(ts,kind,project,model,tier,issue,success,"
                "latency_ms,tokens_in,tokens_out,est_cost_usd,value_usd,lines_changed,note)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    dt.datetime.now(dt.timezone.utc).isoformat(),
                    str(kind)[:32],
                    str(project)[:256],
                    str(model)[:128],
                    str(tier)[:32],
                    str(issue)[:512],
                    1 if success else 0,
                    int(latency_ms),
                    int(tokens_in),
                    int(tokens_out),
                    float(est_cost_usd),
                    float(value_usd),
                    int(lines_changed),
                    str(note)[:1024],
                ),
            )
            con.commit()
            return int(cur.lastrowid)
        finally:
            con.close()
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return -1


def summary(db: Path | None = None) -> dict:
    """Aggregate compute/value metrics. Never raises."""
    try:
        con = _connect(db)
        try:
            total = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if not total:
                return {"events": 0}
            successes = con.execute("SELECT COUNT(*) FROM events WHERE success=1").fetchone()[0]
            avg_lat = con.execute("SELECT AVG(latency_ms) FROM events").fetchone()[0] or 0
            tokens = con.execute("SELECT SUM(tokens_in+tokens_out) FROM events").fetchone()[0] or 0
            cost = con.execute("SELECT SUM(est_cost_usd) FROM events").fetchone()[0] or 0.0
            value = con.execute("SELECT SUM(value_usd) FROM events").fetchone()[0] or 0.0
            lines = con.execute("SELECT SUM(lines_changed) FROM events").fetchone()[0] or 0
            by_tier = {
                row[0]: {"events": row[1], "successes": row[2]}
                for row in con.execute("SELECT tier, COUNT(*), SUM(success) FROM events GROUP BY tier").fetchall()
            }
            by_kind = {
                row[0]: {"events": row[1], "successes": row[2]}
                for row in con.execute("SELECT kind, COUNT(*), SUM(success) FROM events GROUP BY kind").fetchall()
            }
            return {
                "events": total,
                "successes": successes,
                "success_rate": round(successes / total, 4),
                "avg_latency_ms": round(float(avg_lat), 1),
                "total_tokens": int(tokens),
                "tokens_per_second": round(tokens / (avg_lat / 1000), 1) if avg_lat else 0.0,
                "total_cost_usd": round(float(cost), 6),
                "total_value_usd": round(float(value), 4),
                "total_lines_changed": int(lines),
                "net_value_usd": round(float(value) - float(cost), 4),
                "by_tier": by_tier,
                "by_kind": by_kind,
            }
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        return {"events": 0, "error": "ledger unreadable"}


def hardware_goal() -> dict:
    """Hardware upgrade goal (from tool profiles ledger, else default)."""
    try:
        from robots.common import PROFILE_ROOT

        data = json.loads((PROFILE_ROOT / "ledger.json").read_text(encoding="utf-8"))
        target = data.get("target_hardware", {})
        return {
            "item": str(target.get("item", "hardware upgrade")),
            "cost_usd": float(target.get("cost_usd", HARDWARE_GOAL_DEFAULT_USD)),
            "achieved": bool(target.get("achieved", False)),
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "item": "hardware upgrade",
            "cost_usd": HARDWARE_GOAL_DEFAULT_USD,
            "achieved": False,
        }


def status_summary(db: Path | None = None) -> dict:
    """Sovereignty status: value generated vs hardware goal. Never raises."""
    try:
        stats = summary(db)
        goal = hardware_goal()
        value = float(stats.get("total_value_usd", 0.0))
        cost = float(goal.get("cost_usd", HARDWARE_GOAL_DEFAULT_USD) or HARDWARE_GOAL_DEFAULT_USD)
        progress = min(1.0, value / cost) if cost > 0 else 0.0
        return {
            **stats,
            "goal_item": goal["item"],
            "goal_cost_usd": goal["cost_usd"],
            "goal_achieved": goal["achieved"],
            "progress": round(progress, 4),
        }
    except Exception:
        return {"events": 0, "error": "status unavailable"}
