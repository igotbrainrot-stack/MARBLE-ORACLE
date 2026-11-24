"""0.5.3: rounded corners and the Inter typeface in Dark and Light.

Pure checks (no display needed):
* Inter's four styles and its licence (SIL OFL 1.1) ship with the suite;
* a pumice card image has a whole tile in the middle, transparent rounded corners and an opaque body;
* canvas rounded rectangles pin their straight edges, so a corner curves over the whole radius.

Window checks (Dark, in its own process, as the appearance is applied once per run):
* Inter is registered from the bundled files and is the interface family;
* a rounded button face matches a pixel-by-pixel reference, and 40 faces take well under a second;
* RoundButton keeps the Button interface (cget, configure, invoke) and its logical colours;
* buttons stretched across shared grid columns settle (no endless resizing), stretch and shrink with the room;
* the suite's buttons are RoundButtons, fields and lists get corner pieces, textured cards use rounded styles;
* nothing is drawn or freed from a worker thread.
"""
import io
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {str(detail)[:300]}'))


def pure_checks():
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-round-')
    import marble_uberata
    missing = [p.name for p in marble_uberata.INTER_FILES if not Path(p).is_file()]
    check('Inter: the four styles ship with the suite', not missing, missing)
    licence = APP / 'fonts' / 'Inter-OFL.txt'
    text = licence.read_text(encoding='utf-8') if licence.is_file() else ''
    check('Inter: its licence (SIL Open Font License 1.1) ships beside it',
          'SIL OPEN FONT LICENSE' in text.upper() and 'Version 1.1' in text)

    import oracle_pumice
    r = 10
    png = oracle_pumice.rounded_tile_png('#2A2A2E', r)
    side = oracle_pumice.SIZE + 2 * r
    check('rounded card: a PNG the size of a tile plus the corners', png[:8] == b'\x89PNG\r\n\x1a\n'
          and int.from_bytes(png[16:20], 'big') == side and int.from_bytes(png[20:24], 'big') == side)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        im = Image.open(io.BytesIO(png)).convert('RGBA')
        corners = [im.getpixel(p)[3] for p in ((0, 0), (side - 1, 0), (0, side - 1), (side - 1, side - 1))]
        check('rounded card: the four corners are transparent', corners == [0, 0, 0, 0], corners)
        body = [im.getpixel(p)[3] for p in ((side // 2, side // 2), (r, 0), (0, r), (side // 2, 0))]
        check('rounded card: the body and the straight edges are opaque', body == [255] * 4, body)
        # The texture wraps: the border band repeats the tile's far edge, so ttk's repeating stays seamless.
        tile = Image.open(io.BytesIO(oracle_pumice.tile_png('#2A2A2E'))).convert('RGB')
        same = all(im.getpixel((r + x, r + y))[:3] == tile.getpixel((x, y)) for x in range(0, 256, 37) for y in range(0, 256, 41))
        wraps = all(im.getpixel((x, r + y))[:3] == tile.getpixel((oracle_pumice.SIZE - r + x, y)) for x in range(r) for y in range(0, 256, 51))
        check('rounded card: the middle is the pumice tile and the border wraps it', same and wraps)
    else:
        print('SKIP rounded card pixels: Pillow is not installed')

    import oracle_sidebar

    class Canvas:
        def create_polygon(self, pts, **kw):
            self.pts, self.kw = pts, kw
            return 1
    c = Canvas()
    oracle_sidebar.round_rect(c, 0, 0, 100, 40, 10, fill='#000')
    pairs = list(zip(c.pts[::2], c.pts[1::2]))
    check('round_rect: a smoothed polygon whose straight edges end where the curve starts',
          c.kw.get('smooth') and pairs.count((10, 0)) == 2 and pairs.count((90, 0)) == 2 and pairs.count((100, 30)) == 2,
          pairs)


def reference_face(w, h, radius, fill, ground, ring=None, ring_width=2):
    """The rounded face worked out pixel by pixel (the slow, obvious way)."""
    def hx(c):
        c = c.lstrip('#')
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    w, h = max(2, int(w)), max(2, int(h))
    r = max(0, min(int(radius), w // 2, h // 2))
    fc, gc, rc = hx(fill), hx(ground), hx(ring) if ring else None

    def coverage(x, y, inset):
        rr = max(0.0, r - inset)
        x0, y0, x1, y1 = inset, inset, w - inset, h - inset
        inside = 0
        for sx, sy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
            px, py = x + sx, y + sy
            if not (x0 <= px <= x1 and y0 <= py <= y1):
                continue
            cx, cy = min(max(px, x0 + rr), x1 - rr), min(max(py, y0 + rr), y1 - rr)
            inside += (px - cx) ** 2 + (py - cy) ** 2 <= rr * rr
        return inside / 4.0

    def blend(a, b, t):
        return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))
    out = []
    for y in range(h):
        for x in range(w):
            o = coverage(x, y, 0)
            c = blend(gc, fc, o)
            if rc is not None:
                c = blend(c, rc, max(0.0, o - coverage(x, y, ring_width)))
            out.append(c)
    return out


def gui_checks():
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-round-')
    os.environ['MARBLE_ORACLE_APPEARANCE'] = 'dark'
    os.environ['MARBLE_ORACLE_NO_WELCOME'] = '1'
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        import tkinter as tk
        from tkinter import font as tkfont
        import oracle_widgets as W

        # -- the rounded face and the button, on their own
        root = tk.Tk()
        bad = []
        for w, h, r, ring in ((120, 32, 8, None), (120, 32, 8, '#ff8800'), (7, 5, 8, None), (40, 6, 7, '#123456'),
                              (3, 40, 9, None), (11, 11, 5, '#00ff00')):
            img = W.rounded_photo(root, w, h, r, '#303034', '#1b1b1d', ring)
            got = [tuple(img.get(x, y)) for y in range(img.height()) for x in range(img.width())]
            if got != reference_face(w, h, r, '#303034', '#1b1b1d', ring):
                bad.append((w, h, r, ring))
        check('a rounded face matches the pixel-by-pixel reference (with and without the focus ring)', not bad, bad)
        start = time.perf_counter()
        for i in range(40):
            W.rounded_photo(root, 100 + i, 34, 8, '#3%02x333' % i, '#111111')
        took = time.perf_counter() - start
        check('40 button faces take under a second', took < 1.0, round(took, 3))
        check('colour names are understood', W._hex('white', root) == (255, 255, 255) and W._hex('#0f0') == (0, 255, 0))

        root.geometry('600x300')
        frame = tk.Frame(root, bg='#111111')
        frame.pack(fill='both', expand=True)
        for col in range(3):
            frame.columnconfigure(col, weight=1, uniform='u')
        buttons = [W.RoundButton(frame, text=t, bg='#333333', fg='white', ground='#111111')
                   for t in ('A', 'A much longer label', 'Mid')]
        for col, b in enumerate(buttons):
            b.grid(row=0, column=col, sticky='ew', padx=4)
        for _ in range(10):
            root.update()
        renders = []
        original = W.RoundButton._render
        W.RoundButton._render = lambda self, *a, **k: (renders.append(1), original(self, *a, **k))[1]
        for _ in range(30):
            root.update()
            time.sleep(0.005)
        W.RoundButton._render = original
        check('buttons stretched across shared columns settle (no endless resizing)', not renders, len(renders))
        faces = [b._image.width() for b in buttons]
        check('a stretched button\'s face fills its cell', all(abs(f - (b.winfo_width() - 2)) <= 1 for f, b in zip(faces, buttons)),
              list(zip(faces, [b.winfo_width() for b in buttons])))
        root.geometry('360x200')
        for _ in range(10):
            root.update()
        check('and shrinks with it', all(b._image.width() <= b.winfo_width() for b in buttons[::2]),
              [(b._image.width(), b.winfo_width()) for b in buttons])
        b = buttons[0]
        clicked = []
        b.configure(bg='#ff0000', command=lambda: clicked.append(1))
        b.invoke()
        check('RoundButton keeps the Button interface (cget, configure, invoke)',
              b.cget('bg') == '#ff0000' and b['text'] == 'A' and clicked == [1] and isinstance(b, tk.Button))
        b.configure(state='disabled')
        root.update()
        check('a disabled RoundButton reports its state and does nothing', str(b.cget('state')) == 'disabled'
              and (b.invoke() or True) and clicked == [1])
        root.destroy()

        # -- the suite in Dark
        from marble_oracle import launch_plan, WindowApp
        import oracle_appearance
        import oracle_round
        import oracle_shell
        app = WindowApp(launch_plan(['--selftest', '--no-network'])[1])
        root, scene = app.root, app.scene
        check('Dark: Inter is the interface family', oracle_appearance.family() == 'Inter', oracle_appearance.family())
        check('Dark: Inter comes from the bundled files', 'Inter' in tkfont.families(root))
        check('Dark: the corner pieces are installed', getattr(root, '_marble_round_after', None) is not None)

        def pump(n=6):
            for _ in range(n):
                root.update()
                if scene.W == 0 or getattr(scene, 'need_build', False):
                    scene.resized(*app.canvas_size())
                scene.tick()
                time.sleep(0.01)
        root.geometry('1280x720+0+0')
        root.update()
        scene.resized(1280, 720)
        pump()
        scene.act('tab_augurspex')
        pump(12)
        tracked = {str(e[0]) for e in oracle_round._TRACKED}
        fields = [w for w in _walk(root) if w.winfo_class() in ('Entry', 'Listbox') and w.winfo_ismapped()]
        rounded_fields = [w for w in fields if str(w) in tracked]
        check('Dark: fields and lists get corner pieces', fields and len(rounded_fields) == len(fields),
              (len(fields), len(rounded_fields)))
        scene.act('tab_passphrase')
        pump(12)
        session = scene.dk
        walk = list(_walk(session.frame))
        plain = [w for w in walk if isinstance(w, tk.Button) and not isinstance(w, W.RoundButton)
                 and w.winfo_ismapped() and w.winfo_class() == 'Button']
        rounded = [w for w in walk if isinstance(w, W.RoundButton)]
        check('Dark: the passphrase workspace\'s buttons are rounded', len(rounded) >= 8 and not plain,
              (len(rounded), [w.cget('text') for w in plain][:6]))
        styles = [w.cget('style') for w in _walk(root) if w.winfo_class() == 'TFrame']
        check('Dark: textured cards use the rounded card styles', any('.on' in str(s) for s in styles),
              sorted(set(map(str, styles)))[:8])
        check('Dark: shell.button makes RoundButtons', isinstance(
            oracle_shell.button(session.frame, 'Try', lambda: None), W.RoundButton))
        app.quit()
    warnings = stderr.getvalue()
    check('Dark: no Tk call from a worker thread', 'main thread is not in main loop' not in warnings, warnings[-300:])
    check('Dark: no image freed from a worker thread', 'image' not in warnings.lower() or 'Tcl_AsyncDelete' not in warnings,
          warnings[-300:])


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        gui_checks()
        sys.exit(0 if all(results) else 1)
    pure_checks()
    if os.environ.get('DISPLAY') or os.name == 'nt':
        env = {k: v for k, v in os.environ.items() if k != 'MARBLE_ORACLE_APPEARANCE'}
        done = subprocess.run([sys.executable, __file__, 'gui'], env=env, capture_output=True, text=True, timeout=900)
        print(done.stdout, end='')
        results.extend(line.startswith('PASS') for line in done.stdout.splitlines() if line[:4] in ('PASS', 'FAIL'))
        if done.returncode != 0 and 'FAIL' not in done.stdout:
            print(done.stderr[-1500:])
            results.append(False)
    else:
        print('SKIP the window checks: no display')
    print(f'ROUNDED 0.5.3: {sum(results)}/{len(results)} checks passed')
    sys.exit(0 if all(results) else 1)
