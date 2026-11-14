"""Native local file and folder selectors for the EIDOLITH workspace.

Linux GTK desktop: Zenity/YAD; KDE: KDialog; Windows: OS common dialog.
Folders reuse Oggcultist's Windows Explorer COM and GTK/KDE implementation.
The chooser is an OS dialog, not a separate file-manager application.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog

VIDEO_FILETYPES = [('Video files', '*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.mts *.flv'),
                   ('All files', '*.*')]


def choose_directory(*, parent=None, title='Choose folder', initialdir=None):
    ogg_root = str(Path(__file__).resolve().parent / 'Oggcultist')
    if ogg_root not in sys.path:
        sys.path.insert(0, ogg_root)
    from oggcultist.gui.native_folders import choose_directory as native_choose_directory
    return native_choose_directory(parent=parent, title=title, initialdir=initialdir)


def choose_video_files(*, parent=None, title='Open video files') -> tuple[str, ...]:
    """Ask the local desktop to choose video files. Cancel returns an empty tuple.

    Windows Tk uses GetOpenFileName's OS-native Explorer-style picker.
    On Linux use GTK/KDE native chooser, falling back to Tk when unavailable.
    """
    if sys.platform.startswith('linux'):
        gtk = shutil.which('zenity') or shutil.which('yad')
        if gtk:
            cmd = [gtk, '--file-selection', '--multiple', '--separator=\n',
                   f'--title={title}']
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, errors='replace', check=False)
                if result.returncode == 0:
                    return tuple(p for p in result.stdout.splitlines() if p)
                if result.returncode == 1:
                    return ()
            except OSError:
                pass
        kde = shutil.which('kdialog')
        if kde:
            try:
                result = subprocess.run([kde, '--getopenfilename', str(Path.home()),
                                         'Video files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.mts *.flv)',
                                         '--multiple', '--separate-output', '--title', title],
                                        capture_output=True, text=True, errors='replace', check=False)
                if result.returncode == 0:
                    return tuple(p for p in result.stdout.splitlines() if p)
                if result.returncode == 1:
                    return ()
            except OSError:
                pass
    return tuple(filedialog.askopenfilenames(parent=parent, title=title,
                                             filetypes=VIDEO_FILETYPES) or ())
