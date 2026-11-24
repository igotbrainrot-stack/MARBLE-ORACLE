"""Entry point for the installed ``overcast`` command and ``python -m overcast``.

The command opens the desktop app; ``overcast cli ...`` (or the separate ``overcast-cli`` command) runs the
headless tools. A missing Tkinter is reported with the install command for the user's platform instead of a
traceback.
"""
from __future__ import annotations

import sys

from . import APP_NAME, TAGLINE, __version__

_TK_HELP = {
    'linux': 'Fedora: sudo dnf install python3-tkinter\n'
             'Debian/Ubuntu: sudo apt install python3-tk\n'
             'Arch: sudo pacman -S tk',
    'darwin': 'Install Python from python.org (it includes Tk), or: brew install python-tk',
    'win32': 'Re-run the Python installer and tick "tcl/tk and IDLE".',
}


def _tk_missing_message(error: Exception) -> str:
    platform = 'linux' if sys.platform.startswith('linux') else sys.platform
    hint = _TK_HELP.get(platform, 'Install the Tk bindings for your Python.')
    return (f'{APP_NAME.title()} needs Tkinter, which this Python ({sys.executable}) does not have.\n'
            f'({error})\n\n{hint}\n\nThe command-line tools still work: overcast-cli --help')


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] in (['--version'], ['-V']):
        print(f'{APP_NAME.title()} {__version__} — {TAGLINE}')
        return 0
    if args[:1] in (['--help'], ['-h']):
        print(f'{APP_NAME.title()} {__version__}\n\n'
              'usage: overcast            open the desktop app\n'
              '       overcast cli ...    headless tools (same as overcast-cli; try overcast cli --help)\n'
              '       overcast --version')
        return 0
    if args[:1] == ['cli']:
        from .cli import main as cli_main
        result = cli_main(args[1:])
        return result if isinstance(result, int) else 0
    if args:
        print(f'overcast: unknown argument {args[0]!r} (try overcast --help)', file=sys.stderr)
        return 2
    try:
        import tkinter  # noqa: F401
    except ImportError as error:
        print(_tk_missing_message(error), file=sys.stderr)
        return 1
    from .ui import run_standalone
    run_standalone()
    return 0


def cli() -> int:
    from .cli import main as cli_main
    result = cli_main()
    return result if isinstance(result, int) else 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
