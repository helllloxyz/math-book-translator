import logging
import os
import sys


class ErrorAccessLogFilter(logging.Filter):
    """Keep failed HTTP requests while hiding routine successful traffic."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        try:
            return int(args[4]) >= 400
        except (TypeError, ValueError):
            return True


def _level_from_env() -> int:
    configured = os.getenv("APP_LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, configured, logging.INFO)


def _configure_access_log() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.filters = [
        item for item in access_logger.filters if not isinstance(item, ErrorAccessLogFilter)
    ]

    mode = os.getenv("APP_ACCESS_LOG", "errors").strip().lower()
    if mode == "all":
        access_logger.disabled = False
    elif mode == "off":
        access_logger.disabled = True
    else:
        # The default keeps useful 4xx/5xx request records, but suppresses 2xx/3xx noise.
        access_logger.disabled = False
        access_logger.addFilter(ErrorAccessLogFilter())


def configure_logging() -> None:
    """Configure concise console logging for normal application use."""

    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logging.getLogger("app").setLevel(_level_from_env())
    for logger_name in ("httpcore", "httpx", "openai", "anthropic"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    _configure_access_log()
