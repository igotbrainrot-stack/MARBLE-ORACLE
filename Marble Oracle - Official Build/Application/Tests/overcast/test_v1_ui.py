"""OVERCAST 1.0 UI: dashboard, command palette, ledger filters/sorting, bad-news marking,
revisions, Markdown export, shortcuts, auto-refresh and settings migration."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from test_v06_broad_outlook import article
from test_v1_gloom import RiskFake

HAS_DISPLAY = bool(os.environ.get('DISPLAY') or sys.platform == 'win32')


@unittest.skipUnless(HAS_DISPLAY, 'No GUI display present')
class OvercastPanel(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from tkinter import messagebox, simpledialog
        from overcast.ui import NewsOraclePanel
        self.tk, self.Panel, self.simpledialog = tk, NewsOraclePanel, simpledialog
        self._saved = (messagebox.showerror, messagebox.showwarning, simpledialog.askstring, simpledialog.askinteger)
        messagebox.showerror = messagebox.showwarning = lambda *a, **k: None
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, 'signal_settings.json').write_text(json.dumps({'context_profile': '8K', 'runs': 2}))
        self.root = tk.Tk(); self.root.geometry('1024x680')
        self.p = NewsOraclePanel(self.root, state_dir=self.tmp.name)
        self.p.pack(fill='both', expand=True); self.root.update()

    def tearDown(self):
        from tkinter import messagebox, simpledialog
        messagebox.showerror, messagebox.showwarning, simpledialog.askstring, simpledialog.askinteger = self._saved
        self.p.destroy(); self.root.destroy(); self.tmp.cleanup()

    def card(self, key):
        return self.p.dash_cards[key].get('1.0', 'end')

    def seed_outlook(self):
        p = self.p
        p.engine.store.save_articles([article(1, 'Arcadia weighs tariffs on Borealis steel', 'a.example'),
                                      article(2, 'Borealis signals trade talks', 'b.example'),
                                      article(3, 'Arcadia central bank warns on inflation', 'c.example')])
        ids = [r['id'] for r in p.engine.store.articles(10)]
        p.engine.client = RiskFake(ids)
        result = p.engine.broad_outlook(ids, 'm', scope='TRADE & SUPPLY CHAINS', runs=2)
        p._running = True
        p._handle_job('Building broad outlook', True, result, None)
        self.root.update()
        return result

    def test_layout_dashboard_and_settings_migration(self):
        p = self.p
        self.assertEqual(len(p.tabs.tabs()), 11)
        self.assertEqual(p.tabs.select(), str(p.dashboard_tab), 'the app opens on the dashboard')
        self.assertEqual(p.page_title.get(), 'Dashboard')
        self.assertEqual(p.context.get(), '8K', 'SIGNAL settings carried across the rename')
        self.assertEqual(p._runs(), 2)
        self.assertIn('Three steps', self.card('gloom'))
        self.seed_outlook()
        p.reload_dashboard(); self.root.update()
        self.assertIn('Chance things go badly: 40%', self.card('gloom'))
        self.assertIn('×', self.card('risks'))
        self.assertIn('No resolved forecasts yet', self.card('record'))
        p._open_page(p.settings_tab)
        self.assertEqual(p.page_title.get(), 'Settings')

    def test_palette_filters_and_runs_commands(self):
        p = self.p
        p.scope.set('CRISES & DISASTERS')
        self.assertEqual(p.scope_label.get(), 'Crises & disasters', 'people see sentence case')
        p.scope_label.set('Global markets')
        self.assertEqual(p.scope.get(), 'GLOBAL MARKETS', 'the engine gets the canonical scope')
        hits = p.filter_commands(p._commands(), 'ledger go')
        self.assertEqual([h[0] for h in hits], ['Go to Ledger'])
        self.assertTrue(p.filter_commands(p._commands(), 'scope crises'))
        p.open_palette(); self.root.update()
        self.assertIsNotNone(p._palette)
        hits[0][1](); self.root.update()
        self.assertEqual(p.tabs.select(), str(p.forecast_tab))

    def test_ledger_filters_sorting_and_mark_bad_news(self):
        p = self.p
        self.seed_outlook()
        fid = p.engine.store.add_forecast({'question': 'Will the ceasefire collapse?', 'probability': 0.2,
            'target_date': '2099-01-01', 'resolution_criteria': 'r', 'reasoning': 'r', 'counterargument': 'c',
            'change_mind': 'm'}, [], 'm', 'v', {})
        p.reload_forecasts()
        for mode, expected in (('SIGNPOSTS', 4), ('TOP RISKS', 4), ('OPEN', 5), ('RESOLVED', 0)):
            p.ledger_filter.set(mode); p.reload_forecasts()
            self.assertEqual(len(p.forecast_tree.get_children()), expected, mode)
        p.ledger_filter.set('ALL'); p.ledger_search.set('ceasefire'); p.reload_forecasts()
        self.assertEqual(p.forecast_tree.get_children(), (str(fid),))
        self.assertEqual(p.forecast_tree.set(str(fid), 'risk'), '—', 'not yet oriented')
        self.simpledialog.askstring = lambda *a, **k: 'yes'
        self.simpledialog.askinteger = lambda *a, **k: 5
        p._select_tree(p.forecast_tree, fid)
        p._mark_bad_news()
        self.assertEqual(p.forecast_tree.set(str(fid), 'risk'), '1.0')        # 20% x severity 5
        p.ledger_search.set(''); p.ledger_filter.set('ALL'); p.reload_forecasts()
        p._sort_tree(p.forecast_tree, 'p')
        probs = [float(p.forecast_tree.set(i, 'p').rstrip('%')) for i in p.forecast_tree.get_children()]
        self.assertEqual(probs, sorted(probs, reverse=True))

    def test_revision_job_markdown_shortcuts_and_auto_refresh(self):
        from overcast.ui import spans_to_markdown
        p = self.p
        first = self.seed_outlook()
        revised = p.engine.revise_outlook(first['id'], 'm', runs=2)
        p._running = True
        p._handle_job('Revising broad outlook', True, revised, None)
        self.assertEqual(p._result_kind, f"Broad outlook #{revised['id']}")
        self.assertIn(f"revision of #{first['id']}", p._result_plain)
        md = spans_to_markdown(p._result_spans)
        self.assertIn('## Bad news first', md)
        p.install_shortcuts(self.root)
        p.auto_refresh.set('6'); p._schedule_auto_refresh()
        self.assertIsNotNone(p._auto_after)
        p.auto_refresh.set('0'); p._schedule_auto_refresh()
        self.assertIsNone(p._auto_after)


if __name__ == '__main__':
    unittest.main()
