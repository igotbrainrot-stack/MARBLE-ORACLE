"""The Appearance window (0.5.1): Dark, Light or Classic, and the accent colour.

Opened from the sidebar's Appearance row (Dark / Light) or with the A key (every appearance). The choice is
saved at once; it takes effect when the suite next starts, and RESTART NOW does that straight away (the suite
closes as its close button does, so a running conversion still asks first).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk

import oracle_appearance as appearance
from oggcultist_design_system import COLOR as C


def _font(size, bold=False):
    return (appearance.family(), size, 'bold' if bold else 'normal')


def restart(scene):
    """Close the suite as its close button does, then start it again with the same arguments."""
    host = getattr(scene, 'host', None)
    if host is None or scene.o.get('selftest'):
        return False
    root = host.root
    host.quit()
    try:
        alive = bool(root.winfo_exists())
    except tk.TclError:
        alive = False
    if alive:            # a conversion in progress kept the suite open
        return False
    env = dict(os.environ)
    env.pop('MARBLE_ORACLE_EXIT_FILE', None)
    subprocess.Popen([sys.executable] + sys.argv, env=env, close_fds=True)
    return True


def show_appearance(scene):
    root = scene.root
    existing = getattr(root, '_appearance_window', None)
    if existing is not None:
        try:
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing
        except tk.TclError:
            pass
    current, tint = appearance.appearance(), appearance.accent()
    saved = appearance.read_prefs()
    look_var = tk.StringVar(master=root, value=saved.get('appearance', current))
    accent_var = tk.StringVar(master=root, value=saved.get('accent', tint))

    win = tk.Toplevel(root, bg=C['canvas'])
    root._appearance_window = win
    win.title('Appearance — Marble Oracle')
    win.transient(root)
    win.resizable(False, False)
    body = tk.Frame(win, bg=C['canvas'], padx=24, pady=20)
    body.pack(fill='both', expand=True)
    tk.Label(body, text='Appearance', font=_font(20, True), bg=C['canvas'], fg=C['text'], anchor='w').pack(fill='x')
    tk.Label(body, text='How Marble Oracle looks. OVERCAST, inside the suite, follows the same choice.',
             font=_font(10), bg=C['canvas'], fg=C['text_2'], anchor='w', justify='left').pack(fill='x', pady=(2, 14))

    cards = {}

    def paint():
        chosen = look_var.get()
        for name, (frame, labels) in cards.items():
            on = name == chosen
            colour = C['accent_soft'] if on else C['raised']
            frame.configure(bg=colour, highlightbackground=C['accent'] if on else C['line'])
            for label in labels:
                label.configure(bg=colour)
        state = 'disabled' if chosen == 'classic' else 'normal'
        for button in accent_buttons:
            button.configure(state=state)
        paint_accents()

    for name in appearance.APPEARANCES:
        frame = tk.Frame(body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'], padx=14, pady=10,
                         cursor='hand2', takefocus=True)
        frame.pack(fill='x', pady=(0, 8))
        title = tk.Label(frame, text=appearance.LABELS[name] + ('  (now)' if name == current else ''),
                         font=_font(12, True), bg=C['raised'], fg=C['text'], anchor='w')
        title.pack(fill='x')
        blurb = tk.Label(frame, text=appearance.DESCRIPTIONS[name], font=_font(10), bg=C['raised'], fg=C['text_2'],
                         anchor='w', justify='left', wraplength=380)
        blurb.pack(fill='x')
        cards[name] = (frame, (title, blurb))
        for widget in (frame, title, blurb):
            widget.bind('<Button-1>', lambda _e, n=name: (look_var.set(n), paint()))
        frame.bind('<Key-space>', lambda _e, n=name: (look_var.set(n), paint()))
        frame.bind('<Return>', lambda _e, n=name: (look_var.set(n), paint()))
        frame.bind('<FocusIn>', lambda _e, f=frame: f.configure(highlightthickness=2))
        frame.bind('<FocusOut>', lambda _e, f=frame: f.configure(highlightthickness=1))

    tk.Label(body, text='Accent', font=_font(11, True), bg=C['canvas'], fg=C['text'], anchor='w').pack(fill='x',
                                                                                                    pady=(8, 4))
    row = tk.Frame(body, bg=C['canvas'])
    row.pack(fill='x')
    accent_buttons = []

    def paint_accents():
        for button in accent_buttons:
            on = button._accent == accent_var.get()
            button.configure(bg=C['accent'] if on else C['control'],
                             fg=C['text_on_accent'] if on else C['text'],
                             activebackground=C['accent_deep'] if on else C['hover'])

    for name in appearance.accents():
        button = tk.Button(row, text=name, font=_font(10, True), relief='flat', bd=0, padx=12, pady=5,
                           cursor='hand2', highlightthickness=1, highlightbackground=C['canvas'],
                           command=lambda n=name: (accent_var.set(n), paint_accents()))
        button._accent = name
        button.pack(side='left', padx=(0, 6))
        accent_buttons.append(button)
    note = tk.Label(body, text='Saved at once. It takes effect when Marble Oracle next starts.', font=_font(9),
                    bg=C['canvas'], fg=C['text_2'], anchor='w')
    note.pack(fill='x', pady=(14, 0))

    def save():
        appearance.write_prefs(look_var.get(), accent_var.get())

    def close():
        root._appearance_window = None
        win.destroy()

    def save_close():
        save()
        changed = (look_var.get(), accent_var.get()) != (current, tint)
        close()
        if changed:
            scene.say(appearance.display('APPEARANCE SAVED · IT APPLIES WHEN MARBLE ORACLE NEXT STARTS'), 6)

    def save_restart():
        save()
        close()
        if not restart(scene):
            scene.say(appearance.display('APPEARANCE SAVED · RESTART MARBLE ORACLE TO SEE IT'), 6)

    buttons = tk.Frame(body, bg=C['canvas'])
    buttons.pack(fill='x', pady=(16, 0))
    for text, command, primary in (('Restart now', save_restart, True), ('Save', save_close, False),
                                   ('Cancel', close, False)):
        tk.Button(buttons, text=text, command=command, font=_font(10, True), relief='flat', bd=0, padx=14, pady=6,
                  cursor='hand2', bg=C['accent'] if primary else C['control'],
                  fg=C['text_on_accent'] if primary else C['text'],
                  activebackground=C['accent_deep'] if primary else C['hover'],
                  activeforeground=C['text_on_accent'] if primary else C['text'],
                  highlightthickness=1, highlightbackground=C['canvas']).pack(side='right', padx=(6, 0))
    win.bind('<Escape>', lambda _e: close())
    win.protocol('WM_DELETE_WINDOW', close)
    paint()
    win.update_idletasks()
    try:
        x = root.winfo_rootx() + max(0, (root.winfo_width() - win.winfo_reqwidth()) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - win.winfo_reqheight()) // 3)
        win.geometry(f'+{x}+{y}')
    except tk.TclError:
        pass
    cards[look_var.get()][0].focus_set()
    return win
