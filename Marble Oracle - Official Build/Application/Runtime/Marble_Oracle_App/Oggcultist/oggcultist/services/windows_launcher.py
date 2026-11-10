"""Quiet Windows GUI bootstrap, without VBScript, WSH, PowerShell, or a console.

Launched by Oggcultist.pyw (the standard Python Windows GUI file association).
WINDOWS LAUNCHER.bat (next to the Oggcultist folder) prepares Python and covers machines without that association.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000  # Windows subprocess creation flag


class StartupError(RuntimeError):
    pass


def logs_dir(environ=None):
    env = os.environ if environ is None else environ
    location = env.get('LOCALAPPDATA') or env.get('TEMP') or tempfile.gettempdir()
    return Path(location) / 'Oggcultist' / 'logs'


def _show_error(message: str) -> None:
    """Display a user-friendly startup error even when pythonw has no stderr."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror('Oggcultist startup', message, parent=root)
        finally:
            root.destroy()
    except Exception:
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, message, 'Oggcultist startup', 0x10)
            except Exception:
                pass


def venv_gui_python(folder: Path) -> Path:
    return folder / '.venv' / 'Scripts' / 'pythonw.exe'


def _requirements_signature(folder: Path) -> str:
    # Only our dependency list and the Python major/minor version control venv requirements.
    payload = (folder / 'requirements.txt').read_bytes() + f'|{sys.version_info[:2]}'.encode('ascii')
    return hashlib.sha256(payload).hexdigest()


def _run(cmd: list[str], root: Path, stream, *, runner=subprocess.run) -> None:
    """Run venv/pip/GUI child with no console on Windows; log stdout and stderr."""
    result = runner([str(v) for v in cmd], cwd=str(root), stdin=subprocess.DEVNULL,
                    stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                    check=False)
    if result.returncode != 0:
        raise StartupError(f'Startup command failed (exit {result.returncode}): {Path(str(cmd[0])).name}')


def run(root: Path, stream, *, runner=subprocess.run) -> None:
    root = root.resolve()
    if sys.version_info < (3, 10):
        raise StartupError('Python 3.10 or newer is required. Install Python from python.org with Tcl/Tk support.')
    if not (root / 'launch.py').is_file() or not (root / 'requirements.txt').is_file():
        raise StartupError('Program files are missing. Extract the entire Oggcultist ZIP before launching.')

    env_py = venv_gui_python(root)
    pip_py = root / '.venv' / 'Scripts' / 'python.exe'
    if not env_py.is_file() or not pip_py.is_file():
        print('Creating private Python environment...', file=stream, flush=True)
        _run([sys.executable, '-m', 'venv', str(root / '.venv')], root, stream, runner=runner)
        if not env_py.is_file() or not pip_py.is_file():
            raise StartupError('Python environment setup did not create pythonw.exe. Check the startup log.')

    marker = root / '.venv' / '.oggcultist_requirements'
    signature = _requirements_signature(root)
    if not marker.is_file() or marker.read_text(encoding='ascii').strip() != signature:
        print('Installing required Python packages...', file=stream, flush=True)
        _run([str(pip_py), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')],
             root, stream, runner=runner)
        marker.write_text(signature, encoding='ascii')

    print('Starting Oggcultist music player...', file=stream, flush=True)
    _run([str(env_py), str(root / 'launch.py'), '--windowless'], root, stream, runner=runner)


def main(root: Path | None = None) -> int:
    """Never leave a silent failure: write the log and display a GUI dialog."""
    root = root or Path(__file__).resolve().parents[2]
    logfile = None
    try:
        folder = logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        logfile = folder / 'launcher.log'
        with logfile.open('a', encoding='utf-8', buffering=1) as stream:
            print('\n=== Oggcultist startup ===', file=stream)
            try:
                run(root, stream)
            except Exception:
                traceback.print_exc(file=stream)
                raise
        return 0
    except Exception as exc:
        location = str(logfile) if logfile else 'the local Oggcultist logs folder'
        _show_error(f'Oggcultist could not open.\n\n{exc}\n\n'
                    f'Details: {location}\n\n'
                    'Run DIAGNOSE_WINDOWS.bat (inside the Oggcultist folder) to see the error in a command window.')
        return 1
