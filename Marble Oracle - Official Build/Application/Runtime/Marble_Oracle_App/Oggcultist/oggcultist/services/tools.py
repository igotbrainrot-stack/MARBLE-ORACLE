"""Running FFmpeg-family child processes consistently on every platform.

On Windows a GUI process (pythonw.exe or a windowed .exe) has no console. A
console program such as ffmpeg.exe started from it would pop up a console
window for every call unless CREATE_NO_WINDOW is passed. Every child process
Oggcultist starts goes through :func:`no_window_kwargs`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def no_window_kwargs(platform: str | None = None) -> dict:
    """Popen/run keyword arguments that suppress console windows on Windows."""
    if (platform or sys.platform) == 'win32':
        return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', CREATE_NO_WINDOW)}
    return {}


def find_tool(name: str) -> str | None:
    """Resolve ffmpeg/ffprobe/ffplay on the (already configured) PATH."""
    suffix = '.exe' if sys.platform == 'win32' and not name.endswith('.exe') else ''
    return shutil.which(name + suffix) or shutil.which(name)


def missing_tools(names=('ffmpeg', 'ffprobe')) -> list[str]:
    return [name for name in names if not find_tool(name)]


# --------------------------------------------------------------------------- child lifetime
_JOB = None
_JOB_LOCK = __import__('threading').Lock()


def _windows_job():
    """One Windows job object that kills every process in it when Oggcultist exits.

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: the job's handle belongs to this process, so when
    Oggcultist ends for any reason (closed, crashed, ended in Task Manager) Windows closes
    the handle and ends FFplay/FFmpeg with it.
    """
    global _JOB
    with _JOB_LOCK:
        if _JOB is not None:
            return _JOB or None
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount',
                        'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                        ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                        ('SchedulingClass', wintypes.DWORD)]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
                        ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            _JOB = 0
            return None
        info = EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        JobObjectExtendedLimitInformation = 9
        if not kernel32.SetInformationJobObject(wintypes.HANDLE(job), JobObjectExtendedLimitInformation,
                                                ctypes.byref(info), ctypes.sizeof(info)):
            _JOB = 0
            return None
        _JOB = (kernel32, job)
        return _JOB


def tie_to_app(process, platform: str | None = None):
    """Make a helper process (FFplay/FFmpeg for playback) end when Oggcultist ends.

    Windows: put it in the kill-on-close job object. Elsewhere nothing is needed: the
    player's FFplay exits when its input pipe closes (``-autoexit``), and FFmpeg decoders
    exit when their output pipe closes. Never raises; returns the process.
    """
    if (platform or sys.platform) != 'win32':
        return process
    try:
        job = _windows_job()
        handle = getattr(process, '_handle', None)
        if job and handle:
            import ctypes
            from ctypes import wintypes
            kernel32, job_handle = job
            kernel32.AssignProcessToJobObject(wintypes.HANDLE(job_handle), wintypes.HANDLE(int(handle)))
    except Exception:  # noqa: BLE001 - best effort; the normal shutdown still stops everything
        pass
    return process
