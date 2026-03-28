import importlib
import logging
from unittest.mock import patch

from b2500_meter.config.logger import setLogLevel

logger_module = importlib.import_module("b2500_meter.config.logger")


def test_set_log_level_uses_timestamped_format():
    with patch.object(logger_module.logging, "basicConfig") as basic_config:
        setLogLevel("info")

    basic_config.assert_called_once()
    assert basic_config.call_args.kwargs == {
        "level": logging.INFO,
        "format": "%(asctime)s %(levelname)s:%(name)s:%(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
        "force": True,
    }
