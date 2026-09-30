"""friday · adapters/system.py

The Mac's own vitals for the HUD system-monitor card — CPU, memory, disk,
uptime. psutil is already in the tree (chromadb pulls it); lazy-imported so the
kill path never pays for it. Read-only; a probe failure degrades to zeros.
"""

import time


def snapshot() -> dict:
    """Live percentages + uptime. Never raises — a dead probe reads 0."""
    try:
        import psutil

        boot = getattr(psutil, "boot_time", lambda: time.time())()
        return {
            "cpu": round(psutil.cpu_percent(interval=0.15)),
            "ram": round(psutil.virtual_memory().percent),
            "disk": round(psutil.disk_usage("/").percent),
            "uptime_h": round((time.time() - boot) / 3600, 1),
        }
    except Exception:
        return {"cpu": 0, "ram": 0, "disk": 0, "uptime_h": 0}
