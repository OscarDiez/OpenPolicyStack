from apscheduler.schedulers.background import BackgroundScheduler
import time
import logging
from datetime import datetime, timedelta
from src.core.ingestion import IngestionService
from src.data.s3_manager import S3Manager

logger = logging.getLogger(__name__)

def daily_delta_ingest():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=1)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    logger.info(f"Running daily delta ingest from {start_str} to {end_str}")
    service = IngestionService(start_date=start_str, end_date=end_str)
    # TODO: Update service to use dates in fetch_all_pages params
    service.ingest_proveedores()
    # Add other ingests: contratos, procesos, etc.
    s3 = S3Manager()
    # TODO: service.save_to_s3()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_delta_ingest, 'cron', hour=2, minute=0, id='daily_ingest')
    scheduler.start()
    logger.info('Data Lake Scheduler started. Press Ctrl+C to exit.')
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()