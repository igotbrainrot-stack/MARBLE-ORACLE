"""v1.7.0 regression tests: package layout, paths/portable data, packaging readiness,
child-process flags, single-window GUI navigation, keyboard selection, playlists.

GUI tests need an X display (xvfb-run) or a Windows desktop and are skipped otherwise.
All user data is isolated with OGGCULTIST_DATA_DIR; no real settings are touched.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from oggcultist import paths

ROOT = Path(__file__).resolve().parents[1]
HAS_DISPLAY = sys.platform == 'win32' or bool(os.environ.get('DISPLAY'))
needs_display = pytest.mark.skipif(not HAS_DISPLAY, reason='Requires an X display or a Windows desktop')


# --------------------------------------------------------------------------- package layout
def test_compatibility_aliases_are_the_same_module_objects():
    import launch
    import setup_ffmpeg
    import oggcultist.artwork
    import oggcultist.core
    import oggcultist.musicbrainz
    import oggcultist.selection
    import oggcultist.windows_launcher
    from oggcultist import startup
    from oggcultist.converter import artwork, core, musicbrainz
    from oggcultist.gui import selection
    from oggcultist.services import ffmpeg_setup, windows_launcher
    assert launch is startup and setup_ffmpeg is ffmpeg_setup
    assert oggcultist.core is core and oggcultist.artwork is artwork and oggcultist.musicbrainz is musicbrainz
    assert oggcultist.selection is selection and oggcultist.windows_launcher is windows_launcher


def test_gui_alias_is_the_same_module_object():
    pytest.importorskip('tkinter')
    import oggcultist.app
    from oggcultist.gui import app
    assert oggcultist.app is app


def test_cli_and_converter_do_not_import_tkinter():
    code = ('import sys; import oggcultist.startup, oggcultist.converter.core, oggcultist.player; '
            'print("tkinter" in sys.modules)')
    out = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), capture_output=True, text=True, check=True)
    assert out.stdout.strip() == 'False'


def test_end_user_files_and_developer_files_are_separated():
    for name in ('Oggcultist.pyw', 'DIAGNOSE_WINDOWS.bat', 'launch.py', 'requirements.txt',
                 'README.md', 'LICENSE', 'CHANGELOG.md', 'pyproject.toml'):
        assert (ROOT / name).is_file(), name
    # 2.0.1: only the two labelled launchers sit outside the program folder
    assert ROOT.name == 'Oggcultist'
    for name in ('WINDOWS LAUNCHER.bat', 'LINUX LAUNCHER.sh'):
        assert (ROOT.parent / name).is_file(), name
    assert not (ROOT / 'run_windows.bat').exists() and not (ROOT / 'run_linux.sh').exists()
    loose_reports = [p.name for p in ROOT.iterdir() if p.is_file() and
                     (p.name.startswith(('TEST_REPORT', 'CODE_REVIEW', 'HANDOVER', 'PATCH_NOTES', 'START_HERE')))]
    assert loose_reports == []
    assert (ROOT / 'docs' / 'reviews').is_dir() and (ROOT / 'docs' / 'history').is_dir()


def test_windows_batch_files_use_crlf():
    for path in (ROOT.parent / 'WINDOWS LAUNCHER.bat', ROOT / 'DIAGNOSE_WINDOWS.bat', ROOT / 'packaging' / 'windows' / 'build_windows.bat'):
        data = path.read_bytes()
        assert b'\r\n' in data and b'\n' not in data.replace(b'\r\n', b''), path.name


def test_windows_launcher_default_root_is_project_root():
    from oggcultist.services import windows_launcher
    assert (Path(windows_launcher.__file__).resolve().parents[2] / 'launch.py').is_file()


# --------------------------------------------------------------------------- paths, frozen, portable
def _freeze(monkeypatch, exe_dir: Path, meipass: Path | None):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe_dir / 'Oggcultist.exe'))
    if meipass is None:
        monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    else:
        monkeypatch.setattr(sys, '_MEIPASS', str(meipass), raising=False)


def test_frozen_paths_use_executable_folder_and_bundle(tmp_path, monkeypatch):
    exe_dir = tmp_path / 'Program Files Ü' / 'Oggcultist'
    bundle = tmp_path / '_MEI123'
    (bundle / 'tools').mkdir(parents=True)
    (exe_dir / 'tools').mkdir(parents=True)
    _freeze(monkeypatch, exe_dir, bundle)
    assert paths.is_frozen()
    assert paths.app_dir() == exe_dir.resolve()
    assert paths.bundle_dir() == bundle
    # Tools next to the .exe win over tools embedded in the one-file bundle.
    assert paths.bundled_tools_dirs() == [exe_dir.resolve() / 'tools', bundle / 'tools']


def test_resource_lookup_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    icon = paths.resource_path('icon.png')
    assert icon.is_file() and icon.is_absolute()
    assert (paths.resource_path('icon.ico')).is_file()


def test_frozen_resource_fallback_reads_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / '_MEI9'
    (bundle / 'oggcultist' / 'resources').mkdir(parents=True)
    (bundle / 'oggcultist' / 'resources' / 'only-in-bundle.txt').write_text('x')
    _freeze(monkeypatch, tmp_path, bundle)
    assert paths.resource_path('only-in-bundle.txt') == bundle / 'oggcultist' / 'resources' / 'only-in-bundle.txt'


def test_standard_locations_match_previous_versions():
    win = {'APPDATA': r'C:\Users\Zoë\AppData\Roaming', 'LOCALAPPDATA': r'C:\Users\Zoë\AppData\Local'}
    assert paths.config_dir(win, 'win32') == Path(win['APPDATA']) / 'Oggcultist'
    assert paths.private_tools_dir(win, 'win32') == Path(win['LOCALAPPDATA']) / 'Oggcultist' / 'ffmpeg' / 'bin'
    assert paths.logs_dir(win, 'win32') == Path(win['LOCALAPPDATA']) / 'Oggcultist' / 'logs'
    linux = {'XDG_CONFIG_HOME': '/home/zoë/.config'}
    assert paths.config_dir(linux, 'linux') == Path('/home/zoë/.config/Oggcultist')
    from oggcultist.services import ffmpeg_setup
    assert ffmpeg_setup.local_bin('win32', win) == Path(win['LOCALAPPDATA']) / 'Oggcultist' / 'ffmpeg' / 'bin'


def test_portable_mode_by_marker_and_env(tmp_path, monkeypatch):
    exe_dir = tmp_path / 'USB stick ✓'
    exe_dir.mkdir()
    _freeze(monkeypatch, exe_dir, None)
    monkeypatch.delenv(paths.DATA_ENV, raising=False)
    assert paths.portable_root() is None
    (exe_dir / 'OggcultistData').mkdir()
    root = exe_dir.resolve() / 'OggcultistData'
    assert paths.portable_root() == root
    assert paths.settings_file() == root / 'config' / 'settings.json'
    assert paths.playlist_file() == root / 'config' / 'playlists.json'
    assert paths.logs_dir() == root / 'logs'
    assert paths.private_tools_dir() == root / 'tools' / 'ffmpeg' / 'bin'
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'elsewhere'))
    assert paths.portable_root() == tmp_path / 'elsewhere'


def test_portable_migration_copies_never_moves_or_overwrites(tmp_path):
    standard = tmp_path / 'xdg' / 'Oggcultist'
    standard.mkdir(parents=True)
    (standard / 'settings.json').write_text('{"library": "/music"}', encoding='utf-8')
    (standard / 'playlists.json').write_text('{"format": 1, "playlists": {"Old": []}}', encoding='utf-8')
    env = {'XDG_CONFIG_HOME': str(tmp_path / 'xdg'), paths.DATA_ENV: str(tmp_path / 'portable')}
    if sys.platform == 'win32':
        env['APPDATA'] = str(tmp_path / 'xdg')
    copied = paths.migrate_to_portable(env)
    assert sorted(copied) == ['playlists.json', 'settings.json']
    assert (standard / 'settings.json').read_text(encoding='utf-8') == '{"library": "/music"}'
    target = tmp_path / 'portable' / 'config'
    assert json.loads((target / 'playlists.json').read_text(encoding='utf-8'))['playlists'] == {'Old': []}
    assert (target / 'MIGRATED_FROM.txt').is_file()
    (target / 'settings.json').write_text('{"library": "/new"}', encoding='utf-8')
    assert paths.migrate_to_portable(env) == []          # never overwrites portable data
    assert json.loads((target / 'settings.json').read_text(encoding='utf-8')) == {'library': '/new'}


def test_tool_path_priority(tmp_path, monkeypatch):
    exe_dir = tmp_path / 'app'
    (exe_dir / 'tools').mkdir(parents=True)
    _freeze(monkeypatch, exe_dir, None)
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(paths, 'private_tools_dir', lambda env=None, platform=None: private)
    env = {'PATH': '/usr/bin'}
    added = paths.configure_tool_path(env)
    entries = env['PATH'].split(os.pathsep)
    assert added == [exe_dir.resolve() / 'tools', private]
    assert entries[:3] == [str(exe_dir.resolve() / 'tools'), str(private), '/usr/bin']
    paths.configure_tool_path(env)                    # idempotent
    assert env['PATH'].split(os.pathsep).count(str(private)) == 1


# --------------------------------------------------------------------------- child processes
def test_every_ffmpeg_child_process_suppresses_console_windows():
    """A windowed .exe/pythonw would flash a console for each FFmpeg call otherwise."""
    tree = ast.parse((ROOT / 'oggcultist' / 'converter' / 'core.py').read_text(encoding='utf-8'))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == 'subprocess'
             and n.func.attr in ('run', 'Popen')]
    assert len(calls) >= 5
    for call in calls:
        assert any(kw.arg is None and isinstance(kw.value, ast.Call) and getattr(kw.value.func, 'id', '') == 'no_window_kwargs'
                   for kw in call.keywords), f'line {call.lineno}'


def test_no_window_flag_values():
    from oggcultist.services.tools import no_window_kwargs
    assert no_window_kwargs('win32') == {'creationflags': 0x08000000}
    assert no_window_kwargs('linux') == {}


def test_probe_passes_flags_to_subprocess(monkeypatch, tmp_path):
    from oggcultist.converter import core
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"streams":[{"codec_name":"opus","duration":"1"}],"format":{"duration":"1"}}', stderr='')
    monkeypatch.setattr(core.subprocess, 'run', fake_run)
    monkeypatch.setattr(core, 'no_window_kwargs', lambda: {'creationflags': 0x08000000})
    core.probe(tmp_path / 'x.opus')
    assert seen.get('creationflags') == 0x08000000


# --------------------------------------------------------------------------- entry points
def _run_launch(args, cwd, env=None):
    return subprocess.run([sys.executable, str(ROOT / 'launch.py'), *args], cwd=str(cwd),
                          capture_output=True, text=True, env=env, timeout=120)


def test_cli_dry_run_from_other_directory_with_unicode_and_spaces(tmp_path):
    source = tmp_path / 'Mü sic sóurce'
    source.mkdir()
    destination = tmp_path / 'Out pút ✓'
    result = _run_launch(['--cli', '--input', str(source), '--output', str(destination)], cwd=tmp_path.anchor)
    assert result.returncode == 0, result.stderr
    assert 'DRY RUN ONLY' in result.stdout
    assert not destination.exists()            # a preview creates nothing


def test_module_entry_and_version_and_paths_report(tmp_path):
    env = dict(os.environ, **{paths.DATA_ENV: str(tmp_path / 'data ü')})
    version = subprocess.run([sys.executable, '-m', 'oggcultist', '--version'], cwd=str(ROOT),
                             capture_output=True, text=True, env=env, check=True)
    from oggcultist import __version__
    assert version.stdout.strip() == f'Oggcultist {__version__}'
    report = _run_launch(['--paths'], cwd=tmp_path, env=env)
    assert report.returncode == 0
    assert str(tmp_path / 'data ü') in report.stdout and 'Icon resource' in report.stdout
    assert 'exists: True' in report.stdout


def test_cli_run_reports_missing_ffmpeg(monkeypatch, capsys):
    from oggcultist import startup
    monkeypatch.setattr(startup.setup_ffmpeg, 'ensure_ffmpeg', lambda **kw: False)
    with pytest.raises(SystemExit) as exc:
        startup.main(['--cli', '--input', 'a', '--output', 'b', '--run'])
    assert 'FFmpeg setup did not complete' in str(exc.value.code)


def test_desktop_start_reports_missing_ffplay_but_still_opens(monkeypatch):
    from oggcultist import startup
    opened = []
    monkeypatch.setattr(startup.setup_ffmpeg, 'ensure_ffmpeg', lambda **kw: True)
    monkeypatch.setattr(startup.setup_ffmpeg, 'ensure_ffplay', lambda **kw: False)
    monkeypatch.setitem(sys.modules, 'oggcultist.app', SimpleNamespace(main=lambda **kw: opened.append(kw)))
    startup._start_desktop()
    assert opened and 'FFplay is not installed' in opened[0]['startup_message']


def test_frozen_windows_defaults_to_windowless_prompts(monkeypatch):
    from oggcultist import startup
    monkeypatch.setattr(startup.sys, 'platform', 'win32')
    monkeypatch.setattr(startup.paths, 'is_frozen', lambda: True)
    assert startup._default_windowless()
    monkeypatch.setattr(startup.sys, 'platform', 'linux')
    assert not startup._default_windowless()


def test_missing_stdout_is_redirected_to_log(tmp_path, monkeypatch):
    from oggcultist import startup
    monkeypatch.setattr(startup.paths, 'logs_dir', lambda *a, **k: tmp_path / 'logs')
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    startup._redirect_missing_streams()
    print('hello from a windowed build')
    sys.stdout.flush()
    assert 'hello from a windowed build' in (tmp_path / 'logs' / 'oggcultist.log').read_text(encoding='utf-8')
    sys.stdout.close()


# --------------------------------------------------------------------------- packaging readiness
def test_versions_are_consistent_for_the_build():
    sys.path.insert(0, str(ROOT / 'packaging'))
    try:
        import build
        build.check_versions(build.project_version())
    finally:
        sys.path.remove(str(ROOT / 'packaging'))


def test_pyinstaller_recipe_is_windowed_and_includes_resources():
    spec = (ROOT / 'packaging' / 'oggcultist.spec').read_text(encoding='utf-8')
    assert "console=False" in spec and "oggcultist/resources" in spec and 'icon.ico' in spec
    assert 'OGGCULTIST_BUNDLE_TOOLS' in spec and "'tools'" in spec
    entry = (ROOT / 'packaging' / 'entry.py').read_text(encoding='utf-8')
    assert 'from oggcultist.startup import main' in entry


def test_requirements_are_bounded():
    for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            assert '>=' in line and '<' in line, line


# --------------------------------------------------------------------------- playlists and settings
def test_playlist_rename_move_and_unicode_round_trip(tmp_path):
    from oggcultist.player import PlaylistStore
    path = tmp_path / 'plists ü' / 'playlists.json'
    store = PlaylistStore(path)
    store.create('Road trip ✓')
    songs = [tmp_path / f'{n} sóng.opus' for n in 'abcd']
    store.add('Road trip ✓', songs)
    assert store.move('Road trip ✓', [songs[2], songs[3]], -1)
    assert store.playlists['Road trip ✓'] == [str(songs[i]) for i in (0, 2, 3, 1)]
    assert not store.move('Road trip ✓', [songs[0]], -1)      # already first
    assert store.rename('Road trip ✓', 'Driving') == 'Driving'
    with pytest.raises(ValueError):
        store.create('driving')
    reloaded = PlaylistStore(path)
    assert list(reloaded.playlists) == ['Driving']
    assert reloaded.playlists['Driving'] == [str(songs[i]) for i in (0, 2, 3, 1)]


def test_v15_playlist_file_still_loads(tmp_path):
    from oggcultist.player import PlaylistStore
    path = tmp_path / 'playlists.json'
    path.write_text(json.dumps({'format': 1, 'playlists': {'Old mix': ['/m/a.opus', '/m/b.opus']}}), encoding='utf-8')
    assert PlaylistStore(path).playlists == {'Old mix': ['/m/a.opus', '/m/b.opus']}


def test_settings_keep_unknown_keys_from_other_versions(tmp_path, monkeypatch):
    pytest.importorskip('tkinter')
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path))
    from oggcultist.gui import app as gui_app
    target = paths.settings_file()
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({'input': '/src', 'output': '/dst', 'email': 'a@b.c', 'future': 1}), encoding='utf-8')
    gui_app.save_settings({'library': '/dst', 'volume': 40})
    data = json.loads(target.read_text(encoding='utf-8'))
    assert data == {'input': '/src', 'output': '/dst', 'email': 'a@b.c', 'future': 1, 'library': '/dst', 'volume': 40}


def test_song_track_artist_keeps_guest_credit(tmp_path):
    import shutil as _sh
    if not _sh.which('ffmpeg'):
        pytest.skip('FFmpeg missing')
    from mutagen.flac import FLAC
    from oggcultist.player import read_song
    path = tmp_path / 'a.flac'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'flac', str(path)], check=True)
    f = FLAC(path)
    f.update({'title': 'T', 'artist': 'Singer feat. Guest', 'albumartist': 'Singer', 'album': 'A', 'originaldate': '1999'})
    f.save()
    song = read_song(path)
    assert (song.artist, song.track_artist, song.display_artist, song.year) == ('Singer', 'Singer feat. Guest', 'Singer feat. Guest', '1999')


def test_converter_status_categories():
    pytest.importorskip('tkinter')
    from oggcultist.gui.converter_view import category
    assert category('Ready')[0] == 'Ready'
    assert category('Done')[0] == 'Completed'
    assert category('Duplicate')[0] == 'Skipped'
    assert category('Review')[0] == category('Collision')[0] == 'Needs review'
    assert category('Error')[0] == 'Failed'
    assert category('SomethingNew')[0] == 'Needs review'     # unknown statuses are never treated as safe


# --------------------------------------------------------------------------- GUI
class FakeProcess:
    def __init__(self, *a, **k):
        self.code = None

    def poll(self):
        return self.code

    def terminate(self):
        self.code = -15

    kill = terminate

    def wait(self, timeout=None):
        return self.code


def _songs(tmp_path, count=6):
    from oggcultist.player import Song
    songs = []
    for i in range(count):
        p = tmp_path / 'lib' / f'Ärtist {i % 2}' / f'{i:02} sóng {i}.opus'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'not really audio')
        songs.append(Song(path=p, title=f'Sóng {i}', artist=f'Ärtist {i % 2}', album=f'Album {i % 3}',
                          track=i + 1, duration=120 + i, track_artist=f'Ärtist {i % 2} feat. Guest' if i == 3 else ''))
    return songs


@pytest.fixture
def gui(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'data'))
    # A modal dialog in a headless test would wait forever: fail instead.
    from tkinter import messagebox, simpledialog

    def unexpected(*args, **kwargs):
        raise AssertionError(f'unexpected modal dialog: {args[:2]}')
    for name in ('showinfo', 'showwarning', 'showerror', 'askyesno', 'askokcancel'):
        monkeypatch.setattr(messagebox, name, unexpected)
    monkeypatch.setattr(simpledialog, 'askstring', unexpected)
    from oggcultist.gui import app as gui_app, player_view
    from oggcultist.player import FFplayTransport
    monkeypatch.setattr(player_view, 'find_ffplay', lambda: 'ffplay')
    app = gui_app.OggcultistApp(startup_message='test start')
    app.player.transport = FFplayTransport(finder=lambda: 'ffplay', spawner=FakeProcess)
    songs = _songs(tmp_path)
    app._library_loaded((songs, []))
    app.update()
    yield app
    try:
        app.destroy()
    except Exception:
        pass


def _click(tree, iid, modifiers=''):
    tree.update_idletasks()
    x, y, _w, h = tree.bbox(iid, column='#2') or tree.bbox(iid)
    tree.event_generate(f'<{modifiers}Button-1>', x=x + 5, y=y + h // 2)
    tree.update()


@needs_display
def test_gui_navigation_and_keyboard_shortcuts(gui):
    assert gui.current_page == 'library'
    for number, key in enumerate(('library', 'artists', 'albums', 'playlists', 'converter'), start=1):
        gui.focus_force()
        gui.event_generate(f'<Control-Key-{number}>')
        gui.update()
        assert gui.current_page == key
    gui.nav['albums'].invoke()
    assert gui.current_page == 'albums'
    gui.focus_search()
    assert gui.current_page == 'albums' and gui.focus_get() == gui.search_entry


@needs_display
def test_gui_real_mouse_multi_selection_on_library(gui):
    tree = gui.pages['library'].table.tree
    tree.see('0')
    gui.update()
    _click(tree, '1')
    assert tree.selection() == ('1',)
    _click(tree, '3', 'Control-')
    assert set(tree.selection()) == {'1', '3'}
    _click(tree, '1', 'Control-')
    assert set(tree.selection()) == {'3'}
    _click(tree, '5', 'Shift-')
    assert set(tree.selection()) == {'3', '4', '5'}
    _click(tree, '0', 'Control-Shift-')
    assert set(tree.selection()) == {'0', '1', '2', '3', '4', '5'}
    _click(tree, '2')
    assert tree.selection() == ('2',)
    tree.focus_set()
    tree.event_generate('<Control-a>')
    gui.update()
    assert len(tree.selection()) == len(gui.pages['library'].shown)


@needs_display
def test_gui_double_click_and_enter_play_and_playback_survives_converter(gui):
    page = gui.pages['library']
    tree = page.table.tree
    tree.update_idletasks()
    x, y, _w, h = tree.bbox('2', column='#2')
    for _ in range(2):   # two quick clicks = a real double-click (Tk cannot generate <Double-1> directly)
        tree.event_generate('<ButtonPress-1>', x=x + 5, y=y + h // 2)
        tree.event_generate('<ButtonRelease-1>', x=x + 5, y=y + h // 2)
    gui.update()
    assert gui.player.song is page.shown[2]
    assert tree.item('2', 'values')[0] == '▶' and 'playing' in tree.item('2', 'tags')
    assert gui.now.title_var.get() == page.shown[2].title
    gui.show_converter()
    gui.update()
    assert gui.player.transport.playing                      # switching screens never stops music
    gui.show_player()
    tree.selection_set(('4',))
    tree.focus_set()
    tree.event_generate('<Return>')
    gui.update()
    assert gui.player.song is page.shown[4]
    assert tree.item('2', 'values')[0] != '▶'                # old marker cleared
    gui.player.toggle()
    assert gui.player.transport.paused
    gui.player.next()
    assert gui.player.song is page.shown[5]
    gui.player.stop()
    assert gui.player.song is None and gui.now.title_var.get() == 'Nothing playing'


@needs_display
def test_gui_search_filters_and_artist_album_views(gui):
    gui.search.set('feat. guest')
    gui._apply_search()
    assert [s.title for s in gui.pages['library'].shown] == ['Sóng 3']
    gui.search.set('')
    gui.show_page('artists')
    artists = gui.pages['artists']
    assert [k for k, _ in artists.groups] == ['Ärtist 0', 'Ärtist 1']
    artists.list_table.tree.selection_set(('1',))
    gui.update()
    assert {s.artist for s in artists.shown} == {'Ärtist 1'}
    gui.show_page('albums')
    albums = gui.pages['albums']
    assert len(albums.groups) == 6 and albums.shown


@needs_display
def test_gui_playlist_create_add_reorder_remove_persist(gui, tmp_path):
    from oggcultist.player import PlaylistStore
    gui.show_page('playlists')
    page = gui.pages['playlists']
    page.new_name.set('Mïx ✓')
    page.create()
    assert page.current_name() == 'Mïx ✓' and page.new_name.get() == ''
    songs = gui.songs[:3]
    gui.add_to_playlist('Mïx ✓', songs)
    page.select_name('Mïx ✓')
    assert [s.title for s in page.shown] == [s.title for s in songs]
    page.table.tree.selection_set(('2',))
    page.table.tree.focus_set()
    page.table.tree.event_generate('<Control-Up>')
    gui.update()
    assert [s.title for s in page.shown] == [songs[0].title, songs[2].title, songs[1].title]
    page.table.tree.selection_set(('0',))
    page.table.tree.event_generate('<Delete>')
    gui.update()
    assert [s.title for s in page.shown] == [songs[2].title, songs[1].title]
    stored = PlaylistStore(paths.playlist_file()).playlists['Mïx ✓']
    assert stored == [str(songs[2].path), str(songs[1].path)]
    page.new_name.set('mïx ✓')
    page.create()                                             # duplicate refused without a dialog
    assert 'already exists' in gui.status.get()


@needs_display
def test_gui_converter_status_chips_and_filter(gui, tmp_path):
    from oggcultist.metadata import Track
    conv = gui.converter
    statuses = ['Ready', 'Ready', 'Done', 'Review', 'Collision', 'Duplicate', 'Error']
    conv.tracks = [Track(source=tmp_path / f'{i}.flac', size=1, title=f'T{i}', album='A', albumartist='B',
                         year='2000', track=i + 1, disc=1, status=s) for i, s in enumerate(statuses)]
    conv.refresh()
    assert conv.counts() == {'Ready': 2, 'Completed': 1, 'Needs review': 2, 'Skipped': 1, 'Failed': 1}
    assert conv.chips['Ready'].cget('text').endswith('2')
    conv.toggle_filter('Needs review')
    assert len(conv.tree.get_children()) == 2
    conv.toggle_filter('Needs review')
    assert len(conv.tree.get_children()) == 7
    assert conv.convert_btn.cget('text') == 'Convert 2 ready track(s)'
    conv.tree.selection_set(('6',))
    conv.details()
    assert 'Failed' in conv.detail.get('1.0', 'end')
    conv.tree.focus_set()
    conv.tree.event_generate('<Control-a>')
    gui.update()
    assert len(conv.selected()) == 7
    conv.exclude_selected()                                   # no modal; batch only
    assert conv.tracks == [] and 'untouched' in conv.status_var.get()


@needs_display
def test_gui_missing_ffplay_on_linux_is_a_notice_not_a_dialog(gui, monkeypatch):
    if sys.platform == 'win32':
        pytest.skip('Windows offers a consented download instead')
    from oggcultist.gui import player_view
    monkeypatch.setattr(player_view, 'find_ffplay', lambda: None)
    gui.player.play_list(gui.songs, 0)
    assert gui.player.song is None
    assert 'apt install ffmpeg' in gui.status.get() and gui.now.title_var.get() == 'Playback unavailable'


@needs_display
def test_gui_close_persists_settings_and_library_folder_with_unicode(gui, tmp_path):
    folder = tmp_path / 'Mý Músic ✓'
    folder.mkdir()
    gui.library_folder.set(str(folder))
    gui.volume.set(37)
    gui.show_page('albums')
    gui._on_close()
    data = json.loads(paths.settings_file().read_text(encoding='utf-8'))
    assert data['library'] == str(folder) and data['volume'] == 37 and data['page'] == 'albums'


@needs_display
def test_gui_window_is_usable_at_minimum_size(gui):
    gui.geometry('960x600')
    for key in ('library', 'playlists', 'converter'):
        gui.show_page(key)
        gui.update()
    conv = gui.converter
    for widget in (conv.convert_btn, conv.cancel_btn, conv.scan_btn, gui.now.play_btn):
        assert widget.winfo_ismapped()
        bottom = widget.winfo_rooty() + widget.winfo_height()
        assert bottom <= gui.winfo_rooty() + gui.winfo_height() + 1, widget


# --------------------------------------------------------------------------- v1.7.1 dark film-grain theme
def test_grain_textures_are_deterministic_and_subtle():
    pytest.importorskip('PIL')
    from oggcultist.gui import textures
    a = textures.grain('#161B1A', (64, 64), seed=3)
    b = textures.grain('#161B1A', (64, 64), seed=3)
    assert a.tobytes() == b.tobytes()                       # reproducible screenshots/builds
    values = list(a.tobytes()[0::3])   # red channel
    mean = sum(values) / len(values)
    assert abs(mean - 0x16) < 3                             # grain keeps the base colour
    assert 2 < (max(values) - min(values)) < 60              # visible but not static noise


def test_shaded_surface_has_flat_tileable_middle():
    from oggcultist.gui import textures
    img = textures.surface((40, 44), '#404040', '#202020', behind='#000000', radius=0, amount=0)
    middle = {img.getpixel((20, y)) for y in range(8, 36)}
    assert len(middle) == 1                                 # no gradient where ttk tiles (no banding)
    assert img.getpixel((20, 0)) != img.getpixel((20, 43))  # shading lives in the edges


@needs_display
def test_textured_elements_do_not_inflate_widget_sizes(gui):
    from tkinter import ttk
    label = ttk.Label(gui, text='x', style='TLabel')
    frame = ttk.Frame(gui, style='Card.TFrame')
    button = ttk.Button(gui, text='OK')
    gui.update_idletasks()
    # Image elements must not impose their 192 px tile as a minimum size.
    assert label.winfo_reqheight() < 40 and frame.winfo_reqheight() < 20
    assert button.winfo_reqheight() < 50


@needs_display
def test_dark_theme_and_chip_states(gui):
    from tkinter import ttk
    style = ttk.Style(gui)
    assert style.lookup('Treeview', 'background').lower() == '#16110f'
    assert 'Og.page' in style.element_names() and 'Og.Accent' in style.element_names()
    chip = gui.converter.chips['Failed']
    gui.converter.toggle_filter('Failed')
    assert chip.instate(['selected'])
    gui.converter.toggle_filter('Failed')
    assert not chip.instate(['selected'])
    assert hasattr(gui, '_og_textures') and len(gui._og_textures.images) > 20


@needs_display
def test_accent_gradient_matches_button_height(gui):
    """Gradient images are rendered at the button's natural height so ttk never stretches them."""
    from tkinter import ttk
    button = ttk.Button(gui, text='Ag ▶', style='Accent.TButton')
    gui.update_idletasks()
    images = [img for name, img in gui._og_textures.images.items() if name.startswith('Og.Accent-')]
    assert len(images) == 9      # v1.8.9: 5 states + 3 hover steps + the release flash
    assert {int(img.height()) for img in images} == {button.winfo_reqheight()}
    button.destroy()


