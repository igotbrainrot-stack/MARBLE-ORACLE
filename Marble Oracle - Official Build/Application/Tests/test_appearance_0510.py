"""0.5.1: Dark and Light (OVERCAST's design, the default) and Classic.

Pure checks: the sentence-case rule, the saved choice and its overrides, the Ember-to-OVERCAST colour mapping.
Then, for Dark and for Light (each in its own process, since the appearance is applied once per run), the
suite under a real Tk display at the supported sizes:
* the sidebar holds the seven workspaces, the welcome guide and Appearance, each row inside the sidebar and
  its name not cut off; HOME's panels sit right of it; nothing is drawn with film grain;
* every workspace opens in the whole box right of the sidebar and under the header, and the open one is
  marked in the sidebar and named in the header;
* rune stones stay inside their slots without overlapping; passphrase words fit their cards;
* the Appearance window opens, saves the choice, and the A key opens it;
* no Tk call comes from a worker thread.
Classic is covered by the older tests, which pin it.
"""
import io
import json
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
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-look-')
    import oracle_appearance as a
    a._state.update(appearance='dark', applied=True)
    for raw, want in (('PLATE VAULT', 'Plate vault'), ('ADD FILES', 'Add files'), ('FFMPEG', 'FFmpeg'),
                      ('COPY   [CTRL+C]', 'Copy   [Ctrl+C]'), ('VIDEO · ARCHIVE', 'Video · Archive'),
                      ('01 BTC-USD', '01 BTC-USD'), ('OPEN OVERCAST', 'Open Overcast'), ('Already fine', 'Already fine'),
                      ('YOUR PASSPHRASE', 'Your passphrase'), ('CPU AV1 10-BIT', 'CPU AV1 10-BIT')):
        check(f'sentence case: {raw!r} -> {want!r}', a.display(raw) == want, a.display(raw))
    a._state.update(appearance='classic')
    check('Classic keeps capitals', a.display('PLATE VAULT') == 'PLATE VAULT')
    a._state.update(appearance=None, applied=False)
    check('no saved choice: Dark with Amber', a.chosen() == ('dark', 'Amber'), a.chosen())
    a.write_prefs('light', 'Blue')
    check('the saved choice is read back', a.chosen() == ('light', 'Blue'), a.chosen())
    os.environ['MARBLE_ORACLE_APPEARANCE'] = 'classic'
    check('the environment overrides it for one run', a.chosen()[0] == 'classic')
    os.environ['MARBLE_ORACLE_APPEARANCE'] = 'neon'
    check('an unknown appearance falls back to Dark', a.chosen()[0] == 'dark')
    del os.environ['MARBLE_ORACLE_APPEARANCE']
    try:
        a.write_prefs('neon', 'Amber')
        check('an unknown appearance is refused', False)
    except ValueError:
        check('an unknown appearance is refused', True)
    from overcast.theme import palette
    for look in ('dark', 'light'):
        p = palette(look, 'Amber')
        check(f'{look}: OVERCAST colours pass through unchanged',
              all(a.translate_ember(p[k], p) == p[k] for k in ('bg', 'card', 'side', 'field', 'ink', 'dim', 'line')))
        check(f'{look}: Ember surfaces map onto OVERCAST surfaces',
              a.translate_ember('#1D1714', p) == p['bg'] and a.translate_ember('#261F1B', p) == p['card'])
        check(f'{look}: amber highlights map to the accent',
              a.translate_ember('#FDA629', p) in (p['accent'], p['accent_hover']))


