import importlib.util
import sys
# PyInstaller build recipe for Oggcultist. Run through packaging/build.py.
#
# Environment options (all optional):
#   OGGCULTIST_ONEDIR=1          build a folder instead of a single .exe
#   OGGCULTIST_BUNDLE_TOOLS=DIR  embed ffmpeg/ffprobe/ffplay from DIR into the build
#                                (see docs/development/PACKAGING.md for licensing duties)
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
WINDOWS = sys.platform == 'win32'
ONEDIR = os.environ.get('OGGCULTIST_ONEDIR') == '1'
TOOLS = os.environ.get('OGGCULTIST_BUNDLE_TOOLS', '')

# 2.0.5: Uberata must be bundled in the executable and verified before building.
FONT_DIR = ROOT / 'oggcultist' / 'resources' / 'fonts'
if not (FONT_DIR / 'OFL_UBERATA_CLEAR.txt').is_file() or not (FONT_DIR / 'NOTO_SOURCE_NOTICE.md').is_file():
    raise SystemExit('Missing Uberata font licence/attribution in oggcultist/resources/fonts')
import hashlib
if not (FONT_DIR / 'Uberata-Clear.ttf').is_file() or hashlib.sha256((FONT_DIR / 'Uberata-Clear.ttf').read_bytes()).hexdigest() != '248df02a4e0c52c541456ac19f29a2ccc50ff0b12428982a378d1576a5097482':
    raise SystemExit('Required Uberata Clear v3.0 TTF missing or wrong version')

datas = [(str(ROOT / 'oggcultist' / 'resources'), 'oggcultist/resources')]
binaries = []
if TOOLS:
    suffix = '.exe' if WINDOWS else ''
    for name in ('ffmpeg', 'ffprobe', 'ffplay'):
        path = Path(TOOLS) / (name + suffix)
        if not path.is_file():
            raise SystemExit(f'OGGCULTIST_BUNDLE_TOOLS is missing {path.name}')
        binaries.append((str(path), 'tools'))
    for extra in ('LICENSE.txt', 'README.txt'):
        if (Path(TOOLS) / extra).is_file():
            datas.append((str(Path(TOOLS) / extra), 'tools'))

a = Analysis(
    [str(ROOT / 'packaging' / 'entry.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    # jeepney (Linux media buttons, MPRIS) is imported lazily; include it when it is installed
    hiddenimports=['PIL._tkinter_finder', 'oggcultist.gui.media_keys']
                  + (['jeepney', 'jeepney.io.blocking', 'jeepney.bus_messages']
                     if sys.platform.startswith('linux') and importlib.util.find_spec('jeepney') else []),
    excludes=['pytest', 'unittest', 'pydoc', 'test', 'oggcultist.font_source', 'fontTools', 'shapely'],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = str(ROOT / 'oggcultist' / 'resources' / 'icon.ico')
version = str(ROOT / 'packaging' / 'windows' / 'version_info.txt') if WINDOWS else None

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Oggcultist', console=False,
              icon=icon, version=version, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name='Oggcultist', upx=False)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Oggcultist', console=False,
              icon=icon, version=version, upx=False, runtime_tmpdir=None)