def test_grain_is_lighter_on_bright_surfaces_and_mottle_is_faint_and_seamless():
    pytest.importorskip('PIL')
    from PIL import ImageChops, ImageFilter, ImageStat
    from oggcultist.gui import textures as tx
    dark = ImageStat.Stat(tx.grain('#1D1714', mottle=False).convert('L')).stddev[0]
    bright = ImageStat.Stat(tx.grain('#FDA629', mottle=False).convert('L')).stddev[0]
    assert bright < dark * 0.45, (bright, dark)
    # the mottle only lifts dark areas, by a few levels at most
    plain = tx.grain('#1D1714', mottle=False).convert('L').filter(ImageFilter.GaussianBlur(8))
    mottled = tx.grain('#1D1714').convert('L').filter(ImageFilter.GaussianBlur(8))
    lift = ImageChops.subtract(mottled, plain).getextrema()
    assert 2 <= lift[1] <= tx.MOTTLE
    assert tx.grain('#FDA629').tobytes() == tx.grain('#FDA629', mottle=False).tobytes()
    # seamless: the mottle field wraps at its edges
    field = tx._mottle((tx.TILE, tx.TILE), 0)
    w = field.width
    left = [field.getpixel((0, y)) for y in range(w)]
    right = [field.getpixel((w - 1, y)) for y in range(w)]
    interior = max(abs(field.getpixel((x, y)) - field.getpixel((x + 1, y))) for y in range(0, w, 4) for x in range(w - 1))
    assert max(abs(a - b) for a, b in zip(left, right)) <= interior


