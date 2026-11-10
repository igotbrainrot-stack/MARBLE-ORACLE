"""Where Oggcultist's files live — one place for every path decision.

Three kinds of location are kept strictly apart:

* **Application files** (code, bundled resources, optional bundled tools):
  read-only. For a PyInstaller one-file build these live in a temporary
  extraction folder that is deleted on exit, so nothing mutable may go there.
* **Per-user data** (settings, playlists, logs, the private FFmpeg copy):
  the same locations as every earlier version, so upgrading moves nothing.
* **Library data** (completion ledger, cover database, conversion reports):
  stays inside the destination music library at ``<library>/.oggcultist``,
  exactly as before. It is never moved by this module.

Portable mode
-------------
If a folder named ``OggcultistData`` exists next to the executable (or next to
``launch.py`` when running from source), per-user data is kept there instead,
so the whole program can live on a USB stick. ``OGGCULTIST_DATA_DIR`` overrides
both. On first use the existing settings and playlists are *copied* (never
moved) into the portable folder; the originals are left untouched.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = 'Oggcultist'
PORTABLE_FOLDER = 'OggcultistData'
DATA_ENV = 'OGGCULTIST_DATA_DIR'
_PACKAGE_DIR = Path(__file__).resolve().parent


def is_frozen() -> bool:
    """True inside a PyInstaller (or similar) executable."""
    return bool(getattr(sys, 'frozen', False))


def app_dir() -> Path:
    """Folder the user launched from: the .exe's folder, or the source folder."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _PACKAGE_DIR.parent


def bundle_dir() -> Path:
    """Read-only folder holding bundled files (PyInstaller's _MEIPASS when frozen)."""
    meipass = getattr(sys, '_MEIPASS', None)
    return Path(meipass) if meipass else _PACKAGE_DIR.parent


def resource_path(*parts: str) -> Path:
    """Locate a bundled resource independently of the current working directory."""
    candidate = _PACKAGE_DIR.joinpath('resources', *parts)
    if candidate.exists():
        return candidate
    return bundle_dir().joinpath('oggcultist', 'resources', *parts)


def portable_root(environ=None) -> Path | None:
    """The portable data folder, if portable mode is active."""
    env = os.environ if environ is None else environ
    override = env.get(DATA_ENV)
    if override:
        return Path(override).expanduser()
    marker = app_dir() / PORTABLE_FOLDER
    return marker if marker.is_dir() else None


def _windows_root(env, key: str, fallback: tuple[str, ...]) -> Path:
    value = env.get(key)
    return Path(value) if value else Path.home().joinpath(*fallback)


def config_dir(environ=None, platform: str | None = None) -> Path:
    """settings.json and playlists.json (unchanged location since v1.5)."""
    env = os.environ if environ is None else environ
    portable = portable_root(env)
    if portable is not None:
        return portable / 'config'
    if (platform or sys.platform) == 'win32':
        return _windows_root(env, 'APPDATA', ('AppData', 'Roaming')) / APP_NAME
    base = env.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / APP_NAME


def logs_dir(environ=None, platform: str | None = None) -> Path:
    env = os.environ if environ is None else environ
    portable = portable_root(env)
    if portable is not None:
        return portable / 'logs'
    if (platform or sys.platform) == 'win32':
        base = env.get('LOCALAPPDATA') or env.get('TEMP') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / APP_NAME / 'logs'
    base = env.get('XDG_STATE_HOME') or str(Path.home() / '.local' / 'state')
    return Path(base) / 'oggcultist' / 'logs'


def private_tools_dir(environ=None, platform: str | None = None) -> Path:
    """The user's private FFmpeg copy (unchanged location since v1.5)."""
    env = os.environ if environ is None else environ
    portable = portable_root(env)
    if portable is not None:
        return portable / 'tools' / 'ffmpeg' / 'bin'
    if (platform or sys.platform) == 'win32':
        return _windows_root(env, 'LOCALAPPDATA', ('AppData', 'Local')) / APP_NAME / 'ffmpeg' / 'bin'
    return Path.home() / '.local' / 'share' / 'oggcultist' / 'ffmpeg' / 'bin'


def bundled_tools_dirs() -> list[Path]:
    """Folders that may contain FFmpeg shipped *with* the program, best first.

    ``tools/`` next to the executable (portable-folder distribution) wins over
    tools embedded inside a one-file executable.
    """
    found = []
    for folder in (app_dir() / 'tools', bundle_dir() / 'tools'):
        if folder.is_dir() and folder not in found:
            found.append(folder)
    return found


def settings_file(environ=None) -> Path:
    return config_dir(environ) / 'settings.json'


def playlist_file(environ=None) -> Path:
    return config_dir(environ) / 'playlists.json'


def standard_config_dir(environ=None, platform: str | None = None) -> Path:
    """The non-portable config folder, used as the migration source."""
    env = dict(os.environ if environ is None else environ)
    env.pop(DATA_ENV, None)
    if (platform or sys.platform) == 'win32':
        return _windows_root(env, 'APPDATA', ('AppData', 'Roaming')) / APP_NAME
    base = env.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / APP_NAME


def migrate_to_portable(environ=None) -> list[str]:
    """Copy settings and playlists into a new portable folder; never move or delete.

    Returns the names copied. Existing portable files are never overwritten.
    """
    env = os.environ if environ is None else environ
    portable = portable_root(env)
    if portable is None:
        return []
    source = standard_config_dir(env)
    target = portable / 'config'
    if source.resolve() == target.resolve():
        return []
    copied = []
    for name in ('settings.json', 'playlists.json'):
        old, new = source / name, target / name
        if old.is_file() and not new.exists():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, new)
            copied.append(name)
    if copied:
        note = target / 'MIGRATED_FROM.txt'
        if not note.exists():
            note.write_text(f'Copied from {source}\nThe original files were left in place.\n', encoding='utf-8')
    return copied


def prepend_to_path(folder: Path, environ=None) -> None:
    env = os.environ if environ is None else environ
    current = env.get('PATH', '')
    entries = [p.casefold() for p in current.split(os.pathsep) if p]
    if str(folder).casefold() not in entries:
        env['PATH'] = str(folder) + (os.pathsep + current if current else '')


def configure_tool_path(environ=None) -> list[Path]:
    """Put bundled tools first, then the private user copy, on this process's PATH.

    Child processes (FFmpeg, FFprobe, FFplay) inherit the result. Returns the
    folders added, highest priority first.
    """
    env = os.environ if environ is None else environ
    folders = [*bundled_tools_dirs()]
    private = private_tools_dir(env)
    if private.is_dir():
        folders.append(private)
    for folder in reversed(folders):
        prepend_to_path(folder, env)
    return folders
