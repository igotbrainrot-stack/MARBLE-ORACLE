"""OVERCAST's own unit tests, run against the copy inside the suite (0.5.0).

The tests live in Tests/overcast/ as delivered with OVERCAST, apart from the
path they import from. Graphical tests need a display (Xvfb on Linux CI)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
# Never touch the real forecast ledger.
os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-overcast-tests-')

suite = unittest.defaultTestLoader.discover(str(HERE / 'overcast'), pattern='test_*.py',
                                            top_level_dir=str(HERE / 'overcast'))
result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
print(f'OVERCAST package: {result.testsRun} tests, {len(result.failures)} failures, '
      f'{len(result.errors)} errors, {len(result.skipped)} skipped')
sys.exit(0 if result.wasSuccessful() else 1)
