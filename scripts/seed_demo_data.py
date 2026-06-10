"""
scripts/seed_demo_data.py
Inserts 30 days of synthetic weather data for demo/testing purposes.

Run once:
    python scripts/seed_demo_data.py
"""

import sys, os, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

from config  import CITIES
import database as db

CITY_BASELINES = {
    "Mumbai":    {"temp": 28, "hum": 70, "pressure": 1010},
    "Delhi":     {"temp": 22, "hum": 45, "pressure": 1015},
    "Bangalore": {"temp": 24, "hum": 65, "pressure": 1013},
    "Chennai":   {"temp": 30, "hum": 75, "pressure": 1009},
    "Kolkata":   {"temp": 27, "hum": 78, "pressure": 1011},
    "Hyderabad": {"temp": 29, "hum": 55, "pressure": 1012},
    "Pune":      {"temp": 25, "hum": 60, "pressure": 1014},
    "Ahmedabad": {"temp": 31, "hum": 40, "pressure": 1013},
    "Jaipur":    {"temp": 26, "hum": 35, "pressure": 1016},
    "Surat":     {"temp": 30, "hum": 68, "pressure": 1010},
}

CONDITIONS = [
    "Clear Sky", "Partly Cloudy", "Overcast", "Light Rain",
    "Heavy Rain", "Thunderstorm", "Haze", "Fog", "Sunny",
]


def seed(days: int = 30, records_per_city_per_day: int = 4):
    db.setup_database()
    total = 0
    now   = datetime.utcnow()

    for city_cfg in CITIES:
        cname   = city_cfg["name"]
        base    = CITY_BASELINES.get(cname, {"temp": 28, "hum": 65, "pressure": 1012})
        city_id = db.upsert_city(cname, city_cfg["country"])

        for day_offset in range(days, 0, -1):
            for hour in range(0, 24, 24 // records_per_city_per_day):
                ts      = now - timedelta(days=day_offset, hours=hour)
                diurnal = 3 * (1 - abs(hour - 14) / 14)
                temp    = round(base["temp"] + diurnal + random.uniform(-3, 3), 1)
                hum     = min(100, max(0, base["hum"] + random.randint(-10, 10)))
                rain    = round(random.uniform(0, 2), 2) if hum > 80 else 0.0
                wind    = round(random.uniform(0.5, 12), 1)

                record = {
                    "city_id":           city_id,
                    "timestamp":         ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "temperature_c":     temp,
                    "feels_like_c":      round(temp + random.uniform(-1, 2), 1),
                    "temp_min_c":        round(temp - 1.5, 1),
                    "temp_max_c":        round(temp + 1.5, 1),
                    "humidity":          hum,
                    "pressure_hpa":      round(base["pressure"] + random.uniform(-3, 3), 1),
                    "wind_speed_mps":    wind,
                    "wind_direction":    random.randint(0, 360),
                    "weather_condition": random.choice(CONDITIONS),
                    "weather_icon":      "01d",
                    "visibility_m":      random.randint(5000, 10000),
                    "cloudiness_pct":    random.randint(0, 100),
                    "rain_1h_mm":        rain,
                    "data_quality_flag": "OK",
                }
                db.insert_weather_record(record)
                total += 1

        print(f"  [OK] {cname}: seeded")

    print(f"\n[DONE] Seeded {total:,} demo records across {len(CITIES)} cities over {days} days.")
    print("       You can now run: python main.py --dashboard")


if __name__ == "__main__":
    seed()
