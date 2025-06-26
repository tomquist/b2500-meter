import unittest
from unittest.mock import patch, MagicMock

from powermeter.tq_em import TQEnergyManager


class TestTQEnergyManager(unittest.TestCase):
    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_three_phase(self, mock_get, mock_post):
        # login GET
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"serial": "123", "authentication": False}),
            MagicMock(status_code=200, json=lambda: {
                "1-0:21.4.0*255": 1,
                "1-0:41.4.0*255": 2,
                "1-0:61.4.0*255": 3,
            }),
        ]
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"authentication": True})

        meter = TQEnergyManager("192.168.0.10")
        self.assertEqual(meter.get_powermeter_watts(), (1.0, 2.0, 3.0))

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_total_only(self, mock_get, mock_post):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"serial": "321", "authentication": False}),
            MagicMock(status_code=200, json=lambda: {"1-0:1.4.0*255": 9}),
        ]
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"authentication": True})

        meter = TQEnergyManager("192.168.0.12")
        self.assertEqual(meter.get_powermeter_watts(), (9.0,))

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_relogin_on_expired_session(self, mock_get, mock_post):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"serial": "123", "authentication": False}),
            MagicMock(status_code=200, json=lambda: {"status": 901}),
            MagicMock(status_code=200, json=lambda: {"serial": "123", "authentication": False}),
            MagicMock(status_code=200, json=lambda: {"1-0:1.4.0*255": 5}),
        ]
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"authentication": True}),
            MagicMock(status_code=200, json=lambda: {"authentication": True}),
        ]

        meter = TQEnergyManager("192.168.0.11")
        self.assertEqual(meter.get_powermeter_watts(), (5.0,))


if __name__ == "__main__":
    unittest.main()

