"""EIDOLITH: local-first video player + archival converter tab for Marble Oracle.

This is a self-contained Tk panel that matches the other suite tabs closely.
Playback renders FFmpeg-decoded video inside the application, with an
explicit fullscreen option. Probing and conversion use ffprobe/ffmpeg locally.
The queue itself lives in oracle_eidolith_jobs.QueueRunner (serial,
fail-and-continue, cancellable, persisted, per-job logs) and keeps original
files intact.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from marble_uberata import FAMILY
from oracle_ogg_texture import frame as ogl_frame, label as ogl_label, install as ogl_install
from oggcultist_design_system import COLOR as C
from oracle_assets import load_json, save_json, state_dir
from oracle_eidolith_core import (PROFILES, PROFILE_ORDER, NAME_MODES, RESOLUTIONS, RESOLUTION_ORDER, output_name,
                                  detect_encoders, profile_support, seconds_label)
from oracle_eidolith_jobs import (QueueRunner, new_job, diagnostics_report, ACTIVE, RETRYABLE)

APP_NAME = "EIDOLITH"
APP_VERSION = "0.4"
QUEUE_STATE = 'eidolith_queue.json'
STALL_NOTICE_SECONDS = 30

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
        saved_res = self.state.get('resolution')
        # Short names by default: 'Mr. Robot (2015) - S01E01.mkv'.
        self.name_episode_title = tk.BooleanVar(value=bool(self.state.get('name_episode_title', False)))
        self.name_format_tag = tk.BooleanVar(value=bool(self.state.get('name_format_tag', False)))
        self.slim_output = tk.BooleanVar(value=bool(self.state.get('slim_output', True)))
        self.resolution = tk.StringVar(value=saved_res if saved_res in RESOLUTIONS else 'Original')
        self.active_nav = tk.StringVar(value='PLAYER')
        self.status_var = tk.StringVar(value='Ready. Import a local video file to inspect or convert.')
        self.play_proc = None
        self.uiq = queue.Queue()
        self._after_id = None
        self._profile_desc_text = None
        self._anim_phase = 0
        self.log_dir = os.path.join(state_dir(), 'eidolith_logs')
        self.runner = QueueRunner(self.ffmpeg, self.ffprobe, self.encoders, self.uiq,
                                  log_dir=self.log_dir, persist=self._persist_queue)
        saved_queue = load_json(QUEUE_STATE, {})
        restore_messages = self.runner.restore(saved_queue.get('jobs', []) if isinstance(saved_queue, dict) else [])
        self.queue_seq = self.runner.next_id()
        self._build_ui()
        self._load_files()
        self._refresh_queue()
        for message in restore_messages:
            self._append_log('RESTORE: ' + message)
        if self.runner.jobs:
            waiting = len(self.runner.pending())
            retry = sum(j['status'] in RETRYABLE for j in self.runner.jobs)
            self._append_log(f'Restored queue: {waiting} queued, {retry} failed/cancelled/interrupted. '
                             'Nothing starts until you press START QUEUE.')
        self._schedule_ui_queue()
        for var in (self.profile, self.rename_mode, self.title_override, self.season_override, self.episode_override,
                    self.resolution, self.name_episode_title, self.name_format_tag):
            var.trace_add('write', lambda *_: self._update_name_preview())
        self.profile.trace_add('write', lambda *_: self._update_profile_desc())
        self.after_idle(self._probe_selected)

    # ---------- queue engine bridge (names kept from 0.3 for compatibility) ----------
    @property
    def queue_items(self):
        return self.runner.jobs

    @property
    def worker_thread(self):
        return self.runner.thread

    @property
    def active_proc(self):
        return self.runner.active_proc

    def _persist_queue(self, jobs):
        save_json(QUEUE_STATE, {'version': 1, 'jobs': jobs})

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
        self._label(row2, 'RESOLUTION', 11, 'text_3', bold=True).pack(anchor='w', pady=(8, 0))
        res_menu = tk.OptionMenu(row2, self.resolution, *RESOLUTION_ORDER, command=lambda *_: self._save_state())
        res_menu.config(relief='flat', bd=0, font=(FAMILY, 10), bg=C['control'], fg=C['text'], activebackground=C['hover'], activeforeground=C['text'])
        res_menu['menu'].config(font=(FAMILY, 10), bg=C['control'], fg=C['text'])
        res_menu.pack(fill='x', pady=(4, 0))
        self._label(row2, 'Scale down only, keeping aspect ratio. From 1080p, 720p encodes about 2–3× faster (more for grainy video).',
                    10, 'text_3').pack(anchor='w', pady=(4, 0))
        tk.Checkbutton(row2, text='SLIM OUTPUT: video + main audio track only', variable=self.slim_output,
                       command=self._save_state, anchor='w', font=(FAMILY, 10, 'bold'), bg=C['raised'],
                       fg=C['text_2'], selectcolor=C['control'], activebackground=C['raised'],
                       activeforeground=C['text'], highlightthickness=0, bd=0).pack(anchor='w', fill='x', pady=(8, 0))
        self._label(row2, 'Drops extra audio tracks, subtitles, cover art, fonts, chapters and metadata. '
                          'Every drop is listed in the job log.', 10, 'text_3').pack(anchor='w', pady=(2, 0))

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
        for text, variable in (('Add episode title', self.name_episode_title),
                               ('Add format tag, e.g. [AV1 720p]', self.name_format_tag)):
            tk.Checkbutton(naming, text=text, variable=variable, command=self._save_state, anchor='w',
                           font=(FAMILY, 10), bg=C['raised'], fg=C['text_2'], selectcolor=C['control'],
                           activebackground=C['raised'], activeforeground=C['text'],
                           highlightthickness=0, bd=0).pack(anchor='w', fill='x')
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
        tools.pack(fill='x', pady=(0, 8))
        self._button(tools, 'START QUEUE', self.start_queue, primary=True).pack(side='left')
        self._button(tools, 'STOP QUEUE', self.stop_queue).pack(side='left', padx=(7, 0))
        self._button(tools, 'CANCEL CURRENT', self.cancel_current).pack(side='left', padx=(7, 0))
        self._button(tools, 'RETRY FAILED', self.retry_failed).pack(side='left', padx=(7, 0))
        self._button(tools, 'CLEAR FINISHED', self.clear_finished).pack(side='left', padx=(7, 0))

        # Current job: index/total, state, a real progress bar (or an
        # indeterminate sweep when duration is unknown), timings and the
        # last time FFmpeg reported anything.
        now = ogl_frame(parent, bg=C['raised'])
        now.pack(fill='x', pady=(0, 8))
        self.job_headline = self._label(now, 'NO ACTIVE JOB', 12, 'text_bright', bold=True, bg=C['raised'])
        self.job_headline.pack(anchor='w', padx=12, pady=(9, 3))
        self.progress_canvas = tk.Canvas(now, height=12, bg=C['sunken'], highlightthickness=1,
                                         highlightbackground=C['control_line'], bd=0)
        self.progress_canvas.pack(fill='x', padx=12)
        self.job_detail = self._label(now, 'Queue a file from CONVERT, then press START QUEUE.', 10, 'text_2',
                                      bg=C['raised'])
        self.job_detail.pack(anchor='w', fill='x', padx=12, pady=(4, 9))

        outer, box = self._section_frame(parent, 'ENCODE JOBS',
                                         'Queued / probing / converting / validating / completed / failed / cancelled.')
        outer.pack(fill='both', expand=True)
        self.queue_list = tk.Listbox(box, activestyle='none', bg=C['canvas'], fg=C['text'], bd=0,
                                     highlightthickness=1, highlightbackground=C['control_line'],
                                     selectbackground=C['hover'], selectforeground=C['text_bright'],
                                     exportselection=False, font=(FAMILY, 11), height=8)
        self.queue_list.pack(fill='both', expand=True, padx=12, pady=(12, 6))
        self.queue_list.bind('<<ListboxSelect>>', lambda e: self._update_progress_panel())
        logtools = ogl_frame(box, bg=C['raised'])
        logtools.pack(fill='x', padx=12, pady=(0, 10))
        self._button(logtools, 'OPEN LOG', self.open_job_log).pack(side='left')
        self._button(logtools, 'COPY DIAGNOSTICS', self.copy_diagnostics).pack(side='left', padx=(7, 0))
        self._button(logtools, 'LOG FOLDER', self.open_log_folder).pack(side='left', padx=(7, 0))
        self._button(logtools, 'RETRY SELECTED', self.retry_selected).pack(side='left', padx=(7, 0))

        outer2, logbox = self._section_frame(parent, 'CONVERSION LOG',
                                             'Recent events. Full FFmpeg output is kept in one log file per job.')
        outer2.pack(fill='both', expand=True)
        self.log_text = self._text(logbox, height=9)
        self.log_text.pack(fill='both', expand=True, padx=12, pady=12)

    def _selected_job(self):
        sel = self.queue_list.curselection() if hasattr(self, 'queue_list') else ()
        if sel and sel[0] < len(self.queue_items):
            return self.queue_items[sel[0]]
        if self.runner.current is not None:
            return self.runner.current
        finished = [j for j in self.queue_items if j.get('finished_at')]
        return max(finished, key=lambda j: j['finished_at']) if finished else None

    def _open_path(self, path):
        try:
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            return True
        except (OSError, AttributeError) as exc:
            self._set_status(f'Could not open {path}: {exc}')
            return False

    def open_job_log(self):
        job = self._selected_job()
        path = job.get('log_path') if job else ''
        if not path or not os.path.isfile(path):
            self._set_status('No log yet for this job; logs are written once a job starts. Folder: ' + self.log_dir)
            return
        if self._open_path(path):
            self._set_status('Opened log: ' + path)

    def open_log_folder(self):
        os.makedirs(self.log_dir, exist_ok=True)
        if self._open_path(self.log_dir):
            self._set_status('Log folder: ' + self.log_dir)

    def copy_diagnostics(self):
        job = self._selected_job()
        if not job:
            self._set_status('Select a job to copy its diagnostics.')
            return
        report = diagnostics_report(job)
        try:
            self.clipboard_clear()
            self.clipboard_append(report)
        except tk.TclError:
            pass
        self._append_log(f'Diagnostics for job {job["id"]} copied to clipboard (folders replaced by placeholders).')
        self._set_status('Diagnostics copied. Local folder names are replaced; the full log stays on this computer.')

    def retry_failed(self):
        count = self.runner.retry()
        self._set_status(f'{count} failed/cancelled/interrupted job(s) returned to queue. Press START QUEUE to run them.'
                         if count else 'No failed, cancelled or interrupted jobs to retry.')

    def retry_selected(self):
        job = self._selected_job()
        if not job or job['status'] not in RETRYABLE:
            self._set_status('Select a failed, cancelled or interrupted job to retry it.')
            return
        self.runner.retry(ids={job['id']})
        self._set_status(f'Job {job["id"]} returned to queue. Press START QUEUE to run it.')

    def clear_finished(self):
        removed = self.runner.clear_finished()
        self._set_status(f'Cleared {removed} finished job(s); queued and active jobs preserved.')

    def _section_about(self, parent):
        outer, box = self._section_frame(parent, 'ABOUT EIDOLITH',
                                        'Local-first video playback and archival conversion.')
        outer.pack(fill='both', expand=True)
        about = self._text(box, height=16)
        about.pack(fill='both', expand=True, padx=14, pady=14)
        about.insert('1.0',
                     f'EIDOLITH {APP_VERSION} — LOCAL VIDEO WORKSPACE\n\n'
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
                     '• Serial jobs in order; a failed job is marked FAILED and the queue continues.\n'
                     '• CANCEL CURRENT skips one job; STOP QUEUE leaves the remaining jobs queued.\n'
                     '• Job N of M, progress bar, elapsed time, speed, ETA and last FFmpeg activity.\n'
                     '• One full log per job (command, FFmpeg output, exit code, checks); OPEN LOG / COPY DIAGNOSTICS.\n'
                     '• Convert to temporary files; verify tracks, codec, bit depth and duration, then publish without overwriting.\n'
                     '• Cover art, subtitles and attachments are carried or reported; nothing is dropped silently.\n'
                     '• The queue is saved: after a restart, interrupted jobs are marked and their own partial files removed.\n'
                     '• HDR / Dolby Vision re-encoding and resuming a half-finished encode remain future work.\n\n'
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
            'resolution': self.resolution.get(),
            'name_episode_title': bool(self.name_episode_title.get()),
            'name_format_tag': bool(self.name_format_tag.get()),
            'slim_output': bool(self.slim_output.get()),
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
        if description != self._profile_desc_text:
            self._profile_desc_text = description
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
                               self.episode_override.get() if single else '',
                               self.resolution.get(), self.name_episode_title.get(), self.name_format_tag.get())
        except (ValueError, KeyError):
            name = '(invalid profile/name)'
        self.name_preview.configure(text='OUTPUT: ' + name, wraplength=440)

    def _make_output_path(self, src, profile_name, *, name_mode=None, title='', season='', episode=''):
        dest_dir = self.output_var.get().strip() or self.output_dir or os.path.join(os.path.dirname(src), 'Eidolith Outputs')
        os.makedirs(dest_dir, exist_ok=True)
        self.output_dir = dest_dir
        name = output_name(src, profile_name, name_mode or self.rename_mode.get(), title, season, episode,
                           self.resolution.get(), self.name_episode_title.get(), self.name_format_tag.get())
        original_base, ext = os.path.splitext(name)
        path = os.path.join(dest_dir, name)
        n = 2
        taken = {os.path.normcase(os.path.abspath(j['dst'])) for j in self.queue_items}
        taken.add(os.path.normcase(os.path.abspath(src)))
        while os.path.exists(path) or os.path.normcase(os.path.abspath(path)) in taken:
            path = os.path.join(dest_dir, f'{original_base} ({n}){ext}')
            n += 1
        return path

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
        if PROFILES[profile_name]['codec'] == 'copy' and RESOLUTIONS.get(self.resolution.get()):
            self._set_status(f'Lossless remux copies video unchanged and cannot resize to {self.resolution.get()}. '
                             'Choose an encoding profile, or set RESOLUTION to Original.')
            return
        single = len(files) == 1
        for src in files:
            dst = self._make_output_path(src, profile_name,
                                         name_mode=self.rename_mode.get(),
                                         title=self.title_override.get(),
                                         season=self.season_override.get() if single else '',
                                         episode=self.episode_override.get() if single else '')
            self.queue_seq = max(self.queue_seq, self.runner.next_id())
            self.runner.add(new_job(self.queue_seq, src, dst, profile_name, self.audio_mode.get(),
                                    self.resolution.get(), self.slim_output.get()))
            self.queue_seq += 1
        self._refresh_queue()
        self._set_nav('QUEUE')
        running = self.runner.running()
        self._set_status(f'Queued {len(files)} file(s) with standard names. '
                         + ('They will run after the current jobs.' if running else 'Press START QUEUE to begin.'))
        self._save_state()

    def _refresh_queue(self):
        if not hasattr(self, 'queue_list'):
            return
        selected = self.queue_list.curselection()
        top = self.queue_list.yview()[0] if self.queue_list.size() else 0.0
        self.queue_list.delete(0, 'end')
        total = len(self.queue_items)
        colours = {'completed': C['done'], 'failed': C['failed'], 'cancelled': C['skipped'],
                   'interrupted': C['review'], 'converting': C['accent'], 'probing': C['accent'],
                   'validating': C['accent']}
        for n, job in enumerate(list(self.queue_items), 1):
            line = (f"[{job['status'].upper():11}] {n}/{total}  {os.path.basename(job['src'])} "
                    f"→ {os.path.basename(job['dst'])}")
            if job.get('progress'):
                line += f" · {job['progress']}"
            self.queue_list.insert('end', line)
            if job['status'] in colours:
                self.queue_list.itemconfigure('end', foreground=colours[job['status']])
        for index in selected:
            if index < self.queue_list.size():
                self.queue_list.selection_set(index)
        self.queue_list.yview_moveto(top)
        self._update_progress_panel()

    def _update_progress_panel(self):
        if not hasattr(self, 'progress_canvas'):
            return
        job = self.runner.current
        if job is None:
            sel = self.queue_list.curselection()
            job = self.queue_items[sel[0]] if sel and sel[0] < len(self.queue_items) else self._selected_job()
        canvas = self.progress_canvas
        canvas.delete('all')
        width = max(10, canvas.winfo_width() - 2)
        height = max(6, int(canvas.cget('height')))
        if job is None:
            self.job_headline.configure(text='NO ACTIVE JOB')
            pending = len(self.runner.pending())
            self.job_detail.configure(text=(f'{pending} job(s) queued. Press START QUEUE.' if pending else
                                            'Queue a file from CONVERT, then press START QUEUE.'))
            return
        index, total = self.runner.position(job)
        status = job['status']
        self.job_headline.configure(
            text=f'JOB {index} OF {total} · {status.upper()} · {os.path.basename(job["src"])}')
        now = time.time()
        bits = []
        percent = job.get('percent')
        if status in ACTIVE:
            if percent is not None and status == 'converting':
                canvas.create_rectangle(1, 1, 1 + width * percent, height, fill=C['accent'], width=0)
                bits.append(f'{percent:.1%}')
            else:
                # Indeterminate: progress cannot be calculated, so show motion, not a number.
                seg = max(40, width // 6)
                x = (self._anim_phase * 9) % (width + seg) - seg
                canvas.create_rectangle(max(1, x), 1, min(width, x + seg), height, fill=C['accent_deep'], width=0)
                bits.append({'probing': 'probing tracks', 'validating': 'verifying output'}.get(status, 'progress unknown'))
            if status == 'converting' and job.get('duration'):
                bits.append(f'{seconds_label(job.get("out_seconds", 0))} / {seconds_label(job["duration"])} encoded')
            elif status == 'converting':
                bits.append(f'{seconds_label(job.get("out_seconds", 0))} encoded (duration unknown)')
            if job.get('started_at'):
                bits.append(f'elapsed {seconds_label(now - job["started_at"])}')
            if job.get('speed'):
                bits.append(f'speed {job["speed"]:.2f}x')
            if status == 'converting':
                bits.append(f'ETA {seconds_label(job["eta"])}' if job.get('eta') is not None else 'ETA estimating')
            last = job.get('last_activity')
            if last:
                quiet = now - last
                bits.append(f'last FFmpeg activity {seconds_label(quiet)} ago at {time.strftime("%H:%M:%S", time.localtime(last))}')
                advance = job.get('last_advance')
                if status == 'converting' and quiet > STALL_NOTICE_SECONDS:
                    bits.append(f'NO PROGRESS REPORT FOR {int(quiet)}s — FFmpeg (pid {job.get("pid")}) is still '
                                'running; check OPEN LOG before cancelling')
                elif status == 'converting' and advance and now - advance > STALL_NOTICE_SECONDS:
                    bits.append(f'FFmpeg alive but no new output for {int(now - advance)}s (slow encoder warming up?)')
        else:
            colour = {'completed': C['done'], 'failed': C['failed'], 'interrupted': C['review']}.get(status, C['skipped'])
            fill = 1.0 if status in ('completed', 'failed') else (percent or 0)
            if status != 'queued':
                canvas.create_rectangle(1, 1, 1 + width * fill, height, fill=colour, width=0)
            bits.append(job.get('error') or job.get('progress') or status)
            if job.get('started_at') and job.get('finished_at'):
                bits.append(f'took {seconds_label(job["finished_at"] - job["started_at"])}')
        self.job_detail.configure(text='  ·  '.join(str(b) for b in bits if b), wraplength=max(300, width))

    def _append_log(self, text):
        stamp = time.strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{stamp}] {text}\n')
        if int(self.log_text.index('end-1c').split('.')[0]) > 400:
            self.log_text.delete('1.0', '101.0')
        self.log_text.see('end')

    def start_queue(self):
        self._update_profile_desc()
        message = self.runner.start()
        self._set_status(message)
        self._refresh_queue()

    def cancel_current(self):
        self._set_status(self.runner.cancel_current())

    def stop_queue(self):
        self._set_status(self.runner.stop_queue())

    # ---------- UI queue ----------
    def _schedule_ui_queue(self):
        try:
            while True:
                kind, payload = self.uiq.get_nowait()
                if kind == 'refresh':
                    self._refresh_queue()
                elif kind == 'log':
                    self._append_log(payload)
                elif kind in ('status', 'done'):
                    self._set_status(payload)
                    if kind == 'done':
                        self._refresh_queue()
        except queue.Empty:
            pass
        self._anim_phase += 1
        if self.runner.current is not None:
            self._update_progress_panel()
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
        # Return False while a conversion is active and the user chooses to
        # keep it: the host uses this to protect in-progress work. 0.3 refused
        # silently, which looked like the window ignoring the close button.
        if self.runner.running():
            current = self.runner.current
            name = os.path.basename(current['src']) if current else 'a job'
            try:
                stop = messagebox.askyesno(
                    'EIDOLITH: conversion running',
                    f'EIDOLITH is converting {name} ({len(self.runner.pending())} more queued).\n\n'
                    'Stop the queue and close? The partial output is removed, the original is '
                    'unchanged, and queued jobs are kept for next time.', parent=self)
            except tk.TclError:
                stop = False
            if not stop:
                self._set_status('Close cancelled: conversion continues.')
                return False
            self.runner.stop_queue()
            deadline = time.monotonic() + 30
            while self.runner.running() and time.monotonic() < deadline:
                try:
                    self.update()
                except tk.TclError:
                    break
                time.sleep(0.05)
            if self.runner.running():
                self._set_status('FFmpeg is still stopping; try closing again in a moment.')
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
