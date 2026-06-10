"""
database.py - SQLite database setup and all DB operations.
Tables: cities, weather_data, alerts, pipeline_runs
"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import DB_PATH

logger = logging.getLogger("database")


def get_connection() -> sqlite3.Connection:
    if DB_PATH != ":memory:":
        parent = os.path.dirname(DB_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def setup_database() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            city_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name  TEXT    NOT NULL,
            country    TEXT    NOT NULL DEFAULT 'IN',
            latitude   REAL,
            longitude  REAL,
            timezone   TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(city_name, country)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            record_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id           INTEGER NOT NULL,
            timestamp         TIMESTAMP NOT NULL,
            temperature_c     REAL    NOT NULL,
            feels_like_c      REAL,
            temp_min_c        REAL,
            temp_max_c        REAL,
            humidity          INTEGER NOT NULL,
            pressure_hpa      REAL    NOT NULL,
            wind_speed_mps    REAL,
            wind_direction    INTEGER,
            weather_condition TEXT,
            weather_icon      TEXT,
            visibility_m      INTEGER,
            cloudiness_pct    INTEGER,
            rain_1h_mm        REAL    DEFAULT 0,
            data_quality_flag TEXT    DEFAULT 'OK',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities(city_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id      INTEGER NOT NULL,
            alert_type   TEXT    NOT NULL,
            alert_value  REAL    NOT NULL,
            threshold    REAL    NOT NULL,
            message      TEXT    NOT NULL,
            severity     TEXT    NOT NULL DEFAULT 'WARNING',
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved     INTEGER DEFAULT 0,
            FOREIGN KEY (city_id) REFERENCES cities(city_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at       TIMESTAMP NOT NULL,
            finished_at      TIMESTAMP,
            status           TEXT    NOT NULL DEFAULT 'RUNNING',
            cities_fetched   INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            alerts_triggered INTEGER DEFAULT 0,
            errors           TEXT,
            duration_sec     REAL
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_city_time ON weather_data(city_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_city ON alerts(city_id, triggered_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status, started_at)")

    conn.commit()
    conn.close()
    logger.info("Database setup complete: %s", DB_PATH)


def upsert_city(city_name: str, country: str,
                lat: float = None, lon: float = None,
                timezone: str = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cities (city_name, country, latitude, longitude, timezone)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(city_name, country) DO UPDATE SET
            latitude  = excluded.latitude,
            longitude = excluded.longitude,
            timezone  = excluded.timezone
    """, (city_name, country, lat, lon, timezone))
    conn.commit()
    city_id = cursor.execute(
        "SELECT city_id FROM cities WHERE city_name=? AND country=?",
        (city_name, country)
    ).fetchone()["city_id"]
    conn.close()
    return city_id


def get_all_cities() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cities ORDER BY city_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_weather_record(record: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO weather_data
          (city_id, timestamp, temperature_c, feels_like_c,
           temp_min_c, temp_max_c, humidity, pressure_hpa,
           wind_speed_mps, wind_direction, weather_condition, weather_icon,
           visibility_m, cloudiness_pct, rain_1h_mm, data_quality_flag)
        VALUES
          (:city_id, :timestamp, :temperature_c, :feels_like_c,
           :temp_min_c, :temp_max_c, :humidity, :pressure_hpa,
           :wind_speed_mps, :wind_direction, :weather_condition, :weather_icon,
           :visibility_m, :cloudiness_pct, :rain_1h_mm, :data_quality_flag)
    """, record)
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_latest_weather(limit: int = 10) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT w.*, c.city_name, c.country
        FROM weather_data w
        JOIN cities c USING(city_id)
        WHERE w.rowid IN (
            SELECT MAX(rowid) FROM weather_data GROUP BY city_id
        )
        ORDER BY c.city_name
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_city_stats(days: int = 30) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.city_name,
            COUNT(*)                        AS record_count,
            ROUND(AVG(temperature_c), 1)    AS avg_temp,
            ROUND(MAX(temperature_c), 1)    AS max_temp,
            ROUND(MIN(temperature_c), 1)    AS min_temp,
            ROUND(AVG(humidity), 1)         AS avg_humidity,
            ROUND(AVG(wind_speed_mps), 2)   AS avg_wind
        FROM weather_data w
        JOIN cities c USING(city_id)
        WHERE w.timestamp >= datetime('now', ?)
        GROUP BY c.city_id
        ORDER BY avg_temp DESC
    """, (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_hourly_trend(city_name: str, days: int = 7) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            strftime('%Y-%m-%d %H:00', w.timestamp) AS hour,
            ROUND(AVG(temperature_c), 1)             AS avg_temp,
            ROUND(AVG(humidity), 0)                  AS avg_humidity
        FROM weather_data w
        JOIN cities c USING(city_id)
        WHERE c.city_name = ?
          AND w.timestamp >= datetime('now', ?)
        GROUP BY hour
        ORDER BY hour
    """, (city_name, f"-{days} days")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_alert(alert: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts
          (city_id, alert_type, alert_value, threshold, message, severity)
        VALUES
          (:city_id, :alert_type, :alert_value, :threshold, :message, :severity)
    """, alert)
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid


def get_recent_alerts(hours: int = 24) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, c.city_name
        FROM alerts a
        JOIN cities c USING(city_id)
        WHERE a.triggered_at >= datetime('now', ?)
        ORDER BY a.triggered_at DESC
    """, (f"-{hours} hours",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def start_pipeline_run() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pipeline_runs (started_at, status) VALUES (?, 'RUNNING')",
        (datetime.now(),)
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def finish_pipeline_run(run_id: int, cities: int, records: int,
                         alert_count: int, errors: str = None) -> None:
    conn = get_connection()
    now = datetime.now()
    conn.execute("""
        UPDATE pipeline_runs SET
            finished_at      = ?,
            status           = ?,
            cities_fetched   = ?,
            records_inserted = ?,
            alerts_triggered = ?,
            errors           = ?,
            duration_sec     = (julianday(?) - julianday(started_at)) * 86400
        WHERE run_id = ?
    """, (now, "SUCCESS" if not errors else "PARTIAL",
          cities, records, alert_count, errors, now, run_id))
    conn.commit()
    conn.close()


def get_pipeline_health() -> Dict:
    conn = get_connection()
    last = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    total_records = conn.execute(
        "SELECT COUNT(*) AS cnt FROM weather_data"
    ).fetchone()["cnt"]
    total_cities = conn.execute(
        "SELECT COUNT(*) AS cnt FROM cities"
    ).fetchone()["cnt"]
    conn.close()
    return {
        "last_run":      dict(last) if last else {},
        "total_records": total_records,
        "total_cities":  total_cities,
    }
