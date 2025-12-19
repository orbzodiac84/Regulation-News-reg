from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import os
import logging
from src.main import run_cycle

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Scheduler")

def job_function():
    logger.info("Executing scheduled job...")
    run_cycle()

def main():
    scheduler = BlockingScheduler()
    
    # Schedule key: Runs every 10 minutes
    scheduler.add_job(job_function, 'interval', minutes=10, next_run_time=datetime.now())
    
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")

if __name__ == "__main__":
    main()
