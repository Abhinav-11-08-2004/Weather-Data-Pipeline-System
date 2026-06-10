"""
query_system.py - Historical weather analysis queries.
"""

import sqlite3
import logging
from typing import List, Dict, Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import DB_PATH

logger = logging.getLogger("query_system")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def hottest_city(days: int = 30) -> Dict:
    with _conn() as conn:
        row = conn.execute("""
            SELECT c.city_name, ROUND(AVG(w.temperature_c), 2) AS avg_temp
            FROM weather_data w JOIN cities c USING(city_id)
            WHERE w.timestamp >= datetime('now', ?)
            GROUP BY c.city_id
            ORDER BY avg_temp DESC LIMIT 1
        """, (f"-{days} days",)).fetchone()
    return dict(row) if row else {}


def temperature_trend(city_name: str, days: int = 30) -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                date(w.timestamp)              AS day,
                ROUND(AVG(w.temperature_c), 1) AS avg_temp,
                ROUND(MAX(w.temperature_c), 1) AS max_temp,
                ROUND(MIN(w.temperature_c), 1) AS min_temp
            FROM weather_data w JOIN cities c USING(city_id)
            WHERE c.city_name = ?
              AND w.timestamp >= datetime('now', ?)
            GROUP BY day ORDER BY day
        """, (city_name, f"-{days} days")).fetchall()
    return [dict(r) for r in rows]


def humidity_rain_correlation() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                (humidity / 10) * 10        AS humidity_band,
                COUNT(*)                     AS samples,
                ROUND(AVG(rain_1h_mm), 3)    AS avg_rain_mm,
                ROUND(AVG(temperature_c), 1) AS avg_temp
            FROM weather_data
            GROUP BY humidity_band
            ORDER BY humidity_band
        """).fetchall()
    return [dict(r) for r in rows]


def extreme_weather_by_month() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%m', timestamp)     AS month_num,
                CASE strftime('%m', timestamp)
                    WHEN '01' THEN 'January'   WHEN '02' THEN 'February'
                    WHEN '03' THEN 'March'     WHEN '04' THEN 'April'
                    WHEN '05' THEN 'May'       WHEN '06' THEN 'June'
                    WHEN '07' THEN 'July'      WHEN '08' THEN 'August'
                    WHEN '09' THEN 'September' WHEN '10' THEN 'October'
                    WHEN '11' THEN 'November'  WHEN '12' THEN 'December'
                END                            AS month_name,
                ROUND(MAX(temperature_c), 1)  AS max_temp,
                ROUND(MIN(temperature_c), 1)  AS min_temp,
                ROUND(MAX(wind_speed_mps), 2) AS max_wind,
                ROUND(AVG(humidity), 0)        AS avg_humidity,
                COUNT(*)                       AS records
            FROM weather_data
            GROUP BY month_num
            ORDER BY month_num
        """).fetchall()
    return [dict(r) for r in rows]


def peak_temp_hours(city_name: str) -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                CAST(strftime('%H', w.timestamp) AS INTEGER) AS hour,
                ROUND(AVG(w.temperature_c), 1)               AS avg_temp,
                COUNT(*)                                      AS samples
            FROM weather_data w JOIN cities c USING(city_id)
            WHERE c.city_name = ?
            GROUP BY hour ORDER BY hour
        """, (city_name,)).fetchall()
    return [dict(r) for r in rows]


def windiest_days(top_n: int = 10) -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                c.city_name,
                date(w.timestamp)               AS day,
                ROUND(MAX(w.wind_speed_mps), 2) AS max_wind,
                w.weather_condition
            FROM weather_data w JOIN cities c USING(city_id)
            GROUP BY c.city_id, day
            ORDER BY max_wind DESC LIMIT ?
        """, (top_n,)).fetchall()
    return [dict(r) for r in rows]


def data_quality_summary() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                data_quality_flag,
                COUNT(*) AS count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
            FROM weather_data
            GROUP BY data_quality_flag
        """).fetchall()
    return [dict(r) for r in rows]


def print_analysis_report(city: str = "Mumbai") -> None:
    print("\n" + "=" * 55)
    print("  HISTORICAL WEATHER ANALYSIS")
    print("=" * 55)

    h = hottest_city()
    if h:
        print(f"\n  Hottest city (30-day avg): {h['city_name']} -- {h['avg_temp']} C")

    trend = temperature_trend(city, 7)
    if trend:
        print(f"\n  {city} -- 7-day temperature trend:")
        for t in trend:
            bar = "#" * int(t["avg_temp"] / 2)
            print(f"     {t['day']}  avg={t['avg_temp']:>5} C  {bar}")

    corr = humidity_rain_correlation()
    if corr:
        print("\n  Humidity -> Rain correlation:")
        for c_row in corr:
            if c_row["avg_rain_mm"] > 0:
                print(f"     Humidity {c_row['humidity_band']:>3}%+  "
                      f"avg rain={c_row['avg_rain_mm']} mm  "
                      f"(n={c_row['samples']})")

    extreme = extreme_weather_by_month()
    if extreme:
        print("\n  Extreme weather by month:")
        print(f"  {'Month':<12} {'MaxT':>6} {'MinT':>6} {'Wind':>6} {'Hum':>5}")
        for m in extreme:
            print(f"  {m['month_name']:<12} {m['max_temp']:>6} {m['min_temp']:>6} "
                  f"{m['max_wind']:>6} {m['avg_humidity']:>5}%")

    peak = peak_temp_hours(city)
    if peak:
        hottest_hour = max(peak, key=lambda x: x["avg_temp"])
        print(f"\n  Peak temp hour in {city}: "
              f"{hottest_hour['hour']:02d}:00 -- {hottest_hour['avg_temp']} C avg")

    dq = data_quality_summary()
    if dq:
        print("\n  Data quality breakdown:")
        for row in dq:
            print(f"     {row['data_quality_flag']:<10}: {row['count']:>6} records  ({row['pct']}%)")

    print("\n" + "=" * 55 + "\n")
