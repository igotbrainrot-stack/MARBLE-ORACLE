"""Compatibility alias for ``oggcultist.services.ffmpeg_setup`` (the FFmpeg first-run helper).

``python setup_ffmpeg.py`` still runs the interactive FFmpeg setup.
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from oggcultist.services import ffmpeg_setup as _impl  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(_impl.main())
sys.modules[__name__] = _impl
