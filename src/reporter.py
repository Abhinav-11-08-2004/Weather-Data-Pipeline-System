"""
reporter.py - Generate text, CSV, and JSON reports from the database.
Emojis are used only in the LATEST WEATHER SNAPSHOT section.
"""

import os
import json
import csv
import logging
from datetime import datetime
from typing import List, Dict, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import REPORT_DIR

import database as db

logger = logging.getLogger("reporter")

os.makedirs(REPORT_DIR, exist_ok=True)


def _condition_icon(condition: str) -> str:
    """Return a weather emoji based on condition string."""
    c = condition.lower()
    if "thunder" in c:              return "⛈️ "
    if "heavy rain" in c:           return "🌧️ "
    if "light rain" in c:           return "🌦️ "
    if "rain" in c:                 return "🌧️ "
    if "snow" in c:                 return "❄️ "
    if "fog" in c or "mist" in c:  return "🌫️ "
    if "haze" in c:                 return "🌫️ "
    if "overcast" in c:             return "☁️ "
    if "cloud" in c:                return "⛅ "
    if "clear" in c:                return "☀️ "
    if "sunny" in c:                return "☀️ "
    return "🌡️ "


def print_dashboard() -> None:
    """Print an ASCII dashboard to stdout."""
    health   = db.get_pipeline_health()
    latest   = db.get_latest_weather(10)
    alerts   = db.get_recent_alerts(24)
    stats    = db.get_city_stats(30)
    last_run = health.get("last_run", {})

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*57}")
    print("  WEATHER DATA PIPELINE  --  REAL-TIME DASHBOARD")
    print(f"{'='*57}")
    print(f"  Report Time   : {now_str}")
    print(f"  Total Records : {health['total_records']:,}")
    print(f"  Cities Tracked: {health['total_cities']}")

    # Last pipeline run
    print(f"\n  {'-'*53}")
    print("  LAST PIPELINE RUN")
    print(f"  {'-'*53}")
    if last_run:
        status_label = "[SUCCESS]" if last_run.get("status") == "SUCCESS" else "[WARNING]"
        print(f"  {status_label} Status       : {last_run.get('status', 'N/A')}")
        print(f"  Started       : {last_run.get('started_at', 'N/A')}")
        print(f"  Duration      : {last_run.get('duration_sec', 0):.1f}s")
        print(f"  Records Added : {last_run.get('records_inserted', 0)}")
        print(f"  Alerts Fired  : {last_run.get('alerts_triggered', 0)}")
        if last_run.get("errors"):
            print(f"  [ERROR]       : {last_run['errors']}")
    else:
        print("  (no runs yet)")

    # Latest weather snapshot — emojis kept here only
    print(f"\n  {'-'*53}")
    print(f"  {'LATEST WEATHER SNAPSHOT':^53}")
    print(f"  {'-'*53}")
    if latest:
        print(f"  {'City':^14}  {'Temp':^7}  {'Humidity':^8}  {'Wind':^9}  {'Condition':^16}")
        print(f"  {'-'*14}  {'-'*7}  {'-'*8}  {'-'*9}  {'-'*16}")
        for row in latest:
            condition  = row.get("weather_condition", "")
            icon       = _condition_icon(condition)
            # ⛅ (U+26C5, no FE0F) renders 3 display cols in this terminal;
            # all FE0F icons render 3 display cols too but via (2-wide emoji + 1 space).
            # ⛅ is already 2-wide + 1 space = 3, so the same — EXCEPT the Python
            # len is 2 vs 3, making city padding land 1 col off.
            # Compensate: reduce city_width by 1 for len-2 icons so display totals match.
            city_width = 9 if len(icon) == 2 else 10
            print(f"  {icon}{row['city_name']:<{city_width}}"
                  f"  {row['temperature_c']:>5.1f} C  "
                  f"{row['humidity']:>6}%  "
                  f"{row.get('wind_speed_mps', 0):>7.1f} m/s  "
                  f"{condition}")
    else:
        print("  (no data yet)")

    # 30-day stats — no emojis
    print(f"\n  {'-'*53}")
    print("  30-DAY CITY STATISTICS")
    print(f"  {'-'*53}")
    print(f"  {'City':<12} {'Avg C':>6} {'Max C':>6} {'Min C':>6} {'Hum%':>5} {'Recs':>5}")
    print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*5}")
    for s in stats:
        print(f"  {s['city_name']:<12} {s['avg_temp']:>6} {s['max_temp']:>6} "
              f"{s['min_temp']:>6} {s['avg_humidity']:>5} {s['record_count']:>5}")

    # Alerts — no emojis
    print(f"\n  {'-'*53}")
    print(f"  ALERTS (last 24 hours)  -- {len(alerts)} total")
    print(f"  {'-'*53}")
    if alerts:
        for a in alerts:
            sev_label = "[CRITICAL]" if a["severity"] == "CRITICAL" else "[WARNING] "
            print(f"  {sev_label} {a['message']}")
            print(f"             Triggered: {a['triggered_at']}")
    else:
        print("  No alerts in the last 24 hours.")

    print(f"\n{'='*57}\n")


def generate_csv_report(days: int = 7) -> str:
    stats = db.get_city_stats(days)
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    path  = os.path.join(REPORT_DIR, f"weather_stats_{ts}.csv")
    fieldnames = ["city_name", "record_count", "avg_temp", "max_temp",
                  "min_temp", "avg_humidity", "avg_wind"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stats)
    logger.info("CSV report written: %s", path)
    return path


def generate_json_report() -> str:
    health = db.get_pipeline_health()
    latest = db.get_latest_weather(20)
    alerts = db.get_recent_alerts(24)
    stats  = db.get_city_stats(30)

    def _serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")

    report = {
        "generated_at":    datetime.now().isoformat(),
        "pipeline_health": health,
        "latest_weather":  latest,
        "recent_alerts":   alerts,
        "city_stats_30d":  stats,
    }
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORT_DIR, f"weather_report_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=_serial)
    logger.info("JSON report written: %s", path)
    return path
