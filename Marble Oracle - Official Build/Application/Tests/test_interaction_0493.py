"""One hover, keyboard-focus and tooltip behaviour for the whole suite.

    xvfb-run -a python3 Application/Tests/test_interaction_0493.py

Before 0.4.9.3 a button gave no feedback under the pointer on Windows, the
keyboard focus outline was black on near-black, and shortened captions had no
way to be read in full.
"""
from pathlib import Path
import sys
import time

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

from oracle_design import COLOR, hover_tint  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


def tint_rule():
    check('a dark control lightens', hover_tint('#2F2620') != '#2F2620' and int(hover_tint('#2F2620')[1:3], 16) > 0x2F)
    check('the accent lightens too', hover_tint(COLOR['accent']) != COLOR['accent'])
    check('zero amount changes nothing', hover_tint('#2F2620', 0) == '#2F2620')
    check('full amount is the bright text colour', hover_tint('#000000', 1).upper() == COLOR['text_bright'].upper())
    for odd in ('SystemButtonFace', '', '#FFF', '#GGGGGG', None):
        check(f'a colour it cannot read is left alone ({odd!r})', hover_tint(odd) == odd)


def pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def gui():
    import tkinter as tk
    from oracle_widgets import install_interaction_defaults, tooltip
    root = tk.Tk()
    try:
        root.geometry('420x260+0+0')
        install_interaction_defaults(root)
        install_interaction_defaults(root)          # twice must not double the bindings
        plain = tk.Button(root, text='PLAIN', bg='#2F2620', relief='flat')
        own = tk.Button(root, text='OWN', bg='#2F2620', highlightcolor='#123456')
        off = tk.Button(root, text='OFF', bg='#2F2620', state='disabled')
        entry = tk.Entry(root)
        for widget in (plain, own, off, entry):
            widget.pack()
        root.update()

        check('focus outline is the accent by default', str(plain.cget('highlightcolor')).upper() == COLOR['focus'].upper(),
              plain.cget('highlightcolor'))
        check('entries get it too', str(entry.cget('highlightcolor')).upper() == COLOR['focus'].upper())
        check('a control that chose its own outline keeps it', own.cget('highlightcolor') == '#123456')
        check('disabled captions use the tertiary text colour',
              str(off.cget('disabledforeground')).upper() == COLOR['text_3'].upper())

        plain.event_generate('<Enter>')
        root.update()
        check('hover lightens the button', str(plain.cget('bg')).upper() == hover_tint('#2F2620').upper(), plain.cget('bg'))
        plain.event_generate('<Leave>')
        root.update()
        check('leaving restores it exactly', str(plain.cget('bg')).upper() == '#2F2620', plain.cget('bg'))

        plain.event_generate('<Enter>')
        root.update()
        plain.configure(bg='#4A2C18')                # a click selected it while the pointer was still over it
        plain.event_generate('<Leave>')
        root.update()
        check('leaving never undoes a colour set while hovering', str(plain.cget('bg')).upper() == '#4A2C18', plain.cget('bg'))

        off.event_generate('<Enter>')
        root.update()
        check('a disabled button does not react', str(off.cget('bg')).upper() == '#2F2620', off.cget('bg'))

        label = tk.Label(root, text='SHORT…')
        label.pack()
        full = {'text': 'The whole sentence that did not fit'}
        tooltip(label, lambda _event: full['text'], delay_ms=60)
        root.update()

        def panels():
            return [w for w in label.winfo_children() if isinstance(w, tk.Toplevel)]

        label.event_generate('<Enter>', x=3, y=3)
        pump(root, 0.4)
        shown = panels()
        check('resting on a shortened caption shows the full text', len(shown) == 1
              and any(child.cget('text') == full['text'] for child in shown[0].winfo_children()), len(shown))
        label.event_generate('<Leave>')
        pump(root, 0.1)
        check('and it goes away on leave', not panels())

        full['text'] = ''
        label.event_generate('<Enter>', x=3, y=3)
        pump(root, 0.3)
        check('nothing is shown when there is nothing more to say', not panels())
    finally:
        root.destroy()


if __name__ == '__main__':
    tint_rule()
    gui()
    print(f'INTERACTION: {checks - len(failures)}/{checks} checks passed')
    sys.exit(1 if failures else 0)
