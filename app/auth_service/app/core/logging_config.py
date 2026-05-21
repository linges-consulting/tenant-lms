import logging
import sys
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

import os

# Log directory - default to a 'logs' directory in the project root if not specified
default_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../logs"))
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
        
        # Add extra fields if they exist (passed via extra={"key": "value"})
        if hasattr(record, "extra") and record.extra:
             log_record.update(record.extra)
             
        # Add correlation ID if present in the record attributes
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
            
        return json.dumps(log_record)

def setup_logging():
    # Base logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Formatter
    formatter = StructuredFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Master Log File Handler (All logs)
    master_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "master.log"),
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    master_handler.setFormatter(formatter)
    
    # Error Log File Handler (Errors only)
    error_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    logger.addHandler(console_handler)
    logger.addHandler(master_handler)
    logger.addHandler(error_handler)
    
    # Request/Response Logger
    req_resp_logger = logging.getLogger("request_response")
    req_resp_logger.setLevel(logging.INFO)
    req_resp_logger.propagate = False # Don't send these to the master log twice
    
    req_resp_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "request_response.log"),
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    req_resp_handler.setFormatter(formatter)
    req_resp_logger.addHandler(req_resp_handler)
    
    # Uvicorn loggers
    logging.getLogger("uvicorn.access").handlers = [console_handler, master_handler]
    logging.getLogger("uvicorn.error").handlers = [console_handler, master_handler]
    
    return logger
