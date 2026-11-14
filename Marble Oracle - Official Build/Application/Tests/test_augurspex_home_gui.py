"""Headless GUI integration: AUGURSPEX chart is inside former market footprint.
Run: xvfb-run -a python3 Application/Tests/test_augurspex_home_gui.py
"""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from marble_oracle import WindowApp, parse, CLEAN_LAYOUTS

app = WindowApp(vars(parse(['--selftest','--no-bezel','--os-frame'])))
try:
    app.root.update()
    s=app.scene
    s.resized(1216, 848)
    app.root.update()
    assert 'aug' in s.rect
    assert 'mkt' not in s.rect
    assert s.c.find_withtag('aug-chart')
    assert {'aug_previous','aug_next'}.issubset({h[4] for h in s.hot})
    first=s.augurspex_chart.snapshot()
    assert first['total'] > 20 and first['symbol'] == 'BTC-USD', first
    # The disabled-network selftest can render an injected provider-shaped result,
    # without any public network calls or placeholder fake prices in production.
    with s.augurspex_chart._lock:
        s.augurspex_chart._results[first['symbol']] = {
            'source':'coinbase', 'cache':'fresh','latest_observation':'2026-11-11T00:00:00Z',
            'candles':[{'close':10+i*0.1} for i in range(40)]}
        # Since 0.4.7.8 the app intentionally rejects an undated cache entry.
        # The injected synthetic fixture must represent a newly received result.
        s.augurspex_chart._received_at[first['symbol']] = time.time()
    s.draw_augurspex_chart()
    assert any(s.c.type(i)=='line' for i in s.c.find_withtag('aug-chart'))
    plotted_lines=[i for i in s.c.find_withtag('aug-chart') if s.c.type(i)=='line']
    assert max(float(s.c.itemcget(i,'width')) for i in plotted_lines)>=3, 'HOME price trace must be bold'
    assert len(plotted_lines)>=8, 'HOME plot must draw both horizontal and vertical grid guides'
    s.act('aug_next')
    assert s.augurspex_chart.snapshot()['index']==1
    s.act('aug_previous')
    assert s.augurspex_chart.snapshot()['index']==0
    # Rebuild all clean GRADE layouts and verify accessible click targets.
    for layout in CLEAN_LAYOUTS:
        s.o['layout']=layout
        s.build(s.W,s.H)
        app.root.update_idletasks()
        assert 'aug' in s.rect, layout
        assert s.c.find_withtag('aug-chart'), layout
        for action in ('aug_previous','aug_next'):
            hits=[h for h in s.hot if h[4]==action]
            assert len(hits)==1, (layout,action,hits)
            hit=hits[0]
            assert s.hit((hit[0]+hit[2])/2,(hit[1]+hit[3])/2)[4] == action, (layout,action)
    print('AUGURSPEX HOME CHART GUI: PASS (all GRADE layouts, injected graph, buttons)')
finally:
    app.quit()
