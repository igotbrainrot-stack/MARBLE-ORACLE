"""0.4.9.3: PASSPHRASE engine security properties. Runs without a display.

    python3 Application/Tests/test_passphrase_security_0493.py

* every random draw comes from the operating system's cryptographic source
  (the `secrets` module); the predictable `random` module is never used;
* a phrase never appears in an exception message (unhandled errors are
  written to the suite's error log) and the engine writes no files;
* the published entropy figure matches the word list actually shipped;
* a re-roll changes exactly the part asked for.
"""
from __future__ import annotations

import ast
import builtins
import math
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

import oracle_dicekey  # noqa: E402
from oracle_dicekey import PARTS, SYMBOLS, Dicekey  # noqa: E402


class Passphrase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Dicekey()

    def test_ships_the_full_eff_long_list(self):
        self.assertEqual(self.engine.size, 7776)
        self.assertEqual(self.engine.source, 'eff_large.txt')

    def test_no_predictable_random_module_anywhere_in_the_passphrase_code(self):
        for name in ('oracle_dicekey.py', 'marble_passphrase_tab.py'):
            tree = ast.parse((APP / name).read_text(encoding='utf-8'))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {alias.name.split('.')[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split('.')[0])
            self.assertNotIn('random', imported, name)
            self.assertNotIn('numpy', imported, name)
        import secrets
        self.assertIs(oracle_dicekey.secrets, secrets)
        self.assertIsInstance(secrets.SystemRandom(), random.SystemRandom, 'secrets draws from the OS random source')
        calls = []
        original = secrets.randbelow
        secrets.randbelow = lambda n: (calls.append(n), original(n))[1]
        try:
            self.engine.roll()
        finally:
            secrets.randbelow = original
        self.assertGreaterEqual(len(calls), 5, 'every part of a roll is drawn with secrets.randbelow')

    def test_seeding_the_predictable_generator_does_not_repeat_phrases(self):
        random.seed(1234)
        first = [self.engine.roll() for _ in range(40)]
        random.seed(1234)
        second = [self.engine.roll() for _ in range(40)]
        self.assertNotEqual(first, second)

    def test_rolls_have_the_documented_shape_and_spread(self):
        rolls = [self.engine.roll() for _ in range(4000)]
        self.assertTrue(all(self.engine.check(phrase) for phrase in rolls))
        self.assertGreater(len(set(rolls)), 3990)
        symbols = Counter(phrase[-1] for phrase in rolls)
        self.assertEqual(set(symbols), set(SYMBOLS))
        expected = len(rolls) / len(SYMBOLS)
        self.assertTrue(all(abs(count - expected) < expected * 0.35 for count in symbols.values()), symbols)
        digits = Counter(phrase[-3:-1] for phrase in rolls)
        self.assertGreater(len(digits), 95)
        self.assertGreater(len({phrase.split(' ')[2] for phrase in rolls}), 2500)

    def test_published_entropy_matches_the_shipped_list(self):
        engine = self.engine
        pool = engine.first_pool
        mean = sum(math.log2(len(engine.buckets[oracle_dicekey.initial(w)]) - 1) for w in pool) / len(pool)
        bits = math.log2(len(pool)) + mean + math.log2(len(engine.eligible) - 2) + math.log2(100) + math.log2(len(SYMBOLS))
        self.assertAlmostEqual(engine.bits, bits, places=9)
        self.assertAlmostEqual(engine.bits, 44.33, delta=0.05)

    def test_reroll_changes_only_the_requested_part(self):
        for _ in range(300):
            phrase = self.engine.roll()
            before = self.engine.split(phrase)
            for index, part in enumerate(PARTS):
                changed, note = self.engine.reroll(phrase, part)
                self.assertTrue(self.engine.check(changed))
                after = self.engine.split(changed)
                if note:        # the pair had to be re-rolled together; word 3 and the tail still hold
                    self.assertEqual(after[2:], before[2:])
                    continue
                self.assertNotEqual(after[index], before[index])
                self.assertEqual([a for i, a in enumerate(after) if i != index],
                                 [b for i, b in enumerate(before) if i != index])

    def test_a_phrase_never_appears_in_an_error_message(self):
        phrase = self.engine.roll()
        words = phrase.split(' ')
        attempts = (
            lambda: self.engine.reroll(phrase, 'not-a-part'),
            lambda: self.engine.reroll(phrase + ' extra', 'w1'),
            lambda: self.engine.reroll(phrase.replace(' ', '  '), 'w3'),
            lambda: self.engine.swap_first_two(phrase + '!'),
            lambda: self.engine.swap_first_two(' '.join(words[:3])),
        )
        for attempt in attempts:
            with self.assertRaises(ValueError) as caught:
                attempt()
            message = str(caught.exception) + repr(caught.exception)
            self.assertNotIn(phrase, message)
            for word in words[:3]:
                self.assertNotIn(word, message)

    def test_engine_writes_no_files(self):
        original = builtins.open
        writes = []

        def guarded(file, mode='r', *args, **kwargs):
            if any(flag in mode for flag in ('w', 'a', 'x', '+')):
                writes.append((file, mode))
            return original(file, mode, *args, **kwargs)
        builtins.open = guarded
        try:
            engine = Dicekey()
            phrase = engine.roll()
            for part in PARTS:
                phrase, _note = engine.reroll(phrase, part)
            engine.swap_first_two(phrase)
        finally:
            builtins.open = original
        self.assertEqual(writes, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
