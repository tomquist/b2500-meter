import logging
from unittest.mock import patch

from b2500_meter.config.logger import setLogLevel


def test_set_log_level_uses_timestamped_format():
    with patch("logging.basicConfig") as basic_config:
        setLogLevel("info")

    basic_config.assert_called_once_with(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
