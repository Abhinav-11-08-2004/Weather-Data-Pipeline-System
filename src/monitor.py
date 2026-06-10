"""
monitor.py - System health checks for the pipeline.
"""

import os
import logging
import shutil
from datetime import datetime
from typing import Dict, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import DB_PATH, LOG_DIR

import database as db

logger = logging.getLogger("monitor")

MIN_FREE_MB   = 100
MAX_STALE_MIN = 90


def check_database() -> Dict[str, Any]:
    try:
        health = db.get_pipeline_health()
        return {"status": "OK", "details": health}
    except Exception as exc:
        return {"status": "ERROR", "details": str(exc)}


def check_disk_space() -> Dict[str, Any]:
    total, used, free = shutil.disk_usage(os.path.dirname(DB_PATH) or ".")
    free_mb = free // (1024 * 1024)
    status  = "OK" if free_mb >= MIN_FREE_MB else "WARNING"
    return {"status": status, "free_mb": free_mb, "total_mb": total // (1024 * 1024)}


def check_data_freshness() -> Dict[str, Any]:
    try:
        latest = db.get_latest_weather(1)
        if not latest:
            return {"status": "WARNING", "details": "No records in database"}
        ts  = datetime.strptime(latest[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
        age = (datetime.utcnow() - ts).total_seconds() / 60
        if age > MAX_STALE_MIN:
            return {"status": "WARNING", "age_minutes": round(age, 1),
                    "details": f"Last record is {age:.0f} min old (threshold: {MAX_STALE_MIN} min)"}
        return {"status": "OK", "age_minutes": round(age, 1)}
    except Exception as exc:
        return {"status": "ERROR", "details": str(exc)}


def check_log_directory() -> Dict[str, Any]:
    exists = os.path.isdir(LOG_DIR)
    return {"status": "OK" if exists else "WARNING",
            "path": LOG_DIR, "exists": exists}


def run_health_checks() -> Dict[str, Any]:
    checks = {
        "database":   check_database(),
        "disk_space": check_disk_space(),
        "data_fresh": check_data_freshness(),
        "log_dir":    check_log_directory(),
    }
    overall = "OK"
    for name, result in checks.items():
        s = result.get("status", "UNKNOWN")
        if s == "ERROR":
            overall = "ERROR"
            logger.error("Health check [%s]: %s", name, result)
        elif s == "WARNING" and overall != "ERROR":
            overall = "WARNING"
            logger.warning("Health check [%s]: %s", name, result)
        else:
            logger.info("Health check [%s]: OK", name)

    return {
        "timestamp": datetime.now().isoformat(),
        "overall":   overall,
        "checks":    checks,
    }


def print_health_report() -> None:
    report  = run_health_checks()
    overall = report["overall"]
    print(f"\n{'-'*47}")
    print(f"  SYSTEM HEALTH  [{overall}]")
    print(f"{'-'*47}")
    for name, result in report["checks"].items():
        status = result.get("status", "UNKNOWN")
        print(f"  [{status:<7}] {name:<16}: {_summarize(result)}")
    print(f"{'-'*47}\n")


def _summarize(result: Dict) -> str:
    ignore = {"status"}
    parts  = [f"{k}={v}" for k, v in result.items() if k not in ignore]
    return ", ".join(parts[:3]) if parts else ""
