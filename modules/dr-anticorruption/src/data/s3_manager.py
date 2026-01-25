import boto3
from botocore.client import Config
from datetime import datetime
import json
import logging
from typing import Any, List
from src.config.config import config

logger = logging.getLogger(__name__)

class S3Manager:
    def __init__(self):
        endpoint = config.get('minio.endpoint', 'http://localhost:9000')
        access_key = config.get('minio.access_key', 'minioadmin')
        secret_key = config.get('minio.secret_key', 'minioadmin')
        self.bucket = config.get('minio.bucket', 's3-raw')
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4')
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except:
            self.s3.create_bucket(Bucket=self.bucket)
            logger.info(f"Created bucket {self.bucket}")

    def upload_json(self, data: List[dict[str, Any]], key: str):
        json_str = json.dumps(data, default=str, ensure_ascii=False, indent=2)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json_str.encode('utf-8'))
        logger.info(f"Uploaded {len(data)} records to s3://{self.bucket}/{key}")

    def get_partitioned_key(self, data_type: str, ingest_date: str = None) -> str:
        if ingest_date is None:
            ingest_date = datetime.now().strftime('%Y-%m-%d')
        year, month, day = ingest_date.split('-')
        return f"raw/{data_type}/year={year}/month={month}/day={day}/{data_type}_{ingest_date}.json"
