"""Smoke-test standalone Tk workspace and its latest actions under a display."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.ui import NewsOraclePanel


class TkSmoke(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DISPLAY') or sys.platform == 'win32', 'No GUI display present')
    def test_panel_and_event_tab(self):
        with tempfile.TemporaryDirectory() as d:
            root=tk.Tk();root.geometry('1360x850')
            try:
                p=NewsOraclePanel(root,state_dir=d)
                p.pack(fill='both',expand=True)
                root.update_idletasks();root.update()
                self.assertEqual(len(p.tabs.tabs()),11)  # 1.0: DASHBOARD, SETTINGS added; 9 in v0.6
                self.assertTrue(p.result_text.winfo_exists())
                self.assertIn('Welcome to OVERCAST',p.result_text.get('1.0','end'))
                self.assertTrue(callable(p.generate_overview))
                self.assertTrue(callable(p.copy_result))
                self.assertTrue(callable(p.export_result))
                self.assertTrue(callable(p.reload_calendar))
                self.assertTrue(callable(p._export_calendar))
                self.assertEqual(len(p.cal_buttons),42)
                self.assertTrue(callable(p.multi_forecast))
                self.assertTrue(callable(p.reload_events))
                self.assertEqual(p.engine.events(),[])
                # Test actual on-screen rendering and navigation after a stored report.
                text={'title':'Synthetic test briefing','briefing':'SYNTHETIC BRIEFING VISIBLE',
                      'uncertainties':'This is fixture data.'}
                p.engine.store.add_briefing(text,[],'test-local','test-version')
                p.reload_briefings()
                root.update()
                self.assertIn('SYNTHETIC BRIEFING VISIBLE',p.result_text.get('1.0','end'))
                p._open_page(p.results_tab)
                self.assertEqual(p.tabs.select(),str(p.results_tab))
                self.assertIn('SYNTHETIC BRIEFING VISIBLE',p._result_plain)
                # Avoid destroying root while pending after callbacks.
                p.destroy()
            finally:root.destroy()

if __name__=='__main__':unittest.main()
