import json
import logging
import sys
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "event_type": "etl_log",
            "message": record.getMessage(),
            "job_name": getattr(record, "job_name", None),
            "status": getattr(record, "status", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)

class ETLLogger:
    def __init__(self, job_name):
        self.job_name = job_name

        # Get the logger, set job and level
        self._logger = logging.getLogger(job_name)
        self._logger.setLevel(logging.INFO)

        # clear handlers since we want to ensure exactly one logger object across modules
        self._logger.handlers.clear()

        # add the handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        self._logger.addHandler(handler)

        # Do not propagate logs to parent loggers
        self._logger.propagate = False
    
    def _log(self, level, message, status=None, exc_info=False):
        self._logger.log(
            level,
            message,
            extra={
                "job_name": self.job_name,
                "status": status
            },
            exc_info=exc_info
        )
    
    def info(self, message):
        self._log(logging.INFO, message)

    def warning(self, message):
        self._log(logging.WARNING, message)
    
    def error(self, message, exc_info=False):
        self._log(logging.ERROR, message, exc_info=exc_info)
    
    def success(self, message="Job completed successfully"):
        self._log(logging.INFO, message, status="success")

    def failure(self, message="Job failed", exc_info=False):
        self._log(logging.ERROR, message, status="failure", exc_info=exc_info)

def get_logger(job_name):
    return ETLLogger(job_name=job_name)