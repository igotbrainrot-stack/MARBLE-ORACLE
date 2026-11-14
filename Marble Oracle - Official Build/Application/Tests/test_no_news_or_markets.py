"""Dashboard regression: news runner and fixed Bitcoin/gold market tape stay retired; AUGURSPEX history chart is present.
Run: xvfb-run -a python3 test_no_news_or_markets.py
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'Runtime'/'Marble_Oracle_App'))
from marble_oracle import WindowApp, CLEAN_LAYOUTS, LAYOUTS, parse

assert all('mkt' not in layout for layout in (*LAYOUTS.values(), *CLEAN_LAYOUTS.values()))
for flag in ([], ['--retro'], ['--flat']):
    opts = vars(parse(['--selftest', '--no-network', '--no-bezel', '--os-frame'] + flag))
    app = WindowApp(opts)
    try:
        app.root.update()
        s = app.scene
        s.resized(1216, 848)
        app.root.update()
        s = app.scene
        assert s.news.enabled is False
        assert s.markets.md is None
        assert s.c.itemcget(s.tick_id, 'text') == ''
        assert 'mkt' not in s.rect
        assert 'aug' in s.rect
        assert s.c.find_withtag('aug-chart')
        for panel in ('arch', 'lex', 'trans', 'cards'):
            assert panel in s.rect
        # Layout geometry is checked for every preset without slow GUI redraws.
        for name, layout in {**LAYOUTS, **CLEAN_LAYOUTS}.items():
            assert 'mkt' not in layout, name
            assert set(layout) == {'arch', 'lex', 'trans', 'cards', 'aug'}, name
            for box in layout.values():
                assert box[0] < box[2] and box[1] < box[3], (name, box)
        s._status(1e15, 0.2)
        assert s.c.itemcget(s.tick_id, 'text') == ''
    finally:
        app.quit()
print('NO NEWS OR FIXED MARKET TAPE; AUGURSPEX CHART: PASS')
