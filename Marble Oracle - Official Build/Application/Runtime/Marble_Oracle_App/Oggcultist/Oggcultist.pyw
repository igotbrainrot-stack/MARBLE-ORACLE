"""Double-click to open Oggcultist with no console window (Python on Windows).

Creates a private Python environment on first run, then starts the music player.
If nothing appears, run DIAGNOSE_WINDOWS.bat (in this folder) to see what went wrong.
The usual way to start is WINDOWS LAUNCHER.bat, next to this folder.
"""
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if not sys.pycache_prefix and not os.environ.get('PYTHONPYCACHEPREFIX'):
    # Keep compiled-bytecode caches out of the program folder.
    _cache = (_HERE / 'OggcultistData' / 'cache' if (_HERE / 'OggcultistData').is_dir() else
              Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Oggcultist' / 'cache')
    sys.pycache_prefix = str(_cache / 'pycache')
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from oggcultist.windows_launcher import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main(_HERE))
