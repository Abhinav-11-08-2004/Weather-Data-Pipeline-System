"""
test_pipeline.py - Unit and integration tests.
Run with: python -m pytest tests/ -v
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "config"))

import config
import database as db
from validators  import validate_record
from api_client  import WeatherAPIClient


def _good_record(**overrides):
    base = {
        "city_id":           1,
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature_c":     28.5,
        "feels_like_c":      30.0,
        "temp_min_c":        27.0,
        "temp_max_c":        31.0,
        "humidity":          65,
        "pressure_hpa":      1012.0,
        "wind_speed_mps":    3.5,
        "wind_direction":    180,
        "weather_condition": "Clear Sky",
        "weather_icon":      "01d",
        "visibility_m":      10000,
        "cloudiness_pct":    0,
        "rain_1h_mm":        0.0,
        "data_quality_flag": "OK",
    }
    base.update(overrides)
    return base


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        db.DB_PATH = self._tmp.name
        db.setup_database()

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_setup_creates_tables(self):
        conn  = db.get_connection()
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        self.assertIn("cities", names)
        self.assertIn("weather_data", names)
        self.assertIn("alerts", names)
        self.assertIn("pipeline_runs", names)

    def test_upsert_city_creates_new(self):
        city_id = db.upsert_city("TestCity", "IN", 17.4, 78.5)
        self.assertIsInstance(city_id, int)
        self.assertGreater(city_id, 0)

    def test_upsert_city_deduplicates(self):
        id1 = db.upsert_city("Duplicate", "IN")
        id2 = db.upsert_city("Duplicate", "IN")
        self.assertEqual(id1, id2)

    def test_insert_weather_record(self):
        city_id = db.upsert_city("Mumbai", "IN")
        rid     = db.insert_weather_record(_good_record(city_id=city_id))
        self.assertIsInstance(rid, int)

    def test_pipeline_run_lifecycle(self):
        run_id = db.start_pipeline_run()
        self.assertIsInstance(run_id, int)
        db.finish_pipeline_run(run_id, 5, 5, 0)
        conn = db.get_connection()
        row  = conn.execute(
            "SELECT status FROM pipeline_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "SUCCESS")

    def test_insert_alert(self):
        city_id  = db.upsert_city("Chennai", "IN")
        alert_id = db.insert_alert({
            "city_id":     city_id,
            "alert_type":  "HIGH_TEMP",
            "alert_value": 36.0,
            "threshold":   35.0,
            "message":     "Test alert",
            "severity":    "WARNING",
        })
        self.assertIsInstance(alert_id, int)


class TestValidators(unittest.TestCase):

    def test_valid_record_passes(self):
        is_valid, flag, _ = validate_record(_good_record())
        self.assertTrue(is_valid)
        self.assertEqual(flag, "OK")

    def test_missing_required_field_fails(self):
        rec = _good_record()
        del rec["temperature_c"]
        is_valid, flag, _ = validate_record(rec)
        self.assertFalse(is_valid)
        self.assertEqual(flag, "INVALID")

    def test_temperature_out_of_range_warns(self):
        rec = _good_record(temperature_c=999.0, temp_max_c=999.0)
        is_valid, flag, _ = validate_record(rec)
        self.assertTrue(is_valid)
        self.assertEqual(flag, "WARNING")

    def test_negative_wind_warns(self):
        rec = _good_record(wind_speed_mps=-5.0)
        is_valid, flag, _ = validate_record(rec)
        self.assertEqual(flag, "WARNING")

    def test_humidity_out_of_range_warns(self):
        rec = _good_record(humidity=150)
        is_valid, flag, _ = validate_record(rec)
        self.assertEqual(flag, "WARNING")

    def test_temperature_consistency(self):
        rec = _good_record(temperature_c=20.0, temp_min_c=25.0, temp_max_c=30.0)
        is_valid, flag, _ = validate_record(rec)
        self.assertEqual(flag, "WARNING")


class TestAPIClient(unittest.TestCase):

    MOCK_RESPONSE = {
        "coord":    {"lat": 19.07, "lon": 72.88},
        "weather":  [{"description": "clear sky", "icon": "01d"}],
        "main":     {"temp": 28.5, "feels_like": 30.1, "temp_min": 27.0,
                     "temp_max": 31.0, "pressure": 1012, "humidity": 65},
        "wind":     {"speed": 3.5, "deg": 180},
        "clouds":   {"all": 0},
        "visibility": 10000,
        "rain":     {},
        "sys":      {"country": "IN"},
        "dt":       1700000000,
        "timezone": 19800,
    }

    def _mock_resp(self, status_code=200):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = self.MOCK_RESPONSE
        return m

    @patch("api_client.requests.Session.get")
    def test_successful_fetch(self, mock_get):
        mock_get.return_value = self._mock_resp()
        result = WeatherAPIClient(api_key="test").fetch_current_weather("Mumbai")
        self.assertIsNotNone(result)
        self.assertEqual(result["temperature_c"], 28.5)

    @patch("api_client.requests.Session.get")
    def test_city_not_found_returns_none(self, mock_get):
        mock_get.return_value = self._mock_resp(404)
        result = WeatherAPIClient(api_key="test").fetch_current_weather("NoWhere")
        self.assertIsNone(result)

    @patch("api_client.requests.Session.get")
    def test_normalise_maps_fields_correctly(self, mock_get):
        mock_get.return_value = self._mock_resp()
        result = WeatherAPIClient(api_key="test").fetch_current_weather("Mumbai")
        for field in ["city", "temperature_c", "pressure_hpa",
                      "wind_speed_mps", "weather_condition"]:
            self.assertIn(field, result)

    @patch("api_client.requests.Session.get")
    def test_timeout_retries_and_returns_none(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout
        config.API_RETRY_DELAY = 0
        result = WeatherAPIClient(api_key="test").fetch_current_weather("Mumbai")
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, config.API_RETRY_ATTEMPTS)


class TestETLIntegration(unittest.TestCase):

    MOCK_WEATHER = {
        "coord":    {"lat": 19.07, "lon": 72.88},
        "weather":  [{"description": "clear sky", "icon": "01d"}],
        "main":     {"temp": 28.5, "feels_like": 30.0, "temp_min": 27.0,
                     "temp_max": 31.0, "pressure": 1012, "humidity": 65},
        "wind":     {"speed": 3.5, "deg": 180},
        "clouds":   {"all": 0},
        "visibility": 10000,
        "rain":     {},
        "sys":      {"country": "IN"},
        "dt":       1700000000,
        "timezone": 19800,
    }

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        db.DB_PATH = self._tmp.name
        db.setup_database()

    def tearDown(self):
        os.unlink(self._tmp.name)

    @patch("api_client.requests.Session.get")
    def test_full_pipeline_run(self, mock_get):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = self.MOCK_WEATHER
        mock_get.return_value = m

        from etl_pipeline import run_pipeline
        result = run_pipeline(WeatherAPIClient(api_key="test"))
        self.assertIn("run_id", result)
        self.assertGreater(result["cities_fetched"], 0)
        self.assertGreater(result["records_inserted"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
