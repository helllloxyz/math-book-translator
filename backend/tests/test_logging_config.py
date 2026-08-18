import logging

from app.logging_config import ErrorAccessLogFilter


def _access_record(status_code: int) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:12345", "GET", "/static/image.jpg", "1.1", status_code),
        exc_info=None,
    )


def test_access_log_filter_hides_success_and_cache_hits():
    access_filter = ErrorAccessLogFilter()

    assert access_filter.filter(_access_record(200)) is False
    assert access_filter.filter(_access_record(304)) is False


def test_access_log_filter_keeps_client_and_server_errors():
    access_filter = ErrorAccessLogFilter()

    assert access_filter.filter(_access_record(404)) is True
    assert access_filter.filter(_access_record(500)) is True
