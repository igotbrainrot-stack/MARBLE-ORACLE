"""Single-font Oggcultist typography: bundled Uberata Clear v3.0.

Uberata's exact user-provided TTF and licence files ship inside the program.
There is no import, Downloads scanning, extraction or system-wide installation.
All application text roles use only this font family.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import paths

HEADING_FAMILY = BODY_FAMILY = FAMILY = CLEAR_FAMILY = 'Uberata Clear'
HEADING_SETTING = 'heading_font'  # legacy preferences safely ignored
BODY_SETTING = 'body_font'
FONT_NAME = 'Uberata-Clear.ttf'
FONT_SHA256 = '248df02a4e0c52c541456ac19f29a2ccc50ff0b12428982a378d1576a5097482'
FONT_VERSION = '3.000'
LICENCE_FILES = ('OFL_UBERATA_CLEAR.txt', 'NOTO_SOURCE_NOTICE.md')


@dataclass(frozen=True)
class FontInfo:
    filename: str
    family: str
    style: str
    use: str
    key: str
    licences: tuple[str, ...]
    sha256: str

    @property
    def title(self):
        return f'{self.family} {self.style} · v3.0'


FONTS = (FontInfo(FONT_NAME, FAMILY, 'Regular',
                  'All interface text, headings, buttons and newly generated album covers',
                  'uberata-clear-v3', LICENCE_FILES, FONT_SHA256),)
FONT_BY_KEY = {x.key: x for x in FONTS}
HEADING_FILE = FONT_NAME
BODY_FILES = {'regular': FONT_NAME, 'bold': FONT_NAME}
EXPORT_FOLDER = 'Oggcultist Uberata Fonts'
_registered = None


def font_cache() -> Path:
    """Historical cache location (read-only for v2.0.5; never required)."""
    return paths.config_dir() / 'fonts' / 'uberata-v3'


def _valid(path: Path) -> bool:
    """Reject missing, damaged or wrong-release font binaries."""
    try:
        if not path.is_file():
            return False
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest() == FONT_SHA256
    except OSError:
        return False


def resource(name: str) -> Path | None:
    """Resolve *only* the bundled Uberata v3.0 and its licence files.

    Deliberately do not use an older user cache: a stale app-data copy must
    never override the exact font included in the versioned release.
    """
    if name not in (FONT_NAME, *LICENCE_FILES):
        return None
    path = paths.resource_path('fonts', name)
    if name == FONT_NAME:
        return path if _valid(path) else None
    return path if path.is_file() else None


def prepare_uberata() -> bool:
    """Validate the built-in font. No Downloads-folder scan or extraction."""
    return resource(FONT_NAME) is not None


def heading_file() -> Path | None:
    prepare_uberata()
    return resource(FONT_NAME)


def body_file(weight: str = 'regular') -> Path | None:
    return heading_file()


def font_file(weight: str = 'regular', choice=None) -> Path | None:
    return heading_file()


def normalise_heading_choice(value=None):
    return 'uberata'


def normalise_body_choice(value=None):
    return 'uberata'


def heading_family(choice=None):
    return FAMILY


def body_family(choice=None):
    return FAMILY


def saved_heading_choice():
    return 'uberata'


def missing_or_damaged() -> list[str]:
    return [] if prepare_uberata() else [FONT_NAME + ' (missing or corrupt in application resources)']


def require_complete_bundle(*, strict: bool = False) -> None:
    """Refuse to release or export a program missing the bundled font."""
    if not prepare_uberata():
        raise FileNotFoundError('Bundled Uberata Clear v3.0 is missing or corrupt; extract the complete program ZIP again.')
    if strict:
        for name in LICENCE_FILES:
            if not resource(name):
                raise FileNotFoundError(f'Uberata release licence missing: {name}')


def register_private_fonts(platform: str | None = None, gdi32=None, fontconfig=None) -> bool:
    global _registered
    if _registered is not None and gdi32 is None and fontconfig is None:
        return _registered
    font = heading_file()
    if font is None:
        return False
    platform = platform or sys.platform
    try:
        if platform == 'win32':
            import ctypes
            lib = gdi32 or ctypes.WinDLL('gdi32')
            ok = bool(lib.AddFontResourceExW(str(font), 0x10, None))
        elif platform.startswith('linux'):
            import ctypes
            import ctypes.util
            lib = fontconfig or ctypes.CDLL(ctypes.util.find_library('fontconfig') or 'libfontconfig.so.1')
            if fontconfig is None:
                lib.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
            ok = bool(lib.FcConfigAppFontAddFile(None, str(font).encode()))
        else:
            ok = False
    except (OSError, ImportError, AttributeError):
        ok = False
    if gdi32 is None and fontconfig is None:
        _registered = ok
    return ok


def ensure_ui_fonts_loaded(root, heading_choice=None) -> bool:
    from tkinter import font as tkfont
    return FAMILY in set(tkfont.families(root))


INSTALL_TEXT = '''Oggcultist uses Uberata Clear v3.0 throughout its interface.\n\nThe font is installed privately for Oggcultist and does not change system fonts.\nIt was adapted from Noto Serif under SIL OFL 1.1; see the included licence notices.\n'''


def export_fonts(parent: Path | str, font_key: str | None = None) -> Path:
    parent = Path(parent)
    if not parent.is_dir():
        raise FileNotFoundError(f'Folder not found: {parent}')
    if font_key is not None and font_key not in FONT_BY_KEY:
        raise ValueError(f'Unknown font: {font_key}')
    require_complete_bundle(strict=True)
    for i in range(1, 1000):
        folder = parent / (EXPORT_FOLDER if i == 1 else f'{EXPORT_FOLDER} ({i})')
        try:
            folder.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError('No available folder name')
    try:
        for name in (FONT_NAME, *LICENCE_FILES):
            shutil.copyfile(resource(name), folder / name)
        (folder / 'HOW TO INSTALL.txt').write_text(INSTALL_TEXT, encoding='utf-8')
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder
