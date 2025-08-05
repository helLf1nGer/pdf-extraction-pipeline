"""
Logging configuration for the PDF extraction API.

This module sets up structured logging with proper formatting,
file rotation, and different log levels for development and production.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured information."""
        # Get extra fields from the record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                'filename', 'module', 'lineno', 'funcName', 'created', 
                'msecs', 'relativeCreated', 'thread', 'threadName', 
                'processName', 'process', 'getMessage', 'stack_info', 
                'exc_info', 'exc_text'
            ]:
                extra_fields[key] = value
        
        # Base log message
        base_msg = super().format(record)
        
        # Add structured fields if present
        if extra_fields:
            extra_str = " ".join([f"{k}={v}" for k, v in extra_fields.items()])
            return f"{base_msg} | {extra_str}"
        
        return base_msg


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Set up application logging with file rotation and structured format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Set log level
    numeric_level = getattr(logging, log_level.upper())
    root_logger.setLevel(numeric_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Console formatter (simpler for development)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "api.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    
    # File formatter (structured for parsing)
    file_formatter = StructuredFormatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    # Log setup completion
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured",
        extra={
            "log_level": log_level,
            "log_dir": str(log_path),
            "handlers": len(root_logger.handlers)
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class APILogger:
    """Context manager for API request logging."""
    
    def __init__(self, request_id: str, endpoint: str, method: str):
        self.request_id = request_id
        self.endpoint = endpoint
        self.method = method
        self.logger = get_logger("api.requests")
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.info(
            f"API request started",
            extra={
                "request_id": self.request_id,
                "endpoint": self.endpoint,
                "method": self.method,
                "event": "request_start"
            }
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type:
            self.logger.error(
                f"API request failed",
                extra={
                    "request_id": self.request_id,
                    "endpoint": self.endpoint,
                    "method": self.method,
                    "duration": duration,
                    "error": str(exc_val),
                    "event": "request_error"
                }
            )
        else:
            self.logger.info(
                f"API request completed",
                extra={
                    "request_id": self.request_id,
                    "endpoint": self.endpoint,
                    "method": self.method,
                    "duration": duration,
                    "event": "request_complete"
                }
            )


def log_job_event(job_id: str, event: str, **kwargs):
    """Log job processing events with structured data."""
    logger = get_logger("api.jobs")
    
    extra_data = {
        "job_id": job_id,
        "event": event,
        **kwargs
    }
    
    if event in ["job_started", "job_completed"]:
        logger.info(f"Job {event}", extra=extra_data)
    elif event in ["job_failed", "job_error"]:
        logger.error(f"Job {event}", extra=extra_data)
    else:
        logger.debug(f"Job {event}", extra=extra_data)