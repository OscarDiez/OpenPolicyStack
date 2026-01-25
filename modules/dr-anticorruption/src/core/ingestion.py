"""
Core Ingestion Service for DR Anti-Corruption Platform.
Handles DGCP API extraction with config pagination rate limiting.
"""

import requests
import logging
from datetime import datetime
import json
import os
import sys
import argparse
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

from src.config.config import config
from src.data.s3_manager import S3Manager
from src.data.postgres import PostgresManager
from src.core.__init__ import logger  # Assume logger setup

logger = logging.getLogger("IngestionService")

class IngestionService:
    def __init__(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        self.base_url = config.get('dgcp.base_url')
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DR-AntiCorruption/1.0",
            "Accept": "application/json"
        })
        self.max_retries = config.get('dgcp.max_retries', 5)
        self.timeout_connect = config.get('dgcp.timeout_connect', 10)
        self.timeout_read = config.get('dgcp.timeout_read', 30)
        self.rate_limit_delay = config.get('dgcp.rate_limit_delay', 0.2)
        self.start_date = start_date
        self.end_date = end_date
        self.s3 = S3Manager()
        self.pg = PostgresManager()
        self.pg._init_db()

    def _get_date_params(self) -> Dict[str, str]:
        params = {}
        if self.start_date and self.end_date:
            params["fechaInicio"] = self.start_date
            params["fechaFin"] = self.end_date
        return params

    def _get_request(self, endpoint: str, params: dict = None) -> Optional[requests.Response]:
        url = f"{self.base_url}{endpoint}"
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                response = self.session.get(url, params=params, timeout=(self.timeout_connect, self.timeout_read))
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit hit for {url}. Waiting {retry_after}s.")
                    time.sleep(retry_after + 1)
                    retry_count += 1
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {url}: {e}")
                time.sleep(2 ** retry_count)
                retry_count += 1
        logger.error(f"Max retries exceeded for {endpoint}")
        return None

    def fetch_all_pages(self, endpoint: str, output_name: str, params: dict = None, limit: int = 100, max_pages: int = None):
        if params is None:
            params = {}
        params.update(self._get_date_params())
        params['limit'] = limit
        page = 1
        all_data = []
        logger.info(f"Starting ingestion for: {endpoint}")
        while True:
            if max_pages and page > max_pages:
                logger.info(f"Reached max_pages limit ({max_pages}). Stopping.")
                break
            params['page'] = page
            logger.info(f"Fetching page {page}...")
            response = self._get_request(endpoint, params)
            if not response:
                break
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for {endpoint} page {page}")
                break
            items = data if isinstance(data, list) else data.get('data', [])
            if isinstance(data, dict) and 'data' not in data:
                items = [data]
            if not items:
                logger.info(f"No more data at page {page}.")
                break
            all_data.extend(items)
            page += 1
            time.sleep(self.rate_limit_delay)
        if all_data:
            self._save_to_lake(all_data, output_name)
        else:
            logger.warning(f"No data found for {endpoint}")

    def _save_to_lake(self, data: List[Dict[str, Any]], data_type: str):
        ingest_date = self.start_date or datetime.now().strftime('%Y-%m-%d')
        key = self.s3.get_partitioned_key(data_type, ingest_date)
        self.s3.upload_json(data, key)
        table = f"dgcp_{data_type}"
        self.pg.insert_batch(data, table)

    # Specific methods unchanged, use self.fetch_all_pages

    def ingest_proveedores(self, **kwargs):
        self.fetch_all_pages("/proveedores", "proveedores", **kwargs)
        self.fetch_all_pages("/proveedores/rubro", "proveedores_rubros", **kwargs)
        self.fetch_all_pages("/proveedores/estadisticas-mujeres", "proveedores_mujeres", **kwargs)

    def ingest(self, target: str = "all", max_pages: int = None):
        """Generic ingest dispatcher."""
        fetch_kwargs = {'max_pages': max_pages} if max_pages else {}
        if target in ["all", "proveedores"]:
            self.ingest_proveedores(**fetch_kwargs)
        # Add other targets as needed
        logger.info(f"Ingestion for {target} complete.")

def main():
    parser = argparse.ArgumentParser(description="DGCP Data Ingestion Service")
    parser.add_argument("--target", type=str, default="all", 
                        choices=["all", "proveedores", "contratos", "procesos", "pacc", "ocds", "ofertas", "unidades", "tablas", "catalogo"])
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--startdate", type=str, default=None)
    parser.add_argument("--enddate", type=str, default=None)
    parser.add_argument("--config", type=str, default=None, help="Config path")
    args = parser.parse_args()
    if args.config:
        from src.config.config import config
        config.reload(args.config)
    service = IngestionService(start_date=args.startdate, end_date=args.enddate)
    fetch_kwargs = {'max_pages': args.max_pages} if args.max_pages else {}
    logger.info(f"Starting ingestion (Target: {args.target.upper()})")
    if args.target in ["all", "proveedores"]:
        service.ingest_proveedores(**fetch_kwargs)
    # ... other targets
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    main()
