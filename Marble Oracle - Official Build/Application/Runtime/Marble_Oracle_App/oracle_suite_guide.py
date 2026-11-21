"""The welcome window: what Marble Oracle is, its six workspaces, and how to get around.

Shown once, shortly after the first start (and again at start while "Show this
when Marble Oracle starts" stays ticked). F1 opens it at any time.

Every workspace has a card with what it is for, a few things to try first and
an OPEN button that goes straight there. The cards reflow from three columns
to one with the window, and the whole body scrolls, so nothing is out of reach
on a small screen. Colours, type and buttons come from the shared shell.
"""
from __future__ import annotations

import json
import os
import tkinter as tk

import oracle_shell as shell
from oggcultist_design_system import COLOR as C
from oracle_version import SUITE_VERSION
from oracle_widgets import SlimScrollbar

PREFS_FILE = 'welcome.json'

# (number, name, tab action, one-line role, description, things to try)
WORKSPACES = (
    ('01', 'HOME', 'tab_home', 'The oracle dashboard',
     'Marble statues, THE WIRE of rotating quotations, a Latin word with its two pronunciations, '
     'a glance at the markets, and a three-card tarot or rune reading.',
     ('Space: the next quotation', 'T: deal the tarot again', 'Tab: step through the controls')),
    ('02', 'OGGCULTIST', 'tab_oggcultist', 'Music library and player',
     'Point it at your music folder to browse artists, albums and playlists, convert audio, and '
     'tidy album art. Music keeps playing while you use the other workspaces.',
     ('Choose music folder…', 'Double-click a song to play it', 'Ctrl+F: search the library')),
    ('03', 'EIDOLITH', 'tab_eidolith', 'Video player and converter',
     'Preview a video, then convert it or a whole batch to compact AV1 files with a profile for '
     'size, speed and resolution. Your original files are never changed.',
     ('CONVERT: add files, pick a folder', 'QUEUE: watch progress and logs', 'Needs FFmpeg installed')),
    ('04', 'AUGURSPEX', 'tab_augurspex', 'Market history charts',
     '23 starter markets (US stocks and ETFs, currencies, crypto) as line or candle charts with '
     'simple signals. Every price comes from a named public source; none is ever made up.',
     ('CHARTS 1 / 2 / 4 / 6 / 9', 'SOURCE DETAILS: where data came from', 'MANAGE LIST: add markets or a CSV')),
    ('05', 'PASSPHRASE', 'tab_passphrase', 'Strong, memorable passphrases',
     'Builds passphrases from the EFF word list with your system\'s secure random generator. '
     'A copied phrase is cleared from the clipboard after a minute.',
     ('Choose how many words', 'Copy, then paste where needed', 'Roll again for a new one')),
    ('06', 'TOUCH TYPE', 'tab_touch_type', 'Typing practice',
     'Learn the home row first, then unlock more letters as you improve, with lessons, games and '
     'a record of your progress.',
     ('Click the typing field to start', 'Follow the finger hints', 'Unlock letters as you go')),
)

SHORTCUTS = (
    ('F1', 'This guide'),
    ('Tab / Shift+Tab', 'Move between HOME\'s controls'),
    ('Enter', 'Press the ringed control'),
    ('Escape', 'Leave the ring, or close a window'),
    ('F', 'Full screen'),
    ('N', 'New Latin word'),
    ('E', 'Classical / Ecclesiastical Latin'),
    ('V', 'Change HOME\'s colour grade'),
)


# ---- the "show at start" preference ---------------------------------------
def _prefs_path():
    from oracle_assets import state_dir
    return os.path.join(state_dir(), PREFS_FILE)


