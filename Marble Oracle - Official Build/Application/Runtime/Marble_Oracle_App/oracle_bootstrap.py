"""Shared cross-platform launcher for MARBLE_ORACLE CRT V2.

Default V2 requires Pillow for its photographic hardware and physical controls.
Legacy screenshot-barrel mode is opt-in only. Real audio loopback is optional.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import traceback

def console_python():
    """Find python.exe corresponding to THIS process, not a different pyw."""
    exe = Path(sys.executable)
    if exe.name.lower() == 'pythonw.exe':
        candidate = exe.with_name('python.exe')
        if candidate.exists():
            return str(candidate)
    return str(exe)


def _diagnostic_path():
    """Where a failed pip install leaves its output: the per-user state folder."""
    from oracle_assets import state_dir
    return Path(state_dir()) / 'pip_install_diagnostic.txt'


def _has_v2_pillow():
    try:
        from PIL import Image, ImageTk, ImageEnhance
        return True
    except (ImportError, OSError):
        return False


def _install_v2_pillow():
    if _has_v2_pillow():
        return True
    cmd = [console_python(), '-m', 'pip', 'install',
           '--disable-pip-version-check', 'Pillow>=10.0']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            _diagnostic_path().write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
            return False
        import importlib
        importlib.invalidate_caches()
        return _has_v2_pillow()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _has_barrel():
    try:
        import cv2
        import numpy
        from PIL import Image
        return True
    except ImportError:
        return False


def _install_barrel():
    """The inner-glass bend needs NumPy, OpenCV and Pillow. The metal does not."""
    if _has_barrel():
        return True
    cmd = [console_python(), '-m', 'pip', 'install', '--disable-pip-version-check',
           'numpy>=1.26', 'opencv-python-headless>=4.9', 'Pillow>=10.0']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode != 0:
            _diagnostic_path().write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
            return False
        import importlib
        importlib.invalidate_caches()
        return _has_barrel()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _has_audio_capture():
    try:
        import numpy
        import soundcard
        return True
    except (ImportError, OSError):
        return False


def _install_audio(gui):
    """Optional Windows WASAPI loopback: always use launcher's interpreter."""
    if os.name != 'nt' or _has_audio_capture():
        return True
    if gui:
        try:
            from tkinter import messagebox
            if not messagebox.askyesno('Marble_Oracle',
                'Install SoundCard and NumPy to animate the CRT green screens using actual PC speaker output?'
                '\n\nInternet access may be required. Cancel leaves the scopes inactive.'):
                return False
        except Exception:
            return False
    cmd=[console_python(),'-m','pip','install','--disable-pip-version-check',
         'soundcard>=0.4.3','numpy>=1.26']
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=300,
                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode != 0:
            _diagnostic_path().write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            return False
        import importlib
        importlib.invalidate_caches()
        return _has_audio_capture()
    except (OSError,subprocess.TimeoutExpired):
        return False


def launch(args=None, *, gui=False):
    args = list(sys.argv[1:] if args is None else args)
    if '--install-audio-only' in args:
        return 0 if _install_audio(gui) else 2
    quiet = any(flag in args for flag in ('--selftest', '--version', '--help', '-h'))
    use_v2 = '--legacy-bezel' not in args or '--crt-v2' in args
    # The clean modern layout (the Linux default) does not need the photographic
    # bezel or Pillow. Never attempt to mutate system Python on Linux.
    needs_pillow = use_v2 and '--no-bezel' not in args and not quiet
    if needs_pillow and not _has_v2_pillow():
        message = ('The approved CRT V2 requires Pillow in the interpreter launching '
                   'MARBLE_ORACLE. Install it explicitly: '
                   'python3 -m pip install Pillow (or install python3-pil using your package manager)')
        if gui:
            from tkinter import messagebox
            messagebox.showerror('MARBLE_ORACLE CRT V2', message)
        else:
            print(message)
        return 3
    # Audio capture is optional; never silently install dependencies during GUI startup.
    # Run an explicit diagnostics/setup command if Windows audio capture is desired.
    # Do not mutate the Python environment at launch for optional legacy effects.
    import marble_oracle
    return marble_oracle.main(args)


def report_gui_error(exc):
    """Keep launch failures diagnosable when started without a terminal."""
    from datetime import datetime
    details = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        from oracle_assets import state_dir
        folder = Path(state_dir())
        folder.mkdir(parents=True, exist_ok=True)
        log = folder / 'startup_error.log'
        with log.open('a', encoding='utf-8') as f:
            f.write('\n--- ' + datetime.now().isoformat(timespec='seconds') + ' ---\n' + details)
        hint = 'Details saved to: ' + str(log)
    except OSError:
        hint = 'Unable to write diagnostic log.'
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror('Marble Oracle could not start', str(exc) + '\n\n' + hint)
        root.destroy()
    except Exception:
        print(details, file=sys.stderr)

if __name__ == '__main__':
    try:
        sys.exit(launch())
    except Exception as exc:
        report_gui_error(exc)
        sys.exit(1)
