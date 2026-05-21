import logging
import sys
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

# Log directory
default_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../logs"))
LOG_DIR = os.environ.get("LOG_DIR", default_log_dir)
os.makedirs(LOG_DIR, exist_ok=True)

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "logger": record.name,
        }
        return json.dumps(log_record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = StructuredFormatter()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    master_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "master.log"),
        maxBytes=10*1024*1024,
        backupCount=5
    )
    master_handler.setFormatter(formatter)
    
    logger.handlers = []
    logger.addHandler(console_handler)
    logger.addHandler(master_handler)
    
    return logger
