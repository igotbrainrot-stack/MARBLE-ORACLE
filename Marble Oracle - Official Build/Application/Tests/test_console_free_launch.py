"""Verify the official startup path avoids console windows (no real system installs)."""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parents[1] / 'Runtime'
ROOT = RUNTIME.parents[1]
loader = SourceFileLoader('marble_consolefree_test',str(RUNTIME/'launch_suite.pyw'))
spec = importlib.util.spec_from_loader(loader.name, loader)
boot = importlib.util.module_from_spec(spec)
loader.exec_module(boot)


def test_windows_launcher_never_starts_cmd_or_powershell():
    source = (ROOT/'START MARBLE ORACLE - WINDOWS.vbs').read_text()
    lower = '\n'.join(line for line in source.lower().splitlines() if not line.lstrip().startswith("'"))
    assert 'pyw -3' in lower
    assert 'pythonw' in lower
    assert 'sh.run command, 0, false' in lower
    assert 'cmd.exe' not in lower
    assert 'cmd /c' not in lower
    assert 'powershell' not in lower


def test_windows_python_subprocesses_are_hidden():
    class FakeStartupInfo:
        dwFlags=0
        wShowWindow=None
    with patch.object(boot,'os', SimpleNamespace(name='nt')):
        with patch.object(boot.subprocess,'STARTUPINFO',FakeStartupInfo,create=True), \
             patch.object(boot.subprocess,'STARTF_USESHOWWINDOW',1,create=True), \
             patch.object(boot.subprocess,'SW_HIDE',0,create=True), \
             patch.object(boot.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True):
            opts=boot.hidden_process_options()
            assert opts['creationflags'] == 0x08000000
            assert opts['startupinfo'].dwFlags & 1
            assert opts['startupinfo'].wShowWindow == 0
            with patch.object(boot.subprocess,'run') as mock_run:
                boot.run_hidden(['example.exe'],timeout=5)
                assert mock_run.call_args.kwargs['creationflags'] == 0x08000000
                assert mock_run.call_args.kwargs['startupinfo'].wShowWindow == 0


def test_linux_menu_installer_targets_official_launcher():
    source = (RUNTIME/'install_linux_desktop.sh').read_text()
    assert 'START MARBLE ORACLE - LINUX.sh' in source
    assert 'Terminal=false' in source
    assert 'Marble_Oracle_Linux.sh' not in source


def test_media_processes_use_hidden_options():
    from pathlib import Path
    path=RUNTIME/'Marble_Oracle_App'/'Oggcultist'/'oggcultist'
    for name in ('converter/core.py','converter/cover_editor.py','player/stream.py','player/transport.py'):
        src=(path/name).read_text(encoding='utf-8')
        assert 'no_window_kwargs' in src or 'CREATE_NO_WINDOW' in src, name

if __name__ == '__main__':
    for fn in (test_windows_launcher_never_starts_cmd_or_powershell,
               test_windows_python_subprocesses_are_hidden,
               test_linux_menu_installer_targets_official_launcher,
               test_media_processes_use_hidden_options):
        fn();print('PASS',fn.__name__)
