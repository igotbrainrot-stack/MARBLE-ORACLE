"""Startup regression tests. No packages or system files are installed."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'Runtime'/'launch_suite.pyw'
loader=SourceFileLoader('marble_suite_launch_tests', str(PATH))
spec=importlib.util.spec_from_loader(loader.name,loader)
boot=importlib.util.module_from_spec(spec)
loader.exec_module(boot)
ALL={'ffmpeg':True,'ffprobe':True,'ffplay':True}
MISSING={'ffmpeg':False,'ffprobe':False,'ffplay':False}
PYS={'pillow':{'ok':True},'mutagen':{'ok':True}}


def make(ready=True, media=True):
    with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable) if ready else None,PYS)), \
         patch.object(boot,'media_tools',return_value=ALL if media else MISSING):
        return boot.Setup()


def test_missing_media_is_optional():
    root=make(media=False)
    assert root.ready and root.start_btn.cget('state')=='normal'
    assert 'Missing' in root.details.cget('text')
    with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable),PYS)), \
         patch.object(boot,'media_tools',return_value=MISSING), \
         patch.object(boot,'launch_main',return_value=(type('Child',(),{'poll':lambda s:None})(),Path('/no/such/ready'))):
        root.start()
        assert root.launching, 'Optional FFmpeg must not block the main app'
    root.launching=False
    root.destroy()


def test_missing_python_blocks_start():
    root=make(ready=False)
    assert not root.ready and root.start_btn.cget('state')=='disabled'
    with patch.object(boot,'runtime_choice',return_value=(None,{'pillow':{'ok':False}})), \
         patch.object(boot,'media_tools',return_value=ALL), \
         patch.object(boot,'launch_main') as launch:
        root.start()
        assert not launch.called
    root.destroy()


def test_failed_install_does_not_crash_or_close_window():
    root=make(media=False)
    root._setbusy(True)
    root._queue.put(('error','Simulated administrator approval cancellation'))
    with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable),PYS)), \
         patch.object(boot,'media_tools',return_value=MISSING), \
         patch.object(boot.messagebox,'showwarning') as warn:
        root.pump()
        assert root.winfo_exists() and not root.running and root.ready
        assert warn.called
    root.destroy()


def test_handshake():
    with tempfile.TemporaryDirectory() as td:
        marker=Path(td)/'ready.flag'
        class Child:
            def poll(self):return None
        root=make()
        with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable),PYS)), \
             patch.object(boot,'media_tools',return_value=ALL), \
             patch.object(boot,'launch_main',return_value=(Child(),marker)), \
             patch.object(boot,'save_state') as saved:
            root.start()
            assert root.launching
            marker.write_text('ok')
            root._check_child()
            assert root.launching and not saved.called, 'Do not close setup on a mere ready-file signal'
            root._ready_seen_at -= 7.0
            root._check_child()
            assert not root.launching and saved.called


def test_early_child_failure_is_reported():
    with tempfile.TemporaryDirectory() as td:
        marker=Path(td)/'ready.flag'
        startup_log=Path(td)/'startup.log'
        startup_log.write_text('ImportError: missing component')
        class Child:
            def poll(self):return 1
        root=make()
        with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable),PYS)), \
             patch.object(boot,'media_tools',return_value=ALL), \
             patch.object(boot,'launch_main',return_value=(Child(),marker)), \
             patch.object(boot,'STARTUP_LOG',startup_log), \
             patch.object(boot.messagebox,'showerror') as error:
            root.start();root._check_child()
            assert error.called
            assert 'ImportError' in str(error.call_args)
        root.destroy()


def test_crash_after_ready_is_reported():
    with tempfile.TemporaryDirectory() as td:
        marker=Path(td)/'ready.flag'
        startup_log=Path(td)/'startup.log'
        startup_log.write_text('Synthetic crash immediately after opening')
        class Child:
            exit_code = None
            def poll(self): return self.exit_code
        child=Child()
        root=make()
        with patch.object(boot,'runtime_choice',return_value=(Path(sys.executable),PYS)), \
             patch.object(boot,'media_tools',return_value=ALL), \
             patch.object(boot,'launch_main',return_value=(child,marker)), \
             patch.object(boot,'STARTUP_LOG',startup_log), \
             patch.object(boot.messagebox,'showerror') as error:
            root.start()
            marker.write_text('ready')
            root._check_child()
            assert root.launching and root.winfo_exists()
            child.exit_code=1
            root._check_child()
            assert error.called and root.winfo_exists(), 'Setup should stay visible to show crash'
            assert not root.launching
        root.destroy()


def test_bad_media_configuration_does_not_crash_probe():
    with patch.object(boot,'configure_media_path',side_effect=ImportError('broken tools setup')):
        assert set(boot.media_tools()) == set(ALL)


if __name__=='__main__':
    for case in (test_missing_media_is_optional,test_missing_python_blocks_start,
                 test_failed_install_does_not_crash_or_close_window,
                 test_handshake,test_early_child_failure_is_reported,
                 test_crash_after_ready_is_reported,
                 test_bad_media_configuration_does_not_crash_probe):
        case(); print('PASS',case.__name__)
