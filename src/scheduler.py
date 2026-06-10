"""
scheduler.py - Automated job scheduling using APScheduler.
"""

import logging
import signal
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import COLLECTION_INTERVAL_MINUTES, REPORT_INTERVAL_HOURS

logger = logging.getLogger("scheduler")


def _etl_job(client):
    from etl_pipeline import run_pipeline
    logger.info("Scheduler: starting ETL job at %s", datetime.now())
    result = run_pipeline(client)
    logger.info("Scheduler: ETL job done -- %s", result)


def _report_job():
    from reporter import generate_csv_report, generate_json_report
    logger.info("Scheduler: generating reports...")
    csv_path  = generate_csv_report()
    json_path = generate_json_report()
    logger.info("Scheduler: reports saved -> %s | %s", csv_path, json_path)


def _health_job():
    from monitor import print_health_report
    print_health_report()


def start_scheduler(client, run_now: bool = True):
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval   import IntervalTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        _etl_job,
        trigger=IntervalTrigger(minutes=COLLECTION_INTERVAL_MINUTES),
        args=[client],
        id="etl_job",
        name="Weather ETL",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _report_job,
        trigger=IntervalTrigger(hours=REPORT_INTERVAL_HOURS),
        id="report_job",
        name="Report Generator",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _health_job,
        trigger=IntervalTrigger(minutes=30),
        id="health_job",
        name="Health Monitor",
        max_instances=1,
    )

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received -- stopping scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if run_now:
        logger.info("Running initial pipeline before entering schedule loop...")
        _etl_job(client)
        _health_job()

    logger.info(
        "Scheduler started. ETL every %d min | Reports every %d hr",
        COLLECTION_INTERVAL_MINUTES, REPORT_INTERVAL_HOURS,
    )
    scheduler.start()
