import logging
from data_workflows import MonitorWorkflow, DataSourcingWorkflow
from workflow_settings import quantum_settings, hpc_settings, sourcing_settings, ai_settings, cybersecurity_settings

import schedule
import time
import os
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

env = os.getenv('ENV', 'dev')
# Verify environment variables are loaded correctly
logger.info("Environment variables loaded:")
logger.info(f"ENV: {os.getenv('ENV', 'not set')[:10]}")
logger.info(f"lite_llm_url: {os.getenv('lite_llm_url', 'not set')[:10]}")
logger.info(f"lite_llm_model: {os.getenv('lite_llm_model', 'not set')[:10]}")
logger.info(f"lite_llm_api_key: {os.getenv('lite_llm_api_key', 'not set')[:10]}")
logger.info(f"hook_teams: {os.getenv('hook_teams', 'not set')[:10]}")

# create necessary folders if missing
folders = ["data", "deliverables", "embedding"]
for folder in folders:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"Created folder: {folder}")
    else:
        logger.info(f"Folder already exists: {folder}")


sourcing_workflow = DataSourcingWorkflow("sourcing", sourcing_settings)
quantum_workflow = MonitorWorkflow("quantum", quantum_settings)
hpc_workflow = MonitorWorkflow("hpc", hpc_settings)
ai_workflow = MonitorWorkflow("ai", ai_settings)
cybersecurity_workflow = MonitorWorkflow("cybersecurity", cybersecurity_settings)


if env == 'prod':
    schedule.every().wednesday.at("0:35").do(lambda: sourcing_workflow.run())
    schedule.every().tuesday.at("06:35").do(lambda: cybersecurity_workflow.run())
    schedule.every().friday.at("06:35").do(lambda: quantum_workflow.run())
    schedule.every().monday.at("06:35").do(lambda: hpc_workflow.run())
    schedule.every().tuesday.at("06:35").do(lambda: ai_workflow.run())
else:
    # dev test - run sourcing immediately and quantum 10 seconds after
    #sourcing_workflow.run()
    #time.sleep(10)  # wait 10 seconds
    quantum_workflow.run()

while True:
    logger.info('Keep alive')
    schedule.run_pending()
    time.sleep(60)
