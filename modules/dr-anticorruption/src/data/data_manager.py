import json
import glob
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from src.config.config import config

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.data_dir = Path(config.get('data.dir', 'data'))
        self.cache: Dict[str, Any] = {}
        self.metadata_file = self.data_dir / 'metadata.json'
        self.metadata: Dict[str, Dict] = {}
        self._load_metadata()

    def _load_metadata(self):
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")

    def _save_metadata(self):
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def save_json(self, data: Any, filename: str):
        """Save data to JSON in the data directory."""
        filepath = self.data_dir / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(data) if isinstance(data, list) else 1} items to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save {filename}: {e}")

    def load_latest(self, pattern: str) -> List[Dict]:
        """
        Load latest JSON matching pattern from data_dir.
        Handles API wrappers, caches, updates metadata.
        """
        cache_key = pattern
        if cache_key in self.cache:
            logger.debug(f"Cache hit for {pattern}")
            return self.cache[cache_key]

        full_pattern = str(self.data_dir / pattern)
        files = glob.glob(full_pattern)
        if not files:
            logger.warning(f"No files found for {pattern}")
            return []

        latest_file = max(files, key=os.path.getmtime)
        logger.info(f"Loading latest: {latest_file}")

        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle wrappers
            content = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'payload' in item:
                        content.extend(item['payload'].get('content', []))
                    else:
                        content.append(item)
            elif isinstance(data, dict) and 'payload' in data:
                content = data['payload'].get('content', [])
            else:
                content = [data] if isinstance(data, dict) else data

            # Cache
            self.cache[cache_key] = content

            # Metadata
            h = hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()
            self.metadata[Path(latest_file).name] = {
                'file': latest_file,
                'timestamp': datetime.fromtimestamp(os.path.getmtime(latest_file)).isoformat(),
                'hash': h,
                'records': len(content)
            }
            self._save_metadata()

            return content

        except Exception as e:
            logger.error(f"Failed to load {latest_file}: {e}")
            return []

    def clear_cache(self):
        self.cache.clear()

    def get_metadata(self) -> Dict:
        return self.metadata

# Global instance
data_manager = DataManager()
