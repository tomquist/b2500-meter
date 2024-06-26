import unittest
from .script import Script


class TestScript(unittest.TestCase):

    def test_script_get_powermeter_watts_integer(self):
        script = Script('echo "456"')
        self.assertEqual(script.get_powermeter_watts(), [456])

    def test_script_get_powermeter_watts_float(self):
        script = Script('echo "456.7"')
        self.assertEqual(script.get_powermeter_watts(), [456.7])


if __name__ == "__main__":
    unittest.main()
