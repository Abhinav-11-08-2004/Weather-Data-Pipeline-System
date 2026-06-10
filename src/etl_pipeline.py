"""
etl_pipeline.py - Main Extract -> Transform -> Load workflow.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import CITIES, ALERT_THRESHOLDS

from api_client import WeatherAPIClient
from validators  import validate_record
import database  as db

logger = logging.getLogger("etl_pipeline")


def extract(client: WeatherAPIClient) -> List[Dict[str, Any]]:
    raw_records = []
    for city_cfg in CITIES:
        data = client.fetch_current_weather(city_cfg["name"], city_cfg["country"])
        if data:
            raw_records.append(data)
            logger.info("  [OK] Extracted: %s", city_cfg["name"])
        else:
            logger.warning("  [FAIL] Failed: %s", city_cfg["name"])
    logger.info("Extract complete: %d/%d cities fetched", len(raw_records), len(CITIES))
    return raw_records


def transform(raw_records: List[Dict[str, Any]]) -> Tuple[List[Dict], int]:
    transformed   = []
    invalid_count = 0

    for raw in raw_records:
        city_id = db.upsert_city(
            raw["city"], raw["country"],
            raw.get("latitude"), raw.get("longitude"),
            raw.get("timezone"),
        )

        record = {
            "city_id":           city_id,
            "timestamp":         raw["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "temperature_c":     raw.get("temperature_c"),
            "feels_like_c":      raw.get("feels_like_c"),
            "temp_min_c":        raw.get("temp_min_c"),
            "temp_max_c":        raw.get("temp_max_c"),
            "humidity":          raw.get("humidity"),
            "pressure_hpa":      raw.get("pressure_hpa"),
            "wind_speed_mps":    raw.get("wind_speed_mps"),
            "wind_direction":    raw.get("wind_direction"),
            "weather_condition": raw.get("weather_condition"),
            "weather_icon":      raw.get("weather_icon"),
            "visibility_m":      raw.get("visibility_m"),
            "cloudiness_pct":    raw.get("cloudiness_pct"),
            "rain_1h_mm":        raw.get("rain_1h_mm", 0.0),
            "_city_name":        raw["city"],
        }

        is_valid, flag, reason = validate_record(record)
        record["data_quality_flag"] = flag

        if is_valid:
            transformed.append(record)
            if flag == "WARNING":
                logger.warning("  Quality warning for %s: %s", raw["city"], reason)
        else:
            invalid_count += 1
            logger.error("  Record for %s is INVALID - skipping: %s", raw["city"], reason)

    logger.info("Transform complete: %d valid, %d invalid", len(transformed), invalid_count)
    return transformed, invalid_count


def load(records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for record in records:
        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        try:
            db.insert_weather_record(clean)
            inserted += 1
        except Exception as exc:
            logger.error("Failed to insert record for city_id=%s: %s",
                         record.get("city_id"), exc)
    logger.info("Load complete: %d records inserted", inserted)
    return inserted


def generate_alerts(records: List[Dict[str, Any]]) -> int:
    alert_count = 0

    for record in records:
        city_name = record.get("_city_name", "Unknown")
        city_id   = record["city_id"]

        checks = [
            ("HIGH_TEMP",
             record.get("temperature_c"), ALERT_THRESHOLDS["high_temp_c"],
             f"{city_name}: High temp {record.get('temperature_c')} C > {ALERT_THRESHOLDS['high_temp_c']} C",
             "WARNING", lambda v, t: v is not None and v > t),

            ("LOW_TEMP",
             record.get("temperature_c"), ALERT_THRESHOLDS["low_temp_c"],
             f"{city_name}: Low temp {record.get('temperature_c')} C < {ALERT_THRESHOLDS['low_temp_c']} C",
             "WARNING", lambda v, t: v is not None and v < t),

            ("HIGH_HUMIDITY",
             record.get("humidity"), ALERT_THRESHOLDS["high_humidity_pct"],
             f"{city_name}: High humidity {record.get('humidity')}% > {ALERT_THRESHOLDS['high_humidity_pct']}%",
             "WARNING", lambda v, t: v is not None and v > t),

            ("HIGH_WIND",
             record.get("wind_speed_mps"), ALERT_THRESHOLDS["high_wind_mps"],
             f"{city_name}: High wind {record.get('wind_speed_mps')} m/s > {ALERT_THRESHOLDS['high_wind_mps']} m/s",
             "CRITICAL", lambda v, t: v is not None and v > t),

            ("LOW_PRESSURE",
             record.get("pressure_hpa"), ALERT_THRESHOLDS["low_pressure_hpa"],
             f"{city_name}: Low pressure {record.get('pressure_hpa')} hPa < {ALERT_THRESHOLDS['low_pressure_hpa']} hPa",
             "WARNING", lambda v, t: v is not None and v < t),
        ]

        for alert_type, value, threshold, message, severity, condition in checks:
            if condition(value, threshold):
                db.insert_alert({
                    "city_id":     city_id,
                    "alert_type":  alert_type,
                    "alert_value": value,
                    "threshold":   threshold,
                    "message":     message,
                    "severity":    severity,
                })
                alert_count += 1
                logger.warning("  [ALERT][%s] %s", severity, message)

    return alert_count


def run_pipeline(client: WeatherAPIClient) -> Dict[str, Any]:
    run_id = db.start_pipeline_run()
    logger.info("=" * 60)
    logger.info("Pipeline Run #%d started at %s", run_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    errors           = None
    records_inserted = 0
    alert_count      = 0
    cities_fetched   = 0

    try:
        logger.info("[EXTRACT] Fetching data for %d cities...", len(CITIES))
        raw = extract(client)
        cities_fetched = len(raw)

        logger.info("[TRANSFORM] Validating and enriching records...")
        valid_records, invalid_count = transform(raw)

        logger.info("[ALERTS] Checking thresholds...")
        alert_count = generate_alerts(valid_records)

        logger.info("[LOAD] Writing to database...")
        records_inserted = load(valid_records)

        if invalid_count:
            errors = f"{invalid_count} invalid records skipped"

    except Exception as exc:
        errors = str(exc)
        logger.exception("Pipeline failed with unhandled exception")

    finally:
        db.finish_pipeline_run(run_id, cities_fetched, records_inserted,
                               alert_count, errors)

    summary = {
        "run_id":           run_id,
        "cities_fetched":   cities_fetched,
        "records_inserted": records_inserted,
        "alerts_triggered": alert_count,
        "errors":           errors,
        "status":           "SUCCESS" if not errors else "PARTIAL",
    }
    logger.info("Pipeline complete: %s", summary)
    return summary
