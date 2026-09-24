"""System Telemetry Robot for Autonomous Hardware-Aware Loop."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def get_system_metrics() -> dict[str, object]:
    total_b, used_b, free_b = shutil.disk_usage(os.getcwd())

    metrics: dict[str, object] = {
        "python_version": sys.version.split()[0],
        "disk": {
            "total_gb": round(total_b / (1024**3), 2),
            "free_gb": round(free_b / (1024**3), 2),
            "used_pct": round((used_b / total_b) * 100, 1),
        },
        "ram": {},
        "gpu": "none",
    }

    if os.path.exists("/proc/meminfo"):
        mem: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    if val.isdigit():
                        mem[key] = int(val)
        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        if total_kb:
            metrics["ram"] = {
                "total_mb": round(total_kb / 1024, 1),
                "available_mb": round(avail_kb / 1024, 1),
                "used_pct": round(((total_kb - avail_kb) / total_kb) * 100, 1),
            }

    try:
        nvidia_out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        name, total_vram, used_vram, temp = [x.strip() for x in nvidia_out.split(",")]
        metrics["gpu"] = {
            "name": name,
            "vram_total_mb": int(total_vram),
            "vram_used_mb": int(used_vram),
            "temp_c": int(temp),
        }
    except Exception:
        metrics["gpu"] = "CPU-only or unexposed driver"

    return metrics


if __name__ == "__main__":
    print(json.dumps(get_system_metrics(), indent=2))  # noqa: T201
