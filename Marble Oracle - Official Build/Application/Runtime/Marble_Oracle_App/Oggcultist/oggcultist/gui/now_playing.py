"""The persistent now-playing bar: cover, title, transport, shuffle/repeat, seek and volume.

Split out of ``player_view.py`` in 2.0. Playback itself lives in ``PlayerController``.
"""
from __future__ import annotations

import io
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..player import Song, embedded_picture
from . import design_system as ds
from . import line_icons
from .player_view import click_to_set, duration_label, fit_text, shorten
from .theme import PALETTE

if TYPE_CHECKING:  # pragma: no cover
    from .app import OggcultistApp

# What the repeat button says beside its icon (nothing when repeat is off).
REPEAT_TEXT = {'off': '', 'all': 'All', 'album': 'Album', 'one': 'One'}


class NowPlayingBar(ttk.Frame):
    COVER = ds.COVER_SMALL

    def __init__(self, parent, app: 'OggcultistApp'):
        super().__init__(parent, style='Now.TFrame', padding=(ds.SPACE['xl'] - 4, ds.SPACE['m'], ds.SPACE['xl'] - 4, ds.SPACE['m']))
        self.app = app
        self.title_var = tk.StringVar(value='Nothing playing')
        self.detail_var = tk.StringVar(value='Double-click a song to play it')
        self.elapsed_var = tk.StringVar(value='0:00')
        self.total_var = tk.StringVar(value='0:00')
        self.seek_value = tk.DoubleVar(value=0)
        self.dragging = False
        self._photo = None

        # Three columns: song info | controls | volume. The two sides share one width
        # (uniform group), so the controls stay exactly centred whatever the song title is,
        # and the centre column has a fixed width so nothing in it moves.
        from .brand import _scale
        scale = _scale(self)
        # Both side frames request the same fixed size (their content never changes it), so
        # grid splits the space identically every time: not even a 1-pixel shift.
        side_height = round(self.COVER + 4 * scale)
        left = ttk.Frame(self, style='Now.TFrame', width=1, height=side_height)
        left.grid(row=0, column=0, sticky='ew')
        left.pack_propagate(False)
        self.cover = tk.Canvas(left, width=self.COVER, height=self.COVER, highlightthickness=0,
                               background=PALETTE['surface'])
        self.cover.pack(side='left', padx=(0, 14))
        info = ttk.Frame(left, style='Now.TFrame')
        info.pack(side='left')
        # v1.8.8: the labels show the text cut to the width that's really there, ending in "..."
        # (the side column is fixed, so a long name used to be clipped mid-letter).
        self._title_label = ttk.Label(info, style='NowTitle.TLabel')
        self._title_label.pack(anchor='w')
        self._detail_label = ttk.Label(info, style='NowMuted.TLabel')
        self._detail_label.pack(anchor='w', pady=(2, 0))
        self._info_left = left
        for var in (self.title_var, self.detail_var):
            var.trace_add('write', lambda *_: self._fit_info())
        left.bind('<Configure>', lambda _e: self._fit_info(), add='+')

        centre = ttk.Frame(self, style='Now.TFrame')
        centre.grid(row=0, column=1, sticky='ew', padx=14)
        buttons = ttk.Frame(centre, style='Now.TFrame')
        buttons.pack(fill='x')
        # play/pause in the middle column; equal-width groups either side keep it centred
        buttons.columnconfigure(0, weight=1, uniform='halves')
        buttons.columnconfigure(2, weight=1, uniform='halves')
        left_group = ttk.Frame(buttons, style='Now.TFrame')
        left_group.grid(row=0, column=0, sticky='e')
        right_group = ttk.Frame(buttons, style='Now.TFrame')
        right_group.grid(row=0, column=2, sticky='w')
        self.prev_btn = ttk.Button(left_group, text='⏮', style='Transport.TButton', command=app.player.previous)
        self.play_btn = ttk.Button(buttons, text='▶', style='Play.TButton', command=app.player.toggle)
        self.next_btn = ttk.Button(right_group, text='⏭', style='Transport.TButton', command=app.player.next)
        self.stop_btn = ttk.Button(right_group, text='■', style='Transport.TButton', command=app.player.stop)
        from .icons import transport_icons
        icons = transport_icons(self, round(20 * scale))
        if icons:
            for button, name in ((self.prev_btn, 'previous'), (self.next_btn, 'next'), (self.stop_btn, 'stop')):
                button.configure(image=icons[name], compound='image')
        self._icons = icons
        # Hold ⏭ to fast-forward through the song (audible); a quick click still skips.
        self._hold_job = None
        self._ramp_job = None
        self._held = False
        self.next_btn.bind('<ButtonPress-1>', self._next_press, add='+')
        self.next_btn.bind('<ButtonRelease-1>', self._next_release)
        # 2.0: shuffle and repeat are line icons (muted when off, amber when on); repeat adds its mode
        icon = round(20 * scale)
        self._mode_icons = {name: (line_icons.photo(self, name, icon, ds.COLOR['text_2']),
                                   line_icons.photo(self, name, icon, ds.COLOR['accent']))
                            for name in ('shuffle', 'repeat', 'repeat_one')}
        self.shuffle_btn = ttk.Button(left_group, text='Shuffle', command=app.player.toggle_shuffle)
        self.repeat_btn = ttk.Button(right_group, text='', command=app.player.cycle_repeat, width=0)
        self.shuffle_btn.pack(side='left', padx=(0, 12))
        self.prev_btn.pack(side='left', padx=(0, 6))
        self.play_btn.grid(row=0, column=1)
        self.next_btn.pack(side='left', padx=(6, 6))
        self.stop_btn.pack(side='left', padx=(0, 12))
        self.repeat_btn.pack(side='left')
        seekrow = ttk.Frame(centre, style='Now.TFrame')
        seekrow.pack(fill='x', pady=(6, 0))
        ttk.Label(seekrow, textvariable=self.elapsed_var, style='NowMuted.TLabel', width=6, anchor='e').pack(side='left')
        from .sliders import GradientSlider               # v1.9.0: modern rounded sliders
        self.seek = GradientSlider(seekrow, from_=0, to=1, variable=self.seek_value, behind=PALETTE['surface'])
        self.seek.pack(side='left', fill='x', expand=True, padx=8)
        click_to_set(self.seek, on_press=lambda: setattr(self, 'dragging', True),
                     on_drag=self._seek_preview, on_release=self._seek_release)
        ttk.Label(seekrow, textvariable=self.total_var, style='NowMuted.TLabel', width=6).pack(side='left')

        volume = ttk.Frame(self, style='Now.TFrame', width=1, height=side_height)
        volume.grid(row=0, column=2, sticky='ew')
        volume.pack_propagate(False)
        self.volume_slider = GradientSlider(volume, from_=0, to=100, length=round(130 * scale),
                                            variable=app.volume, behind=PALETTE['surface'])
        self.volume_slider.pack(side='right')
        self._volume_icon = line_icons.photo(self, 'volume', round(20 * scale), ds.COLOR['text_2'])
        ttk.Label(volume, text='Volume', style='NowMuted.TLabel',
                  **(dict(image=self._volume_icon, compound='image') if self._volume_icon else {})
                  ).pack(side='right', padx=(0, 8))
        # the volume follows the slider while it is dragged (changes are paced; see request_volume)
        click_to_set(self.volume_slider, on_drag=lambda: app.player.request_volume(int(app.volume.get())),
                     on_release=lambda: app.player.request_volume(int(app.volume.get())))
        self.columnconfigure(0, weight=1, uniform='side')
        self._scale = scale
        self.columnconfigure(1, minsize=round(525 * scale))
        self.columnconfigure(2, weight=1, uniform='side')
        self.bind('<Configure>', self._bar_resized, add='+')
        self.show(None)
        self.update_modes()

    def _bar_resized(self, event) -> None:
        if event.widget is not self:
            return
        compact = event.width < 1120
        new_width = round((420 if compact else 525) * self._scale)
        self.columnconfigure(1, minsize=new_width)
        self.volume_slider.configure(width=round((96 if compact else 130) * self._scale))
        # Keep centre transport controls centred while reclaiming room for song names.

    HOLD_MS = 350           # how long a press must last to count as holding
    RAMP_MS = 2000          # then speed up again after this long

    def _cancel_hold_jobs(self) -> None:
        for name in ('_hold_job', '_ramp_job'):
            job = getattr(self, name)
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
                setattr(self, name, None)

    def _next_press(self, _event=None) -> None:
        self._cancel_hold_jobs()
        self._held = False
        if str(self.next_btn.cget('state')) != 'disabled':
            self._hold_job = self.after(self.HOLD_MS, self._hold_started)

    def _hold_started(self) -> None:
        self._hold_job = None
        if self.app.player.start_fast_forward(0):
            self._held = True
            self._ramp_job = self.after(self.RAMP_MS, self._hold_ramp)

    def _hold_ramp(self) -> None:
        self._ramp_job = None
        if self._held:
            self.app.player.start_fast_forward(1)

    def _next_release(self, _event=None) -> str | None:
        self._cancel_hold_jobs()
        if not self._held:
            return None                 # a normal click: ttk runs the button's command (Next)
        self._held = False
        self.next_btn.state(['!pressed'])
        self.app.player.stop_fast_forward()
        return 'break'                  # don't also skip to the next song

    def update_modes(self) -> None:
        player = self.app.player
        on = bool(player.shuffle)
        self.shuffle_btn.configure(style='ModeOn.TButton' if on else 'Mode.TButton')
        if self._mode_icons['shuffle'][0]:
            self.shuffle_btn.configure(image=self._mode_icons['shuffle'][on], compound='image')
        repeat = player.repeat
        self.repeat_btn.configure(text=REPEAT_TEXT[repeat],
                                  style='Mode.TButton' if repeat == 'off' else 'ModeOn.TButton')
        icons = self._mode_icons['repeat_one' if repeat == 'one' else 'repeat']
        if icons[0]:
            self.repeat_btn.configure(image=icons[repeat != 'off'], compound='left' if REPEAT_TEXT[repeat] else 'image')

    def _seek_preview(self) -> None:
        self.elapsed_var.set(duration_label(self.seek_value.get()))

    def _seek_release(self) -> None:
        self.dragging = False
        self.app.player.seek(self.seek_value.get())

    def _draw_placeholder(self, letter: str = '♪') -> None:
        self.cover.delete('all')
        try:                      # v1.9.0: a rounded, bevelled tile like the rest of the interface
            from PIL import Image, ImageTk
            from .textures import rounded_picture
            tile = rounded_picture(Image.new('RGB', (self.COVER, self.COVER), PALETTE['accent_soft']), PALETTE['surface'])
            self._photo = ImageTk.PhotoImage(tile, master=self)
            self.cover.create_image(0, 0, image=self._photo, anchor='nw')
        except Exception:  # noqa: BLE001 - no Pillow: a flat square
            self.cover.configure(background=PALETTE['accent_soft'])
        self.cover.create_text(self.COVER // 2, self.COVER // 2, text=letter, fill=PALETTE['accent'], font='OgSymbol')

    def _draw_cover(self, song: Song) -> None:
        data = embedded_picture(song.path)
        if not data:
            self._draw_placeholder(song.title[:1].upper() or '♪')
            return
        try:
            from PIL import Image, ImageTk
            with Image.open(io.BytesIO(data)) as image:
                image = image.convert('RGB').resize((self.COVER, self.COVER), Image.LANCZOS)
                from .textures import rounded_picture
                self._photo = ImageTk.PhotoImage(rounded_picture(image, PALETTE['surface']), master=self)
            self.cover.delete('all')
            self.cover.create_image(0, 0, image=self._photo, anchor='nw')
        except Exception:
            self._draw_placeholder(song.title[:1].upper() or '♪')

    def _fit_info(self) -> None:
        """Put title and detail into their labels, shortened with "..." to the free width."""
        try:
            room = self._info_left.winfo_width() - self.COVER - 12 - 8
        except tk.TclError:
            return
        for label, var, font in ((self._title_label, self.title_var, 'OgNowTitle'),
                                 (self._detail_label, self.detail_var, 'OgBody')):
            label.configure(text=fit_text(var.get(), font, room, label))

    def show(self, song: Song | None) -> None:
        if song is None:
            self.title_var.set('Nothing playing')
            self.detail_var.set('Double-click a song to play it')
            self.elapsed_var.set('0:00')
            self.total_var.set('0:00')
            self.seek_value.set(0)
            self._photo = None
            self._draw_placeholder()
        else:
            self.title_var.set(shorten(song.title, 48))
            self.detail_var.set(shorten(f'{song.display_artist} · {song.album}', 60))
            self.total_var.set(duration_label(song.duration))
            self.seek.configure(to=max(song.duration, 1))
            self._draw_cover(song)
        self.update_play_state()

    def update_play_state(self) -> None:
        transport = self.app.player.transport
        playing = transport.playing
        self.play_btn.configure(text='⏸' if playing else '▶')
        if self._icons:
            self.play_btn.configure(image=self._icons['pause' if playing else 'play'], compound='image')

    def update_position(self) -> None:
        transport = self.app.player.transport
        if transport.song is None:
            return
        seconds = transport.current_position()
        self.elapsed_var.set(duration_label(seconds))
        if not self.dragging:
            self.seek_value.set(seconds)

    def notice(self, title: str, detail: str) -> None:
        self.title_var.set(title)
        self.detail_var.set(detail)
