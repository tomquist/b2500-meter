import logging

from b2500_meter.config.logger import setLogLevel


def test_set_log_level_uses_timestamped_format():
    setLogLevel("info")

    root = logging.getLogger()
    assert root.level == logging.INFO
    assert root.handlers

    formatter = root.handlers[0].formatter
    assert formatter is not None
    assert formatter._fmt == "%(asctime)s %(levelname)s:%(name)s:%(message)s"
    assert formatter.datefmt == "%Y-%m-%d %H:%M:%S"
