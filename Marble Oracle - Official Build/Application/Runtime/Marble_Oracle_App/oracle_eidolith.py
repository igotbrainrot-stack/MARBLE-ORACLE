"""EIDOLITH: local-first video player + archival converter tab for Marble Oracle.

This is a self-contained Tk panel that matches the other suite tabs closely.
Playback renders FFmpeg-decoded video inside the application, with an
explicit fullscreen option. Probing and conversion use ffprobe/ffmpeg locally. The queue is serial, cancellable, and keeps
original files intact.
"""
from __future__ import annotations

import json
import os
import queue
import uuid
import shutil
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from marble_uberata import FAMILY
from oracle_ogg_texture import frame as ogl_frame, label as ogl_label, install as ogl_install
from oggcultist_design_system import COLOR as C
from oracle_assets import load_json, save_json
from oracle_eidolith_core import (PROFILES, PROFILE_ORDER, NAME_MODES, output_name,
                                  encoding_args, detect_encoders, profile_support,
                                  progress_label, progress_seconds)

APP_NAME = "EIDOLITH"
APP_VERSION = "0.3"

NAV_ITEMS = ("PLAYER", "CONVERT", "QUEUE", "ABOUT")


def which(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    # The suite installer puts Windows binaries in Oggcultist's private
    # per-user tools folder; standalone entrypoints may not have updated PATH.
    try:
        import sys
        from pathlib import Path
        ogg_root = Path(__file__).resolve().parent / 'Oggcultist'
        if str(ogg_root) not in sys.path:
            sys.path.insert(0, str(ogg_root))
        from oggcultist.paths import configure_tool_path
        configure_tool_path()
    except (ImportError, OSError, ValueError, RuntimeError):
        pass
    return shutil.which(name) or ''


class EidolithPanel(tk.Frame):
    def __init__(self, master, on_home):
        super().__init__(master, bg=C['sidebar'], highlightthickness=0)
        ogl_install(self)
        self.on_home = on_home
        self.ffmpeg = which('ffmpeg')
        self.ffprobe = which('ffprobe')
        self.ffplay = which('ffplay') or which('mpv')
        self.encoders = detect_encoders(self.ffmpeg)
        self.state = load_json('eidolith_state.json', {})
        if not isinstance(self.state, dict):
            self.state = {}
        self.files = list(self.state.get('files', []))
        self.output_dir = self.state.get('output_dir') or ''
        self.profile = tk.StringVar(value=self.state.get('profile') if self.state.get('profile') in PROFILES else 'Balanced archive (default)')
        self.rename_mode = tk.StringVar(value=self.state.get('rename_mode') if self.state.get('rename_mode') in NAME_MODES else NAME_MODES[0])
        self.title_override = tk.StringVar(value=self.state.get('title_override') or '')
        self.season_override = tk.StringVar(value=self.state.get('season_override') or '')
        self.episode_override = tk.StringVar(value=self.state.get('episode_override') or '')
        self.audio_mode = tk.StringVar(value=self.state.get('audio_mode') or 'copy')
        self.active_nav = tk.StringVar(value='PLAYER')
        self.status_var = tk.StringVar(value='Ready. Import a local video file to inspect or convert.')
        self.queue_items = []
        self.queue_seq = 0
        self.worker_thread = None
        self.worker_stop = threading.Event()
        self.active_proc = None
        self.play_proc = None
        self.uiq = queue.Queue()
        self._after_id = None
        self._build_ui()
        self._load_files()
        self._schedule_ui_queue()
        for var in (self.profile, self.rename_mode, self.title_override, self.season_override, self.episode_override):
            var.trace_add('write', lambda *_: self._update_name_preview())
        self.after_idle(self._probe_selected)

    # ---------- styling helpers ----------
    def _label(self, parent, txt, size=12, colour='text', bold=False, **kwargs):
        return ogl_label(parent, text=txt, fg=C[colour],
                         font=(FAMILY, size, 'bold' if bold else 'normal'), **kwargs)

    def _button(self, parent, text, cmd, *, primary=False, width=None):
        return tk.Button(parent, text=text, command=cmd, cursor='hand2', relief='flat', bd=0,
                         padx=12, pady=7, width=width,
                         font=(FAMILY, 10, 'bold'),
                         bg=C['accent'] if primary else C['control'],
                         fg=C['text_on_accent'] if primary else C['text'],
                         activebackground=C['accent_deep'] if primary else C['hover'],
                         activeforeground=C['text_on_accent'] if primary else C['text'],
                         highlightthickness=1, highlightbackground=C['control_line'])

    def _entry(self, parent, textvariable=None):
        return tk.Entry(parent, textvariable=textvariable, relief='flat', bd=0,
                        font=(FAMILY, 10), insertbackground=C['text'],
                        bg=C['canvas'], fg=C['text'],
                        highlightthickness=1, highlightbackground=C['control_line'])

    def _text(self, parent, height=8):
        t = tk.Text(parent, relief='flat', bd=0, height=height, width=38, wrap='word',
                    bg=C['canvas'], fg=C['text'], insertbackground=C['text'],
                    highlightthickness=1, highlightbackground=C['control_line'],
                    font=(FAMILY, 10))
        return t

    # ---------- layout ----------
    def _build_ui(self):
        root = ogl_frame(self, bg=C['sidebar'])
        root.pack(fill='both', expand=True)
        self.rail = ogl_frame(root, bg=C['sidebar'], width=240)
        self.rail.pack(side='left', fill='y')
        self.rail.pack_propagate(False)
        tk.Frame(root, bg=C['line'], width=1).pack(side='left', fill='y')
        self.main = ogl_frame(root, bg=C['canvas'])
        self.main.pack(side='left', fill='both', expand=True)
        self._build_rail()
        self._build_main()
        self._refresh_nav()

    def _build_rail(self):
        top = ogl_frame(self.rail, bg=C['sidebar'])
        top.pack(fill='x', padx=16, pady=(10, 6))
        self._label(top, f'{APP_NAME} {APP_VERSION}', 18, 'text_bright', bold=True).pack(anchor='w')
        logo = tk.Canvas(top, width=208, height=54, bg=C['sidebar'], highlightthickness=0, bd=0)
        logo.pack(anchor='w', pady=(6, 2))
        self._draw_logo(logo)
        self._label(top, 'VIDEO · ARCHIVE', 10, 'text_3').pack(anchor='w', pady=(4, 2))

        group = ogl_frame(self.rail, bg=C['sidebar'])
        group.pack(fill='x', padx=12, pady=(10, 0))
        self._label(group, 'WORKSPACE', 10, 'text_3').pack(anchor='w', padx=6, pady=(0, 8))
        self.nav_buttons = {}
        for name in NAV_ITEMS:
            btn = tk.Button(group, text=name, command=lambda n=name: self._set_nav(n), cursor='hand2',
                            relief='flat', bd=0, padx=10, pady=9,
                            font=(FAMILY, 13, 'bold'), anchor='w', justify='left',
                            bg=C['sidebar'], fg=C['text'], activebackground=C['hover'],
                            activeforeground=C['text'], highlightthickness=1, highlightbackground=C['sidebar'])
            btn.pack(fill='x', pady=3)
            self.nav_buttons[name] = btn

        env = ogl_frame(self.rail, bg=C['sidebar'])
        env.pack(fill='x', padx=18, pady=(14, 0))
        self._label(env, 'TOOLS', 10, 'text_3').pack(anchor='w', pady=(0, 8))
        self.env_labels = {}
        for label, path in (('FFMPEG', self.ffmpeg), ('FFPROBE', self.ffprobe), ('FFPLAY', self.ffplay)):
            row = ogl_frame(env, bg=C['sidebar'])
            row.pack(fill='x', pady=1)
            self._label(row, label, 11, 'text_3', bold=True).pack(side='left')
            ok = 'FOUND' if path else 'MISSING'
            colour = 'done' if path else 'failed'
            self.env_labels[label] = self._label(row, ok, 10, colour)
            self.env_labels[label].pack(side='right')

        bottom = ogl_frame(self.rail, bg=C['sidebar'])
        bottom.pack(side='bottom', fill='x', padx=18, pady=18)
        self._button(bottom, 'BACK TO HOME', self.on_home, primary=False).pack(fill='x')
        self._label(bottom, f'{APP_VERSION} · LOCAL', 10, 'text_3').pack(anchor='w', pady=(10, 0))

    def _draw_logo(self, canvas):
        fg = '#E8DDD0'
        accent = C['accent']
        line = C['line_strong']
        canvas.create_polygon(8, 8, 44, 8, 52, 16, 52, 38, 44, 46, 8, 46, 0, 38, 0, 16,
                              outline=fg, fill='', width=2)
        canvas.create_rectangle(14, 14, 38, 40, outline=accent, width=2)
        canvas.create_line(22, 14, 22, 40, fill=fg, width=2)
        canvas.create_line(22, 27, 38, 27, fill=fg, width=2)
        canvas.create_line(14, 40, 38, 14, fill=line, width=2)
        canvas.create_text(59, 27, text='EIDOLITH', anchor='w', fill=fg,
                           font=(FAMILY, 17, 'bold'))

    def _build_main(self):
        title = ogl_frame(self.main, bg=C['canvas'])
        title.pack(fill='x', padx=16, pady=(12, 8))
        self.page_title = self._label(title, 'PLAYER', 20, 'text_bright', bold=True)
        self.page_title.pack(anchor='w')
        self.page_subtitle = self._label(title, 'Play video in the EIDOLITH viewer.', 10, 'text_3')
        self.page_subtitle.pack(anchor='w', pady=(2, 0))

        body = ogl_frame(self.main, bg=C['canvas'])
        body.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.pages = {}
        for name in NAV_ITEMS:
            self.pages[name] = ogl_frame(body, bg=C['canvas'])

        # PLAYER: file browser/probe on left; native video viewer and transport
        # controls on right. Other workspaces are genuinely separate pages.
        page = self.pages['PLAYER']
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)
        left = ogl_frame(page, bg=C['canvas'])
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        right = ogl_frame(page, bg=C['canvas'])
        right.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        self._section_files(left)
        self._section_probe(left)
        from oracle_eidolith_player import InTabVideoPlayer
        self.video = InTabVideoPlayer(right, ffmpeg=self.ffmpeg, ffplay=self.ffplay,
                                     colors=C, font=FAMILY)

        # CONVERTER: source selection left, archival profile/output controls right.
        page = self.pages['CONVERT']
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)
        conv_left = ogl_frame(page, bg=C['canvas'])
        conv_left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        # Filename fields extend the settings area. Keep the entire right
        # column scrollable on compact CRT apertures instead of clipping the
        # QUEUE/START actions below the window.
        conv_shell = ogl_frame(page, bg=C['canvas'])
        conv_shell.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        conv_canvas = tk.Canvas(conv_shell, bg=C['canvas'], highlightthickness=0, bd=0)
        conv_scroll = tk.Scrollbar(conv_shell, orient='vertical', command=conv_canvas.yview)
        conv_canvas.configure(yscrollcommand=conv_scroll.set)
        conv_canvas.pack(side='left', fill='both', expand=True)
        conv_scroll.pack(side='right', fill='y')
        conv_right = ogl_frame(conv_canvas, bg=C['canvas'])
        self._convert_canvas = conv_canvas
        conv_window = conv_canvas.create_window((0, 0), window=conv_right, anchor='nw')
        conv_right.bind('<Configure>', lambda _e: conv_canvas.configure(scrollregion=conv_canvas.bbox('all')), add='+')
        conv_canvas.bind('<Configure>', lambda e: conv_canvas.itemconfigure(conv_window, width=max(1, e.width)), add='+')
        self._section_convert_sources(conv_left)
        self._section_convert(conv_right)

        # QUEUE: large, readable job list and independent run controls/logs.
        self._section_queue(self.pages['QUEUE'])
        self._section_about(self.pages['ABOUT'])

        footer = ogl_frame(self.main, bg=C['canvas'])
        footer.pack(fill='x', padx=16, pady=(0, 8))
        self.status_label = self._label(footer, '', 10, 'text_3')
        self.status_label.pack(anchor='w')
        self._sync_status()
        self._show_page('PLAYER')

    def _show_page(self, name):
        if not hasattr(self, 'pages'):
            return
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill='both', expand=True)
        if name != 'PLAYER' and hasattr(self, 'video'):
            self.video.suspend()

    def _section_frame(self, parent, title, subtitle=''):
        outer = ogl_frame(parent, bg=C['canvas'])
        outer.pack(fill='both', expand=False, pady=(0, 10))
        head = ogl_frame(outer, bg=C['canvas'])
        head.pack(fill='x', pady=(0, 6))
        self._label(head, title, 15, 'text_bright', bold=True).pack(anchor='w')
        if subtitle:
            self._label(head, subtitle, 10, 'text_3').pack(anchor='w')
        box = ogl_frame(outer, bg=C['raised'])
        box.pack(fill='both', expand=True)
        return outer, box

    def _section_files(self, parent):
        outer, box = self._section_frame(parent, 'SOURCE FILES', 'Choose the video to preview or inspect.')
        outer.pack(fill='both', expand=True)
        tools = ogl_frame(box, bg=C['raised'])
        tools.pack(fill='x', padx=8, pady=8)
        self._button(tools, 'OPEN', self.open_files, primary=True).pack(side='left')
        self._button(tools, 'FOLDER', self.add_folder).pack(side='left', padx=(5, 0))
        self._button(tools, 'SELECT ALL', self.select_all).pack(side='left', padx=(5, 0))
        act2 = ogl_frame(box, bg=C['raised'])
        act2.pack(fill='x', padx=8, pady=(0, 8))
        self._button(act2, 'REMOVE', self.remove_selected).pack(side='left')
        self._button(act2, 'CLEAR LIST', self.clear_files).pack(side='left', padx=(5, 0))

        list_frame = ogl_frame(box, bg=C['raised'])
        list_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.file_list = tk.Listbox(list_frame, selectmode='extended', exportselection=False,
                                    activestyle='none', bg=C['canvas'], fg=C['text'], bd=0,
                                    highlightthickness=1, highlightbackground=C['control_line'],
                                    selectbackground=C['hover'], selectforeground=C['text_bright'],
                                    font=(FAMILY, 10))
        ys = tk.Scrollbar(list_frame, orient='vertical', command=self.file_list.yview)
        self.file_list.config(yscrollcommand=ys.set)
        self.file_list.pack(side='left', fill='both', expand=True)
        ys.pack(side='right', fill='y')
        self.file_list.bind('<<ListboxSelect>>', lambda e: self._probe_selected())
        self.file_list.bind('<Control-a>', lambda e: (self.select_all(), 'break')[-1])
        act = ogl_frame(box, bg=C['raised'])
        act.pack(fill='x', padx=8, pady=(0, 9))
        self._button(act, 'PLAY IN VIEWER', self.play_selected, primary=True).pack(side='left')
        self._button(act, 'PROBE', self._probe_selected).pack(side='left', padx=(6, 0))

    def _section_convert_sources(self, parent):
        outer, box = self._section_frame(parent, 'CONVERSION SOURCES',
                                         'Select files for batch encoding.')
        outer.pack(fill='both', expand=True)
        tools = ogl_frame(box, bg=C['raised'])
        tools.pack(fill='x', padx=10, pady=10)
        self._button(tools, 'ADD FILES', self.open_files, primary=True).pack(side='left')
        self._button(tools, 'SELECT ALL', self.select_all).pack(side='left', padx=(6, 0))
        clear_controls = ogl_frame(box, bg=C['raised'])
        clear_controls.pack(fill='x', padx=10, pady=(0, 8))
        self._button(clear_controls, 'CLEAR SELECTION', self.clear_selection).pack(side='left')
        f = ogl_frame(box, bg=C['raised'])
        f.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.convert_list = tk.Listbox(f, selectmode='extended', exportselection=False,
                                       activestyle='none', bg=C['canvas'], fg=C['text'], bd=0,
                                       highlightthickness=1, highlightbackground=C['control_line'],
                                       selectbackground=C['hover'], selectforeground=C['text_bright'],
                                       font=(FAMILY, 10))
        ys = tk.Scrollbar(f, orient='vertical', command=self.convert_list.yview)
        self.convert_list.config(yscrollcommand=ys.set)
        self.convert_list.pack(side='left', fill='both', expand=True)
        ys.pack(side='right', fill='y')
        self.convert_list.bind('<Control-a>', lambda e: (self.select_all(), 'break')[-1])
        self.convert_list.bind('<<ListboxSelect>>', lambda e: self._update_name_preview())
        self._label(box, 'Files are not deleted, modified or replaced by conversion.', 10, 'text_3').pack(
            anchor='w', padx=10, pady=(0, 10))

    def _current_listbox(self):
        return self.convert_list if self.active_nav.get() == 'CONVERT' else self.file_list

    def select_all(self):
        lb = self._current_listbox()
        if lb.size():
            lb.selection_set(0, 'end')
            self._set_status(f'Selected all {lb.size()} source files.')

    def clear_selection(self):
        self._current_listbox().selection_clear(0, 'end')
        self._set_status('Selection cleared.')

    def _section_probe(self, parent):
        outer, box = self._section_frame(parent, 'MEDIA PROBE', 'ffprobe metadata, streams and quick inspection.')
        outer.pack(fill='both', expand=True)
        body = ogl_frame(box, bg=C['raised'])
        body.pack(fill='both', expand=True, padx=10, pady=10)
        self.probe_text = self._text(body, height=8)
        scroll = tk.Scrollbar(body, command=self.probe_text.yview)
        self.probe_text.configure(yscrollcommand=scroll.set)
        self.probe_text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

    def _section_convert(self, parent):
        outer, box = self._section_frame(parent, 'CONVERSION', 'Build archival outputs while preserving originals.')
        outer.pack(fill='both', expand=False)
        pad = 12
        row1 = ogl_frame(box, bg=C['raised'])
        row1.pack(fill='x', padx=pad, pady=(12, 8))
        profile_heading = ogl_frame(row1, bg=C['raised'])
        profile_heading.pack(fill='x')
        self._label(profile_heading, 'PROFILE', 11, 'text_3', bold=True).pack(side='left')
        self._button(profile_heading, 'USE FAST PROFILE', self.select_fast_profile).pack(side='right')
        self.profile_menu = tk.OptionMenu(row1, self.profile, *PROFILE_ORDER, command=lambda *_: self._save_state())
        self.profile_menu.config(relief='flat', bd=0, font=(FAMILY, 10), bg=C['control'], fg=C['text'], activebackground=C['hover'], activeforeground=C['text'])
        self.profile_menu['menu'].config(font=(FAMILY, 10), bg=C['control'], fg=C['text'])
        self.profile_menu.pack(fill='x', pady=(4, 0))
        self.profile_desc = self._label(row1, '', 10, 'text_3')
        self.profile_desc.pack(anchor='w', pady=(6, 0))

        row2 = ogl_frame(box, bg=C['raised'])
        row2.pack(fill='x', padx=pad, pady=(0, 8))
        self._label(row2, 'AUDIO', 11, 'text_3', bold=True).pack(anchor='w')
        audio_menu = tk.OptionMenu(row2, self.audio_mode, 'copy', 'opus', command=lambda *_: self._save_state())
        audio_menu.config(relief='flat', bd=0, font=(FAMILY, 10), bg=C['control'], fg=C['text'], activebackground=C['hover'], activeforeground=C['text'])
        audio_menu['menu'].config(font=(FAMILY, 10), bg=C['control'], fg=C['text'])
        audio_menu.pack(fill='x', pady=(4, 0))
        self._label(row2, 'Copy audio by default; optional Opus transcode.', 10, 'text_3').pack(anchor='w', pady=(4, 0))

        row3 = ogl_frame(box, bg=C['raised'])
        row3.pack(fill='x', padx=pad, pady=(0, 8))
        self._label(row3, 'OUTPUT FOLDER', 11, 'text_3', bold=True).pack(anchor='w')
        line = ogl_frame(row3, bg=C['raised'])
        line.pack(fill='x', pady=(4, 0))
        self.output_var = tk.StringVar(value=self.output_dir)
        ent = self._entry(line, self.output_var)
        ent.pack(side='left', fill='x', expand=True)
        self._button(line, 'CHOOSE', self.choose_output).pack(side='left', padx=(8, 0))

        naming = ogl_frame(box, bg=C['raised'])
        naming.pack(fill='x', padx=pad, pady=(0, 8))
        self._label(naming, 'ORGANISE OUTPUT FILENAME', 11, 'text_3', bold=True).pack(anchor='w')
        mode_menu = tk.OptionMenu(naming, self.rename_mode, *NAME_MODES, command=lambda *_: self._save_state())
        mode_menu.config(relief='flat', bd=0, font=(FAMILY, 10), bg=C['control'], fg=C['text'],
                         activebackground=C['hover'], activeforeground=C['text'])
        mode_menu['menu'].config(font=(FAMILY, 10), bg=C['control'], fg=C['text'])
        mode_menu.pack(fill='x', pady=(3, 3))
        self._label(naming, 'TITLE OVERRIDE (OPTIONAL)', 10, 'text_3').pack(anchor='w')
        title_input = self._entry(naming, self.title_override)
        title_input.pack(fill='x', pady=(3, 5))
        ep_row = ogl_frame(naming, bg=C['raised'])
        ep_row.pack(fill='x')
        for label, variable in (('SEASON', self.season_override), ('EPISODE', self.episode_override)):
            item = ogl_frame(ep_row, bg=C['raised'])
            item.pack(side='left', fill='x', expand=True, padx=(0, 10))
            self._label(item, label, 10, 'text_3').pack(anchor='w')
            self._entry(item, variable).pack(fill='x', pady=(2, 0))
        self._label(naming, 'Season/episode overrides apply to one selected file only.', 10, 'text_3').pack(anchor='w', pady=(3, 2))
        self.name_preview = self._label(naming, 'OUTPUT: Select a source file to preview its name.', 10, 'text_3')
        self.name_preview.pack(anchor='w', fill='x', pady=(0, 2))
        self._update_name_preview()

        row4 = ogl_frame(box, bg=C['raised'])
        row4.pack(fill='x', padx=pad, pady=(0, 12))
        self._button(row4, 'QUEUE SELECTED', self.queue_selected, primary=True).pack(side='left')
        self._button(row4, 'START QUEUE', self.start_queue).pack(side='left', padx=(8, 0))
        self._button(row4, 'CANCEL JOB', self.cancel_current).pack(side='left', padx=(8, 0))
        self._update_profile_desc()

    def _section_queue(self, parent):
        tools = ogl_frame(parent, bg=C['canvas'])
        tools.pack(fill='x', pady=(0, 10))
        self._button(tools, 'START QUEUE', self.start_queue, primary=True).pack(side='left')
        self._button(tools, 'CANCEL CURRENT', self.cancel_current).pack(side='left', padx=(7, 0))
        self._button(tools, 'RETRY FAILED', self.retry_failed).pack(side='left', padx=(7, 0))
        self._button(tools, 'CLEAR FINISHED', self.clear_finished).pack(side='left', padx=(7, 0))
        outer, box = self._section_frame(parent, 'ENCODE JOBS', 'Queued / converting / completed / failed.')
        outer.pack(fill='both', expand=True)
        self.queue_list = tk.Listbox(box, activestyle='none', bg=C['canvas'], fg=C['text'], bd=0,
                                     highlightthickness=1, highlightbackground=C['control_line'],
                                     selectbackground=C['hover'], selectforeground=C['text_bright'],
                                     font=(FAMILY, 11), height=11)
        self.queue_list.pack(fill='both', expand=True, padx=12, pady=12)
        outer2, logbox = self._section_frame(parent, 'CONVERSION LOG', 'FFmpeg output and job diagnostics.')
        outer2.pack(fill='both', expand=True)
        self.log_text = self._text(logbox, height=12)
        self.log_text.pack(fill='both', expand=True, padx=12, pady=12)

    def retry_failed(self):
        for job in self.queue_items:
            if job['status'] in ('failed', 'cancelled'):
                job['status'] = 'queued'
                job['progress'] = ''
        self._refresh_queue()
        self._set_status('Failed and cancelled jobs returned to queue.')

    def clear_finished(self):
        self.queue_items = [j for j in self.queue_items if j['status'] not in ('completed', 'cancelled', 'failed')]
        self._refresh_queue()
        self._set_status('Finished jobs cleared; pending and active jobs preserved.')

    def _section_about(self, parent):
        outer, box = self._section_frame(parent, 'ABOUT EIDOLITH',
                                        'Local-first video playback and archival conversion.')
        outer.pack(fill='both', expand=True)
        about = self._text(box, height=16)
        about.pack(fill='both', expand=True, padx=14, pady=14)
        about.insert('1.0',
                     'EIDOLITH 0.3 — LOCAL VIDEO WORKSPACE\n\n'
                     'PLAYER\n'
                     '• Play video inside the Marble Oracle EIDOLITH tab.\n'
                     '• Play / Pause / Stop, seek, ±10 seconds, audio volume.\n'
                     '• FULLSCREEN is optional and only opens when requested.\n'
                     '• FFmpeg decodes frames into Tk; FFplay supplies audio without a video window.\n'
                     '• This basic preview backend is not frame-accurate and does not guarantee HDR or A/V sync.\n\n'
                     'CONVERTER\n'
                     '• AV1/SVT-AV1, NVIDIA NVENC (when supported), fast CPU AVC, HEVC and remux profiles.\n• Standard file naming: Show - S01E02 - Episode [AV1].mkv or Film (2024) [AV1].mkv.\n'
                     '• Keep original source files; no automatic deletion.\n'
                     '• All conversion uses your local FFmpeg tools.\n\n'
                     'QUEUE\n'
                     '• Serial jobs, percent, processing speed, ETA, cancel, retry and logs.\n• Convert to temporary files; verify streams then publish without overwriting.\n'
                     '• Advanced metadata/HDR/track validation and resumable job history remain future work.\n\n'
                     'PRIVACY\n'
                     '• No cloud, accounts or telemetry.\n'
                     '• FFmpeg/FFprobe/FFplay must be installed and are not bundled here.\n'
                     '• Full conversion tests on physical Windows/Linux Mint machines are still needed.')
        about.config(state='disabled')

    # ---------- navigation ----------
    def _set_nav(self, name):
        if name not in NAV_ITEMS:
            return
        self.active_nav.set(name)
        self._show_page(name)
        self._refresh_nav()

    def _refresh_nav(self):
        subtitles = {
            'PLAYER': 'Inspect, play, queue and convert local video files.',
            'CONVERT': 'Choose archival profiles and build safe queued conversions.',
            'QUEUE': 'Review jobs, logs and output status.',
            'ABOUT': 'Read the design intent, tool availability and scope.'
        }
        for name, btn in self.nav_buttons.items():
            on = name == self.active_nav.get()
            btn.configure(bg=C['hover'] if on else C['sidebar'], fg=C['text_bright'] if on else C['text'],
                          highlightbackground=C['accent'] if on else C['sidebar'])
        self.page_title.configure(text=self.active_nav.get())
        self.page_subtitle.configure(text=subtitles.get(self.active_nav.get(), ''))

    # ---------- source files ----------
    def _load_files(self):
        self.file_list.delete(0, 'end')
        if hasattr(self, 'convert_list'):
            self.convert_list.delete(0, 'end')
        clean = []
        for p in self.files:
            if p and os.path.exists(p):
                clean.append(p)
                self.file_list.insert('end', p)
                if hasattr(self, 'convert_list'):
                    self.convert_list.insert('end', p)
        self.files = clean
        if clean:
            # A newly imported file is immediately ready for PLAY / PROBE;
            # SELECT ALL remains available for batch jobs.
            self.file_list.selection_set(0)
            if hasattr(self, 'convert_list'):
                self.convert_list.selection_set(0)
        self._save_state()
        self._update_name_preview()

    def _save_state(self):
        self.output_dir = self.output_var.get().strip() if hasattr(self, 'output_var') else self.output_dir
        save_json('eidolith_state.json', {
            'files': self.files,
            'output_dir': self.output_dir,
            'profile': self.profile.get(),
            'audio_mode': self.audio_mode.get(),
            'rename_mode': self.rename_mode.get(),
            'title_override': self.title_override.get(),
            'season_override': self.season_override.get(),
            'episode_override': self.episode_override.get(),
        })

    def open_files(self):
        paths = filedialog.askopenfilenames(title='Open video files',
                                            filetypes=[('Video files', '*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.mts *.flv'), ('All files', '*.*')])
        if not paths:
            return
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._load_files()
        self._set_status(f'Added {len(paths)} file(s).')

    def add_folder(self):
        folder = filedialog.askdirectory(title='Add folder')
        if not folder:
            return
        count = 0
        exts = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.ts', '.mts', '.flv'}
        for base, _, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in exts:
                    path = os.path.join(base, name)
                    if path not in self.files:
                        self.files.append(path)
                        count += 1
        self._load_files()
        self._set_status(f'Indexed {count} file(s) from folder.')

    def remove_selected(self):
        sel = list(self._current_listbox().curselection())
        if not sel:
            return
        for idx in reversed(sel):
            try:
                self.files.pop(idx)
            except Exception:
                pass
        self._load_files()
        self._set_status('Removed selected file(s).')

    def clear_files(self):
        self.files = []
        self._load_files()
        self.probe_text.delete('1.0', 'end')
        self._set_status('Cleared source list.')

    def selected_files(self):
        lb = self._current_listbox()
        return [self.files[i] for i in lb.curselection() if 0 <= i < len(self.files)]

    # ---------- probe / player ----------
    def _probe_selected(self):
        chosen = self.selected_files()
        if not chosen:
            self._set_probe('No media file selected.')
            return
        path = chosen[0]
        if getattr(self, 'video', None) is not None and self.video.path != path:
            self.video.load(path)
        if not self.ffprobe:
            self._set_probe('ffprobe is not available. Install FFmpeg to inspect media properties.')
            return
        try:
            cmd = [self.ffprobe, '-v', 'error', '-show_format', '-show_streams', '-print_format', 'json', path]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True,
                                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            data = json.loads(out)
            if getattr(self, 'video', None) is not None and self.video.path == path:
                self.video.duration = float(data.get('format', {}).get('duration', 0) or 0)
                self.video._update_time()
            lines = []
            fmt = data.get('format', {})
            lines.append(f'File: {os.path.basename(path)}')
            lines.append(f'Path: {path}')
            if fmt:
                dur = float(fmt.get('duration', 0) or 0)
                size = int(fmt.get('size', 0) or 0)
                br = fmt.get('bit_rate', 'n/a')
                lines.append(f'Duration: {dur/60:.2f} min')
                lines.append(f'Size: {size/1048576:.2f} MiB')
                lines.append(f'Container: {fmt.get("format_long_name", fmt.get("format_name", "n/a"))}')
                lines.append(f'Bitrate: {br}')
            lines.append('')
            for i, s in enumerate(data.get('streams', [])):
                typ = s.get('codec_type', 'stream').upper()
                codec = s.get('codec_name', 'unknown')
                lines.append(f'{typ} {i}: {codec}')
                if s.get('codec_type') == 'video':
                    wh = f"{s.get('width','?')}x{s.get('height','?')}"
                    lines.append(f'  Resolution: {wh} · pix_fmt {s.get("pix_fmt", "n/a")} · {s.get("r_frame_rate", "n/a")} fps')
                    if s.get('color_primaries'):
                        lines.append(f'  Colour: {s.get("color_primaries")} / {s.get("color_transfer", "n/a")} / {s.get("color_space", "n/a")}')
                elif s.get('codec_type') == 'audio':
                    lines.append(f'  Channels: {s.get("channels", "?")} · sample_rate {s.get("sample_rate", "n/a")}')
                elif s.get('codec_type') == 'subtitle':
                    lines.append(f'  Language: {s.get("tags", {}).get("language", "und")}')
                if s.get('tags', {}).get('title'):
                    lines.append(f'  Title: {s.get("tags", {}).get("title")}')
                lines.append('')
            self._set_probe('\n'.join(lines).strip())
            self._set_status('Probe complete.')
        except Exception as e:
            self._set_probe(f'Probe failed:\n{e}')
            self._set_status('Probe failed.')

    def _set_probe(self, text):
        self.probe_text.delete('1.0', 'end')
        self.probe_text.insert('1.0', text)

    def play_selected(self):
        chosen = self.selected_files()
        if not chosen:
            self._set_status('Choose a file to play in the viewer, or use SELECT ALL for batch conversion.')
            return
        path = chosen[0]
        if self.video.path != path:
            self.video.load(path)
            self._probe_selected()
        self._set_nav('PLAYER')
        self.video.play()
        self._set_status(f'Playing {os.path.basename(path)} inside EIDOLITH. FULLSCREEN is optional.')

    def stop_playback(self):
        if getattr(self, 'video', None) is not None:
            self.video.stop()

    # ---------- conversion ----------
    def choose_output(self):
        folder = filedialog.askdirectory(title='Choose output folder')
        if folder:
            self.output_var.set(folder)
            self.output_dir = folder
            self._save_state()
            self._set_status('Updated output folder.')

    def select_fast_profile(self):
        # Prefer GPU AV1 only when a working NVIDIA driver is visible, not
        # merely because FFmpeg was compiled with an NVENC encoder.
        nvsmi = which('nvidia-smi')
        usable_gpu = False
        if nvsmi:
            try:
                result = subprocess.run([nvsmi, '-L'], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, timeout=4,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                usable_gpu = result.returncode == 0 and 'GPU' in result.stdout
            except (OSError, subprocess.SubprocessError):
                pass
        if usable_gpu and 'av1_nvenc' in self.encoders:
            choice = 'NVIDIA AV1 (fast)'
        elif usable_gpu and 'hevc_nvenc' in self.encoders:
            choice = 'NVIDIA HEVC (fast)'
        elif 'libx264' in self.encoders:
            choice = 'Fast CPU H.264'
        elif 'libsvtav1' in self.encoders:
            choice = 'Faster CPU AV1'
        else:
            self._set_status('No fast encoder found in FFmpeg. Check codec support.')
            return
        self.profile.set(choice)
        self._update_profile_desc()
        self._update_name_preview()
        self._set_status('Fast profile selected: ' + choice + '. Quality/size may differ from CPU archival AV1.')

    def _update_profile_desc(self):
        prof = PROFILES.get(self.profile.get(), {})
        supported, note = profile_support(self.profile.get(), self.encoders)
        description = prof.get('desc', '')
        if not supported:
            description += '  · UNAVAILABLE: ' + note
        elif note:
            description += '  · ' + note
        self.profile_desc.configure(text=description, wraplength=450)

    def _update_name_preview(self):
        if not hasattr(self, 'name_preview') or not hasattr(self, 'convert_list'):
            return
        selected = list(self.convert_list.curselection())
        if not selected:
            self.name_preview.configure(text='OUTPUT: Select a source file to preview its name.')
            return
        src = self.files[selected[0]]
        single = len(selected) == 1
        try:
            name = output_name(src, self.profile.get(), self.rename_mode.get(),
                               self.title_override.get(),
                               self.season_override.get() if single else '',
                               self.episode_override.get() if single else '')
        except (ValueError, KeyError):
            name = '(invalid profile/name)'
        self.name_preview.configure(text='OUTPUT: ' + name, wraplength=440)

    def _make_output_path(self, src, profile_name, *, name_mode=None, title='', season='', episode=''):
        dest_dir = self.output_var.get().strip() or self.output_dir or os.path.join(os.path.dirname(src), 'Eidolith Outputs')
        os.makedirs(dest_dir, exist_ok=True)
        self.output_dir = dest_dir
        name = output_name(src, profile_name, name_mode or self.rename_mode.get(), title, season, episode)
        original_base, ext = os.path.splitext(name)
        path = os.path.join(dest_dir, name)
        n = 2
        taken = {os.path.normcase(os.path.abspath(j['dst'])) for j in self.queue_items}
        taken.add(os.path.normcase(os.path.abspath(src)))
        while os.path.exists(path) or os.path.normcase(os.path.abspath(path)) in taken:
            path = os.path.join(dest_dir, f'{original_base} ({n}){ext}')
            n += 1
        return path

    def _build_command(self, src, dst, profile_name, audio_mode='copy'):
        if not self.ffmpeg:
            raise RuntimeError('ffmpeg is not available')
        ok, reason = profile_support(profile_name, self.encoders)
        if not ok:
            raise RuntimeError(reason)
        cmd = [self.ffmpeg, '-hide_banner', '-nostdin', '-n', '-stats_period', '1',
               '-progress', 'pipe:1', '-nostats', '-i', src,
               '-map', '0:V:0', '-map', '0:a?', '-map', '0:s?']
        if PROFILES[profile_name]['container'] == 'mkv':
            cmd += ['-map', '0:t?']  # preserve subtitle-font attachments in Matroska
        cmd += ['-map_metadata', '0', '-map_chapters', '0']
        cmd.extend(encoding_args(profile_name, audio_mode))
        if PROFILES[profile_name]['container'] == 'mkv':
            cmd += ['-c:t', 'copy']
        cmd.append(dst)
        return cmd

    def _probe_duration(self, src):
        if not self.ffprobe:
            return 0.0
        try:
            out = subprocess.check_output([self.ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                                            '-of', 'default=noprint_wrappers=1:nokey=1', src],
                                           text=True, timeout=12,
                                           stderr=subprocess.DEVNULL,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return max(0.0, float(out.strip()))
        except (ValueError, OSError, subprocess.SubprocessError):
            return 0.0

    def _preflight_source(self, src, profile_name):
        if not self.ffprobe:
            raise RuntimeError('ffprobe is required before encoding to protect track and colour data')
        raw = subprocess.check_output([self.ffprobe, '-v', 'error', '-show_streams',
                                       '-of', 'json', src],
                                      text=True, timeout=20, stderr=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        streams = json.loads(raw).get('streams', [])
        if sum(x.get('codec_type') == 'video' and not x.get('disposition', {}).get('attached_pic')
               for x in streams) != 1:
            raise RuntimeError('Multiple/no video tracks detected; automatic mapping would be incomplete. Source unchanged.')
        if any(x.get('codec_type') == 'data' for x in streams):
            raise RuntimeError('Data streams detected; safe preservation is not configured. Source unchanged.')
        if PROFILES[profile_name]['container'] != 'mkv' and any(x.get('codec_type') == 'attachment' for x in streams):
            raise RuntimeError('Attachments found; MP4 output may discard them. Use an MKV profile.')
        if PROFILES[profile_name]['codec'] != 'copy':
            for video in (x for x in streams if x.get('codec_type') == 'video'):
                if str(video.get('color_transfer', '')).lower() in ('smpte2084', 'arib-std-b67'):
                    raise RuntimeError('HDR source detected: accurate HDR re-encoding is not yet verified. Use Lossless remux or an HDR-aware workflow.')
                if any('dolby vision' in str(v).lower() or 'dovi' in str(v).lower()
                       for d in video.get('side_data_list', []) for v in d.values()):
                    raise RuntimeError('Dolby Vision metadata detected; conversion blocked to avoid silent metadata loss.')

    def _validate_output(self, src, dst):
        if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
            raise RuntimeError('Output file is empty or missing')
        if not self.ffprobe:
            raise RuntimeError('Cannot verify output without ffprobe')
        def probe(path):
            result = subprocess.check_output([self.ffprobe, '-v', 'error', '-show_streams',
                                              '-show_format', '-print_format', 'json', path],
                                             text=True, timeout=30, stderr=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return json.loads(result)
        original, output = probe(src), probe(dst)
        def count(data, kind):
            return sum(s.get('codec_type') == kind for s in data.get('streams', []))
        for kind in ('video', 'audio', 'subtitle', 'attachment'):
            if count(output, kind) != count(original, kind):
                raise RuntimeError(f'{kind} stream count changed ({count(original,kind)} -> {count(output,kind)})')
        a = float(original.get('format', {}).get('duration', 0) or 0)
        b = float(output.get('format', {}).get('duration', 0) or 0)
        if a > 0 and abs(a-b) > max(1.5, a*0.01):
            raise RuntimeError(f'Output duration changed unexpectedly ({a:.1f}s -> {b:.1f}s)')
        return 100.0 * (1 - os.path.getsize(dst) / os.path.getsize(src)) if os.path.getsize(src) else 0.0

    def queue_selected(self):
        files = self.selected_files()
        if not files:
            self._set_status('Select one or more source files to queue.')
            return
        profile_name = self.profile.get()
        supported, reason = profile_support(profile_name, self.encoders)
        if not supported:
            self._set_status('Encoder unavailable: ' + reason)
            messagebox.showerror('EIDOLITH: Encoder missing', reason, parent=self)
            return
        single = len(files) == 1
        for src in files:
            job = {
                'id': self.queue_seq, 'src': src,
                'dst': self._make_output_path(src, profile_name,
                                              name_mode=self.rename_mode.get(),
                                              title=self.title_override.get(),
                                              season=self.season_override.get() if single else '',
                                              episode=self.episode_override.get() if single else ''),
                'profile': profile_name, 'audio_mode': self.audio_mode.get(),
                'status': 'queued', 'progress': '', 'duration': 0.0,
            }
            self.queue_seq += 1
            self.queue_items.append(job)
        self._refresh_queue()
        self._set_nav('QUEUE')
        self._set_status(f'Queued {len(files)} file(s) with standard names. Use FAST PROFILE for shorter encoding time.')
        self._save_state()

    def _refresh_queue(self):
        self.queue_list.delete(0, 'end')
        for job in self.queue_items:
            line = f"[{job['status'].upper():9}] {os.path.basename(job['src'])} → {os.path.basename(job['dst'])}"
            if job.get('progress'):
                line += f" · {job['progress']}"
            self.queue_list.insert('end', line)

    def _append_log(self, text):
        stamp = time.strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{stamp}] {text}\n')
        if int(self.log_text.index('end-1c').split('.')[0]) > 300:
            self.log_text.delete('1.0', '70.0')
        self.log_text.see('end')

    def start_queue(self):
        self._update_profile_desc()
        if self.worker_thread and self.worker_thread.is_alive():
            self._set_status('Queue already running.')
            return
        pending = [j for j in self.queue_items if j['status'] in ('queued', 'failed', 'cancelled')]
        if not pending:
            self._set_status('No queued jobs to start.')
            return
        self.worker_stop.clear()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self._set_status('Queue started.')

    def cancel_current(self):
        self.worker_stop.set()
        proc = self.active_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self._set_status('Cancellation requested.')

    def _worker(self):
        for job in self.queue_items:
            if self.worker_stop.is_set():
                break
            if job['status'] not in ('queued', 'failed', 'cancelled'):
                continue
            temp_path = None
            try:
                if not os.path.isfile(job['src']):
                    raise FileNotFoundError('Source is missing: ' + job['src'])
                if os.path.exists(job['dst']):
                    raise FileExistsError('Output name already exists; originals and existing outputs are never overwritten')
                job['status'] = 'analyzing'
                job['progress'] = 'probing duration'
                self.uiq.put(('refresh', None))
                job['duration'] = self._probe_duration(job['src'])
                self._preflight_source(job['src'], job['profile'])
                stem, ext = os.path.splitext(job['dst'])
                temp_path = f'{stem}.eidolith-{uuid.uuid4().hex[:12]}-part{ext}'
                cmd = self._build_command(job['src'], temp_path, job['profile'], job.get('audio_mode', 'copy'))
                self.uiq.put(('log', 'SOURCE: ' + job['src']))
                self.uiq.put(('log', 'OUTPUT: ' + job['dst']))
                self.uiq.put(('log', 'FFmpeg: ' + subprocess.list2cmdline(cmd)))
                if job['profile'] == 'Balanced archive (default)':
                    self.uiq.put(('log', 'NOTE: CPU 10-bit SVT-AV1 preset 5 may be slower than real time. Pick NVIDIA AV1/HEVC if supported, or Faster CPU AV1.'))
                job['status'] = 'converting'
                job['progress'] = '0% · preparing'
                self.uiq.put(('refresh', None))
                self.active_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                    text=True, errors='replace', bufsize=1,
                                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                current = {}
                for raw in self.active_proc.stdout:
                    if self.worker_stop.is_set():
                        break
                    line = raw.strip()
                    if '=' in line:
                        key, val = line.split('=', 1)
                        if key in ('frame', 'fps', 'stream_0_0_q', 'bitrate', 'total_size',
                                   'out_time_us', 'out_time_ms', 'out_time', 'dup_frames',
                                   'drop_frames', 'speed', 'progress'):
                            current[key] = val
                            if key == 'progress':
                                job['progress'] = progress_label(current, job['duration'])
                                self.uiq.put(('refresh', None))
                                if job['duration'] > 0:
                                    self.uiq.put(('status', f'{os.path.basename(job["src"])} — {job["progress"]}'))
                                current = {}
                            continue
                    if line:
                        self.uiq.put(('log', line))
                if self.worker_stop.is_set() and self.active_proc.poll() is None:
                    self.active_proc.terminate()
                rc = self.active_proc.wait(timeout=20)
                if self.worker_stop.is_set():
                    job['status'], job['progress'] = 'cancelled', 'cancelled — original unchanged'
                elif rc:
                    raise RuntimeError('FFmpeg exited with status ' + str(rc) + ' (see log)')
                else:
                    job['status'], job['progress'] = 'validating', 'checking output streams'
                    self.uiq.put(('refresh', None))
                    savings = self._validate_output(job['src'], temp_path)
                    if os.path.exists(job['dst']):
                        raise FileExistsError('Output destination became occupied during conversion')
                    # Same-directory hard link is atomic and will not overwrite;
                    # delete only the temporary output created by this job.
                    try:
                        os.link(temp_path, job['dst'])
                        os.unlink(temp_path)
                    except OSError as hardlink_error:
                        # exFAT and some Windows filesystems cannot hardlink.
                        # Claim the destination with O_EXCL, then atomically
                        # replace our own empty placeholder, never someone
                        # else's existing output.
                        if os.path.exists(job['dst']):
                            raise FileExistsError('Output destination already exists') from hardlink_error
                        fd = os.open(job['dst'], os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                        os.close(fd)
                        try:
                            os.replace(temp_path, job['dst'])
                        except OSError:
                            # Only remove our empty placeholder; never touch
                            # a non-empty file someone may have created.
                            if os.path.exists(job['dst']) and os.path.getsize(job['dst']) == 0:
                                os.unlink(job['dst'])
                            raise
                    temp_path = None
                    job['status'] = 'completed'
                    job['progress'] = f'finished · {savings:+.1f}% storage saved'
                    self.uiq.put(('log', f'COMPLETED: {job["dst"]} · storage saved: {savings:+.1f}%'))
                self.uiq.put(('refresh', None))
            except Exception as err:
                job['status'] = 'cancelled' if self.worker_stop.is_set() else 'failed'
                job['progress'] = str(err)[:125]
                self.uiq.put(('log', f'{job["status"].upper()}: {job["src"]} — {err} (original retained)'))
                self.uiq.put(('refresh', None))
            finally:
                proc = self.active_proc
                if proc is not None:
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait(timeout=8)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                self.active_proc = None
                if temp_path and os.path.isfile(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        self.uiq.put(('log', 'WARNING: Partial output could not be removed: ' + temp_path))
        self.uiq.put(('status', 'Queue idle. All originals retained.'))

    # ---------- UI queue ----------
    def _schedule_ui_queue(self):
        try:
            while True:
                kind, payload = self.uiq.get_nowait()
                if kind == 'refresh':
                    self._refresh_queue()
                elif kind == 'log':
                    self._append_log(payload)
                elif kind == 'status':
                    self._set_status(payload)
        except queue.Empty:
            pass
        self._update_profile_desc()
        self._after_id = self.after(180, self._schedule_ui_queue)

    def _set_status(self, text):
        self.status_var.set(text)
        self._sync_status()

    def _sync_status(self):
        self.status_label.configure(text=self.status_var.get())

    # ---------- lifecycle ----------
    def resume_panel(self):
        self.after_idle(lambda: self.file_list.focus_set())

    def suspend(self):
        self.video.suspend()

    def shutdown(self):
        # Return False while a conversion is active: the host uses this to
        # protect in-progress work.
        running = bool(self.worker_thread and self.worker_thread.is_alive())
        if running:
            return False
        self.stop_playback()
        self.video.destroy()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._save_state()
        return True


class EmbeddedEidolith:
    def __init__(self, canvas, on_home):
        self.canvas = canvas
        self.frame = EidolithPanel(canvas, on_home=on_home)
        self.window = canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                           tags=('eidowin', 'eidolith-tab'))
        self._box = None

    def layout(self, box):
        self._box = box
        x0, y0, x1, y1 = box
        if not self.canvas.type(self.window):
            self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                                    tags=('eidowin', 'eidolith-tab'))
        self.canvas.coords(self.window, x0, y0)
        self.canvas.itemconfigure(self.window, width=max(100, x1-x0), height=max(100, y1-y0), state='normal')
        self.canvas.tag_raise(self.window)
        self.frame.resume_panel()

    def clear(self):
        self.frame.suspend()
        if self.canvas.type(self.window):
            self.canvas.itemconfigure(self.window, state='hidden')

    def shutdown(self):
        return self.frame.shutdown()

    def key(self, keysym, char=''):
        key = keysym.lower()
        if key in ('escape', 'esc'):
            if self.frame.video._fullscreen is not None:
                self.frame.video.close_fullscreen()
                return None
            return 'close'
        try:
            focus = self.frame.focus_get()
        except tk.TclError:
            focus = None
        if isinstance(focus, (tk.Entry, tk.Text)):
            return None
        if key == 'space':
            self.frame.video.toggle_pause()
        elif key == 'left':
            self.frame.video.seek(self.frame.video.position - 10)
        elif key == 'right':
            self.frame.video.seek(self.frame.video.position + 10)
        elif key == 'f' and self.frame.active_nav.get() == 'PLAYER':
            self.frame.video.open_fullscreen()
        return None
