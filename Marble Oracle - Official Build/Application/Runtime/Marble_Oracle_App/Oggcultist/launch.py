"""Start Oggcultist from source: ``python launch.py`` (GUI) or ``python launch.py --cli ...``.

The program itself lives in the ``oggcultist`` package (see oggcultist/startup.py).
Importing this file gives you that module, so ``import launch`` keeps working.
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _keep_program_folder_clean() -> None:
    """Send Python's bytecode cache to the user cache folder, not the program folder.

    Must run before importing oggcultist (portable: OggcultistData/cache).
    """
    import os
    if sys.pycache_prefix or os.environ.get('PYTHONPYCACHEPREFIX'):
        return
    here = Path(__file__).resolve().parent
    if (here / 'OggcultistData').is_dir():
        base = here / 'OggcultistData' / 'cache'
    elif sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Oggcultist' / 'cache'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'oggcultist'
    sys.pycache_prefix = str(base / 'pycache')


_keep_program_folder_clean()

from oggcultist import startup as _startup  # noqa: E402

if __name__ == '__main__':
    _startup.main()
else:
    sys.modules[__name__] = _startup
