"""
config.py - Central configuration for the Weather Data Pipeline System.
All settings, thresholds, and constants are managed here.
"""

import os

# ─────────────────────────────────────────────
# API CONFIGURATION
# ─────────────────────────────────────────────
API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
API_TIMEOUT = 10
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 5

# ─────────────────────────────────────────────
# CITIES TO TRACK
# ─────────────────────────────────────────────
CITIES = [
    {"name": "Mumbai",    "country": "IN"},
    {"name": "Delhi",     "country": "IN"},
    {"name": "Bangalore", "country": "IN"},
    {"name": "Chennai",   "country": "IN"},
    {"name": "Kolkata",   "country": "IN"},
    {"name": "Hyderabad", "country": "IN"},
    {"name": "Pune",      "country": "IN"},
    {"name": "Ahmedabad", "country": "IN"},
    {"name": "Jaipur",    "country": "IN"},
    {"name": "Surat",     "country": "IN"},
]

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "weather_data.db")

# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────
COLLECTION_INTERVAL_MINUTES = 60
REPORT_INTERVAL_HOURS = 24

# ─────────────────────────────────────────────
# ALERT THRESHOLDS
# ─────────────────────────────────────────────
ALERT_THRESHOLDS = {
    "high_temp_c":       35.0,
    "low_temp_c":        5.0,
    "high_humidity_pct": 85,
    "high_wind_mps":     15.0,
    "low_pressure_hpa":  1000.0,
}

# ─────────────────────────────────────────────
# DATA VALIDATION RANGES
# ─────────────────────────────────────────────
VALID_RANGES = {
    "temperature_c":  (-60.0,  60.0),
    "humidity":       (0,      100),
    "pressure_hpa":   (870.0,  1084.0),
    "wind_speed_mps": (0.0,    113.0),
}

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
LOG_DIR    = os.path.join(os.path.dirname(__file__), "..", "logs")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
