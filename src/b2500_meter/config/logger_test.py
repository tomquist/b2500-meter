import logging
from unittest.mock import patch

from b2500_meter.config.logger import setLogLevel


@patch("b2500_meter.config.logger.logging.basicConfig")
def test_set_log_level_uses_timestamped_format(basic_config):
    setLogLevel("info")

    basic_config.assert_called_once()
    assert basic_config.call_args.kwargs == {
        "level": logging.INFO,
        "format": "%(asctime)s %(levelname)s:%(name)s:%(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
        "force": True,
    }
