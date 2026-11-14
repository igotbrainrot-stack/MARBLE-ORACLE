"""EIDOLITH picks local files through desktop-native file-selection dialogs."""
import sys
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(ROOT))
import oracle_native_files as f


def test_linux_gtk_native_multiselect(monkeypatch):
    monkeypatch.setattr(f.sys, 'platform', 'linux')
    monkeypatch.setattr(f.shutil, 'which', lambda cmd: '/usr/bin/zenity' if cmd == 'zenity' else None)
    commands = []
    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return Mock(returncode=0, stdout='/tmp/one.mkv\n/tmp/two.mp4\n')
    monkeypatch.setattr(f.subprocess, 'run', fake_run)
    assert f.choose_video_files() == ('/tmp/one.mkv', '/tmp/two.mp4')
    assert '--multiple' in commands[0] and '--file-selection' in commands[0]


def test_linux_cancel_does_not_open_second_dialog(monkeypatch):
    monkeypatch.setattr(f.sys, 'platform', 'linux')
    monkeypatch.setattr(f.shutil, 'which', lambda cmd: '/usr/bin/zenity' if cmd == 'zenity' else None)
    monkeypatch.setattr(f.subprocess, 'run', lambda *a, **kw: Mock(returncode=1, stdout=''))
    monkeypatch.setattr(f.filedialog, 'askopenfilenames', lambda **kw: 1 / 0)
    assert f.choose_video_files() == ()


def test_windows_uses_os_common_file_dialog(monkeypatch):
    monkeypatch.setattr(f.sys, 'platform', 'win32')
    monkeypatch.setattr(f.filedialog, 'askopenfilenames', lambda **kw: ('C:/Videos/movie.mkv',))
    assert f.choose_video_files() == ('C:/Videos/movie.mkv',)


def test_linux_without_desktop_chooser_falls_back(monkeypatch):
    monkeypatch.setattr(f.sys, 'platform', 'linux')
    monkeypatch.setattr(f.shutil, 'which', lambda cmd: None)
    monkeypatch.setattr(f.filedialog, 'askopenfilenames', lambda **kw: ('/data/clip.mkv',))
    assert f.choose_video_files() == ('/data/clip.mkv',)


def test_eidolith_routes_all_three_actions_via_native_chooser():
    source = (ROOT / 'oracle_eidolith.py').read_text()
    assert 'paths = choose_video_files(' in source
    assert "folder = choose_directory(parent=self, title='Add folder')" in source
    assert "folder = choose_directory(parent=self, title='Choose output folder'" in source
    assert 'filedialog.askdirectory' not in source
