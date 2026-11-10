"""Artists, Albums and Playlists: a list of groups on the left, their songs on the right.

Split out of ``player_view.py`` in 2.0.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ..player import Song
from .player_view import SongPage, duration_label, header
from .widgets import TrackTable


class _ListAndSongsPage(SongPage):
    """A list on the left (artists, albums or playlists) and its songs on the right."""
    list_columns: tuple = ()
    list_empty = ''

    def __init__(self, parent, app, title: str):
        super().__init__(parent, app)
        self.page_title = title
        header(self, title)
        panes = ttk.Panedwindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True)
        self.left = ttk.Frame(panes, padding=(0, 0, 10, 0))
        self.right = ttk.Frame(panes)
        panes.add(self.left, weight=1)
        panes.add(self.right, weight=3)
        self.list_table = TrackTable(self.left, self.list_columns, empty_text=self.list_empty,
                                     on_activate=self.play_group, style='List.Treeview')
        self.list_table.tree.configure(selectmode='browse')
        self.list_table.tree.bind('<<TreeviewSelect>>', lambda _e: self.show_group())
        self.build_left_extras(self.left)
        self.list_table.pack(fill='both', expand=True)
        self.group_title = tk.StringVar()
        top = ttk.Frame(self.right)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, textvariable=self.group_title, font='OgNowTitle').pack(anchor='w', pady=(2, 8))
        self.right_actions = ttk.Frame(top)
        self.right_actions.pack(anchor='w')
        self.build_right_actions(self.right_actions)
        self.make_table(self.right, self.songs_empty_text()).pack(fill='both', expand=True)
        self.groups: list[tuple[str, list[Song]]] = []

    def build_left_extras(self, frame) -> None:
        pass

    def build_right_actions(self, frame) -> None:
        ttk.Button(frame, text='▶  Play', style='Accent.TButton', command=self.play_group).pack(side='left')
        self.add_menu_button(frame).pack(side='left', padx=(8, 0))

    def songs_empty_text(self) -> str:
        return 'Choose an entry on the left.'

    def compute_groups(self, query: str) -> list[tuple[str, tuple, list[Song]]]:
        raise NotImplementedError

    def selected_group(self) -> int | None:
        chosen = self.list_table.selection()
        return int(chosen[0]) if chosen and int(chosen[0]) < len(self.groups) else None

    def refresh(self) -> None:
        query = self.app.search_query()
        previous = self.selected_group()
        previous_key = self.groups[previous][0] if previous is not None else None
        computed = self.compute_groups(query)
        self.groups = [(key, songs) for key, _values, songs in computed]
        self.list_table.set_rows((str(i), values, ()) for i, (_k, values, _s) in enumerate(computed))
        keys = [k for k, _ in self.groups]
        tree = self.list_table.tree
        if previous_key in keys:
            iid = str(keys.index(previous_key))
        elif keys:
            iid = '0'
        else:
            iid = None
        if iid is not None:
            tree.selection_set((iid,))
            tree.see(iid)
        self.show_group()

    def show_group(self) -> None:
        index = self.selected_group()
        if index is None:
            self.group_title.set('')
            self.populate([])
            return
        key, songs = self.groups[index]
        self.group_title.set(self.describe_group(key, songs))
        query = self.app.search_query()
        self.populate([s for s in songs if self.matches(s, query) or self.group_matches(key, query)])

    def group_matches(self, key: str, query: str) -> bool:
        return bool(query) and query in key.casefold()

    def describe_group(self, key: str, songs: list[Song]) -> str:
        total = sum(s.duration for s in songs)
        return f'{key}  ·  {len(songs)} songs  ·  {duration_label(total)}'

    def play_group(self) -> None:
        if self.shown:
            self.app.player.play_list(self.shown, 0)
        else:
            self.app.notify('Nothing to play here yet.')


class ArtistsPage(_ListAndSongsPage):
    list_columns = (('name', 'Artist', 120, True, 'w'), ('count', 'Songs', 58, False, 'e'))
    list_empty = 'No artists yet.'

    def __init__(self, parent, app):
        super().__init__(parent, app, 'Artists')

    def compute_groups(self, query):
        groups: dict[str, list[Song]] = {}
        for song in self.app.songs:
            groups.setdefault(song.artist, []).append(song)
        result = []
        for name in sorted(groups, key=str.casefold):
            songs = groups[name]
            if query and query not in name.casefold() and not any(self.matches(s, query) for s in songs):
                continue
            result.append((name, (name, len(songs)), songs))
        return result


class AlbumsPage(_ListAndSongsPage):
    list_columns = (('album', 'Album', 110, True, 'w'), ('artist', 'Artist', 80, True, 'w'),
                    ('year', 'Year', 50, False, 'e'))
    list_empty = 'No albums yet.'
    numbered = True

    def __init__(self, parent, app):
        super().__init__(parent, app, 'Albums')

    def compute_groups(self, query):
        groups: dict[tuple[str, str], list[Song]] = {}
        for song in self.app.songs:
            groups.setdefault((song.artist, song.album), []).append(song)
        result = []
        for (artist, album) in sorted(groups, key=lambda k: (k[1].casefold(), k[0].casefold())):
            songs = sorted(groups[(artist, album)], key=lambda s: (s.disc, s.track or 99999, s.title.casefold()))
            label = f'{album} — {artist}'
            if query and query not in label.casefold() and not any(self.matches(s, query) for s in songs):
                continue
            year = next((s.year for s in songs if s.year), '')
            result.append((label, (album, artist, year), songs))
        return result


class PlaylistsPage(_ListAndSongsPage):
    list_columns = (('name', 'Playlist', 120, True, 'w'), ('count', 'Songs', 58, False, 'e'))
    list_empty = 'No playlists yet.\nType a name below and press Create.'

    def __init__(self, parent, app):
        self.new_name = tk.StringVar()
        super().__init__(parent, app, 'Playlists')
        tree = self.table.tree
        tree.bind('<Delete>', lambda _e: (self.remove_selected(), 'break')[1])
        tree.bind('<Control-Up>', lambda _e: (self.move(-1), 'break')[1])
        tree.bind('<Control-Down>', lambda _e: (self.move(1), 'break')[1])
        self.list_table.tree.bind('<F2>', lambda _e: self.rename())
        self.list_table.tree.bind('<Delete>', lambda _e: self.delete())

    def build_left_extras(self, frame) -> None:
        create = ttk.Frame(frame)
        create.pack(side='bottom', fill='x', pady=(8, 0))
        entry = ttk.Entry(create, textvariable=self.new_name, width=8)   # shrinks so Create stays whole
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', lambda _e: self.create())
        self.name_entry = entry
        ttk.Button(create, text='Create', command=self.create).pack(side='left', padx=(6, 0))
        manage = ttk.Frame(frame)
        manage.pack(side='bottom', fill='x', pady=(8, 0))
        ttk.Button(manage, text='Rename', style='Ghost.TButton', command=self.rename).pack(side='left')
        ttk.Button(manage, text='Delete', style='Danger.TButton', command=self.delete).pack(side='left', padx=(4, 0))

    def build_right_actions(self, frame) -> None:
        ttk.Button(frame, text='▶  Play', style='Accent.TButton', command=self.play_group).pack(side='left')
        ttk.Button(frame, text='▲', width=3, command=lambda: self.move(-1)).pack(side='left', padx=(8, 0))
        ttk.Button(frame, text='▼', width=3, command=lambda: self.move(1)).pack(side='left', padx=(4, 0))
        ttk.Button(frame, text='Remove', command=self.remove_selected).pack(side='left', padx=(8, 0))

    def songs_empty_text(self) -> str:
        return ('This playlist is empty.\n\nAdd songs from Library, Artists or Albums:\n'
                'select them, then use "Add to playlist" or right-click.')

    def describe_group(self, key, songs):
        store = self.app.playlists
        stored = len(store.playlists.get(key, [])) if store else 0
        missing = stored - len(songs)
        text = super().describe_group(key, songs)
        return text + (f'  ·  {missing} not in this library' if missing > 0 else '')

    def group_matches(self, key: str, query: str) -> bool:
        return False  # Search filters the songs inside a playlist, not the playlist name.

    def compute_groups(self, query):
        store = self.app.playlists
        if store is None:
            return []
        result = []
        for name in sorted(store.playlists, key=str.casefold):
            songs = [self.app.by_path[p] for p in store.playlists[name] if p in self.app.by_path]
            result.append((name, (name, len(songs)), songs))
        return result

    def current_name(self) -> str | None:
        index = self.selected_group()
        return self.groups[index][0] if index is not None else None

    def select_name(self, name: str) -> None:
        self.refresh()
        for i, (key, _songs) in enumerate(self.groups):
            if key == name:
                self.list_table.tree.selection_set((str(i),))
                self.list_table.tree.see(str(i))
                break

    def create(self) -> None:
        name = self.new_name.get().strip()
        if not name:
            self.name_entry.focus_set()
            self.app.notify('Type a name for the new playlist, then press Create.')
            return
        created = self.app.create_playlist(name)
        if created:
            self.new_name.set('')
            self.select_name(created)

    def rename(self) -> None:
        name = self.current_name()
        store = self.app.playlists
        if not name or store is None:
            return
        new = simpledialog.askstring('Rename playlist', 'New name:', initialvalue=name, parent=self)
        if new is None or new.strip() == name:
            return
        try:
            new = store.rename(name, new)
        except (ValueError, OSError) as exc:
            self.app.notify(f'Could not rename playlist: {exc}')
            return
        self.app.playlists_changed()
        self.select_name(new)
        self.app.notify(f'Renamed playlist to {new}.')

    def delete(self) -> None:
        name = self.current_name()
        store = self.app.playlists
        if not name or store is None:
            return
        if not messagebox.askyesno('Delete playlist', f'Delete the playlist "{name}"?\n\nYour music files are not affected.',
                                   parent=self):
            return
        try:
            store.delete(name)
        except OSError as exc:
            self.app.notify(f'Could not delete playlist: {exc}')
            return
        self.app.playlists_changed()
        self.app.notify(f'Deleted playlist {name}. No music files were touched.')

    def remove_selected(self) -> None:
        name = self.current_name()
        songs = self.selected_songs()
        store = self.app.playlists
        if not name or not songs or store is None:
            self.app.notify('Select songs in the playlist to remove them.')
            return
        try:
            removed = store.remove(name, [s.path for s in songs])
        except OSError as exc:
            self.app.notify(f'Could not save playlist: {exc}')
            return
        self.app.playlists_changed()
        self.app.notify(f'Removed {removed} song(s) from {name}. The files are untouched.')

    def move(self, delta: int) -> None:
        name = self.current_name()
        songs = self.selected_songs()
        store = self.app.playlists
        if not name or not songs or store is None or self.app.search_query():
            if self.app.search_query():
                self.app.notify('Clear the search box to reorder a playlist.')
            return
        try:
            moved = store.move(name, [s.path for s in songs], delta)
        except OSError as exc:
            self.app.notify(f'Could not save playlist: {exc}')
            return
        if moved:
            keys = {str(s.path) for s in songs}
            self.app.playlists_changed()
            tree = self.table.tree
            ids = [iid for iid in tree.get_children('') if str(self.shown[int(iid)].path) in keys]
            if ids:
                tree.selection_set(ids)
                tree.see(ids[0])

    def extra_context_items(self, menu: tk.Menu) -> None:
        menu.add_separator()
        menu.add_command(label='Remove from playlist', command=self.remove_selected)
