import logging
import os
import sys
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger

# Map Python log level names to Pino-style numeric levels
PINO_LEVELS = {
    "TRACE": 10,
    "DEBUG": 20,
    "INFO": 30,
    "WARNING": 40,
    "ERROR": 50,
    "CRITICAL": 60,
}

class LokiJsonFormatter(jsonlogger.JsonFormatter):
    """Emits newline-delimited JSON matching the enphase-data-capture Pino format:
    {"level": 30, "time": "2026-02-21T14:51:18.985Z", "service": "vaillant-data-capture", "msg": "..."}
    """

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Pino-style numeric level
        level_name = record.levelname.upper()
        log_record["level"] = PINO_LEVELS.get(level_name, 30)

        # ISO8601 UTC timestamp
        log_record["time"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                             f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

        # Service label for Loki
        log_record["service"] = "vaillant-data-capture"

        # Rename 'message' -> 'msg' (Pino convention)
        log_record["msg"] = log_record.pop("message", record.getMessage())

        # Remove redundant fields added by python-json-logger
        for field in ("levelname", "name", "pathname", "filename", "module",
                      "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                      "created", "msecs", "relativeCreated", "thread", "threadName",
                      "processName", "process", "asctime", "taskName"):
            log_record.pop(field, None)


def setup_logger(name: str = "vaillant_capture") -> logging.Logger:
    log_level_name = os.getenv("VAILLANT_LOG_LEVEL", "info").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(LokiJsonFormatter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
