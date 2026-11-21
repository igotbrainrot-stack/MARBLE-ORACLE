"""Regression checks for AUGURSPEX settings (the shared core used by the workspace).

0.4.9.9: the old browser companion (a loopback web server and its launcher
bridge) was removed with the two tests that exercised it; the suite's own
AUGURSPEX workspace replaced it in 0.4.7 and never started it.
"""
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from Augurspex.augurspex.core import read_settings, save_settings  # noqa: E402


class AugurspexRegressionTests(unittest.TestCase):
    def test_explicitly_empty_chart_slots_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            save_settings(home, {'layout': 4, 'symbols': [''] * 9})
            actual = read_settings(home)
            self.assertEqual(actual['symbols'], [''] * 9)

    def test_no_saved_settings_uses_starter_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            data = read_settings(Path(directory))
            self.assertTrue(any(data['symbols']))


if __name__ == '__main__':
    unittest.main()
