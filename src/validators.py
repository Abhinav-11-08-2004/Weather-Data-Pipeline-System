"""
validators.py - Data quality and validation checks for weather records.
"""

import logging
from typing import Dict, Any, Tuple, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import VALID_RANGES

logger = logging.getLogger("validators")

ValidationResult = Tuple[bool, str]


def check_required_fields(record: Dict[str, Any]) -> ValidationResult:
    required = ["city_id", "timestamp", "temperature_c", "humidity", "pressure_hpa"]
    missing  = [f for f in required if record.get(f) is None]
    if missing:
        return False, f"Missing required fields: {missing}"
    return True, "OK"


def check_value_ranges(record: Dict[str, Any]) -> ValidationResult:
    issues = []
    for field, (lo, hi) in VALID_RANGES.items():
        val = record.get(field)
        if val is None:
            continue
        if not (lo <= val <= hi):
            issues.append(f"{field}={val} outside [{lo}, {hi}]")
    if issues:
        return False, "; ".join(issues)
    return True, "OK"


def check_humidity_logic(record: Dict[str, Any]) -> ValidationResult:
    h = record.get("humidity")
    if h is None:
        return True, "OK"
    if not isinstance(h, (int, float)) or not (0 <= h <= 100):
        return False, f"Humidity {h} invalid (must be 0-100)"
    return True, "OK"


def check_wind_non_negative(record: Dict[str, Any]) -> ValidationResult:
    ws = record.get("wind_speed_mps")
    if ws is not None and ws < 0:
        return False, f"Wind speed {ws} is negative"
    return True, "OK"


def check_temperature_consistency(record: Dict[str, Any]) -> ValidationResult:
    t  = record.get("temperature_c")
    lo = record.get("temp_min_c")
    hi = record.get("temp_max_c")
    if None in (t, lo, hi):
        return True, "OK"
    if not (lo <= t <= hi + 0.5):
        return False, f"Temp {t} outside min/max [{lo}, {hi}]"
    return True, "OK"


ALL_CHECKS = [
    check_required_fields,
    check_value_ranges,
    check_humidity_logic,
    check_wind_non_negative,
    check_temperature_consistency,
]


def validate_record(record: Dict[str, Any]) -> Tuple[bool, str, str]:
    failures: List[str] = []
    for check in ALL_CHECKS:
        ok, reason = check(record)
        if not ok:
            failures.append(reason)

    if not failures:
        return True, "OK", "All checks passed"

    if any("Missing required" in f for f in failures):
        return False, "INVALID", " | ".join(failures)

    return True, "WARNING", " | ".join(failures)
