"""
Logging Configuration Module
Structured logging for FastAPI Gateway
"""
import logging
import json
from datetime import datetime
from typing import Optional
import uuid


class JSONFormatter(logging.Formatter):
    """JSON Formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", use_json: bool = False):
    """
    Setup logging configuration for the application

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Use JSON formatter if True, else use standard format
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
            defaults={"correlation_id": "N/A"},
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.LoggerAdapter:
    """
    Get logger with correlation ID support

    Args:
        name: Logger name

    Returns:
        Logger adapter with correlation ID
    """
    logger = logging.getLogger(name)
    return logger


class CorrelationIDFilter(logging.Filter):
    """Filter to add correlation ID to log records"""

    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize filter with correlation ID

        Args:
            correlation_id: Correlation ID for request tracking
        """
        super().__init__()
        self.correlation_id = correlation_id or str(uuid.uuid4())

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record"""
        record.correlation_id = self.correlation_id
        return True


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())
