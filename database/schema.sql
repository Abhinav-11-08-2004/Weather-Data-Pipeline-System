-- ============================================================
-- Weather Data Pipeline - Complete Database Schema
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS cities (
    city_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name  TEXT    NOT NULL,
    country    TEXT    NOT NULL DEFAULT 'IN',
    latitude   REAL,
    longitude  REAL,
    timezone   TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(city_name, country)
);

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
);

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
);

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
);

CREATE INDEX IF NOT EXISTS idx_weather_city_time    ON weather_data(city_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp    ON weather_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_city          ON alerts(city_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status, started_at);

-- Useful views
CREATE VIEW IF NOT EXISTS daily_city_summary AS
SELECT
    c.city_name,
    date(w.timestamp)              AS day,
    COUNT(*)                        AS records,
    ROUND(AVG(w.temperature_c), 1) AS avg_temp,
    ROUND(MAX(w.temperature_c), 1) AS max_temp,
    ROUND(MIN(w.temperature_c), 1) AS min_temp,
    ROUND(AVG(w.humidity), 0)      AS avg_humidity,
    ROUND(SUM(w.rain_1h_mm), 2)    AS total_rain_mm
FROM weather_data w
JOIN cities c USING(city_id)
GROUP BY c.city_id, day;

CREATE VIEW IF NOT EXISTS active_alerts AS
SELECT a.alert_id, c.city_name, a.alert_type, a.alert_value,
       a.threshold, a.severity, a.message, a.triggered_at
FROM alerts a
JOIN cities c USING(city_id)
WHERE a.resolved = 0
ORDER BY a.severity DESC, a.triggered_at DESC;
