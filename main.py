"""
main.py - Entry point for the Weather Data Pipeline System.

Usage:
    python main.py                  # run once (manual trigger)
    python main.py --schedule       # start the scheduler loop
    python main.py --dashboard      # print dashboard and exit
    python main.py --analysis       # print analysis report and exit
    python main.py --health         # run health checks and exit
    python main.py --report         # generate CSV + JSON reports and exit
"""

import argparse
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "config"))

from logger_setup import setup_logging
setup_logging()

import logging
logger = logging.getLogger("main")

from config     import API_KEY, CITIES
from database   import setup_database
from api_client import WeatherAPIClient


def main():
    parser = argparse.ArgumentParser(description="Weather Data Pipeline System")
    parser.add_argument("--schedule",  action="store_true", help="Start scheduler loop")
    parser.add_argument("--dashboard", action="store_true", help="Print real-time dashboard")
    parser.add_argument("--analysis",  action="store_true", help="Print analysis report")
    parser.add_argument("--health",    action="store_true", help="Run health checks")
    parser.add_argument("--report",    action="store_true", help="Generate file reports")
    parser.add_argument("--city",      default="Mumbai",    help="City for analysis (default: Mumbai)")
    args = parser.parse_args()

    logger.info("Initialising database...")
    setup_database()

    client = WeatherAPIClient(api_key=API_KEY)

    if API_KEY == "YOUR_API_KEY_HERE":
        logger.warning("=" * 60)
        logger.warning("API key not set!")
        logger.warning("Set env variable: export OPENWEATHER_API_KEY=your_key")
        logger.warning("Get a free key at: https://openweathermap.org/api")
        logger.warning("=" * 60)
        if not (args.dashboard or args.analysis or args.health or args.report):
            sys.exit(1)

    if args.health:
        from monitor import print_health_report
        print_health_report()

    elif args.dashboard:
        from reporter import print_dashboard
        print_dashboard()

    elif args.analysis:
        from query_system import print_analysis_report
        print_analysis_report(city=args.city)

    elif args.report:
        from reporter import generate_csv_report, generate_json_report
        csv_path  = generate_csv_report()
        json_path = generate_json_report()
        print(f"CSV  report: {csv_path}")
        print(f"JSON report: {json_path}")

    elif args.schedule:
        from scheduler import start_scheduler
        start_scheduler(client, run_now=True)

    else:
        from etl_pipeline import run_pipeline
        from reporter     import print_dashboard
        from monitor      import print_health_report

        logger.info("Running one-shot ETL pipeline...")
        result = run_pipeline(client)
        print_health_report()
        print_dashboard()
        print(f"\nPipeline result: {result}")


if __name__ == "__main__":
    main()
