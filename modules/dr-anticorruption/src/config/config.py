import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.config_path = Path(config_path or 'config/config.yaml')
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if not self.config_path.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            # Try finding it in src/config/config just in case
            alt_path = Path('src/config/config/config.yaml')
            if alt_path.exists():
                self.config_path = alt_path
                self._load()
                return

            self._set_defaults()
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.data = yaml.safe_load(f) or {}
            logger.info(f"Loaded config from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._set_defaults()

    def _set_defaults(self):
        self.data = {
            'data': {'dir': 'data'},
            'logging': {'level': 'INFO'},
            'dgcp': {'base_url': 'https://datosabiertos.dgcp.gob.do/api-dgcp/v1'},
            # Minimal defaults
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
            if value is None:
                return default
        return value

    def reload(self, path: str = None):
        if path:
            self.config_path = Path(path)
        self._initialized = False
        self.__init__(str(self.config_path))

# Global instance
config = Config()
