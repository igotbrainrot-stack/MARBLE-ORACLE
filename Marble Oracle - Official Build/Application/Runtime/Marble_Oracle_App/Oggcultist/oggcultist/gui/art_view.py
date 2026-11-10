"""Album Art page: change the colour and text on the covers Oggcultist generated.

The checks and file updates live in ``converter.cover_editor`` (no Tk); this page is the
editor around them: album list, live preview, colour and text controls, and Apply.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk
from typing import TYPE_CHECKING

from ..converter.cover_editor import CoverDesign, CoverEditError, CoverEditor, EditableAlbum
from . import design_system as ds
from .theme import PALETTE
from .widgets import Swatch, TrackTable

if TYPE_CHECKING:  # pragma: no cover
    from .app import OggcultistApp

PREVIEW = 280
INK_CHOICES = ('Automatic (best contrast)', 'Black', 'White', 'Custom...')


class CoverArtPage(ttk.Frame):
    def __init__(self, parent, app: 'OggcultistApp'):
        super().__init__(parent, padding=ds.PAGE_PADDING)
        self.app = app
        self.editor: CoverEditor | None = None
        self.albums: list[EditableAlbum] = []
        self.current: EditableAlbum | None = None
        self.events: queue.Queue = queue.Queue()
        self.working = False
        self._preview_job = None
        self._photo = None
        self._preview_size = 158
        self._full_preview = None
        self._loading = False

        self.subtitle = tk.StringVar(value='')
        bar = ttk.Frame(self)
        bar.pack(fill='x', pady=(0, 12))
        ttk.Label(bar, text='Album Art', style='Title.TLabel').pack(anchor='w')
        self.subtitle_label = ttk.Label(bar, textvariable=self.subtitle, style='Muted.TLabel', wraplength=640)
        self.subtitle_label.pack(anchor='w', pady=(2, 0))

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, minsize=248)            # preserves usable space for the editor at 960 px
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        left = ttk.Frame(main, padding=(0, 0, 12, 0))
        left.grid(row=0, column=0, sticky='nsew')
        right_box = ttk.Frame(main)
        right_box.grid(row=0, column=1, sticky='nsew')
        right_box.rowconfigure(0, weight=1)
        right_box.columnconfigure(0, weight=1)
        self._editor_canvas = tk.Canvas(right_box, background=PALETTE['bg'],
                                        borderwidth=0, highlightthickness=0)
        self._editor_canvas.grid(row=0, column=0, sticky='nsew')
        self._editor_scroll = ttk.Scrollbar(right_box, orient='vertical', command=self._editor_canvas.yview)
        self._editor_scroll.grid(row=0, column=1, sticky='ns')
        self._editor_canvas.configure(yscrollcommand=self._editor_scroll.set)
        right = ttk.Frame(self._editor_canvas)
        self._editor_content = right
        self._editor_window = self._editor_canvas.create_window((0, 0), window=right, anchor='nw')
        right.bind('<Configure>', lambda _e: self._editor_canvas.configure(
            scrollregion=self._editor_canvas.bbox('all')), add='+')
        self._editor_canvas.bind('<Configure>', lambda e: self._editor_canvas.itemconfigure(
            self._editor_window, width=e.width), add='+')
        self.bind('<Configure>', self._art_resized, add='+')

        self.list_table = TrackTable(left, (('album', 'Album', 112, True, 'w'), ('artist', 'Artist', 74, True, 'w'),
                                            ('songs', '#', 44, False, 'e')),
                                     empty_text='No converted albums here yet.', style='List.Treeview')
        self.list_table.tree.configure(selectmode='browse')
        self.list_table.tree.bind('<<TreeviewSelect>>', lambda _e: self._select())
        self.list_table.pack(fill='both', expand=True)

        # ---------------------------------------------------------------- editor
        self.album_title = tk.StringVar(value='Choose an album on the left.')
        self.album_title_label = ttk.Label(right, textvariable=self.album_title, font='OgNowTitle')
        self.album_title_label.pack(anchor='w', pady=(2, 10))
        body = ttk.Frame(right)
        body.pack(fill='x')
        self.preview = tk.Label(body, background=PALETTE['bg'], width=self._preview_size, height=self._preview_size,
                                borderwidth=0, highlightthickness=0)
        self.preview.grid(row=0, column=0, sticky='nw', padx=(0, 12))
        self._photo = self._empty_preview()
        if self._photo is not None:
            self.preview.configure(image=self._photo, width=self._preview_size, height=self._preview_size)

        form = ttk.Frame(body)
        form.grid(row=0, column=1, sticky='nw')
        self._editor_form = form
        self._editor_body = body
        body.columnconfigure(1, weight=1)

        self.colour_var = tk.StringVar()
        self.ink_choice = tk.StringVar(value=INK_CHOICES[0])
        self.ink_custom = 'FFFFFF'
        self.line_vars = [tk.StringVar() for _ in range(3)]

        ttk.Label(form, text='Background colour', style='Section.TLabel').grid(row=0, column=0, columnspan=3, sticky='w')
        self.swatch = Swatch(form, command=self.choose_colour)          # v1.9.0: rounded swatch
        self.swatch.grid(row=1, column=0, sticky='w', pady=(4, 10))
        self.colour_entry = ttk.Entry(form, textvariable=self.colour_var, width=10)
        self.colour_entry.grid(row=1, column=1, sticky='w', padx=8, pady=(4, 10))
        self.random_btn = ttk.Button(form, text='Random', command=self.random_colour)
        self.random_btn.grid(row=1, column=2, sticky='w', pady=(4, 10))

        ttk.Label(form, text='Text', style='Section.TLabel').grid(row=2, column=0, columnspan=3, sticky='w')
        self.line_entries = []
        for i, (var, hint) in enumerate(zip(self.line_vars, ('Large', 'Medium', 'Small'))):
            entry = ttk.Entry(form, textvariable=var, width=21)
            entry.grid(row=3 + i, column=0, columnspan=3, sticky='we', pady=2)
            self.line_entries.append(entry)
        ttk.Label(form, text='Leave a line empty to leave it out.', style='Muted.TLabel').grid(
            row=6, column=0, columnspan=3, sticky='w', pady=(2, 8))
        self.default_text_btn = ttk.Button(form, text='Use album, artist and year', command=self.default_text)
        self.default_text_btn.grid(row=7, column=0, columnspan=3, sticky='w', pady=(0, 10))

        ttk.Label(form, text='Text colour', style='Section.TLabel').grid(row=8, column=0, columnspan=3, sticky='w')
        self.ink_box = ttk.Combobox(form, textvariable=self.ink_choice, values=INK_CHOICES, state='readonly', width=18)
        self.ink_box.grid(row=9, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.ink_box.bind('<<ComboboxSelected>>', lambda _e: self._ink_changed())
        self.ink_swatch = Swatch(form, command=self.choose_ink)
        self.ink_swatch.grid(row=9, column=2, sticky='w', pady=(4, 0))

        self.note = tk.StringVar(value='')
        self.note_label = ttk.Label(right, textvariable=self.note, style='Muted.TLabel', wraplength=560, justify='left')
        self.note_label.pack(anchor='w', pady=(12, 6))
        actions = ttk.Frame(right)
        actions.pack(anchor='w')
        self.apply_btn = ttk.Button(actions, text='Apply to album', style='Accent.TButton', command=self.apply)
        self.apply_btn.pack(side='left')
        self.revert_btn = ttk.Button(actions, text='Revert', command=self.revert)
        self.revert_btn.pack(side='left', padx=(8, 0))
        self.details = tk.StringVar(value='')
        ttk.Label(right, textvariable=self.details, style='Muted.TLabel', wraplength=560, justify='left').pack(
            anchor='w', pady=(10, 0))

        for var in (self.colour_var, *self.line_vars):
            var.trace_add('write', lambda *_: self._changed())
        self._set_controls('disabled')

    # ------------------------------------------------------------------ responsive editor layout
    def _art_resized(self, event) -> None:
        if event.widget is not self:
            return
        width = event.width
        size = 158 if width < 850 else (212 if width < 1230 else PREVIEW)
        if size != self._preview_size:
            self._preview_size = size
            if self.current is None:
                self._photo = self._empty_preview()
                self.preview.configure(image=self._photo or '', width=size, height=size)
            else:
                self._render_preview()
        if width < 850:
            self.preview.grid_configure(row=0, column=0, padx=0, pady=(0, 10))
            self._editor_form.grid_configure(row=1, column=0, sticky='nw')
        else:
            self.preview.grid_configure(row=0, column=0, padx=(0, 12), pady=0)
            self._editor_form.grid_configure(row=0, column=1, sticky='nw')
        self.subtitle_label.configure(wraplength=max(360, width - 35))
        self.album_title_label.configure(wraplength=max(190, int(width * .55) - 30))
        if getattr(self, 'note_label', None) is not None:
            self.note_label.configure(wraplength=max(225, int(width * .52) - 40))

    # ------------------------------------------------------------------ library
    def library_folder(self) -> Path | None:
        """The player library if it is an Oggcultist library, else the converter's destination."""
        candidates = [self.app.library_folder.get()]
        converter = getattr(self.app, 'converter', None)
        if converter is not None:
            candidates.append(converter.output_var.get())
        for value in candidates:
            if value and CoverEditor(Path(value)).available:
                return Path(value)
        return Path(candidates[0]) if candidates[0] else None

    def _empty_preview(self):
        """A rounded, sunken empty tile where the cover preview goes."""
        try:
            from PIL import ImageTk
            from . import textures
            tile = textures.surface((self._preview_size, self._preview_size), PALETTE['table'], PALETTE['table'], behind=PALETTE['bg'],
                                    radius=3, outline=PALETTE['border'], edge=0, amount=0.10, bevel=-0.22)
            return ImageTk.PhotoImage(tile, master=self)
        except Exception:  # noqa: BLE001
            return None

    def refresh(self) -> None:
        if self.working:
            return
        folder = self.library_folder()
        self.editor = CoverEditor(folder) if folder else None
        if self.editor is None or not self.editor.available:
            self.albums = []
            self.subtitle.set('Change the colour and text of the covers Oggcultist made. Choose a music folder '
                              'that the converter has written to.')
        else:
            try:
                self.albums = self.editor.albums()
            except Exception as exc:  # noqa: BLE001 - shown, never fatal
                self.albums = []
                self.app.notify(f'Could not read the album covers: {exc}')
            self.subtitle.set(f'Change the colour and text of the covers Oggcultist made  ·  {folder}')
        query = self.app.search_query()
        shown = [(i, a) for i, a in enumerate(self.albums)
                 if not query or query in a.label.casefold()]
        keep = self.current.folder_name if self.current else None
        self.list_table.set_rows((str(i), (a.album, a.artist, a.file_count), ()) for i, a in shown)
        match = next((str(i) for i, a in shown if a.folder_name == keep), None)
        if match:
            self.list_table.tree.selection_set(match)
        elif not shown:
            self._show(None)

    def focus_content(self) -> None:
        self.list_table.tree.focus_set()

    def _select(self) -> None:
        chosen = self.list_table.selection()
        if chosen:
            album = self.albums[int(chosen[0])]
            if self.current is None or album.folder_name != self.current.folder_name:
                self._show(album)

    # ------------------------------------------------------------------ form
    def _set_controls(self, state: str) -> None:
        for widget in (self.colour_entry, self.random_btn, self.default_text_btn, self.apply_btn, self.revert_btn,
                       *self.line_entries):
            widget.configure(state=state)
        self.ink_box.configure(state='readonly' if state == 'normal' else 'disabled')
        for swatch in (self.swatch, self.ink_swatch):
            swatch.configure(state=state)

    def _show(self, album: EditableAlbum | None) -> None:
        self.current = album
        self._loading = True
        try:
            if album is None:
                self.album_title.set('Choose an album on the left.')
                self.colour_var.set('')
                for var in self.line_vars:
                    var.set('')
                self._photo = self._empty_preview()
                self.preview.configure(image=self._photo or '')
                self.note.set('')
                self._set_controls('disabled')
                return
            self.album_title.set(album.label)
            self.colour_var.set('#' + album.design.colour)
            lines = list(album.design.lines) + [''] * 3
            for var, line in zip(self.line_vars, lines[:3]):
                var.set(line)
            ink = album.design.ink
            if ink == 'auto':
                self.ink_choice.set(INK_CHOICES[0])
            elif ink == '000000':
                self.ink_choice.set('Black')
            elif ink == 'FFFFFF':
                self.ink_choice.set('White')
            else:
                self.ink_choice.set('Custom...')
                self.ink_custom = ink
            self._set_controls('disabled' if self.working else 'normal')
            self.details.set('')
        finally:
            self._loading = False
        self._changed()

    def design(self) -> CoverDesign:
        choice = self.ink_choice.get()
        ink = {'Black': '000000', 'White': 'FFFFFF', 'Custom...': self.ink_custom}.get(choice, 'auto')
        return CoverDesign(self.colour_var.get(), [v.get() for v in self.line_vars], ink)

    def _changed(self) -> None:
        if self._loading or self.current is None:
            return
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(120, self._render_preview)

    def _render_preview(self) -> None:
        self._preview_job = None
        album = self.current
        if album is None:
            return
        design = self.design()
        self.ink_swatch.configure(background='#' + (self.ink_custom if self.ink_choice.get() == 'Custom...' else
                                                     {'Black': '000000', 'White': 'FFFFFF'}.get(self.ink_choice.get(),
                                                                                              '808080')))
        try:
            from ..converter.cover_editor import normalise_colour
            colour = normalise_colour(design.colour)
            self.swatch.configure(background='#' + colour, activebackground='#' + colour)
            png = CoverDesign(colour, design.lines, design.ink).png(album.album, album.artist, album.year)
            from PIL import Image, ImageTk
            import io
            with Image.open(io.BytesIO(png)) as image:
                from .textures import rounded_picture       # v1.9.0: rounded, bevelled corners
                self._photo = ImageTk.PhotoImage(rounded_picture(image.convert('RGB').resize((self._preview_size, self._preview_size),
                                                                                               Image.LANCZOS),
                                                                 PALETTE['bg'], radius=3, amount=0.20),
                                                 master=self)
            self.preview.configure(image=self._photo, width=self._preview_size, height=self._preview_size)
            owner = self.editor.colour_owner(colour, album.album_key) if self.editor else None
            if owner:
                self.note.set(f'#{colour} is the cover colour of {self.editor.owner_label(owner)}. Every album keeps its '
                              'own colour, so a nearly identical shade will be used.')
            else:
                self.note.set(f'Applies to the {album.file_count} songs in {album.folder.name}. Only the covers '
                              'Oggcultist made are changed; the audio is never touched.')
            self.note_label.configure(foreground=PALETTE['muted'])
            if not self.working:
                self.apply_btn.configure(state='normal')
        except CoverEditError as exc:
            self.note.set(str(exc))
            self.note_label.configure(foreground=PALETTE['failed'])
            self.apply_btn.configure(state='disabled')

    # ------------------------------------------------------------------ controls
    def choose_colour(self) -> None:
        if self.current is None:
            return
        chosen = colorchooser.askcolor(color=self.colour_var.get() or None, parent=self, title='Background colour')
        if chosen and chosen[1]:
            self.colour_var.set(chosen[1].upper())

    def random_colour(self) -> None:
        if self.current is None or self.editor is None:
            return
        try:
            self.colour_var.set('#' + self.editor.random_colour(self.current.album_key))
        except CoverEditError as exc:
            self.app.notify(str(exc))

    def default_text(self) -> None:
        if self.current is None:
            return
        for var, line in zip(self.line_vars, self.current.default_lines()):
            var.set(line)
        self.ink_choice.set(INK_CHOICES[0])
        self._changed()

    def _ink_changed(self) -> None:
        if self.ink_choice.get() == 'Custom...':
            self.choose_ink()
        self._changed()

    def choose_ink(self) -> None:
        if self.current is None:
            return
        chosen = colorchooser.askcolor(color='#' + self.ink_custom, parent=self, title='Text colour')
        if chosen and chosen[1]:
            self.ink_custom = chosen[1].lstrip('#').upper()
            self.ink_choice.set('Custom...')
        self._changed()

    def revert(self) -> None:
        if self.current is not None:
            self._show(self.current)

    # ------------------------------------------------------------------ apply
    def apply(self) -> None:
        album, editor = self.current, self.editor
        if album is None or editor is None or self.working:
            return
        if getattr(self.app, 'converter', None) is not None and self.app.converter.busy:
            self.app.notify('Wait for the converter to finish before changing covers.')
            return
        design = self.design()
        self._busy(True, 'Checking the files...')
        threading.Thread(target=self._plan_worker, args=(editor, album, design), daemon=True).start()
        self._poll_job = self.after(100, self._poll)

    def destroy(self):
        for job in (getattr(self, '_poll_job', None), self._preview_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        super().destroy()

    def _plan_worker(self, editor, album, design) -> None:
        try:
            self.events.put(('planned', editor.plan(album, design)))
        except Exception as exc:  # noqa: BLE001
            self.events.put(('error', str(exc)))

    def _apply_worker(self, editor, plan) -> None:
        try:
            result = editor.apply(plan, progress=lambda n, total, path: self.events.put(('progress', (n, total))))
            self.events.put(('applied', (plan, result)))
        except Exception as exc:  # noqa: BLE001
            self.events.put(('error', str(exc)))

    def _poll(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                getattr(self, '_on_' + kind)(data)
        except queue.Empty:
            pass
        if self.working:
            self._poll_job = self.after(100, self._poll)
        else:
            self._poll_job = None

    def _on_progress(self, data) -> None:
        number, total = data
        self.app.notify(f'Updating covers: {number} of {total}...', sticky=True)

    def _on_error(self, message: str) -> None:
        self._busy(False)
        self.app.notify(f'Covers not changed: {message}', sticky=True)

    def _on_planned(self, plan) -> None:
        album = plan.album
        if not plan.eligible:
            self._busy(False)
            if plan.already:
                self.app.notify(f'{album.album}: all its covers already look like this.')
            else:
                self._explain(plan.skipped, [], heading='No files could be changed.')
                self.app.notify('No covers were changed.', sticky=True)
            return
        lines = [f'Change the cover of {len(plan.eligible)} song{"s" if len(plan.eligible) != 1 else ""} '
                 f'in "{album.album}"?',
                 '',
                 'Only the embedded cover picture changes. Each file is checked before it is replaced: the audio '
                 'must decode identically and every other tag must be unchanged. Your original source files are '
                 'not involved.']
        if plan.colour_note:
            lines += ['', plan.colour_note]
        if plan.skipped:
            lines += ['', f'{len(plan.skipped)} file(s) will be left as they are (details after).']
        playing = self.app.player.song
        resume = None
        if playing is not None and Path(playing.path).parent == album.folder:
            lines += ['', 'Playback pauses for a moment while the playing song is updated.']
        if not messagebox.askyesno('Change album cover', '\n'.join(lines), parent=self):
            self._busy(False)
            self.app.notify('Cover change cancelled; nothing was changed.')
            return
        transport = self.app.player.transport
        if playing is not None and Path(playing.path).parent == album.folder and transport.playing:
            transport.pause()                    # Windows can't replace a file FFplay has open
            resume = True
        self._resume_after = resume
        self.app.on_play_state()
        threading.Thread(target=self._apply_worker, args=(self.editor, plan), daemon=True).start()

    def _on_applied(self, data) -> None:
        plan, result = data
        self._busy(False)
        if getattr(self, '_resume_after', None):
            try:
                self.app.player.transport.resume()
            except Exception:  # noqa: BLE001
                pass
            self.app.on_play_state()
        self._resume_after = None
        album = plan.album
        message = f'{album.album}: cover updated in {len(result.updated)} song{"s" if len(result.updated) != 1 else ""}.'
        if result.failed or result.skipped:
            message += f' {len(result.failed) + len(result.skipped)} left unchanged (see details).'
        self.app.notify(message, sticky=bool(result.failed))
        self._explain(result.skipped, result.failed)
        playing = self.app.player.song
        if playing is not None and Path(playing.path).parent == album.folder:
            self.app.now._draw_cover(playing)
        self.refresh()
        if self.current is not None:
            fresh = next((a for a in self.albums if a.folder_name == album.folder_name), None)
            if fresh is not None:
                self._show(fresh)
                self.details.set(self.details.get() or '')
        self._explain(result.skipped, result.failed)

    def _explain(self, skipped, failed, heading: str = '') -> None:
        rows = [f'•  {p.name}: {why}' for p, why in list(failed) + list(skipped)]
        if not rows:
            self.details.set(heading)
            return
        shown = rows[:8] + ([f'...and {len(rows) - 8} more'] if len(rows) > 8 else [])
        self.details.set('\n'.join(([heading] if heading else ['Left unchanged:']) + shown))

    def _busy(self, flag: bool, message: str = '') -> None:
        self.working = flag
        self._set_controls('disabled' if flag or self.current is None else 'normal')
        if message:
            self.app.notify(message, sticky=flag)