def gui_checks(look):
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-look-')
    os.environ['MARBLE_ORACLE_APPEARANCE'] = look
    os.environ['MARBLE_ORACLE_NO_WELCOME'] = '1'
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        from marble_oracle import launch_plan, WindowApp
        import oracle_appearance
        import oracle_ogg_texture
        from oracle_sidebar import WORKSPACES, EXTRAS
        app = WindowApp(launch_plan(['--selftest', '--no-network'])[1])
        root, scene = app.root, app.scene
        p = oracle_appearance.palette()
        check(f'{look}: the appearance is applied', oracle_appearance.appearance() == look and p is not None)
        print(f'INFO {look}: interface font {oracle_appearance.family()}')
        check(f'{look}: no film grain', oracle_ogg_texture.ENABLED is False)
        check(f'{look}: HOME uses the palette', scene.th['bg'] == p['bg'] and scene.th['panel'] == p['card'])

        def pump(n=6):
            for _ in range(n):
                root.update()
                if scene.W == 0 or getattr(scene, 'need_build', False):
                    scene.resized(*app.canvas_size())
                scene.tick()
                time.sleep(0.01)

        for size in ('900x580', '1000x650', '1280x720', '1920x1080'):
            w, h = map(int, size.split('x'))
            root.geometry(f'{w}x{h}+0+0')
            root.update()
            scene.resized(w, h)
            pump()
            check(f'{look} {size}: the sidebar is drawn', scene.modern_chrome() and 'side' in scene.rect)
            side = scene.rect['side']
            actions = [h_[4] for h_ in scene.hot if h_[2] <= side[2] + 1]
            wanted = [a for a, *_ in WORKSPACES] + [a for a, *_ in EXTRAS]
            check(f'{look} {size}: it has the seven workspaces, the guide and Appearance',
                  all(a in actions for a in wanted), actions)
            rows = [h_ for h_ in scene.hot if h_[4] in wanted]
            check(f'{look} {size}: every row is inside the sidebar and the window',
                  all(side[0] <= r[0] and r[2] <= side[2] and 0 <= r[1] and r[3] <= h for r in rows), rows)
            overlap = [(a[4], b[4]) for i, a in enumerate(rows) for b in rows[i + 1:] if a[1] < b[3] and b[1] < a[3]]
            check(f'{look} {size}: no two rows overlap', not overlap, overlap)
            rail = getattr(scene, '_side_rail', False)
            check(f'{look} {size}: the sidebar is a rail below 1100 px, with names from 1100 px', rail == (w < 1100), rail)
            cut = []
            for action, (pill, text, _tag) in scene._side_rows.items():
                bbox = scene.c.bbox(text)
                if not rail and (bbox is None or bbox[2] > side[2] - 4):
                    cut.append(action)
            check(f'{look} {size}: no sidebar name is cut off', not cut, cut)
            panels = [scene.rect[n] for n in ('arch', 'lex', 'trans', 'cards', 'aug') if n in scene.rect]
            check(f'{look} {size}: HOME\'s panels sit right of the sidebar, inside the window',
                  all(r[0] > side[2] and r[2] <= w and r[3] <= h for r in panels), panels)
            for action, name, _blurb, _icon in WORKSPACES[1:]:
                scene.act(action)
                pump(10)
                box = scene.overlay_box()
                session = getattr(scene, scene._which_overlay() or '', None)
                frame = getattr(session, 'frame', None)
                ok = (box == (side[2] + 1, scene.rect['menu'][3], w, h) and frame is not None
                      and abs(frame.winfo_width() - (box[2] - box[0])) <= 2)
                check(f'{look} {size}: {name} fills the box right of the sidebar', ok,
                      (box, frame and (frame.winfo_width(), frame.winfo_height())))
                if frame is not None:
                    import tkinter as tk
                    from tkinter import ttk

                    def squeezed_buttons():
                        fx0, fx1 = frame.winfo_rootx(), frame.winfo_rootx() + frame.winfo_width()
                        found = []
                        for widget in _walk(frame):
                            if not isinstance(widget, (tk.Button, ttk.Button)) or not widget.winfo_viewable():
                                continue
                            bx0, bx1 = widget.winfo_rootx(), widget.winfo_rootx() + widget.winfo_width()
                            if widget.winfo_width() + 2 < widget.winfo_reqwidth() or bx1 > fx1 + 1 or bx0 < fx0 - 1:
                                found.append((str(widget.cget('text'))[:24], widget.winfo_width(), widget.winfo_reqwidth()))
                        return found
                    # Workspaces compact themselves on <Configure>; on a slow machine that can take a moment.
                    squeezed = squeezed_buttons()
                    deadline = time.time() + 1.5
                    while squeezed and time.time() < deadline:
                        pump(3)
                        squeezed = squeezed_buttons()
                    check(f'{look} {size}: no button in {name} is squeezed or cut off', not squeezed, squeezed)
                pill = scene._side_rows[action][0]
                check(f'{look} {size}: {name} is marked in the sidebar and named in the header',
                      scene.c.itemcget(pill, 'fill').upper() == p['select_side'].upper()
                      and scene.c.itemcget(scene._hdr_title, 'text') == name)
                if action == 'tab_passphrase' and w >= 900:
                    import tkinter as tk
                    from tkinter import ttk
                    tight, seen = [], 0
                    for widget in _walk(scene.dk.frame):
                        if isinstance(widget, (tk.Label, ttk.Label)) and widget.winfo_ismapped() and widget.cget('text'):
                            seen += 1
                            if widget.winfo_reqwidth() > widget.winfo_width() + 2:
                                tight.append(widget.cget('text'))
                    check(f'{look} {size}: passphrase words fit their cards ({seen} labels)', seen >= 5 and not tight,
                          (seen, tight))
            scene.act('tab_home')
            pump()
            # Rune stones: inside their slots, apart.
            scene.divination_mode = 'runes'
            scene.rune_drawn = [scene.rune_deck.runes[i] for i in (4, 9, 10)]
            scene.rune_revealed, scene.rune_state, scene.rune_anim_index, scene.rune_sel = 3, 'complete', -1, 1
            scene.draw_cards()
            root.update()
            bounds = [x.rune_bounds for x in scene.rune_widgets]
            safe = [x.rune_safe_box for x in scene.rune_widgets]
            check(f'{look} {size}: rune stones stay inside their slots and apart',
                  len(bounds) == 3 and all(s[0] <= b[0] < b[2] <= s[2] and s[1] <= b[1] < b[3] <= s[3]
                                           for b, s in zip(bounds, safe))
                  and all(bounds[i][2] < bounds[i + 1][0] for i in (0, 1)), (bounds, safe))
            check(f'{look} {size}: rune stones have a real size',
                  all(x.image.width() >= 40 for x in scene.rune_widgets), [x.image.width() for x in scene.rune_widgets])
            scene.divination_mode = 'tarot'
            scene.draw_cards()
        # The Appearance window.
        scene.act('appearance')
        pump()
        win = getattr(root, '_appearance_window', None)
        check(f'{look}: Appearance opens', win is not None and win.winfo_exists())
        win.destroy()
        root._appearance_window = None

        class Key:
            keysym, char = 'a', 'a'
        scene.on_key(Key)
        pump()
        win = getattr(root, '_appearance_window', None)
        check(f'{look}: the A key opens it', win is not None and win.winfo_exists())
        oracle_appearance.write_prefs('classic', 'Green')
        saved = json.loads(Path(os.environ['MARBLE_ORACLE_STATE'], 'appearance.json').read_text())
        check(f'{look}: a choice is saved', saved == {'appearance': 'classic', 'accent': 'Green'}, saved)
        app.quit()
    warnings = stderr.getvalue()
    check(f'{look}: no Tk call from a worker thread', 'main thread is not in main loop' not in warnings, warnings[-300:])


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        gui_checks(sys.argv[1])
        sys.exit(0 if all(results) else 1)
    pure_checks()
    if os.environ.get('DISPLAY') or os.name == 'nt':
        for look in ('dark', 'light'):
            env = {k: v for k, v in os.environ.items() if k not in ('MARBLE_ORACLE_APPEARANCE',)}
            done = subprocess.run([sys.executable, __file__, look], env=env, capture_output=True, text=True, timeout=900)
            out = done.stdout
            print(out, end='')
            if done.returncode != 0 and 'FAIL' not in out:
                print(done.stderr[-1500:])
            results.extend(line.startswith('PASS') for line in out.splitlines() if line[:4] in ('PASS', 'FAIL'))
            if done.returncode != 0 and 'FAIL' not in out:
                results.append(False)
    else:
        print('SKIP the window checks: no display')
    print(f'APPEARANCE 0.5.1: {sum(results)}/{len(results)} checks passed')
    sys.exit(0 if all(results) else 1)
