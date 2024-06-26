import unittest
from unittest.mock import patch, MagicMock
from powermeter import Shrdzm


class TestShrdzm(unittest.TestCase):

    @patch("requests.Session.get")
    def test_shrdzm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"1.7.0": 5000, "2.7.0": 2000}
        mock_get.return_value = mock_response

        shrdzm = Shrdzm("192.168.1.5", "user", "pass")
        self.assertEqual(shrdzm.get_powermeter_watts(), [3000])


if __name__ == "__main__":
    unittest.main()
