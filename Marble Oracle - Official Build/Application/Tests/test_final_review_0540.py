"""0.5.4: the final design review's fixes.

Pure checks (no display needed):
* every text colour in Dark and Light meets WCAG AA (4.5:1) on the page, cards, sidebar and fields, for
  every accent; text on an accent button reads as well as the accent allows;
* OVERCAST's Classic palette is the suite's Ember, and OVERCAST keeps its own saved look while a host sets one;
* labels written in capitals become sentence case in Dark/Light (acronyms, market symbols, keys and list
  numbers kept), and are unchanged in Classic;
* the passphrase strength breakdown adds up to the engine's figure.

Window checks (Dark, in their own process):
* widget labels are cased on the way to Tk; canvas text is not; the caller's options are not changed;
* market colours read on Light and Dark surfaces;
* Dark/Light workspaces leave HOME to the suite's sidebar (the button still exists and works);
* text fields get inner padding, check boxes are drawn, sliders and empty-list hints work;
* Touch Type's keyboard grows with the window; the scrolled Convert settings take the mouse wheel without
  touching any application-wide binding.
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
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-final-')
    import overcast.theme as T
    short = []
    for look in ('dark', 'light'):
        for accent in T.ACCENTS:
            p = T.palette(look, accent)
            for fg in ('ink', 'dim', 'accent_text', 'green', 'red'):
                for surface in ('bg', 'card', 'side', 'field'):
                    ratio = T.contrast(p[fg], p[surface])
                    if ratio < 4.5:
                        short.append((look, accent, fg, surface, round(ratio, 2)))
    check('every text colour reads (4.5:1) on page, cards, sidebar and fields, in every look and accent',
          not short, short[:6])
    weak = []
    for look in ('dark', 'light'):
        for accent in T.ACCENTS:
            p = T.palette(look, accent)
            best = max(T.contrast(c, p['accent']) for c in ('#FFFFFF', '#1C1C1E', p['on_accent']))
            if T.contrast(p['on_accent'], p['accent']) < min(4.5, best) - 0.01:
                weak.append((look, accent))
    check('text on an accent button reads as well as the accent allows', not weak, weak)
    dark = T.palette('dark', 'Amber')
    check('Dark keeps its hierarchy: secondary text is still dimmer than body text',
          T.luminance(dark['dim']) < T.luminance(dark['ink']) * 0.6, (dark['dim'], dark['ink']))
    classic = T.palette('classic')
    check("OVERCAST's Classic palette is the suite's Ember",
          classic['bg'] == '#1D1714' and classic['accent'] == '#FB8E22' and classic['appearance'] == 'classic')

    import oracle_appearance as A
    A._state['appearance'] = 'dark'
    A.register_terms(['AAPL', 'MSFT'])
    cases = {
        'CHARTS: 2 REQUESTED · 2 SHOWN · 0 WITH DATA': 'Charts: 2 requested · 2 shown · 0 with data',
        '~44.3 BITS': '~44.3 bits', '−10 SEC': '−10 sec', '01 HOME ROW': '01 Home row',
        '02 ETH-USD': '02 ETH-USD', 'FX:EURUSD': 'FX:EURUSD', 'STK AAPL': 'STK AAPL', 'USD/JPY': 'USD/JPY',
        'QUEUE A FILE FROM CONVERT, THEN PRESS START QUEUE.': 'Queue a file from convert, then press start queue.',
        'NO VIDEO LOADED': 'No video loaded', 'FFMPEG': 'FFmpeg', 'COPY [CTRL+C]': 'Copy [Ctrl+C]',
        'Already mixed Case': 'Already mixed Case', 'R': 'R',
    }
    wrong = {k: A.display(k) for k, v in cases.items() if A.display(k) != v}
    check('Dark/Light: capitals become sentence case; acronyms, symbols, keys and list numbers stay', not wrong, wrong)
    A._state['appearance'] = 'classic'
    check('Classic: labels are unchanged', A.display('NO VIDEO LOADED') == 'NO VIDEO LOADED')
    A._state['appearance'] = None

    from oracle_dicekey import Dicekey, load_words
    words, source = load_words()
    if words:
        engine = Dicekey(words, source)
        parts = engine.breakdown()
        check('passphrase: the strength breakdown has the five parts and adds up to the engine\'s bits',
              [p[0] for p in parts] == ['w1', 'w2', 'w3', 'digits', 'symbol']
              and abs(sum(p[1] for p in parts) - engine.bits) < 1e-9, (parts, engine.bits))
    else:
        print('SKIP passphrase breakdown: no word list')

    # OVERCAST keeps its own saved look while a host sets one.
    import json
    import tkinter as tk
    state = tempfile.mkdtemp(prefix='mo-final-ovc-')
    Path(state, 'overcast_settings.json').write_text(json.dumps({'appearance': 'light', 'accent': 'Blue'}))
    if os.environ.get('DISPLAY') or os.name == 'nt':
        root = tk.Tk()
        try:
            from overcast import create_panel
            panel = create_panel(root, state_dir=state, appearance='classic', font=None)
            panel._save_settings()
            saved = json.loads(Path(state, 'overcast_settings.json').read_text())
            check("OVERCAST inside Classic uses Ember but keeps its own saved look",
                  panel.theme.appearance == 'classic' and saved.get('appearance') == 'light'
                  and saved.get('accent') == 'Blue', (panel.theme.appearance, saved))
        finally:
            root.destroy()


def gui_checks():
    os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-final-')
    os.environ['MARBLE_ORACLE_APPEARANCE'] = os.environ.get('LOOK', 'dark')
    os.environ['MARBLE_ORACLE_NO_WELCOME'] = '1'
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        import tkinter as tk
        from marble_oracle import launch_plan, WindowApp
        import oracle_appearance
        import oracle_design
        import oracle_widgets as W
        import oracle_shell
        from overcast.theme import contrast
        app = WindowApp(launch_plan(['--selftest', '--no-network'])[1])
        root, scene = app.root, app.scene
        look = oracle_appearance.appearance()
        p = oracle_appearance.palette()

        label = tk.Label(root, text='NO VIDEO LOADED')
        options = {'text': 'START QUEUE'}
        label.configure(options)
        canvas = tk.Canvas(root)
        item = canvas.create_text(10, 10, text='NETWORK DISABLED')
        check(f'{look}: widget labels are written in sentence case', label.cget('text') == 'Start queue',
              label.cget('text'))
        check(f'{look}: the caller\'s options are left as they were', options == {'text': 'START QUEUE'})
        check(f'{look}: canvas text keeps its own case', canvas.itemcget(item, 'text') == 'NETWORK DISABLED')
        bad = {k: round(contrast(v, p[s]), 2) for k, v in oracle_design.MARKET_COLORS.items()
               for s in ('bg', 'card', 'side', 'field') if contrast(v, p[s]) < 4.5}
        check(f'{look}: market colours read on every surface', not bad, bad)

        def pump(n=8):
            for _ in range(n):
                root.update()
                if scene.W == 0 or getattr(scene, 'need_build', False):
                    scene.resized(*app.canvas_size())
                scene.tick()
                time.sleep(0.01)
        root.geometry('1216x848+0+0')
        root.update()
        scene.resized(1216, 848)
        pump()

        scene.act('tab_passphrase')
        pump(12)
        frame = scene.dk.frame
        check(f'{look}: the workspace leaves Home to the suite\'s sidebar', not frame.home_button.winfo_manager())
        check(f'{look}: the workspace Home button still exists for keyboard and callers',
              frame.home_button.winfo_exists())
        entry = frame.entry
        check(f'{look}: text fields get inner padding', int(float(entry.cget('bd'))) >= 4, entry.cget('bd'))
        checks = [w for w in _walk(frame) if w.winfo_class() == 'Checkbutton']
        check(f'{look}: check boxes are drawn (no Tk indicator)',
              checks and all(not int(w.cget('indicatoron')) and str(w.cget('image')) for w in checks))

        scene.act('tab_touch_type')
        pump(12)
        touch = scene.touch.frame if getattr(scene, 'touch', None) else None
        if touch is None:
            touch = next((w for w in _walk(root) if hasattr(w, '_draw_keyboard')), None)
        sizes = {}
        for geometry in ('1216x848', '1920x1080'):
            root.geometry(geometry + '+0+0')
            pump(14)
            keys = [touch.keyboard.bbox(i) for i in touch.keyboard.find_all()
                    if touch.keyboard.type(i) == 'polygon']
            sizes[geometry] = max((b[2] - b[0]) for b in keys if b) if keys else 0
        check(f'{look}: Touch Type\'s keyboard grows with the window', sizes['1920x1080'] > sizes['1216x848'] * 1.15,
              sizes)
        root.geometry('1216x848+0+0')
        pump(6)

        scene.act('tab_eidolith')
        pump(12)
        eido = scene.eido.frame
        hint = getattr(eido.file_list, '_empty_hint', None)
        check(f'{look}: an empty file list says what to do', hint is not None and hint.winfo_manager() == 'place')
        eido.file_list.insert('end', 'clip.mkv')
        root.update()
        check(f'{look}: the hint goes when the list has rows', not hint.winfo_manager())
        eido.file_list.delete(0, 'end')
        root.update()
        check(f'{look}: and comes back when it is empty again', hint.winfo_manager() == 'place')
        slider = eido.video.seek_slider
        check(f'{look}: the player uses the rounded slider', isinstance(slider, W.FlatSlider))
        moved = []
        slider.configure(command=moved.append)
        slider.event_generate('<ButtonPress-1>', x=slider.winfo_width() // 2, y=5)
        slider._pointer(type('E', (), {'x': slider.winfo_width() // 2})())
        check(f'{look}: the slider follows a click and reports the value as text',
              moved and isinstance(moved[-1], str) and 300 <= float(moved[-1]) <= 700, moved[-1:])
        before = root.bind_all('<MouseWheel>')
        eido._show_page('CONVERT')
        pump(6)
        check(f'{look}: the Convert settings take the mouse wheel without any application-wide binding',
              root.bind_all('<MouseWheel>') == before)
        check(f'{look}: shell.workspace_home_shown is off', not oracle_shell.workspace_home_shown())
        app.quit()
    warnings = stderr.getvalue()
    check(f'{look}: no Tk error output', 'Traceback' not in warnings and 'TclError' not in warnings, warnings[-400:])


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
        for look in ('dark', 'light'):
            env = {k: v for k, v in os.environ.items() if k != 'MARBLE_ORACLE_APPEARANCE'}
            env['LOOK'] = look
            done = subprocess.run([sys.executable, __file__, 'gui'], env=env, capture_output=True, text=True,
                                  timeout=900)
            print(done.stdout, end='')
            results.extend(line.startswith('PASS') for line in done.stdout.splitlines() if line[:4] in ('PASS', 'FAIL'))
            if done.returncode != 0 and 'FAIL' not in done.stdout:
                print(done.stderr[-2000:])
                results.append(False)
    else:
        print('SKIP the window checks: no display')
    print(f'FINAL REVIEW 0.5.4: {sum(results)}/{len(results)} checks passed')
    sys.exit(0 if all(results) else 1)
