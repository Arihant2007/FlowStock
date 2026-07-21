import sys
import structlog
from http import HTTPStatus
import json

structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()

try:
    logger.warning("test", status_code=HTTPStatus.UNAUTHORIZED)
    print("Success")
except Exception as e:
    print("Error:", repr(e))