# ---------------------------------------------------------------- v1.7.2 brand (Ember Grooves)
def test_brand_resources_exist_and_icon_sizes_are_exact():
    PIL = pytest.importorskip('PIL')
    from PIL import Image
    from oggcultist import paths
    for name in ('icon.png', 'icon.ico', 'brand_symbol.png', 'brand_wordmark.png'):
        assert paths.resource_path(name).is_file(), name
    assert Image.open(paths.resource_path('icon.png')).size == (256, 256)
    for size in (16, 32, 48):
        assert Image.open(paths.resource_path(f'icon-{size}.png')).size == (size, size)
    ico = Image.open(paths.resource_path('icon.ico'))
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(ico.info['sizes'])


def test_brand_lockup_composes_with_transparency():
    pytest.importorskip('PIL')
    pytest.importorskip('tkinter')
    from oggcultist.gui import brand
    from PIL import Image
    from oggcultist import paths
    image = brand.compose_lockup(36, 18, 8)
    assert image.mode == 'RGBA' and image.height >= 36
    symbol = Image.open(paths.resource_path(brand.SYMBOL))
    symbol_width = round(symbol.width * 36 / symbol.height)                  # proportions kept, not squashed
    word = Image.open(paths.resource_path(brand.WORDMARK))
    assert image.width == symbol_width + 8 + round(word.width * 18 / word.height)
    assert image.getpixel((0, 0))[3] == 0          # transparent corner, no baked background


