"""SIGNALS report: figures come only from validated observations and are stated honestly.

    python3 Application/Tests/test_augurspex_signals_0493.py      (no display needed)
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))

from oracle_augurspex_signals import market_signal_report, rsi, sma, valid_closes  # noqa: E402


def bars(closes, start_day=1):
    return [{'time': f'2026-09-{start_day + i:02d}T00:00:00+00:00', 'close': close} for i, close in enumerate(closes)]


class Signals(unittest.TestCase):
    def test_sub_cent_prices_keep_significant_digits(self):
        report = market_signal_report('TINY-USD', {'source': 'fixture', 'candles': bars([0.0000100 + i * 1e-7 for i in range(25)])})
        self.assertIn('Latest recorded close: 0.0000124', report)
        self.assertNotIn('0.0000\n', report + '\n')
        self.assertIn('20-observation mean: 0.0000115', report)

    def test_change_names_the_two_observations_it_spans(self):
        report = market_signal_report('X', {'source': 'fixture', 'candles': bars([100, 90, 110])})
        self.assertIn('+10.00% (2026-09-01 to 2026-09-03)', report)

    def test_invalid_rows_never_reach_a_calculation(self):
        rows = bars([10, 11, 12]) + [
            {'time': 'not a date', 'close': 500}, {'time': '2026-09-20T00:00:00+00:00', 'close': 0},
            {'time': '2026-09-21T00:00:00+00:00', 'close': -4}, {'time': '2026-09-22T00:00:00+00:00', 'close': 'n/a'},
            {'time': '2026-09-23T00:00:00+00:00', 'close': float('nan')}, 'junk', None]
        self.assertEqual([price for _time, price in valid_closes(rows)], [10.0, 11.0, 12.0])

    def test_a_corrected_observation_replaces_the_earlier_one(self):
        rows = bars([10, 11]) + [{'time': '2026-09-02T00:00:00+00:00', 'close': 12}]
        self.assertEqual([price for _time, price in valid_closes(rows)], [10.0, 12.0])

    def test_indicators_need_enough_observations(self):
        self.assertIsNone(sma([1, 2, 3], 20))
        self.assertIsNone(rsi(list(range(1, 15)), 14))        # 14 prices give only 13 changes
        self.assertEqual(rsi(list(range(1, 16)), 14), 100.0)  # 14 rises, no falls
        self.assertEqual(rsi([5] * 15, 14), 50.0)             # no movement is neutral, not a division by zero
        report = market_signal_report('X', {'candles': bars([1, 2, 3])})
        self.assertEqual(report.count('not enough observations'), 3)

    def test_rsi_matches_a_hand_calculation(self):
        prices = [44, 44.5, 44, 45, 45.5, 45, 46, 46.5, 46, 47, 47.5, 47, 48, 48.5, 48]
        gains = (0.5 + 1 + 0.5 + 1 + 0.5 + 1 + 0.5 + 1 + 0.5) / 14
        losses = (0.5 * 5) / 14
        self.assertAlmostEqual(rsi(prices, 14), 100 - 100 / (1 + gains / losses), places=9)

    def test_no_observations_no_numbers(self):
        report = market_signal_report('X', {'candles': []})
        self.assertIn('No valid observations', report)
        self.assertNotIn('%', report)


if __name__ == '__main__':
    unittest.main(verbosity=1)
