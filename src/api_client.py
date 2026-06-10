"""
api_client.py - Weather API communication with retry logic and error handling.
Supports OpenWeatherMap free tier.
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import (API_KEY, BASE_URL, API_TIMEOUT,
                    API_RETRY_ATTEMPTS, API_RETRY_DELAY)

logger = logging.getLogger("api_client")


class WeatherAPIError(Exception):
    pass


class WeatherAPIClient:

    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._call_count = 0

    def fetch_current_weather(self, city: str, country_code: str = "IN") -> Optional[Dict[str, Any]]:
        params = {
            "q":     f"{city},{country_code}",
            "appid": self.api_key,
            "units": "metric",
        }
        raw = self._get_with_retry(BASE_URL, params, city)
        if raw is None:
            return None
        return self._normalize(raw, city)

    def test_connection(self) -> bool:
        try:
            resp = self.session.get(
                BASE_URL,
                params={"q": "London,GB", "appid": self.api_key, "units": "metric"},
                timeout=API_TIMEOUT,
            )
            if resp.status_code == 401:
                logger.error("API key is invalid or inactive.")
                return False
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.error("Connection test failed: %s", exc)
            return False

    def _get_with_retry(self, url: str, params: dict, label: str) -> Optional[dict]:
        for attempt in range(1, API_RETRY_ATTEMPTS + 1):
            try:
                self._call_count += 1
                resp = self.session.get(url, params=params, timeout=API_TIMEOUT)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 429:
                    wait = API_RETRY_DELAY * attempt
                    logger.warning("[%s] Rate limited. Waiting %ss (attempt %d/%d)",
                                   label, wait, attempt, API_RETRY_ATTEMPTS)
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    logger.error("[%s] City not found (404).", label)
                    return None

                logger.error("[%s] HTTP %d: %s", label, resp.status_code, resp.text[:200])

            except requests.exceptions.Timeout:
                logger.warning("[%s] Timeout on attempt %d/%d",
                               label, attempt, API_RETRY_ATTEMPTS)
            except requests.exceptions.ConnectionError:
                logger.warning("[%s] Connection error on attempt %d/%d",
                               label, attempt, API_RETRY_ATTEMPTS)
            except requests.RequestException as exc:
                logger.error("[%s] Unexpected request error: %s", label, exc)
                return None

            if attempt < API_RETRY_ATTEMPTS:
                time.sleep(API_RETRY_DELAY)

        logger.error("[%s] All %d attempts failed.", label, API_RETRY_ATTEMPTS)
        return None

    @staticmethod
    def _normalize(raw: dict, city: str) -> Dict[str, Any]:
        main    = raw.get("main", {})
        wind    = raw.get("wind", {})
        weather = raw.get("weather", [{}])[0]
        rain    = raw.get("rain", {})
        coord   = raw.get("coord", {})
        sys_    = raw.get("sys", {})

        return {
            "city":              city,
            "country":           sys_.get("country", "IN"),
            "latitude":          coord.get("lat"),
            "longitude":         coord.get("lon"),
            "timezone":          str(raw.get("timezone")),
            "timestamp":         datetime.utcfromtimestamp(raw.get("dt", 0)),
            "temperature_c":     main.get("temp"),
            "feels_like_c":      main.get("feels_like"),
            "temp_min_c":        main.get("temp_min"),
            "temp_max_c":        main.get("temp_max"),
            "humidity":          main.get("humidity"),
            "pressure_hpa":      main.get("pressure"),
            "wind_speed_mps":    wind.get("speed"),
            "wind_direction":    wind.get("deg"),
            "weather_condition": weather.get("description", "").title(),
            "weather_icon":      weather.get("icon", ""),
            "visibility_m":      raw.get("visibility"),
            "cloudiness_pct":    raw.get("clouds", {}).get("all"),
            "rain_1h_mm":        rain.get("1h", 0.0),
        }