@needs_display
def test_sidebar_shows_brand_image_and_window_icons(gui):
    assert gui._brand_image is not None
    assert str(gui.brand_label.cget('image'))
    assert gui.brand_label.winfo_reqwidth() <= 196
    assert len(gui._icons) == 4


@needs_display
def test_brand_falls_back_to_text_when_resources_missing(tmp_path, monkeypatch):
    import tkinter as tk
    from oggcultist import paths
    from oggcultist.gui import brand
    monkeypatch.setattr(paths, 'resource_path', lambda *parts: tmp_path.joinpath(*parts))
    root = tk.Tk()
    try:
        assert brand.sidebar_lockup(root, 170) is None
        assert brand.window_icons(root) == []
    finally:
        root.destroy()


# ---------------------------------------------------------------- v1.7.4 shuffle / repeat / click-to-seek
@needs_display
def test_mode_buttons_toggle_persist_and_follow_repeat_one(gui):
    from oggcultist.gui import app as gui_app
    gui.player.play_list(gui.songs, 2)
    assert gui.now.shuffle_btn.cget('style') == 'Mode.TButton'
    gui.now.shuffle_btn.invoke()
    assert gui.player.shuffle and gui.now.shuffle_btn.cget('style') == 'ModeOn.TButton'
    assert 'Shuffle on' in gui.status.get()
    for expected in ('All', 'Album', 'One'):          # 2.0: beside the repeat icon
        gui.now.repeat_btn.invoke()
        assert gui.now.repeat_btn.cget('text') == expected
    assert gui_app.load_settings()['shuffle'] is True and gui_app.load_settings()['repeat'] == 'one'
    playing = gui.player.song
    gui.player.transport._current.process.code = 0      # the song ends by itself
    gui.player.tick()
    assert gui.player.song.path == playing.path          # repeat one plays it again
    gui.now.repeat_btn.invoke()
    # 2.0: repeat is an icon; it only adds the mode's name when repeat is on
    assert gui.now.repeat_btn.cget('text') == '' and gui.player.repeat == 'off'


