"""Converter screen: choose folders, scan, review, convert — without stopping playback.

All blocking work (scanning, planning, MusicBrainz, conversion) runs on worker
threads and reports back through ``self.events``; the UI thread only reads the
queue. Behaviour and safety rules are unchanged from v1.6.3.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from ..converter.artwork import ArtworkStore
from ..converter.core import plan, process, scan, validate_folders
from ..converter.musicbrainz import MetadataLookupError, MusicBrainz
from ..metadata import Track
from .dialogs import Editor, MatchPicker
from . import design_system as ds
from .theme import PALETTE
from .native_folders import choose_directory
from .widgets import Chip, TrackTable, section_label

if TYPE_CHECKING:  # pragma: no cover
    from .app import OggcultistApp

# Converter status → (category label, row tag, symbol). Categories are what the user sees.
CATEGORIES = {
    'Ready': ('Ready', 'ready', '●'),
    'Done': ('Completed', 'done', '✓'),
    'Duplicate': ('Skipped', 'skipped', '–'),
    'Review': ('Needs review', 'review', '!'),
    'Collision': ('Needs review', 'review', '!'),
    'Error': ('Failed', 'failed', '✕'),
}
CATEGORY_ORDER = ('Ready', 'Completed', 'Needs review', 'Skipped', 'Failed')
CATEGORY_COLOURS = {'Ready': PALETTE['ready'], 'Completed': PALETTE['done'], 'Needs review': PALETTE['review'],
                    'Skipped': PALETTE['skipped'], 'Failed': PALETTE['failed']}

COLUMNS = (
    ('status', 'Status', 130, False, 'w'),
    ('albumartist', 'Album artist', 120, True, 'w'),
    ('album', 'Album', 120, True, 'w'),
    ('year', 'Year', 52, False, 'center'),
    ('disc', 'Disc/Track', 88, False, 'center'),
    ('title', 'Title', 140, True, 'w'),
    ('artist', 'Track artist', 120, True, 'w'),
    ('output', 'Proposed location', 240, True, 'w'),
)


def category(status: str) -> tuple[str, str, str]:
    return CATEGORIES.get(status, ('Needs review', 'review', '!'))


class ConverterPage(ttk.Frame):
    def __init__(self, parent, app: 'OggcultistApp'):
        super().__init__(parent, padding=ds.PAGE_PADDING)
        self.app = app
        settings = app.settings
        self.input_var = tk.StringVar(value=settings.get('input', ''))
        self.output_var = tk.StringVar(value=settings.get('output', ''))
        self.email_var = tk.StringVar(value=settings.get('email', ''))
        self.autolookup = tk.BooleanVar(value=False)
        self.cancel = threading.Event()
        self.busy = False
        self.events: queue.Queue = queue.Queue()
        self.tracks: list[Track] = []
        self.scan_errors: list[tuple[str, str]] = []
        self.filter_category: str | None = None
        self.status_var = tk.StringVar(value='Choose a source and a separate destination folder, then scan.')
        self.count_var = tk.StringVar(value='')
        self._sort: tuple[str, bool] | None = None
        self._build()
        self.bind('<Configure>', self._converter_resized, add='+')
        self._poll_job = self.after(110, self._poll)

    def destroy(self):
        job = getattr(self, '_poll_job', None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            self._poll_job = None
        super().destroy()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill='x', pady=(0, 10))
        ttk.Label(top, text='Converter', style='Title.TLabel').pack(side='left')
        ttk.Label(top, text='96 kbps Opus  ·  Non-destructive conversion',
                  style='Muted.TLabel').pack(side='left', padx=(16, 0), pady=(8, 0))

        folders = ttk.Frame(self, style='Card.TFrame', padding=(14, 8))
        folders.pack(fill='x')
        self._folders_panel = folders
        self._folders_expanded = True
        section_label(folders, '1 · Folders', card=True).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
        for row, (label, var, must_exist) in enumerate((('Source (read only)', self.input_var, True),
                                                        ('Destination library', self.output_var, False)), start=1):
            ttk.Label(folders, text=label, style='Card.TLabel').grid(row=row, column=0, sticky='w', padx=(0, 12), pady=3)
            ttk.Entry(folders, textvariable=var, style='Card.TEntry').grid(row=row, column=1, sticky='ew', pady=3)
            ttk.Button(folders, text='Browse...', command=lambda v=var, m=must_exist: self.browse(v, m)).grid(
                row=row, column=2, padx=(8, 0), pady=3)
        self.scan_btn = ttk.Button(folders, text='Scan source', style='Accent.TButton', command=self.start_scan)
        self.scan_btn.grid(row=1, column=3, rowspan=2, padx=(16, 0), pady=3)  # natural height: exact gradient
        options = ttk.Frame(folders, style='CardInner.TFrame')
        options.grid(row=3, column=0, columnspan=4, sticky='w', pady=(8, 0))
        self.online_check = ttk.Checkbutton(options, text='Look up album metadata online (MusicBrainz)',
                                            variable=self.autolookup, style='Card.TCheckbutton',
                                            command=self._online_option_changed)
        self.online_check.pack(side='left')
        self.email_label = ttk.Label(options, text='Email', style='CardMuted.TLabel')
        self.email_entry = ttk.Entry(options, textvariable=self.email_var, width=22, style='Card.TEntry')
        self._online_option_changed()
        folders.columnconfigure(1, weight=1)

        self._build_footer()
        review = ttk.Frame(self)
        self._review = review
        review.pack(fill='both', expand=True, pady=(12, 0))
        heading = ttk.Frame(review)
        heading.pack(fill='x', pady=(0, 6))
        section_label(heading, '2 · Review').pack(side='left', padx=(0, 12))
        # A source scan can reclaim vertical space on small screens while the
        # previously chosen paths remain available behind this reversible toggle.
        self.folders_toggle = ttk.Button(heading, text='Folders', style='Ghost.TButton',
                                          command=self._toggle_folders)

        self.chips: dict[str, Chip] = {}
        self._chip_area = ttk.Frame(heading)
        for name in CATEGORY_ORDER:
            chip = Chip(self._chip_area, name, CATEGORY_COLOURS[name], command=lambda n=name: self.toggle_filter(n))
            chip.pack(side='left', padx=(0, 6))
            self.chips[name] = chip
        self._chip_area.pack(side='left')
        # Count lives on the status line in compact mode so the chips can breathe.
        self._review_count = ttk.Label(heading, textvariable=self.count_var, style='Muted.TLabel')
        self._review_count.pack(side='right')

        toolbar = ttk.Frame(review)
        toolbar.pack(fill='x', pady=(0, 6))
        self.edit_btn = ttk.Button(toolbar, text='Edit metadata...', style='Ghost.TButton', command=self.edit_selected)
        self.keep_btn = ttk.Button(toolbar, text='Keep selected duplicate', style='Ghost.TButton', command=self.keep_selected)
        self.exclude_btn = ttk.Button(toolbar, text='Exclude from batch', style='Ghost.TButton', command=self.exclude_selected)
        self.lookup_btn = ttk.Button(toolbar, text='MusicBrainz lookup...', style='Ghost.TButton', command=self.lookup_selected)
        self._review_toolbar = toolbar
        for btn in (self.edit_btn, self.keep_btn, self.exclude_btn, self.lookup_btn):
            btn.pack(side='left', padx=(0, 4))
        self.more_button = ttk.Menubutton(toolbar, text='More actions...', style='Ghost.TButton')
        more_menu = tk.Menu(self.more_button, tearoff=False)
        more_menu.add_command(label='Keep selected duplicate', command=self.keep_selected)
        more_menu.add_command(label='MusicBrainz lookup...', command=self.lookup_selected)
        more_menu.add_command(label='Show / hide selected details', command=self._toggle_details)
        self.more_button.configure(menu=more_menu)
        self._toolbar_hint = ttk.Label(toolbar, text='Double-click to edit metadata', style='Status.TLabel')
        self._toolbar_hint.pack(side='right')

        detail_card = ttk.Frame(review, style='Card.TFrame', padding=(14, 8))
        self._detail_card = detail_card
        self._details_visible = True
        detail_card.pack(side='bottom', fill='x', pady=(8, 0))
        self.table = TrackTable(review, COLUMNS, horizontal_scroll=True, on_activate=self.edit_selected,
                                empty_text='Scan a source folder to review its files here.')
        self.tree = self.table.tree
        for key, *_ in COLUMNS:
            self.tree.heading(key, command=lambda k=key: self.sort_column(k))
        for _label, tag, _symbol in CATEGORIES.values():
            self.tree.tag_configure(tag, foreground=PALETTE[tag])
        self.tree.tag_configure('ready', foreground=PALETTE['text'])  # the normal case stays calm
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self.details())
        self.table.pack(fill='both', expand=True)

        self.detail = tk.Text(detail_card, height=4, wrap='word', relief='flat', borderwidth=0,
                              background=PALETTE['surface'], foreground=PALETTE['text'], font='OgList',
                              highlightthickness=0, padx=0, pady=0, cursor='arrow')
        self.detail.pack(fill='both', expand=True)
        self.detail.tag_configure('label', foreground=PALETTE['muted'], font='OgSmallBold')
        self.detail.tag_configure('failed', foreground=PALETTE['failed'])
        self.detail.tag_configure('review', foreground=PALETTE['review'])
        self._set_detail([('Select a row to see where it will go and why it needs attention.', 'label')])

        self.refresh()

    def _toggle_folders(self) -> None:
        self._folders_expanded = not self._folders_expanded
        if self._folders_expanded:
            self._folders_panel.pack(fill='x', before=self._review)
            self.folders_toggle.configure(text='Hide folders')
        else:
            self._folders_panel.pack_forget()
            self.folders_toggle.configure(text='Folders')

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        if self._details_visible:
            self._detail_card.pack(side='bottom', fill='x', pady=(8, 0))
        else:
            self._detail_card.pack_forget()

    def _online_option_changed(self) -> None:
        # An email field is relevant only when an online lookup is enabled.
        self.email_label.pack_forget()
        self.email_entry.pack_forget()
        if self.autolookup.get():
            self.email_label.pack(side='left', padx=(14, 4))
            self.email_entry.pack(side='left')

    def _converter_resized(self, event) -> None:
        if event.widget is not self:
            return
        # 2.0: the icon rail leaves a wide page at 960×600, so a short page also counts as compact
        compact = event.width < 890 or event.height < 520
        if getattr(self, '_compact', None) == compact:
            return
        self._compact = compact
        for btn in (self.keep_btn, self.lookup_btn):
            if compact:
                btn.pack_forget()
            else:
                btn.pack(side='left', padx=(0, 4))
        for name, chip in self.chips.items():
            chip.compact = compact
            chip.set(self.counts()[name], active=self.filter_category == name)
        if compact:
            self.more_button.pack(side='left', padx=(0, 4))
            self._toolbar_hint.pack_forget()
            self._review_count.pack_forget()
            self.detail.configure(height=2)
            self.folders_toggle.pack(side='right', padx=(4, 8))
            if self.tracks and self._folders_expanded:
                self._toggle_folders()
            if self._details_visible:
                self._detail_card.pack_forget()
                self._details_visible = False
        else:
            self.more_button.pack_forget()
            self._toolbar_hint.pack(side='right')
            self._review_count.pack(side='right')
            self.detail.configure(height=4)
            self.folders_toggle.pack_forget()
            if not self._folders_expanded:
                self._toggle_folders()
            if not self._details_visible:
                self._detail_card.pack(side='bottom', fill='x', pady=(8, 0))
                self._details_visible = True

    def _build_footer(self) -> None:
        self.status_label = ttk.Label(self, textvariable=self.status_var, style='Muted.TLabel', wraplength=900)
        self.status_label.pack(side='bottom', anchor='w', pady=(6, 0))
        self.bind('<Configure>', lambda e: self.status_label.configure(wraplength=max(300, e.width - 60)))
        footer = ttk.Frame(self)
        footer.pack(side='bottom', fill='x', pady=(10, 0))
        section_label(footer, '3 · Convert').pack(side='left', padx=(0, 12))
        from .sliders import GradientBar                   # v1.9.0: rounded gradient progress bar
        self.bar = GradientBar(footer, maximum=100)
        self.bar.pack(side='left', fill='x', expand=True)
        self.cancel_btn = ttk.Button(footer, text='Cancel', command=self.stop, state='disabled')
        self.cancel_btn.pack(side='right', padx=(8, 0))
        self.convert_btn = ttk.Button(footer, text='Convert ready tracks', style='Accent.TButton',
                                      command=self.start_conversion)
        self.convert_btn.pack(side='right', padx=(12, 0))

    def _set_detail(self, parts: list[tuple[str, str | None]]) -> None:
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        for text, tag in parts:
            self.detail.insert('end', text, tag or ())
        self.detail.configure(state='disabled')

    # ------------------------------------------------------------------ settings
    def browse(self, var: tk.StringVar, must_exist: bool) -> None:
        folder = choose_directory(parent=self, mustexist=must_exist,
                                  title='Choose source music folder' if must_exist else 'Choose destination library folder',
                                  initialdir=var.get() or None)
        if folder:
            var.set(folder)
            self.persist()

    def persist(self) -> None:
        self.app.update_settings(input=self.input_var.get(), output=self.output_var.get(), email=self.email_var.get())

    # ------------------------------------------------------------------ workers
    def _busy(self, flag: bool) -> None:
        self.busy = flag
        for btn in (self.scan_btn, self.convert_btn, self.edit_btn, self.keep_btn, self.exclude_btn, self.lookup_btn):
            btn.configure(state='disabled' if flag else 'normal')
        self.cancel_btn.configure(state='normal' if flag else 'disabled')
        self.app.converter_busy_changed(flag)

    def _thread(self, job) -> None:
        self.cancel.clear()
        self._busy(True)

        def run():
            try:
                job()
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('idle',))
        threading.Thread(target=run, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'status':
                    self.status_var.set(event[1])
                elif kind == 'progress':
                    name, i, total, fraction = event[1:]
                    self.bar['value'] = min(100, 100 * (i - 1 + fraction) / max(total, 1))
                    self.status_var.set(f'Converting {i} of {total}: {name}')
                elif kind == 'scanned':
                    self.tracks, self.scan_errors, cancelled = event[1:]
                    if self.tracks and getattr(self, '_compact', False) and self._folders_expanded:
                        self._toggle_folders()
                    self.filter_category = None
                    self.refresh()
                    unreadable = f'; {len(self.scan_errors)} could not be read (see below)' if self.scan_errors else ''
                    self.status_var.set(f'Scan cancelled: partial list of {len(self.tracks)} files.' if cancelled else
                                        f'Scan complete: {len(self.tracks)} audio files{unreadable}.')
                    if self.scan_errors:
                        self._show_scan_errors()
                elif kind == 'replan':
                    self.refresh()
                    self.status_var.set('Destination rechecked.')
                elif kind == 'lookup':
                    self._handle_matches(*event[1:])
                elif kind == 'complete':
                    self.refresh()
                    self._show_summary(event[1])
                elif kind == 'error':
                    self.status_var.set('Error: ' + event[1])
                    self._set_detail([('Something went wrong\n', 'label'), (event[1], 'failed')])
                    messagebox.showerror('Oggcultist error', event[1], parent=self)
                elif kind == 'idle':
                    self._busy(False)
        except queue.Empty:
            pass
        try:
            self._poll_job = self.after(110, self._poll)
        except tk.TclError:
            self._poll_job = None

    def get_folders(self):
        return validate_folders(Path(self.input_var.get()), Path(self.output_var.get()))

    def start_scan(self) -> None:
        if self.busy:
            return
        try:
            src, dest = self.get_folders()
        except Exception as exc:
            self.status_var.set(str(exc))
            messagebox.showerror('Choose folders', str(exc), parent=self)
            return
        self.persist()
        auto_lookup = self.autolookup.get()
        contact_email = self.email_var.get()
        self.bar['value'] = 0
        self.status_var.set('Scanning...')

        def job():
            tracks, errors = scan(src, lambda i, name: self.events.put(('status', f'Scanning {i}: {name}')), self.cancel)
            store = ArtworkStore(dest, read_only=True)
            try:
                plan(tracks, dest, store)
            finally:
                store.close()
            if auto_lookup and not self.cancel.is_set():
                self._auto_lookup(tracks, dest, contact_email)
            # Only expose these Track objects after background metadata work is finished.
            self.events.put(('scanned', tracks, errors, self.cancel.is_set()))
        self._thread(job)

    def _show_scan_errors(self) -> None:
        lines = [f'{Path(p).name}: {why}' for p, why in self.scan_errors[:12]]
        more = len(self.scan_errors) - len(lines)
        self._set_detail([(f'{len(self.scan_errors)} file(s) could not be read and were left out:\n', 'label'),
                          ('\n'.join(lines) + (f'\n... and {more} more' if more > 0 else ''), 'review')])

    def replan(self) -> None:
        if self.busy:
            return
        try:
            _src, out = self.get_folders()
        except Exception as exc:
            # Nothing to recheck against yet: update the table and explain, without a dialog.
            self.refresh()
            self.status_var.set(self.status_var.get() + f'  (Destination not rechecked: {exc})')
            return

        def job():
            store = ArtworkStore(out, read_only=True)
            try:
                plan(self.tracks, out, store)
            finally:
                store.close()
            self.events.put(('replan',))
        self.status_var.set('Rechecking destination files...')
        self._thread(job)

    # ------------------------------------------------------------------ table
    def counts(self) -> dict[str, int]:
        counts = {name: 0 for name in CATEGORY_ORDER}
        for t in self.tracks:
            counts[category(t.status)[0]] += 1
        return counts

    def toggle_filter(self, name: str) -> None:
        self.filter_category = None if self.filter_category == name else name
        self.refresh()

    def refresh(self) -> None:
        output = Path(self.output_var.get()) if self.output_var.get() else None
        rows = []
        for i, t in enumerate(self.tracks):
            label, tag, symbol = category(t.status)
            if self.filter_category and label != self.filter_category:
                continue
            disc = f'{t.disc}/{t.track:02d}' if t.track else f'{t.disc}/?'
            target = ''
            if t.target:
                try:
                    target = str(t.target.relative_to(output)) if output else str(t.target)
                except ValueError:
                    target = str(t.target)
            rows.append((str(i), (f'{symbol}  {label}', t.albumartist, t.album, t.year, disc, t.title,
                                  t.artist, target), (tag, t.status)))
        if self._sort:
            key, reverse = self._sort
            pos = [c[0] for c in COLUMNS].index(key)
            rows.sort(key=lambda r: str(r[1][pos]).casefold(), reverse=reverse)
        self.table.set_rows(rows)
        counts = self.counts()
        for name, chip in self.chips.items():
            chip.set(counts[name], active=self.filter_category == name)
        shown = f'Showing {len(rows)} of {len(self.tracks)}' if self.filter_category else f'{len(self.tracks)} tracks'
        self.count_var.set(shown if self.tracks else '')
        self.convert_btn.configure(text=f'Convert {counts["Ready"]} ready track(s)' if counts['Ready'] else 'Convert ready tracks')
        self.details()

    def sort_column(self, key: str) -> None:
        reverse = bool(self._sort and self._sort[0] == key and not self._sort[1])
        self._sort = (key, reverse)
        self.refresh()

    def selected(self) -> list[Track]:
        return [self.tracks[int(i)] for i in self.tree.selection() if i.isdigit() and int(i) < len(self.tracks)]

    def details(self) -> None:
        selection = self.selected()
        if not selection:
            return
        t = selection[0]
        label, tag, _symbol = category(t.status)
        destination = str(t.target) if t.target else '(needs a metadata correction first)'
        parts = [('Status  ', 'label'), (label + (f' ({t.status})' if label != t.status else '') + '\n', tag),
                 ('Source  ', 'label'), (str(t.source) + '\n', None),
                 ('Destination  ', 'label'), (destination + '\n', None)]
        if t.note:
            parts += [('Why  ', 'label'), (t.note, 'failed' if tag == 'failed' else 'review' if tag == 'review' else None)]
        if len(selection) > 1:
            parts.append((f'\n{len(selection)} rows selected.', 'label'))
        self._set_detail(parts)

    # ------------------------------------------------------------------ actions
    def edit_selected(self) -> None:
        if self.busy:
            return
        selected = self.selected()
        if not selected:
            self.status_var.set('Select one row to edit its metadata.')
            return
        Editor(self, selected[0])

    def exclude_selected(self) -> None:
        if self.busy:
            return
        selected = self.selected()
        if not selected:
            self.status_var.set('Select the rows to leave out of this batch.')
            return
        ids = {id(t) for t in selected}
        self.tracks = [t for t in self.tracks if id(t) not in ids]
        self.status_var.set(f'Excluded {len(selected)} file(s) from this batch. The original files are untouched; '
                            'scan again to bring them back.')
        self.replan()

    def keep_selected(self) -> None:
        if self.busy:
            return
        selected = self.selected()
        if len(selected) != 1:
            self.status_var.set('Select exactly one conflicting or duplicate row to keep.')
            return
        candidate = selected[0]
        if not candidate.target:
            self.status_var.set('Correct the missing metadata on this row first.')
            return
        conflicts = [t for t in self.tracks if t is not candidate and (
            (t.target and str(t.target).casefold() == str(candidate.target).casefold()) or
            (candidate.duplicate_group and t.duplicate_group == candidate.duplicate_group and
             t.album_key() == candidate.album_key()))]
        if not conflicts:
            self.status_var.set('This row has no conflicting destination or exact duplicate in the same album.')
            return
        ids = {id(t) for t in conflicts}
        self.tracks = [t for t in self.tracks if id(t) not in ids]
        self.status_var.set(f'Kept the selected file and left {len(conflicts)} conflicting copy(ies) out of this batch. '
                            'Nothing was deleted.')
        self.replan()

    def _album_tracks(self, selected: Track) -> list[Track]:
        return [t for t in self.tracks if t.album_group() == selected.album_group()]

    def lookup_selected(self) -> None:
        if self.busy:
            return
        selected = self.selected()
        if not selected:
            self.status_var.set('Select a track from the album you want to look up.')
            return
        tracks = self._album_tracks(selected[0])
        self.persist()
        try:
            mb = MusicBrainz(self.email_var.get())
        except MetadataLookupError as exc:
            self.status_var.set(str(exc))
            messagebox.showerror('MusicBrainz setup', str(exc), parent=self)
            return
        album, artist = selected[0].album, selected[0].albumartist or selected[0].artist
        self.status_var.set(f'Looking up {album} on MusicBrainz...')

        def job():
            matches = mb.search(album, artist)
            self.events.put(('lookup', tracks, matches, False))
        self._thread(job)

    def _auto_lookup(self, tracks: list[Track], dest: Path, contact_email: str) -> None:
        try:
            mb = MusicBrainz(contact_email)
        except MetadataLookupError as exc:
            self.events.put(('status', 'Skipped online lookup: ' + str(exc)))
            return
        groups = {t.album_group(): [] for t in tracks}
        for t in tracks:
            groups[t.album_group()].append(t)
        for i, group in enumerate(groups.values(), 1):
            if self.cancel.is_set():
                break
            lead = group[0]
            if not lead.album or not (lead.albumartist or lead.artist):
                continue
            if not mb.auto_lookup_safe(group):
                continue
            self.events.put(('status', f'MusicBrainz lookup {i}/{len(groups)}: {lead.album}'))
            try:
                matches = mb.search(lead.album, lead.albumartist or lead.artist)
                reliable = mb.confident(matches)
                if reliable:
                    for t in group:
                        mb.apply(t, reliable)
                        t.lookup_issue = ''
                elif matches:
                    for t in group:
                        t.lookup_issue = 'Ambiguous MusicBrainz results — review manually'
            except MetadataLookupError as exc:
                self.events.put(('status', f'Lookup failed on {lead.album}: {exc}'))
        store = ArtworkStore(dest, read_only=True)
        try:
            plan(tracks, dest, store)
        finally:
            store.close()

    def _handle_matches(self, group, matches, automated) -> None:
        if not matches:
            self.status_var.set('No matching MusicBrainz release groups were found. No tags were changed.')
            return
        mb = MusicBrainz(self.email_var.get())

        def apply(match):
            for t in group:
                mb.apply(t, match)
                t.lookup_issue = ''
            self.replan()
        # Manual lookup always offers explicit review, even for a confident candidate.
        self.status_var.set(f'{len(matches)} MusicBrainz candidate(s) found — choose one or close.')
        MatchPicker(self, matches, apply)

    def start_conversion(self) -> None:
        if self.busy:
            return
        if not self.tracks:
            self.status_var.set('Scan the source folder first.')
            return
        try:
            _src, out = self.get_folders()
        except Exception as exc:
            self.status_var.set(str(exc))
            messagebox.showerror('Choose folders', str(exc), parent=self)
            return
        counts = self.counts()
        ready = counts['Ready']
        if not ready:
            self.status_var.set('No files are ready. Fix or exclude the rows that need review first.')
            return
        attention = counts['Needs review'] + counts['Skipped'] + counts['Failed']
        if not messagebox.askyesno('Start conversion',
                                   f'Convert {ready} ready track(s) into:\n{out}\n\n'
                                   f'{attention} other row(s) will be left out.\n'
                                   'Original files are never modified or deleted.', parent=self):
            return
        self.bar['value'] = 0
        self.persist()

        def job():
            summary = process(self.tracks, out, self.cancel,
                              lambda name, i, n, f: self.events.put(('progress', name, i, n, f)))
            self.events.put(('complete', summary))
        self._thread(job)

    def _show_summary(self, summary: dict) -> None:
        saved = summary['input_bytes'] - summary['output_bytes']
        if not summary['cancelled']:
            self.bar['value'] = 100
        headline = ('Cancelled' if summary['cancelled'] else 'Finished') + (
            f" — {summary['converted']} converted, {summary['already_done']} already done, "
            f"{summary['errors']} failed, {summary['not_processed']} not processed.")
        parts = [(headline + '\n', 'failed' if summary['errors'] else None),
                 ('Size  ', 'label'),
                 (f"{summary['input_bytes'] / 1048576:.1f} MiB in → {summary['output_bytes'] / 1048576:.1f} MiB out "
                  f"({saved / 1048576:+.1f} MiB saved)\n", None)]
        reports = summary.get('report_paths', ())
        if reports:
            parts += [('Report  ', 'label'), (str(reports[0]) + '\n', None)]
        covers = summary.get('cover_warnings', [])
        if covers:
            parts += [('Covers  ', 'label'), (f'{len(covers)} album folder(s) already contain conflicting older covers.\n', 'review')]
        if summary['errors']:
            first = next(r for r in summary['results'] if r['status'] == 'error')
            parts += [('First failure  ', 'label'), (f"{Path(first['source']).name}\n{first['message'][:700]}\n", 'failed'),
                      ('Original files have not been modified. The JSON report has the details for every file.', 'label')]
        self._set_detail(parts)
        self.status_var.set(headline)
        self.app.notify(headline)

    def stop(self) -> None:
        self.cancel.set()
        self.status_var.set('Cancelling after the current safe stopping point...')

    def focus_content(self) -> None:
        self.tree.focus_set()
