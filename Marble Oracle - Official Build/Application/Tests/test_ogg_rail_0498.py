"""0.4.9.8: every item of OGGCULTIST's rail stays reachable at every window size.

    xvfb-run -a python3 Application/Tests/test_ogg_rail_0498.py

Found by running the suite on a virtual display: at 1280x720 the suite's HOME
button covered half of Oggcultist's Settings item, and at 900x580 Settings was
not reachable at all while Converter and Album Art were cut off.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp, launch_plan  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


_a, options, _c = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene


def settle(size, seconds=0.8):
    root.geometry(size + '+0+0')
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        if scene.W == 0 or getattr(scene, 'need_build', False):
            scene.resized(*app.canvas_size())
        scene.tick()
        time.sleep(0.02)


settle('1280x720')
scene.act('tab_oggcultist')
settle('1280x720')
check('Oggcultist opened inside the suite', scene.ogg is not None and scene.ogg.frame.ogg_app is not None)
panel = scene.ogg.frame
ogg = panel.ogg_app
sidebar = ogg._sidebar
home = panel.home_button
import oracle_shell  # noqa: E402
if not oracle_shell.workspace_home_shown():
    # 0.5.4: in Dark/Light the suite's sidebar has Home, so Oggcultist's rail does not repeat it; the
    # foot of the rail (its version line) takes HOME's place in these checks.
    check('Dark/Light: the rail does not repeat Home', not home.winfo_manager())
    home = ogg.version_label
items = [ogg.nav[k] for k in ('library', 'artists', 'albums', 'playlists', 'converter', 'art', 'settings')
         if k in ogg.nav]
check('the rail has its seven items', len(items) == 7, list(ogg.nav))


def inside(widget, height):
    y = widget.winfo_y()
    return widget.winfo_ismapped() and y >= 0 and y + widget.winfo_height() <= height + 1


for size in ('1280x720', '900x580', '1920x1080', '900x580', '1000x650', '1216x848', '1280x720'):
    settle(size)
    height = sidebar.winfo_height()
    for widget in items + [home]:
        name = widget.cget('text') or str(widget)
        check(f'{size}: {name} is fully inside the rail', inside(widget, height),
              (widget.winfo_ismapped(), widget.winfo_y(), widget.winfo_height(), height))
    top_of_home = home.winfo_y()
    for widget in items:
        bottom = widget.winfo_y() + widget.winfo_height()
        check(f'{size}: HOME does not cover {widget.cget("text") or widget}', bottom <= top_of_home + 1,
              (bottom, top_of_home))
    settings = ogg.nav['settings']
    check(f'{size}: Settings sits just above HOME', settings.winfo_y() < top_of_home)
    compact = bool(getattr(ogg, 'compact', False))
    logo_shown = bool(ogg.brand_label.winfo_manager())
    if not compact:
        check(f'{size}: the full rail shows the Oggcultist logo', logo_shown)
    if logo_shown:
        check(f'{size}: the logo is at the top of the rail',
              ogg.brand_label.winfo_y() < min(w.winfo_y() for w in items),
              (ogg.brand_label.winfo_y(), [w.winfo_y() for w in items]))

scene.act('tab_home')
settle('1280x720', 0.3)
app.quit()
print(f'OGGCULTIST RAIL 0.4.9.8: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
