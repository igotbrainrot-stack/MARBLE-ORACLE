"""Minimal launch bridge for Oggcultist when hosted by another desktop suite.

This adapter does NOT alter Oggcultist's UI, install software or share a Tk root.
It starts the full unmodified Oggcultist application in an isolated process and
returns its Popen handle so the host suite can monitor or terminate it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import paths


def program_root(root: str | Path | None = None) -> Path:
    """Locate the source folder containing launch.py, with explicit-root support."""
    source = Path(root).expanduser().resolve() if root is not None else Path(__file__).resolve().parents[1]
    if (source / 'Oggcultist' / 'launch.py').is_file():
        source /= 'Oggcultist'
    if not (source / 'launch.py').is_file() or not (source / 'oggcultist' / 'startup.py').is_file():
        raise FileNotFoundError(f'Oggcultist source folder not found: {source}. Keep the full source package together.')
    return source


def source_python(root: str | Path | None = None, explicit: str | Path | None = None) -> Path:
    """Choose the program's private venv when available, or a host-provided Python.

    Explicit Python and OGGCULTIST_PYTHON override the venv. For a frozen host
    suite, an external interpreter is required: never try to run the host EXE
    as if it were a Python interpreter.
    """
    home = program_root(root)
    user_choice = explicit or os.environ.get('OGGCULTIST_PYTHON')
    if user_choice:
        interpreter = Path(user_choice).expanduser()
        if not interpreter.is_file():
            raise FileNotFoundError(f'Configured Oggcultist Python does not exist: {interpreter}')
    else:
        if os.name == 'nt':
            candidates = [home / '.venv' / 'Scripts' / 'pythonw.exe', home / '.venv' / 'Scripts' / 'python.exe']
        else:
            candidates = [home / '.venv' / 'bin' / 'python3', home / '.venv' / 'bin' / 'python']
        interpreter = next((p for p in candidates if p.is_file()), None)
        if interpreter is None:
            if getattr(sys, 'frozen', False):
                raise RuntimeError('Suite is compiled: provide OGGCULTIST_PYTHON or install the Oggcultist private .venv first.')
            interpreter = Path(sys.executable)
    if os.name == 'nt' and interpreter.name.lower() == 'python.exe':
        windowless = interpreter.with_name('pythonw.exe')
        if windowless.is_file():
            interpreter = windowless
    return interpreter


def launch(root: str | Path | None = None,
           python_executable: str | Path | None = None,
           arguments: Sequence[str] = ()) -> subprocess.Popen:
    """Open Oggcultist as its own GUI process; return the process handle.

    Launchers should be run once by the user to create `.venv` and install any
    system requirements. Never call this from an existing Tk UI's worker thread.
    The host owns the returned Popen; avoid killing it until user closes the app.
    """
    home = program_root(root)
    interpreter = source_python(home, python_executable)
    log = paths.logs_dir() / 'suite-launch.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # Keep a real stream open during spawn, then let the child inherit its own fd.
    with log.open('a', encoding='utf-8') as stream:
        return subprocess.Popen(
            [str(interpreter), str(home / 'launch.py'), *map(str, arguments)],
            cwd=home, env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, creationflags=flags,
        )