@needs_display
def test_repeat_album_from_gui_stays_in_album(gui):
    gui.player.play_list(gui.songs, 0)
    album = gui.player.song.album
    gui.player.set_repeat('album')
    seen = set()
    for _ in range(6):
        gui.player.transport._current.process.code = 0
        gui.player.tick()
        seen.add(gui.player.song.album)
    assert seen == {album}


@needs_display
def test_clicking_the_seek_bar_jumps_to_that_point(gui):
    gui.player.play_list(gui.songs, 1)
    gui.update()
    seek = gui.now.seek
    gui.geometry('1240x780'); gui.update()
    width = seek.winfo_width()
    assert width > 100
    seeks = []
    gui.player.seek = lambda seconds: seeks.append(seconds)
    seek.event_generate('<ButtonPress-1>', x=int(width * 0.75), y=seek.winfo_height() // 2)
    seek.event_generate('<ButtonRelease-1>', x=int(width * 0.75), y=seek.winfo_height() // 2)
    gui.update()
    duration = gui.player.song.duration
    assert len(seeks) == 1
    assert seeks[0] == pytest.approx(duration * 0.75, abs=duration * 0.05)
    assert not gui.now.dragging


@needs_display
def test_clicking_the_volume_bar_sets_that_volume(gui):
    gui.update()
    slider = gui.now.volume_slider
    volumes = []
    gui.player.set_volume = lambda value: volumes.append(value)
    width = slider.winfo_width()
    slider.event_generate('<ButtonPress-1>', x=int(width * 0.25), y=slider.winfo_height() // 2)
    slider.event_generate('<ButtonRelease-1>', x=int(width * 0.25), y=slider.winfo_height() // 2)
    gui.update()
    assert volumes and abs(volumes[-1] - 25) <= 6


# ---------------------------------------------------------------- v1.7.5 gradient icons, hold ⏭ to fast-forward
@needs_display
def test_transport_buttons_use_gradient_icons(gui):
    for button in (gui.now.prev_btn, gui.now.next_btn, gui.now.stop_btn, gui.now.play_btn):
        assert str(button.cget('image')), button
    assert str(gui.now.next_btn.cget('compound')) == 'image'


def _press_next(gui, hold_s):
    import time
    button = gui.now.next_btn
    button.update()
    x, y = button.winfo_width() // 2, button.winfo_height() // 2
    button.event_generate('<Enter>', x=x, y=y)
    button.event_generate('<ButtonPress-1>', x=x, y=y)
    end = time.monotonic() + hold_s
    while time.monotonic() < end:
        gui.update()
        time.sleep(0.01)
    speed_while_held = gui.player.transport.speed
    button.event_generate('<ButtonRelease-1>', x=x, y=y)
    gui.update()
    return speed_while_held


@needs_display
def test_quick_click_on_next_skips_song(gui):
    gui.player.play_list(gui.songs, 1)
    gui.now.HOLD_MS = 300
    assert _press_next(gui, 0.05) == 1.0
    assert gui.player.song is gui.songs[2]


@needs_display
def test_holding_next_fast_forwards_then_returns_to_normal_without_skipping(gui, monkeypatch):
    gui.player.play_list(gui.songs, 1)
    speeds = []
    transport = gui.player.transport
    real = transport.set_speed
    monkeypatch.setattr(transport, 'set_speed', lambda s: (speeds.append(s), real(s)))
    gui.now.HOLD_MS, gui.now.RAMP_MS = 80, 150
    assert _press_next(gui, 0.4) == 8.0          # 4× after the hold, then 8×
    assert speeds == [4.0, 8.0, 1.0]
    assert gui.player.song is gui.songs[1]        # still the same song: no skip on release
    assert transport.speed == 1.0 and 'Normal speed' in gui.status.get()


import shutil  # noqa: E402
from test_v18_cover_editor import library  # noqa: E402,F401  (fixture)


# ---------------------------------------------------------------- v1.8.0 fixed controls, live volume, album art page
@needs_display
def test_controls_stay_put_when_the_song_changes(gui):
    from oggcultist.player import Song
    gui.geometry('1240x780'); gui.update()
    bar, play = gui.now, gui.now.play_btn

    def positions():
        gui.update()
        return {name: button.winfo_rootx() for name, button in
                (('play', play), ('prev', bar.prev_btn), ('next', bar.next_btn), ('stop', bar.stop_btn),
                 ('shuffle', bar.shuffle_btn), ('repeat', bar.repeat_btn))}
    idle = positions()
    centre = bar.winfo_rootx() + bar.winfo_width() / 2
    assert abs(play.winfo_rootx() + play.winfo_width() / 2 - centre) <= 3      # play/pause in the middle
    gui.player.play_list(gui.songs, 0)
    playing = positions()
    import dataclasses
    long_song = dataclasses.replace(gui.songs[1], title='An Extremely Long Song Title That Goes On And On',
                                    track_artist='Somebody With A Very Long Name feat. Many Guests')
    gui.player.play_list([long_song], 0)
    long_title = positions()
    gui.player.set_repeat('album')
    gui.player.set_shuffle(True)
    modes = positions()
    assert idle == playing == long_title == modes


@needs_display
def test_volume_follows_the_slider_while_dragging(gui):
    import time
    gui.player.play_list(gui.songs, 0)
    calls = []
    real = gui.player.set_volume
    gui.player.set_volume = lambda v: (calls.append(v), real(v))
    slider = gui.now.volume_slider
    gui.update()
    width, y = slider.winfo_width(), slider.winfo_height() // 2
    slider.event_generate('<ButtonPress-1>', x=int(width * 0.9), y=y)
    for i in range(30):                                   # a 0.6 s drag from 90 % down to 30 %
        slider.event_generate('<B1-Motion>', x=int(width * (0.9 - i * 0.02)), y=y)
        gui.update()
        time.sleep(0.02)
    assert calls, 'volume should change during the drag, not only on release'
    slider.event_generate('<ButtonRelease-1>', x=int(width * 0.3), y=y)
    end = time.monotonic() + 1
    while time.monotonic() < end:
        gui.update()
        time.sleep(0.02)
    assert len(calls) <= 8, f'changes must be paced, got {len(calls)}'
    assert abs(gui.player.transport.volume - 30) <= 6


@needs_display
@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg missing')
def test_album_art_page_edits_and_applies(gui, library, monkeypatch):
    from tkinter import messagebox
    from oggcultist.converter.cover_editor import CoverEditor
    _src, out = library
    asked = []
    monkeypatch.setattr(messagebox, 'askyesno', lambda title, text, **k: (asked.append(text), True)[1])
    gui.library_folder.set(str(out))
    gui.show_page('art')
    page = gui.pages['art']
    gui.update()
    assert [a.album for a in page.albums] == ['Ash Lanes', 'Salt Hymns']
    page.list_table.tree.selection_set('1')
    gui.update()
    assert page.album_title.get() == 'Salt Hymns — Tide Choir'
    page.colour_var.set('#2A4B7C')
    page.line_vars[0].set('SALT')
    page._render_preview()
    assert page._photo is not None and 'Only the covers Oggcultist made' in page.note.get()
    page.line_vars[1].set('✦')
    page._render_preview()
    assert "can't draw" in page.note.get() and str(page.apply_btn.cget('state')) == 'disabled'
    page.line_vars[1].set('Tide Choir')
    page._render_preview()
    page.apply()
    import time
    end = time.monotonic() + 20
    while page.working and time.monotonic() < end:
        gui.update()
        time.sleep(0.02)
    assert asked and 'Change the cover of 3 songs in "Salt Hymns"' in asked[0]
    assert 'cover updated in 3 songs' in gui.status.get()
    salt = [a for a in CoverEditor(out).albums() if a.album == 'Salt Hymns'][0]
    assert salt.design.colour == '2A4B7C' and salt.design.lines[0] == 'SALT'


# ---------------------------------------------------------------- v1.8.2 media buttons, Loop One holds, Loop Album = last selected
@needs_display
def test_media_buttons_drive_the_player_and_loop_one_only_restarts(gui):
    from oggcultist.gui.media_keys import MediaControls
    media = MediaControls(gui)
    gui.player.play_list(gui.songs, 1)
    song = gui.player.song
    media.run('play_pause')
    assert gui.player.transport.paused
    media.run('pause')                                   # already paused: nothing happens
    assert gui.player.transport.paused
    media.run('play')
    assert gui.player.transport.playing
    gui.player.set_repeat('one')
    assert 'go back to its start' in gui.status.get()
    media.run('next')
    assert gui.player.song.path == song.path             # headset ⏭ under Loop One: same song, from the start
    media.run('previous')
    assert gui.player.song.path == song.path
    gui.player.set_repeat('off')
    media.run('next')
    assert gui.player.song.path != song.path
    media.run('stop')
    assert gui.player.song is None


@needs_display
def test_loop_album_locks_onto_the_last_selected_song(gui):
    gui.player.play_list(gui.songs, 0)                   # playing one album...
    playing_album = gui.player.song.album
    library = gui.pages['library']
    gui.show_page('library'); gui.update()
    other = next(i for i, s in enumerate(library.shown) if s.album != playing_album)
    library.table.tree.selection_set(str(other)); library.table.tree.focus(str(other)); gui.update()
    gui.player.set_repeat('album')                       # ...but a song from another album was selected last
    assert gui.player.order.locked_album == library.shown[other].album
    assert 'starts when this song ends' in gui.status.get()
    gui.player.transport._current.process.code = 0       # current song ends
    gui.player.tick()
    assert gui.player.song.album == library.shown[other].album
