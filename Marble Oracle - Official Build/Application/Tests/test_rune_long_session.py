"""Stress the Rune panel through many readings without accumulating image memory.

Run: xvfb-run -a python3 Application/Tests/test_rune_long_session.py
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Runtime" / "Marble_Oracle_App"))
from marble_oracle import WindowApp

opts=dict(theme='EMBER', layout='CLASSIC', fps=30, crt=False,
          no_dicekey=False, no_markets=True, no_network=True,
          bezel=False, osframe=True, retro=False, flat=False,
          look=None, crt_v2=False, no_pixel_barrel=True,
          no_audio_scope=True, selftest=True, wire=None)
app = WindowApp(opts)
try:
    root, s = app.root, app.scene
    root.geometry('1216x848+20+20')
    root.update()
    s.resized(s.c.winfo_width(), s.c.winfo_height())
    root.update()
    s.act('mode_runes')
    root.update()
    for reading in range(10):
        s.act('rune_draw')
        for stone in range(3):
            for frame in range(s.rune_deck.flip_frames):
                s.rune_anim_index = stone
                s.rune_anim_frame = frame
                s.rune_revealed = stone
                s.draw_cards()
                assert s.rune_art_error is None, (reading, stone, frame, s.rune_art_error)
            s.rune_revealed = stone + 1
        s.rune_anim_index = -1
        s.rune_state = 'complete'
        s.draw_cards()
        for i in range(3):
            regions = [h for h in s.hot if h[4] == f'rune_select{i}']
            assert len(regions)==1, (reading,i,'missing/duplicated target')
            l,t,r,b,_=regions[0]
            assert b < s.rect['cards'][3]
            hit = s.hit((l+r)/2,(t+b)/2)
            assert hit and hit[4] == f'rune_select{i}', (reading,i,hit)
            wid=s.rune_widgets[i]
            assert wid.winfo_ismapped()
            assert wid.rune_bounds[1] >= wid.rune_safe_box[1]
            # Click the native stone widget as well; the widget may intercept
            # mouse events instead of the underlying Canvas on real desktops.
            s.rune_sel = (i + 1) % 3
            wid.event_generate('<Button-1>', x=wid.winfo_width() // 2,
                               y=wid.winfo_height() // 2)
            root.update_idletasks()
            assert s.rune_sel == i, (reading, i, 'stone widget click lost')
        assert len(s.rune_deck._flip_cache) <= s.rune_deck._flip_cache_limit
    # All 24 symbols, all twelve stages and three different display sizes:
    # this catches a corrupt archive or a memory cache that grows forever.
    for name in [r['name'] for r in s.rune_deck.runes]:
        for requested_size in (24, 48, 96):
            for frame in range(s.rune_deck.flip_frames):
                img=s.rune_deck.flip_frame(s.c, name, frame, requested_size)
                assert img.width() > 0 and img.height() > 0
                assert len(s.rune_deck._flip_cache) <= s.rune_deck._flip_cache_limit
    s.act('mode_tarot')
    assert all(not wid.winfo_ismapped() for wid in s.rune_widgets)
    print('RUNE LONG SESSION OK: 10 full GUI readings, 360 frame draws, 30 label clicks; 24 symbols x 12 frames x 3 sizes; bounded cache')
finally:
    app.quit()