def read_prefs():
    try:
        with open(_prefs_path(), encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_prefs(**changes):
    data = read_prefs()
    data.update(changes)
    try:
        with open(_prefs_path(), 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
    except OSError:
        pass                     # a read-only state folder must never stop the suite


def should_show_at_start():
    """True until the person unticks "Show this when Marble Oracle starts"."""
    return bool(read_prefs().get('show_at_start', True))


def maybe_show_welcome(scene, delay_ms=700):
    """Open the welcome window shortly after start, unless it was switched off.

    Never during the self-test or automated tests (both use --selftest).
    """
    options = getattr(scene, 'o', {}) or {}
    if options.get('selftest') or os.environ.get('MARBLE_ORACLE_NO_WELCOME'):
        return None
    if not should_show_at_start():
        return None
    try:
        return scene.root.after(delay_ms, lambda: show_suite_guide(scene, first_run=True))
    except tk.TclError:
        return None


# ---- the window -------------------------------------------------------------
def _columns_for(width):
    return 3 if width >= 900 else 2 if width >= 600 else 1


def show_suite_guide(scene, first_run=False):
    """Open (or bring forward) the welcome window. Returns the Toplevel."""
    old = getattr(scene, '_guide_window', None)
    if old is not None:
        try:
            if old.winfo_exists():
                old.deiconify()
                old.lift()
                old.focus_set()
                return old
        except tk.TclError:
            pass
    root = scene.root
    win = tk.Toplevel(root)
    scene._guide_window = win
    win.title('Welcome to Marble Oracle')
    win.configure(bg=C['canvas'])
    win.transient(root)
    # Sized from the suite's own window (it sits over it like a sheet), never
    # larger than the screen; centred on the suite.
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
    except tk.TclError:
        rx = ry = 0
        rw = rh = 1
    if rw <= 1 or rh <= 1:
        rx, ry, rw, rh = 0, 0, sw, sh
    w = max(520, min(1040, rw - 60, sw - 40))
    h = max(400, min(760, rh - 40, sh - 60))
    x = min(max(0, rx + (rw - w) // 2), max(0, sw - w))
    y = min(max(0, ry + (rh - h) // 2), max(0, sh - h))
    win.geometry(f'{w}x{h}+{x}+{y}')
    win.minsize(520, 400)
    try:
        if getattr(root, '_marble_icon', None) is not None:
            win.iconphoto(False, root._marble_icon)
    except tk.TclError:
        pass

    def close(_event=None):
        write_prefs(show_at_start=bool(show_var.get()), seen_version=SUITE_VERSION)
        try:
            win.destroy()
        except tk.TclError:
            pass
        scene._guide_window = None
        try:
            root.focus_force()
        except tk.TclError:
            pass

    def open_workspace(action):
        close()
        try:
            scene.act(action)
        except Exception:
            pass

    win.protocol('WM_DELETE_WINDOW', close)
    win.bind('<Escape>', close)

    # Footer first, from the bottom, so the buttons never leave the window.
    footer = tk.Frame(win, bg=C['sidebar'])
    footer.pack(side='bottom', fill='x')
    show_var = tk.BooleanVar(master=win, value=should_show_at_start())
    tk.Checkbutton(footer, text='Show this when Marble Oracle starts', variable=show_var,
                   bg=C['sidebar'], fg=C['text_2'], activebackground=C['sidebar'],
                   activeforeground=C['text'], selectcolor=C['control'], font=shell.font('small'),
                   highlightthickness=2, highlightbackground=C['sidebar'], highlightcolor=C['focus'],
                   bd=0, cursor='hand2').pack(side='left', padx=20, pady=12)
    start = shell.button(footer, 'START EXPLORING' if first_run else 'CLOSE', close, primary=True)
    start.pack(side='right', padx=20, pady=12)
    tk.Label(footer, text='F1 opens this guide again', bg=C['sidebar'], fg=C['text_3'],
             font=shell.font('small')).pack(side='right', padx=4)

    # Header.
    head = tk.Frame(win, bg=C['canvas'])
    head.pack(fill='x', padx=28, pady=(22, 6))
    title_row = tk.Frame(head, bg=C['canvas'])
    title_row.pack(fill='x')
    tk.Label(title_row, text='MARBLE ORACLE', bg=C['canvas'], fg=C['accent'],
             font=(shell.font('brand')[0], 26, 'bold')).pack(side='left')
    tk.Label(title_row, text=SUITE_VERSION, bg=C['raised'], fg=C['text_2'], font=shell.font('small'),
             padx=8, pady=2).pack(side='left', padx=12, pady=(8, 0))
    intro = tk.Label(head, bg=C['canvas'], fg=C['text'], font=shell.font('body'), justify='left', anchor='w',
                     text=('Welcome. Marble Oracle is six tools in one window: an oracle dashboard, a music '
                           'player, a video converter, market charts, a passphrase maker and a typing tutor. '
                           'Pick a workspace below, or use the tabs along the top at any time.'))
    intro.pack(fill='x', pady=(8, 0))
    head.bind('<Configure>', lambda e: intro.configure(wraplength=max(200, e.width - 4)), add='+')

    # Scrolling body.
    body = tk.Frame(win, bg=C['canvas'])
    body.pack(fill='both', expand=True, padx=(20, 8), pady=(8, 8))
    rail = SlimScrollbar(body, orient='vertical', bg=C['canvas'])
    canvas = tk.Canvas(body, bg=C['canvas'], bd=0, highlightthickness=0, yscrollcommand=rail.set)
    rail.configure(command=canvas.yview)
    rail.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(canvas, bg=C['canvas'])
    inner_id = canvas.create_window(0, 0, window=inner, anchor='nw')

    cards = []
    for number, name, action, role, text, tries in WORKSPACES:
        card = tk.Frame(inner, bg=C['raised'], highlightthickness=1, highlightbackground=C['control_line'])
        top = tk.Frame(card, bg=C['raised'])
        top.pack(fill='x', padx=16, pady=(14, 2))
        tk.Label(top, text=number, bg=C['raised'], fg=C['accent'], font=shell.font('group')).pack(side='left')
        tk.Label(top, text=name, bg=C['raised'], fg=C['text_bright'], font=shell.font('section')).pack(
            side='left', padx=(8, 0))
        tk.Label(card, text=role, bg=C['raised'], fg=C['accent'], font=shell.font('body_bold'),
                 anchor='w', justify='left').pack(fill='x', padx=16)
        desc = tk.Label(card, text=text, bg=C['raised'], fg=C['text_2'], font=shell.font('body'),
                        anchor='w', justify='left')
        desc.pack(fill='x', padx=16, pady=(6, 6))
        tips = tk.Frame(card, bg=C['raised'])
        tips.pack(fill='x', padx=16)
        tip_labels = []
        for tip in tries:
            label = tk.Label(tips, text='›  ' + tip, bg=C['raised'], fg=C['text_3'], font=shell.font('small'),
                             anchor='w', justify='left')
            label.pack(fill='x')
            tip_labels.append(label)
        go = shell.button(card, 'OPEN ' + name, lambda a=action: open_workspace(a))
        go.pack(anchor='w', padx=16, pady=(10, 14))
        cards.append((card, [desc] + tip_labels))

    keys = tk.Frame(inner, bg=C['canvas'])
    tk.Label(keys, text='KEYBOARD', bg=C['canvas'], fg=C['text_3'], font=shell.font('group')).grid(
        row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
    for index, (key, meaning) in enumerate(SHORTCUTS):
        row, col = 1 + index // 2, (index % 2) * 2
        tk.Label(keys, text=key, bg=C['control'], fg=C['text_bright'], font=shell.font('small'),
                 padx=7, pady=1).grid(row=row, column=col, sticky='w', padx=(0, 8), pady=3)
        tk.Label(keys, text=meaning, bg=C['canvas'], fg=C['text_2'], font=shell.font('small')).grid(
            row=row, column=col + 1, sticky='w', padx=(0, 28), pady=3)

    layout = {'columns': None, 'width': None}

    def reflow(_event=None):
        width = canvas.winfo_width()
        if width <= 1 or width == layout['width']:
            return
        layout['width'] = width
        canvas.itemconfigure(inner_id, width=width)
        columns = _columns_for(width)
        gap = 14
        card_width = max(160, (width - gap * (columns - 1)) // columns)
        for card, labels in cards:
            for label in labels:
                label.configure(wraplength=card_width - 40)
        if columns != layout['columns']:
            layout['columns'] = columns
            for index, (card, _labels) in enumerate(cards):
                card.grid_forget()
                card.grid(row=index // columns, column=index % columns, sticky='nsew',
                          padx=(0 if index % columns == 0 else gap // 2, 0 if index % columns == columns - 1 else gap // 2),
                          pady=(0, gap))
            for col in range(3):
                inner.grid_columnconfigure(col, weight=1 if col < columns else 0, uniform='card' if col < columns else '')
            keys.grid_forget()
            keys.grid(row=(len(cards) + columns - 1) // columns, column=0, columnspan=columns, sticky='w', pady=(6, 4))

    def update_scroll(_event=None):
        canvas.configure(scrollregion=canvas.bbox('all'))

    def wheel(event):
        if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0:
            canvas.yview_scroll(-2, 'units')
        else:
            canvas.yview_scroll(2, 'units')

    canvas.bind('<Configure>', reflow, add='+')
    inner.bind('<Configure>', update_scroll, add='+')
    for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        win.bind(sequence, wheel, add='+')
    def enter(_event=None):
        # Enter presses the focused button (an OPEN card, START); elsewhere it closes.
        focused = win.focus_get()
        if isinstance(focused, tk.Button):
            focused.invoke()
        else:
            close()
        return 'break'

    win.bind('<Return>', enter)
    win.bind('<KP_Enter>', enter)

    win.update_idletasks()
    reflow()
    start.focus_set()
    if first_run:
        write_prefs(seen_version=SUITE_VERSION)
    return win
