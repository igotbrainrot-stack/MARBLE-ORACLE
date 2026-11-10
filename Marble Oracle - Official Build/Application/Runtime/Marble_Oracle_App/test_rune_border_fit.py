"""Regression: Native rune art must never be cropped by its Tk widget or panel.

Run: xvfb-run -a python3 test_rune_border_fit.py
No Pillow is required by Marble Oracle itself; PIL here is optional screenshots.
"""
from pathlib import Path
import tkinter as tk

from marble_oracle import WindowApp, LAYOUTS


def verify():
    options = dict(theme='EMBER', layout='CLASSIC', fps=30, crt=False,
                   no_dicekey=False, no_markets=True, no_network=True,
                   bezel=False, osframe=True, retro=False, flat=False,
                   look=None, crt_v2=False, no_pixel_barrel=True,
                   no_audio_scope=True, selftest=True, wire=None)
    app = WindowApp(options)
    scene, root = app.scene, app.root
    checks = 0
    try:
        root.update()
        scene.divination_mode = 'runes'
        scene.rune_drawn = scene.rune_deck.draw()
        scene.rune_state = 'revealing'
        for layout_name in sorted(LAYOUTS):
          scene.o['layout'] = layout_name
          for width, height in [(1216, 848), (900, 620), (760, 550), (640, 460)]:
            root.geometry(f'{width}x{height}+30+30')
            root.update()
            scene.resized(width, height)
            root.update()
            x0,y0,x1,y1 = scene.rect['cards']
            for frame in (range(scene.rune_deck.flip_frames) if layout_name == 'CLASSIC' else (0, 5, scene.rune_deck.flip_frames-1)):
                scene.rune_anim_index = 0
                scene.rune_anim_frame = frame
                scene.rune_revealed = 0
                scene.draw_cards()
                root.update_idletasks()
                assert scene.rune_art_error is None, scene.rune_art_error
                for i, widget in enumerate(scene.rune_widgets):
                    left, top, right, bottom = widget.rune_bounds
                    bx0,by0,bx1,by1 = widget.rune_safe_box
                    iw,ih = widget.image.width(), widget.image.height()
                    assert right-left == iw and bottom-top == ih, (width,height,frame,i,'image clipped')
                    assert bx0 <= left < right <= bx1, (width,height,frame,i,'cell border clipped',widget.rune_bounds,widget.rune_safe_box)
                    assert by0 <= top < bottom <= by1, (width,height,frame,i,'reading border clipped',widget.rune_bounds,widget.rune_safe_box)
                    assert x0+2 <= left < right <= x1-2, (width,height,frame,i,'panel border clipped')
                    assert y0+scene.hdr_h() < top < bottom < y1-2, (width,height,frame,i,'panel vertical border clipped')
                    assert widget.winfo_ismapped(), (width,height,frame,i,'stone not visible')
                    checks += 1
            # Save one screenshot per size when the environment supports it.
            if layout_name == 'CLASSIC' and (width,height) in ((1216,848), (760,550)):
                try:
                    from PIL import ImageGrab
                    root.update()
                    im = ImageGrab.grab(bbox=(30,30,30+width,30+height))
                    dest = Path('/mnt/data/oracle_clip_fix') / f'runes_border_{width}x{height}.png'
                    im.save(dest)
                except (ImportError,OSError):
                    pass
        # Real screenshot of all three fully revealed stones, with every
        # image inside its fitted rectangle and inside the original border.
        scene.o['layout'] = 'CLASSIC'
        root.geometry('1216x848+30+30')
        root.update()
        scene.resized(1216, 848)
        scene.rune_state = 'complete'
        scene.rune_revealed = 3
        scene.rune_anim_index = -1
        scene.draw_cards()
        root.update()
        try:
            from PIL import ImageGrab
            ImageGrab.grab(bbox=(30,30,1246,878)).save('/mnt/data/oracle_clip_fix/runes_border_all_revealed.png')
        except (ImportError, OSError):
            pass
        scene.divination_mode = 'tarot'
        scene.draw_cards()
        root.update()
        assert all(not w.winfo_ismapped() for w in scene.rune_widgets)
        print(f'RUNE BORDER FIT OK: {checks} widget placements, {len(LAYOUTS)} layouts, 4 window sizes, all 12 frames in Classic, Tarot return')
    finally:
        try:
            app.quit()
        except Exception:
            root.destroy()


if __name__ == '__main__':
    verify()
