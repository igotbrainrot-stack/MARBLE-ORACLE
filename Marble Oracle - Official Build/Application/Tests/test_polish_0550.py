"""0.5.5: the last open items of the 0.5.4 design review (22-26), in Dark, in their own process.

* Dropdown choices are written in sentence case while the values the code compares stay as they were.
* Workspace rails start with their first section (the suite's top bar already names the workspace).
* The sidebar's and top bar's type does not grow past its reference size at 1920x1080.
* Eidolith's About page sets its headings as headings.
* Oggcultist's now-playing bar gives the song name room in a small window.
* Chart messages are cased like the rest.
"""
import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'Runtime' / 'Marble_Oracle_App'))
os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-polish-')
os.environ['MARBLE_ORACLE_APPEARANCE'] = 'dark'
os.environ['MARBLE_ORACLE_NO_WELCOME'] = '1'
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {str(detail)[:300]}'))


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


if not (os.environ.get('DISPLAY') or os.name == 'nt'):
    print('SKIP: no display')
    sys.exit(0)

stderr = io.StringIO()
with redirect_stderr(stderr):
    import tkinter as tk
    from marble_oracle import launch_plan, WindowApp
    import oracle_widgets as W
    app = WindowApp(launch_plan(['--selftest', '--no-network'])[1])
    root, scene = app.root, app.scene

    # -- 22: dropdowns
    var = tk.StringVar(root, value='MAX BARS')
    menu_button = tk.OptionMenu(root, var, '30 BARS', 'MAX BARS', 'Overview')
    W.style_dropdown(menu_button)
    menu = menu_button['menu']
    labels = [menu.entrycget(i, 'label') for i in range(3)]
    check('dropdown: the button shows the value in sentence case', menu_button.cget('text') == 'Max bars',
          menu_button.cget('text'))
    check('dropdown: its choices are listed in sentence case', labels == ['30 bars', 'Max bars', 'Overview'], labels)
    menu.invoke(0)
    check('dropdown: choosing sets the original value the code compares', var.get() == '30 BARS', var.get())
    check('dropdown: and the button follows it', menu_button.cget('text') == '30 bars', menu_button.cget('text'))
    var.set('Overview')
    check('dropdown: a value set in code shows too', menu_button.cget('text') == 'Overview')
    menu_button.destroy()

    def pump(n=8):
        for _ in range(n):
            root.update()
            if scene.W == 0 or getattr(scene, 'need_build', False):
                scene.resized(*app.canvas_size())
            scene.tick()
            time.sleep(0.01)

    # -- 24: chrome type at 1920x1080
    sizes = {}
    for geometry in ('1216x848', '1920x1080'):
        root.geometry(geometry + '+0+0')
        root.update()
        scene.resized(*[int(v) for v in geometry.split('x')])
        pump(10)
        sizes[geometry] = abs(int(scene.chrome_font(12).actual('size')))
    check('the sidebar\'s type does not grow past its reference size at 1920x1080',
          sizes['1920x1080'] == sizes['1216x848'], sizes)
    root.geometry('1216x848+0+0')
    root.update()
    scene.resized(1216, 848)
    pump(6)

    # -- 23: rails start with their first section
    scene.act('tab_passphrase')
    pump(12)
    shell_ = scene.dk.frame.shell
    check('Passphrase: the rail does not repeat the workspace name', not shell_._brand_box.winfo_manager())
    scene.act('tab_augurspex')
    pump(12)
    aug = scene.aug.frame if getattr(scene, 'aug', None) else next(w for w in walk(root) if hasattr(w, '_rail_brand'))
    first = [w for w in aug.rail.pack_slaves() if w.winfo_manager()]
    texts = [str(w.cget('text')) for w in first if 'text' in w.keys()]
    check('AUGURSPEX: the rail starts at Find market', not aug._rail_brand.winfo_manager() and 'Find market' in texts,
          texts[:3])
    charts = [c for c in walk(aug) if isinstance(c, tk.Canvas)]
    messages = [c.itemcget(i, 'text') for c in charts for i in c.find_all() if c.type(i) == 'text']
    check('AUGURSPEX: chart messages are cased like the rest', 'NETWORK DISABLED' not in messages
          and not any(m.isupper() and len(m) > 12 for m in messages), messages[:6])

    # -- 25: Eidolith About
    scene.act('tab_eidolith')
    pump(12)
    eido = scene.eido.frame
    texts = [w for w in walk(eido.pages['ABOUT']) if isinstance(w, tk.Text)]
    about = texts[0] if texts else None
    headings = about.tag_ranges('heading') if about is not None else ()
    content = about.get('1.0', 'end') if about is not None else ''
    check('Eidolith About: headings are set as headings', len(headings) >= 8, len(headings))
    check('Eidolith About: names the buttons as they are shown', 'Fullscreen' in content and 'FULLSCREEN' not in content)

    # -- 26: Oggcultist's now-playing bar in a small window
    scene.act('tab_oggcultist')
    pump(16)
    bars = [w for w in walk(root) if type(w).__name__ == 'NowPlayingBar']
    if bars:
        bar = bars[0]
        bar.event_generate('<Configure>', width=840, height=80)
        bar._bar_resized(type('E', (), {'widget': bar, 'width': 840})())
        root.update()
        bar._fit_info()
        shown = str(bar._title_label.cget('text'))
        check('Oggcultist: a small window gives the song name room (the cover steps aside)',
              not bar.cover.winfo_manager() and shown == 'Nothing playing', shown)
        bar._bar_resized(type('E', (), {'widget': bar, 'width': 1300})())
        root.update()
        check('Oggcultist: and the cover returns when there is room', bool(bar.cover.winfo_manager()))
    else:
        check('Oggcultist: now-playing bar found', False)
    app.quit()

warnings = stderr.getvalue()
check('no Tk error output', 'Traceback' not in warnings and 'TclError' not in warnings, warnings[-400:])
print(f'POLISH 0.5.5: {sum(results)}/{len(results)} checks passed')
sys.exit(0 if all(results) else 1)
