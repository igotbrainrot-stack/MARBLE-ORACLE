"""v0.5.2 UI behaviour: staged progress, cancel, poll resilience, DUE ledger, settings."""
from datetime import date, timedelta
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))

HAS_DISPLAY = bool(os.environ.get('DISPLAY') or sys.platform == 'win32')


@unittest.skipUnless(HAS_DISPLAY, 'No GUI display present')
class PanelBehaviour(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from tkinter import messagebox
        from overcast.ui import NewsOraclePanel
        self.tk, self.Panel = tk, NewsOraclePanel
        self._showerror = messagebox.showerror
        messagebox.showerror = lambda *a, **k: None   # keep the run non-interactive
        self.tmp = tempfile.TemporaryDirectory()
        self.root = tk.Tk(); self.root.geometry('1024x680')
        self.p = NewsOraclePanel(self.root, state_dir=self.tmp.name)
        self.p.pack(fill='both', expand=True); self.root.update()

    def tearDown(self):
        from tkinter import messagebox
        messagebox.showerror = self._showerror
        self.p.destroy(); self.root.destroy(); self.tmp.cleanup()

    def test_progress_cancel_and_poll_resilience(self):
        from overcast.engine import OperationCancelled
        p = self.p
        started = threading.Event()
        def task(progress, cancel):
            progress(1, 2, 'first'); started.set()
            while not cancel.is_set(): time.sleep(0.01)
            raise OperationCancelled('Cancelled by user. Nothing was saved.')
        p._job('Multi-source forecast', task, staged=True)
        self.assertTrue(started.wait(3))
        time.sleep(0.05); p._poll_jobs(); self.root.update()
        self.assertIn('step 1 of 2', p.status.get())
        self.assertEqual(str(p.cancel_button['state']), 'normal')
        p.cancel_job(); time.sleep(0.2); p._poll_jobs(); self.root.update()
        self.assertEqual(p._result_kind, 'Cancelled')
        self.assertFalse(p._running)
        p._jobs.put(('Fetching headlines', True, {'bad': 'shape'}, None)); p._poll_jobs()
        self.assertIn('Could not display result', p.status.get())

    def test_embedding_model_not_selected_and_settings_persist(self):
        p = self.p
        p._handle_job('Connecting to LM Studio', True,
                      ['text-embedding-nomic-embed-text-v1.5', 'qwen2.5-7b-instruct'], None)
        self.assertEqual(p.model.get(), 'qwen2.5-7b-instruct')
        p.context.set('8K'); p._apply_context()
        again = self.Panel(self.root, state_dir=self.tmp.name)
        try:
            self.assertEqual(again.context.get(), '8K')
            self.assertEqual(again.engine.budget['packet'], 10000)
            self.assertEqual(again.model.get(), 'qwen2.5-7b-instruct')
        finally:
            again.destroy()

    def test_overdue_forecast_is_flagged(self):
        p = self.p
        p.engine.store.add_forecast({'question': 'Will X happen?', 'probability': 0.3,
            'target_date': (date.today() - timedelta(days=2)).isoformat(), 'resolution_criteria': 'r',
            'reasoning': 'r', 'counterargument': 'c', 'change_mind': 'm'}, [], 'm', 'v', {})
        p.reload_forecasts(); self.root.update()
        first = p.forecast_tree.get_children()[0]
        self.assertEqual(p.forecast_tree.set(first, 'outcome'), 'Due')
        self.assertIn('past deadline', p.score.get())


if __name__ == '__main__':
    unittest.main()
