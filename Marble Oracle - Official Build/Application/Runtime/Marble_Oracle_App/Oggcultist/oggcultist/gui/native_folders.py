"""Use the operating system's familiar folder-selection interface.

Windows: the Explorer-style Vista+ IFileOpenDialog with FOS_PICKFOLDERS.
Linux Mint and other GTK desktops: Zenity/YAD native GTK file-chooser dialogs.
Other Linux desktop environments: kdialog, then Tk's built-in folder chooser.

No browser, external service, shell string, or custom filesystem explorer is used.
Cancellation is never treated as an error and never changes saved paths.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog

_UNAVAILABLE = object()


def _initial_directory(path: str | os.PathLike | None) -> str:
    """Resolve an existing start folder without changing the user's chosen destination."""
    try:
        candidate = Path(path).expanduser() if path else Path.home()
        if candidate.is_file():
            candidate = candidate.parent
        while not candidate.is_dir() and candidate != candidate.parent:
            candidate = candidate.parent
        return str(candidate if candidate.is_dir() else Path.home())
    except (OSError, ValueError, TypeError):
        return str(Path.home())


def _gtk_directory(title: str, initial: str):
    """GTK file chooser commonly shipped with Mint. Return _UNAVAILABLE if absent."""
    program = shutil.which('zenity') or shutil.which('yad')
    if not program:
        return _UNAVAILABLE
    # --filename gives the GTK file chooser a starting directory; slash matters.
    initial = initial.rstrip('/\\') + os.sep
    cmd = [program, '--file-selection', '--directory', f'--title={title}', f'--filename={initial}']
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, errors='replace', check=False)
    except OSError:
        return _UNAVAILABLE
    if completed.returncode == 0:
        # Zenity may print a newline; do not trim legitimate whitespace in a pathname.
        return completed.stdout.rstrip('\r\n')
    if completed.returncode == 1:  # cancelled
        return ''
    return _UNAVAILABLE


def _kde_directory(title: str, initial: str):
    program = shutil.which('kdialog')
    if not program:
        return _UNAVAILABLE
    try:
        completed = subprocess.run([program, '--getexistingdirectory', initial, '--title', title],
                                   capture_output=True, text=True, errors='replace', check=False)
    except OSError:
        return _UNAVAILABLE
    if completed.returncode == 0:
        return completed.stdout.rstrip('\r\n')
    if completed.returncode == 1:
        return ''
    return _UNAVAILABLE


