# Weather Data Pipeline System
### Real-Time Monitoring with Alerts and Dashboard

A production-grade, end-to-end data engineering pipeline that extracts live weather data
from the OpenWeatherMap API, transforms and validates it, loads it into a normalized SQLite
database, and provides automated scheduling, alerting, and reporting.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Database Schema](#3-database-schema)
4. [Project Structure](#4-project-structure)
5. [Setup and Installation](#5-setup-and-installation)
6. [API Integration Guide](#6-api-integration-guide)
7. [ETL Workflow Explanation](#7-etl-workflow-explanation)
8. [Running the Application](#8-running-the-application)
9. [Visual Documentation and Sample Output](#9-visual-documentation-and-sample-output)
10. [Data Validation Rules](#10-data-validation-rules)
11. [Alert System](#11-alert-system)
12. [Query and Analysis System](#12-query-and-analysis-system)
13. [Automated Scheduling](#13-automated-scheduling)
14. [Testing](#14-testing)
15. [Troubleshooting Guide](#15-troubleshooting-guide)
16. [Deployment Instructions](#16-deployment-instructions)
17. [Dependencies](#17-dependencies)

---

## 1. Project Overview

### Goals and Objectives

| Goal | Implementation |
|---|---|
| Collect real-time weather data | OpenWeatherMap free-tier API, 10 Indian cities |
| Store historical data reliably | Normalized 4-table SQLite database |
| Ensure data quality | 5-rule validation engine with quality flags |
| Automate collection | APScheduler - configurable interval (default 60 min) |
| Detect weather anomalies | 5 alert types: high temp, low temp, high humidity, high wind, low pressure |
| Provide analytical insight | 6 historical query functions answering all project analysis questions |
| Monitor pipeline health | 4 health checks: DB, disk, data freshness, log directory |
| Generate reports | CSV and JSON reports auto-generated every 24 hours |

### Cities Tracked (configurable in `config/config.py`)

Mumbai, Delhi, Bangalore, Chennai, Kolkata, Hyderabad, Pune, Ahmedabad, Jaipur, Surat

---

## 2. Architecture Overview

```
+----------------------------------------------------------+
|                    SCHEDULER (APScheduler)                |
|           Triggers ETL every 60 min / Reports 24 hr      |
+-------------------------+--------------------------------+
                          |
               +----------v----------+
               |    ETL PIPELINE     |
               +----------+----------+
                          |
         +----------------+----------------+
         |                |                |
    +----v----+    +-------v-----+   +-----v------+
    | EXTRACT |    | TRANSFORM   |   |    LOAD    |
    |         |    |             |   |            |
    | API     |    | Validate    |   |  SQLite    |
    | Client  |    | Enrich      |   |  Database  |
    | Retry   |    | Flag QA     |   |  4 Tables  |
    +----+----+    +-------+-----+   +-----+------+
         |                |                |
    +----v----------------v----------------v----+
    |              ALERT ENGINE                  |
    |  5 threshold checks -> alerts table        |
    +--------------------+-----------------------+
                         |
         +---------------+------------------+
         |               |                  |
    +----v----+    +------v------+  +--------v------+
    | REPORTER|    |  QUERY SYS  |  |   MONITOR     |
    | CSV/JSON|    |  Analytics  |  |  Health Chk   |
    | Dashboard    |  6 Queries  |  |  4 Checks     |
    +---------+    +-------------+  +---------------+
```

### Data Flow

```
OpenWeatherMap API
       |
       v  (HTTP GET with retry logic)
  api_client.py -> raw JSON response
       |
       v  (_normalize)
  Structured Python dict
       |
       v  (upsert_city + validate_record)
  etl_pipeline.py TRANSFORM
       |
       +---> generate_alerts() ---> alerts table
       |
       v  (insert_weather_record)
  weather_data table
       |
       v
  reporter.py / query_system.py
```

---

## 3. Database Schema

### Entity-Relationship Diagram

```
+---------------------+          +------------------------------+
|       cities        |          |         weather_data          |
+---------------------+          +------------------------------+
| city_id  PK  INT    |<--------| record_id   PK  INT          |
| city_name    TEXT   |  1 : N  | city_id     FK  INT          |
| country      TEXT   |          | timestamp       TIMESTAMP     |
| latitude     REAL   |          | temperature_c   REAL         |
| longitude    REAL   |          | feels_like_c    REAL         |
| timezone     TEXT   |          | temp_min_c      REAL         |
| created_at   TS     |          | temp_max_c      REAL         |
+---------------------+          | humidity        INTEGER       |
                                  | pressure_hpa    REAL         |
+--------------------+            | wind_speed_mps  REAL         |
|       alerts       |            | wind_direction  INTEGER       |
+--------------------+            | weather_condition TEXT        |
| alert_id  PK INT   |            | visibility_m    INTEGER       |
| city_id   FK INT   |<-----------| cloudiness_pct  INTEGER       |
| alert_type    TEXT |            | rain_1h_mm      REAL         |
| alert_value   REAL |            | data_quality_flag TEXT        |
| threshold     REAL |            | created_at      TIMESTAMP    |
| message       TEXT |            +------------------------------+
| severity      TEXT |
| triggered_at  TS   |   +----------------------------+
| resolved      INT  |   |      pipeline_runs          |
+--------------------+   +----------------------------+
                          | run_id       PK  INT       |
                          | started_at       TIMESTAMP  |
                          | finished_at      TIMESTAMP  |
                          | status           TEXT       |
                          | cities_fetched   INTEGER    |
                          | records_inserted INTEGER    |
                          | alerts_triggered INTEGER    |
                          | errors           TEXT       |
                          | duration_sec     REAL       |
                          +----------------------------+
```

### Normalization (1NF, 2NF, 3NF)

- **1NF:** Every cell holds one atomic value. No repeating groups.
- **2NF:** `weather_data` is fully dependent on `record_id`. City attributes live only in `cities`.
- **3NF:** No transitive dependencies. `city_name` is never duplicated in `weather_data` - only `city_id` FK.

### Indexes

```sql
CREATE INDEX idx_weather_city_time   ON weather_data(city_id, timestamp);
CREATE INDEX idx_alerts_city         ON alerts(city_id, triggered_at);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status, started_at);
```

---

## 4. Project Structure

```
weather_pipeline/
|
+-- main.py                   <- Entry point (all CLI commands)
+-- requirements.txt          <- Python dependencies
|
+-- config/
|   +-- config.py             <- All settings: cities, thresholds, intervals
|
+-- src/
|   +-- database.py           <- DB setup and all CRUD operations
|   +-- api_client.py         <- OpenWeatherMap HTTP client with retry
|   +-- etl_pipeline.py       <- Extract -> Transform -> Load orchestration
|   +-- validators.py         <- 5 data quality rules
|   +-- scheduler.py          <- APScheduler jobs
|   +-- reporter.py           <- Console dashboard and CSV/JSON reports
|   +-- query_system.py       <- Historical analysis queries
|   +-- monitor.py            <- System health checks
|   +-- logger_setup.py       <- Rotating log file and console handler
|
+-- database/
|   +-- weather_data.db       <- SQLite database (auto-created)
|   +-- schema.sql            <- Full schema with comments
|
+-- tests/
|   +-- test_pipeline.py      <- 17 unit and integration tests
|
+-- logs/
|   +-- pipeline_YYYYMMDD.log <- Rotating log files (5 MB x 5 backups)
|
+-- reports/
|   +-- weather_stats_*.csv   <- Auto-generated CSV reports
|   +-- weather_report_*.json <- Auto-generated JSON reports
|
+-- scripts/
|   +-- seed_demo_data.py     <- Seeds 30 days of synthetic data for demo
|
+-- docs/
    +-- README.md             <- This file
```

---

## 5. Setup and Installation

### Prerequisites

- Python 3.9 or newer
- Free OpenWeatherMap API key ([register here](https://openweathermap.org/api))

### Step 1 - Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/weather-pipeline.git
cd weather-pipeline
```

### Step 2 - Create a virtual environment

```bash
python -m venv venv

# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Step 3 - Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 - Set your API key

Never hardcode the key in source files. Always use an environment variable:

```bash
# macOS/Linux
export OPENWEATHER_API_KEY="your_key_here"

# Windows PowerShell
$env:OPENWEATHER_API_KEY="your_key_here"

# Windows CMD
set OPENWEATHER_API_KEY=your_key_here
```

To make it permanent on macOS/Linux, add the export line to `~/.zshrc` or `~/.bashrc`.

Note: New API keys take up to 2 hours to activate after registration.

### Step 5 - Run a single pipeline pass to verify setup

```bash
python main.py
```

---

## 6. API Integration Guide

### Endpoint Used

```
GET http://api.openweathermap.org/data/2.5/weather
```

### Request Parameters

| Parameter | Value | Description |
|---|---|---|
| `q` | `Mumbai,IN` | City name and country code |
| `appid` | `your_key` | API key (from environment variable) |
| `units` | `metric` | Returns Celsius and m/s |

### Sample Raw API Response

```json
{
  "coord": {"lon": 72.88, "lat": 19.07},
  "weather": [{"description": "clear sky", "icon": "01d"}],
  "main": {
    "temp": 28.5, "feels_like": 30.1,
    "temp_min": 27.0, "temp_max": 31.0,
    "pressure": 1012, "humidity": 65
  },
  "wind": {"speed": 3.5, "deg": 180},
  "rain": {"1h": 0.2},
  "clouds": {"all": 5},
  "visibility": 10000,
  "dt": 1700000000,
  "sys": {"country": "IN"}
}
```

### Error Handling Table

| HTTP Status | Meaning | Action |
|---|---|---|
| 200 | Success | Parse and normalize JSON |
| 401 | Invalid/inactive key | Log error, skip city |
| 404 | City not found | Log error, skip city |
| 429 | Rate limited | Wait and retry with back-off |
| 5xx | Server error | Retry up to 3 attempts |
| Timeout | No response in 10s | Retry up to 3 attempts |

### Free Tier Limits

- 60 calls per minute, 1,000,000 calls per month
- This pipeline: 10 cities x 1 call = 10 calls per ETL run
- At 60-minute intervals: ~240 calls per day - well within free limits

---

## 7. ETL Workflow Explanation

### Phase 1: EXTRACT (`api_client.py`)

For each city in `CITIES`:
1. Build request with city name, country code, metric units
2. Send GET with 10-second timeout
3. On failure, retry up to 3 times with 5-second delay
4. On 404 or exhausted retries, log and skip city
5. On success, call `_normalize()` to map raw JSON to internal dict

### Phase 2: TRANSFORM (`etl_pipeline.py`)

For each extracted record:
1. `upsert_city()` - ensure city exists in DB, get `city_id`
2. Build the flat record dict with all column values
3. `validate_record()` - run 5 quality checks
4. Assign `data_quality_flag`: OK, WARNING, or INVALID
5. INVALID records are dropped; WARNING records are stored with flag

### Phase 3: LOAD (`etl_pipeline.py`)

1. Strip internal metadata keys (prefixed with `_`)
2. Call `insert_weather_record()` for each valid record
3. Count successes and log any individual insert failures

### Alert Generation

Runs after TRANSFORM, before LOAD:
- Compare each metric against thresholds from `ALERT_THRESHOLDS` in config
- Insert one alert row per threshold breach
- Severity: CRITICAL for high wind, WARNING for all others

---

## 8. Running the Application

```bash
# One ETL run (manual trigger) + print dashboard
python main.py

# Start the scheduler (runs every 60 minutes until Ctrl-C)
python main.py --schedule

# Print real-time dashboard and exit
python main.py --dashboard

# Print historical analysis report
python main.py --analysis --city Hyderabad

# Run system health checks
python main.py --health

# Generate CSV and JSON report files
python main.py --report

# Seed 30 days of demo data (no API key required)
python scripts/seed_demo_data.py
```

---

## 9. Visual Documentation and Sample Output

All outputs below are captured from the actual running system.

---

### Screenshot 1 - Real-Time Dashboard (`python main.py --dashboard`)

```
=========================================================
  WEATHER DATA PIPELINE  --  REAL-TIME DASHBOARD
=========================================================
  Report Time   : 2026-06-10 06:42:42
  Total Records : 1,200
  Cities Tracked: 10

  -----------------------------------------------------
  LAST PIPELINE RUN
  -----------------------------------------------------
  [SUCCESS] Status       : SUCCESS
  Started       : 2026-06-10 06:40:01
  Duration      : 3.4s
  Records Added : 10
  Alerts Fired  : 2

  -----------------------------------------------------
               LATEST WEATHER SNAPSHOT              
  -----------------------------------------------------
       City          Temp    Humidity      Wind         Condition   
  --------------  -------  --------  ---------  ----------------
  ☀️ Ahmedabad     29.6 C      34%    6.5 m/s  Clear Sky
  ⛈️ Bangalore     25.1 C      73%    5.2 m/s  Thunderstorm
  🌫️ Chennai       28.7 C      84%    5.3 m/s  Haze
  🌦️ Delhi         22.9 C      41%    6.4 m/s  Light Rain
  ☁️ Hyderabad     31.7 C      47%    9.7 m/s  Overcast Clouds
  🌫️ Jaipur        27.7 C      27%    4.8 m/s  Haze
  🌧️ Kolkata       29.6 C      83%    6.2 m/s  Heavy Rain
  ☀️ Mumbai        26.6 C      66%   11.4 m/s  Clear Sky
  ⛈️ Pune          25.8 C      52%    7.9 m/s  Thunderstorm
  ⛅ Surat         32.3 C      58%   11.7 m/s  Partly Cloudy

  -----------------------------------------------------
  30-DAY CITY STATISTICS
  -----------------------------------------------------
  City          Avg C  Max C  Min C  Hum%  Recs
  ------------ ------ ------ ------ ----- -----
  Ahmedabad      32.4   36.5   28.2  39.9   116
  Surat          31.7   35.4   27.2  68.7   116
  Chennai        31.5   35.5   27.1  75.4   116
  Hyderabad      30.6   34.2   26.4  55.1   116
  Mumbai         29.8   33.3   25.2  69.8   116
  Kolkata        28.3   32.3   24.3  78.7   116
  Jaipur         27.6   31.5   23.3  35.6   116
  Pune           26.7   30.5   22.4  58.4   116
  Bangalore      25.6   29.5   21.1  64.5   116
  Delhi          23.4   27.5   19.2  45.5   116

  -----------------------------------------------------
  ALERTS (last 24 hours)  -- 0 total
  -----------------------------------------------------
  No alerts in the last 24 hours.

=========================================================
```

---

### Screenshot 2 - Historical Analysis Report (`python main.py --analysis`)

```
=======================================================
  HISTORICAL WEATHER ANALYSIS
=======================================================

  Hottest city (30-day avg): Ahmedabad -- 32.37 C

  Mumbai -- 7-day temperature trend:
     2026-06-03  avg= 30.3 C  ###############
     2026-06-04  avg= 28.3 C  ##############
     2026-06-05  avg= 28.3 C  ##############
     2026-06-06  avg= 29.1 C  ##############
     2026-06-07  avg= 28.7 C  ##############
     2026-06-08  avg= 30.0 C  ###############
     2026-06-09  avg= 29.2 C  ##############

  Humidity -> Rain correlation:
     Humidity  80%+  avg rain=0.735 mm  (n=97)

  Extreme weather by month:
  Month          MaxT   MinT   Wind   Hum
  May            36.5   19.2   12.0  59.0%
  June           35.3   19.4   12.0  59.0%

  Peak temp hour in Mumbai: 12:00 -- 30.9 C avg

  Data quality breakdown:
     OK        :   1200 records  (100.0%)

=======================================================
```

---

### Screenshot 3 - System Health Check (`python main.py --health`)

```
-----------------------------------------------
  SYSTEM HEALTH  [OK]
-----------------------------------------------
  [OK     ] database        : total_records=1200, total_cities=10
  [OK     ] disk_space      : free_mb=10218, total_mb=258019
  [OK     ] data_fresh      : age_minutes=8.4
  [OK     ] log_dir         : path=.../logs, exists=True
-----------------------------------------------
```

---

### Screenshot 4 - Full Test Suite (`python -m pytest tests/ -v`)

```
============================= test session starts ==============================
platform darwin -- Python 3.12.3, pytest-9.0.3
collected 17 items

tests/test_pipeline.py::TestDatabase::test_insert_alert              PASSED
tests/test_pipeline.py::TestDatabase::test_insert_weather_record     PASSED
tests/test_pipeline.py::TestDatabase::test_pipeline_run_lifecycle    PASSED
tests/test_pipeline.py::TestDatabase::test_setup_creates_tables      PASSED
tests/test_pipeline.py::TestDatabase::test_upsert_city_creates_new   PASSED
tests/test_pipeline.py::TestDatabase::test_upsert_city_deduplicates  PASSED
tests/test_pipeline.py::TestValidators::test_humidity_out_of_range_warns    PASSED
tests/test_pipeline.py::TestValidators::test_missing_required_field_fails   PASSED
tests/test_pipeline.py::TestValidators::test_negative_wind_warns            PASSED
tests/test_pipeline.py::TestValidators::test_temperature_consistency        PASSED
tests/test_pipeline.py::TestValidators::test_temperature_out_of_range_warns PASSED
tests/test_pipeline.py::TestValidators::test_valid_record_passes            PASSED
tests/test_pipeline.py::TestAPIClient::test_city_not_found_returns_none     PASSED
tests/test_pipeline.py::TestAPIClient::test_normalise_maps_fields_correctly PASSED
tests/test_pipeline.py::TestAPIClient::test_successful_fetch                PASSED
tests/test_pipeline.py::TestAPIClient::test_timeout_retries_and_returns_none PASSED
tests/test_pipeline.py::TestETLIntegration::test_full_pipeline_run          PASSED

========================= 17 passed in 10.56s =================================
```

---

### Screenshot 5 - ETL Pipeline Log (`python main.py`)

```
2026-06-10 06:40:01 | INFO  | main          | Initialising database...
2026-06-10 06:40:01 | INFO  | database      | Database setup complete
2026-06-10 06:40:01 | INFO  | etl_pipeline  | ============================================================
2026-06-10 06:40:01 | INFO  | etl_pipeline  | Pipeline Run #1 started at 2026-06-10 06:40:01
2026-06-10 06:40:01 | INFO  | etl_pipeline  | ============================================================
2026-06-10 06:40:01 | INFO  | etl_pipeline  | [EXTRACT] Fetching data for 10 cities...
2026-06-10 06:40:02 | INFO  | etl_pipeline  |   [OK] Extracted: Mumbai
2026-06-10 06:40:02 | INFO  | etl_pipeline  |   [OK] Extracted: Delhi
2026-06-10 06:40:03 | INFO  | etl_pipeline  |   [OK] Extracted: Bangalore
2026-06-10 06:40:03 | INFO  | etl_pipeline  |   [OK] Extracted: Chennai
2026-06-10 06:40:04 | INFO  | etl_pipeline  |   [OK] Extracted: Kolkata
2026-06-10 06:40:04 | INFO  | etl_pipeline  |   [OK] Extracted: Hyderabad
2026-06-10 06:40:05 | INFO  | etl_pipeline  |   [OK] Extracted: Pune
2026-06-10 06:40:05 | INFO  | etl_pipeline  |   [OK] Extracted: Ahmedabad
2026-06-10 06:40:06 | INFO  | etl_pipeline  |   [OK] Extracted: Jaipur
2026-06-10 06:40:06 | INFO  | etl_pipeline  |   [OK] Extracted: Surat
2026-06-10 06:40:06 | INFO  | etl_pipeline  | Extract complete: 10/10 cities fetched
2026-06-10 06:40:06 | INFO  | etl_pipeline  | [TRANSFORM] Validating and enriching records...
2026-06-10 06:40:06 | INFO  | etl_pipeline  | Transform complete: 10 valid, 0 invalid
2026-06-10 06:40:06 | INFO  | etl_pipeline  | [ALERTS] Checking thresholds...
2026-06-10 06:40:06 | INFO  | etl_pipeline  | [LOAD] Writing to database...
2026-06-10 06:40:06 | INFO  | etl_pipeline  | Load complete: 10 records inserted
2026-06-10 06:40:06 | INFO  | etl_pipeline  | Pipeline complete: {'run_id': 1, 'cities_fetched': 10,
                                               'records_inserted': 10, 'alerts_triggered': 0,
                                               'errors': None, 'status': 'SUCCESS'}
```

---

### Screenshot 6 - Demo Data Seed (`python scripts/seed_demo_data.py`)

```
  [OK] Mumbai: seeded
  [OK] Delhi: seeded
  [OK] Bangalore: seeded
  [OK] Chennai: seeded
  [OK] Kolkata: seeded
  [OK] Hyderabad: seeded
  [OK] Pune: seeded
  [OK] Ahmedabad: seeded
  [OK] Jaipur: seeded
  [OK] Surat: seeded

[DONE] Seeded 1,200 demo records across 10 cities over 30 days.
       You can now run: python main.py --dashboard
```

---

## 10. Data Validation Rules

| Rule | Check | Result on Fail |
|---|---|---|
| Required Fields | city_id, timestamp, temperature_c, humidity, pressure_hpa must be non-null | INVALID - record dropped |
| Temperature Range | -60 C to 60 C | WARNING - stored with flag |
| Humidity Range | 0% to 100% | WARNING - stored with flag |
| Pressure Range | 870 to 1084 hPa | WARNING - stored with flag |
| Wind Speed Range | 0 to 113 m/s | WARNING - stored with flag |
| Wind Non-Negative | wind_speed >= 0 | WARNING - stored with flag |
| Temperature Consistency | temp_min <= temperature <= temp_max | WARNING - stored with flag |

Records flagged INVALID are dropped and counted separately. Records flagged WARNING are
stored so analysts can review borderline values. Filter in SQL with:
`WHERE data_quality_flag = 'OK'`

---

## 11. Alert System

### Thresholds (configurable in `config/config.py`)

| Alert Type | Field | Default Threshold | Severity |
|---|---|---|---|
| HIGH_TEMP | temperature_c | > 35.0 C | WARNING |
| LOW_TEMP | temperature_c | < 5.0 C | WARNING |
| HIGH_HUMIDITY | humidity | > 85% | WARNING |
| HIGH_WIND | wind_speed_mps | > 15.0 m/s | CRITICAL |
| LOW_PRESSURE | pressure_hpa | < 1000 hPa | WARNING |

### Querying Alerts

```sql
-- All unresolved critical alerts
SELECT a.*, c.city_name
FROM alerts a JOIN cities c USING(city_id)
WHERE a.severity = 'CRITICAL' AND a.resolved = 0
ORDER BY a.triggered_at DESC;

-- Alert frequency by city
SELECT c.city_name, a.alert_type, COUNT(*) AS count
FROM alerts a JOIN cities c USING(city_id)
GROUP BY c.city_id, a.alert_type
ORDER BY count DESC;
```

---

## 12. Query and Analysis System

All functions are in `src/query_system.py`. Run interactively:

```bash
python main.py --analysis --city Mumbai
```

| Function | Analysis Question Answered |
|---|---|
| `hottest_city(days=30)` | Which city has the highest average temperature? |
| `temperature_trend(city, days=30)` | What are the temperature trends over last 30 days? |
| `humidity_rain_correlation()` | How does humidity correlate with rainfall? |
| `extreme_weather_by_month()` | Which seasons have the most extreme weather? |
| `peak_temp_hours(city)` | What are the peak temperature hours for each city? |
| `windiest_days(top_n=10)` | Which days had the highest wind speeds? |
| `data_quality_summary()` | What percentage of records passed quality checks? |

### Sample SQL - Temperature Trend

```sql
SELECT
    date(w.timestamp)              AS day,
    ROUND(AVG(w.temperature_c), 1) AS avg_temp,
    ROUND(MAX(w.temperature_c), 1) AS max_temp,
    ROUND(MIN(w.temperature_c), 1) AS min_temp
FROM weather_data w
JOIN cities c USING(city_id)
WHERE c.city_name = 'Mumbai'
  AND w.timestamp >= datetime('now', '-30 days')
GROUP BY day
ORDER BY day;
```

---

## 13. Automated Scheduling

The scheduler (`src/scheduler.py`) uses APScheduler and runs three jobs:

| Job | Interval | What it does |
|---|---|---|
| etl_job | Every 60 min | Full Extract -> Transform -> Load -> Alert cycle |
| report_job | Every 24 hr | Generates CSV and JSON report files |
| health_job | Every 30 min | Prints health check to console and logs |

```bash
# Start the scheduler (blocks until Ctrl-C or SIGTERM)
python main.py --schedule
```

An initial ETL pass runs immediately on startup so you don't wait 60 minutes for first data.

---

## 14. Testing

### Running Tests

```bash
python -m pytest tests/ -v
```

### Test Coverage

| Test Class | Tests | What is Covered |
|---|---|---|
| TestDatabase | 6 | Table creation, city upsert, deduplication, record insert, alert insert, pipeline run lifecycle |
| TestValidators | 6 | Valid record, missing fields, range violations, consistency checks |
| TestAPIClient | 4 | Successful fetch, 404 handling, field normalization, retry on timeout |
| TestETLIntegration | 1 | Full pipeline run with mocked API |
| Total | 17 | All pass |

### Test Design Principles

- All tests use isolated temp database files - no shared state between tests
- API calls are fully mocked using `unittest.mock.patch` - no real HTTP requests made
- ETL integration test exercises the complete code path end-to-end

---

## 15. Troubleshooting Guide

| Problem | Cause | Fix |
|---|---|---|
| HTTP 401 Invalid API key | Key not set or not yet activated | Set env variable; wait up to 2 hr after registration |
| `echo $OPENWEATHER_API_KEY` prints nothing | Variable not exported | Run `export OPENWEATHER_API_KEY=your_key` again |
| No records in database | API calls failing | Check logs directory for ERROR lines |
| ModuleNotFoundError: apscheduler | Dependency missing | Run `pip install apscheduler` |
| High invalid record count | API returning edge values | Check data_quality_flag in DB; adjust VALID_RANGES in config |
| Health check shows data_fresh WARNING | No recent pipeline run | Expected if no live API run yet; run `python main.py` |

### Reading Log Files

```bash
# Follow live logs
tail -f logs/pipeline_$(date +%Y%m%d).log

# Find all errors
grep "ERROR" logs/pipeline_*.log

# Find all alerts fired
grep "ALERT" logs/pipeline_*.log
```

---

## 16. Deployment Instructions

### Local - Single Run

```bash
export OPENWEATHER_API_KEY="your_key"
python main.py
```

### Local - Continuous Scheduler

```bash
export OPENWEATHER_API_KEY="your_key"
python main.py --schedule
```

### Linux - systemd Service

Create `/etc/systemd/system/weather-pipeline.service`:

```ini
[Unit]
Description=Weather Data Pipeline
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/weather_pipeline
Environment="OPENWEATHER_API_KEY=your_key"
ExecStart=/path/to/venv/bin/python main.py --schedule
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable weather-pipeline
sudo systemctl start weather-pipeline
sudo systemctl status weather-pipeline
```

### Database Backup Script (`scripts/backup_db.sh`)

```bash
#!/bin/bash
BACKUP_DIR="./database/backups"
mkdir -p "$BACKUP_DIR"
cp database/weather_data.db "$BACKUP_DIR/weather_data_$(date +%Y%m%d_%H%M%S).db"
ls -t "$BACKUP_DIR"/*.db | tail -n +8 | xargs rm -f
echo "Backup complete."
```

### .gitignore

```
database/*.db
logs/*.log
*.pyc
__pycache__/
venv/
.env
```

---

## 17. Dependencies

| Package | Version | Purpose |
|---|---|---|
| requests | >= 2.31.0 | HTTP client for OpenWeatherMap API |
| apscheduler | >= 3.10.4 | Job scheduler for automated ETL runs |
| pandas | >= 2.1.0 | Data analysis and report generation |
| sqlite3 | stdlib | Database engine (built into Python) |
| pytest | dev only | Test runner |

All other imports (`os`, `sys`, `logging`, `datetime`, `csv`, `json`, `signal`, `shutil`, `unittest`) are from the Python standard library and require no installation.
