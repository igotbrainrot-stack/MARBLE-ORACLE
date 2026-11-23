"""v0.6 UI: BROAD OUTLOOK result display, outlook page, restore on launch, RUNS setting."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from test_v06_broad_outlook import OutlookFake, article

HAS_DISPLAY = bool(os.environ.get('DISPLAY') or sys.platform == 'win32')


@unittest.skipUnless(HAS_DISPLAY, 'No GUI display present')
class OutlookPanel(unittest.TestCase):
    def test_outlook_displayed_listed_and_restored(self):
        import tkinter as tk
        from overcast.ui import NewsOraclePanel
        with tempfile.TemporaryDirectory() as d:
            root = tk.Tk(); root.geometry('1024x680')
            try:
                p = NewsOraclePanel(root, state_dir=d)
                self.assertEqual(p._runs(), 3)
                p.engine.store.save_articles([article(1, 'Arcadia weighs tariffs on Borealis steel', 'a.example'),
                                              article(2, 'Borealis signals trade talks', 'b.example'),
                                              article(3, 'Arcadia central bank warns on inflation', 'c.example')])
                ids = [r['id'] for r in p.engine.store.articles(10)]
                p.engine.client = OutlookFake(ids)
                result = p.engine.broad_outlook(ids, 'm', scope='GLOBAL EVENTS', runs=2)
                p._running = True
                p._handle_job('Building broad outlook', True, result, None)
                root.update()
                self.assertEqual(p._result_kind, f"Broad outlook #{result['id']}")
                self.assertIn('Gloom index', p._result_plain)
                self.assertIn('Scenarios', p._result_plain)
                self.assertEqual(len(p.outlook_tree.get_children()), 1)
                self.assertEqual(len(p.forecast_tree.get_children()), 4, 'signposts are in the ledger')
                p.runs.set('5'); p._save_settings()
                p.destroy()
                again = NewsOraclePanel(root, state_dir=d)
                try:
                    self.assertEqual(again._result_kind, f"Broad outlook #{result['id']}",
                                     'the latest outlook, not one of its signposts, is restored on launch')
                    self.assertEqual(again._runs(), 5)
                finally:
                    again.destroy()
            finally:
                root.destroy()


if __name__ == '__main__':
    unittest.main()