def _windows_explorer_directory(parent, title: str, initial: str):
    """Explorer's modern IFileOpenDialog in folder-picking mode (no pywin32 needed).

    Returns empty string on cancellation, _UNAVAILABLE on COM failure, or a path.
    The caller can still use Tk as a safe fallback if COM is unavailable.
    """
    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                    ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]

        @classmethod
        def parse(cls, value: str):
            return cls.from_buffer_copy(uuid.UUID(value).bytes_le)

    ole32 = ctypes.OleDLL('ole32')
    shell32 = ctypes.OleDLL('shell32')
    coinit = ole32.CoInitializeEx
    coinit.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    coinit.restype = ctypes.c_long
    hr_init = coinit(None, 2)  # STA, the normal Tk main thread
    owned_init = hr_init in (0, 1)
    if hr_init not in (0, 1, -2147417850):  # RPC_E_CHANGED_MODE: already initialized MTA
        return _UNAVAILABLE

    open_dialog = ctypes.c_void_p()
    result_item = ctypes.c_void_p()
    initial_item = ctypes.c_void_p()
    display_name = ctypes.c_void_p()

    # Explicit calling convention required for COM interfaces on 32-bit Windows.
    def method(pointer, slot, ret, *argtypes):
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(ret, ctypes.c_void_p, *argtypes)(vtable[slot])

    def release(pointer):
        if pointer.value:
            method(pointer, 2, wintypes.ULONG)(pointer)

    try:
        create = ole32.CoCreateInstance
        create.argtypes = (ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
        create.restype = ctypes.c_long
        clsid = GUID.parse('DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7')
        iid = GUID.parse('D57C7288-D4AD-4768-BE02-9D969532D960')
        if create(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(open_dialog)) != 0:
            return _UNAVAILABLE

        current_flags = wintypes.DWORD()
        if method(open_dialog, 10, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))(
                open_dialog, ctypes.byref(current_flags)) != 0:
            return _UNAVAILABLE
        # FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST.
        flags = wintypes.DWORD(current_flags.value | 0x20 | 0x40 | 0x800)
        if method(open_dialog, 9, ctypes.c_long, wintypes.DWORD)(open_dialog, flags) != 0:
            return _UNAVAILABLE
        method(open_dialog, 17, ctypes.c_long, wintypes.LPCWSTR)(open_dialog, title)

        shell_item_iid = GUID.parse('43826D1E-E718-42EE-BC55-A1E261C37BFE')
        parse_path = shell32.SHCreateItemFromParsingName
        parse_path.argtypes = (wintypes.LPCWSTR, ctypes.c_void_p,
                               ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
        parse_path.restype = ctypes.c_long
        if parse_path(initial, None, ctypes.byref(shell_item_iid), ctypes.byref(initial_item)) == 0:
            method(open_dialog, 12, ctypes.c_long, ctypes.c_void_p)(open_dialog, initial_item)

        try:
            tk_hwnd = int(parent.winfo_toplevel().winfo_id())
            get_parent = ctypes.windll.user32.GetParent
            get_parent.argtypes = (wintypes.HWND,)
            get_parent.restype = wintypes.HWND
            hwnd = get_parent(wintypes.HWND(tk_hwnd)) or tk_hwnd
        except (AttributeError, RuntimeError, ValueError):
            hwnd = 0
        hr_show = method(open_dialog, 3, ctypes.c_long, wintypes.HWND)(open_dialog, hwnd)
        if hr_show == -2147023673:  # HRESULT_FROM_WIN32(ERROR_CANCELLED), 0x800704C7
            return ''
        if hr_show != 0:
            return _UNAVAILABLE
        if method(open_dialog, 20, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(
                open_dialog, ctypes.byref(result_item)) != 0:
            return _UNAVAILABLE
        # SIGDN_FILESYSPATH = 0x80058000. COM owns the returned memory.
        if method(result_item, 5, ctypes.c_long, wintypes.DWORD,
                  ctypes.POINTER(ctypes.c_void_p))(result_item, 0x80058000, ctypes.byref(display_name)) != 0:
            return _UNAVAILABLE
        return ctypes.wstring_at(display_name.value)
    except (OSError, ValueError, AttributeError, TypeError):
        return _UNAVAILABLE
    finally:
        if display_name.value:
            ole32.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
            ole32.CoTaskMemFree(display_name)
        release(result_item)
        release(initial_item)
        release(open_dialog)
        if owned_init:
            ole32.CoUninitialize()


def choose_directory(parent=None, *, title: str = 'Choose a folder',
                     initialdir: str | os.PathLike | None = None, mustexist: bool = True) -> str:
    """Return selected folder or '' if cancelled. Does not modify the filesystem.

    Linux Mint: choose with its GTK file selector, supporting file-manager navigation,
    bookmarks and the normal Create Folder action. Windows: use Explorer-style COM UI.
    """
    initial = _initial_directory(initialdir)
    native = _UNAVAILABLE
    if sys.platform == 'win32':
        try:
            native = _windows_explorer_directory(parent, title, initial)
        except Exception:  # system-specific COM errors should not block choosing a folder
            native = _UNAVAILABLE
    elif sys.platform.startswith('linux'):
        native = _gtk_directory(title, initial)
        if native is _UNAVAILABLE:
            native = _kde_directory(title, initial)
    if native is not _UNAVAILABLE:
        return str(native)
    return filedialog.askdirectory(parent=parent, title=title, mustexist=mustexist,
                                   initialdir=initial) or ''
