"""Regression checks for console-free, exclusive Oracle startup (no installs).

Run: xvfb-run -a python3 Application/Tests/test_exclusive_handoff.py
The real Linux end-to-end GUI smoke checks are documented separately.
"""
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sys

entry = Path(__file__).resolve().parents[1] / 'Runtime' / 'launch_suite.pyw'
loader = SourceFileLoader('marble_exclusive_handoff_test', str(entry))
spec = spec_from_loader(loader.name, loader)
boot = module_from_spec(spec)
loader.exec_module(boot)
GOOD_MEDIA = {'ffmpeg': True, 'ffprobe': True, 'ffplay': True}
GOOD_LIBS = {'pillow': {'ok': True}, 'mutagen': {'ok': True}}

class Child:
    status = None
    def poll(self):
        return self.status


def prepare(child, marker, log):
    core = patch.object(boot, 'runtime_choice', return_value=(Path(sys.executable), GOOD_LIBS))
    media = patch.object(boot, 'media_tools', return_value=GOOD_MEDIA)
    launch = patch.object(boot, 'launch_main', return_value=(child, marker))
    messages = patch.object(boot.messagebox, 'showerror')
    startup_log = patch.object(boot, 'STARTUP_LOG', log)
    return core, media, launch, messages, startup_log


def tests():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        log = tmp / 'startup.log'
        log.write_text('Synthetic crash details')
        for scenario in ('unexpected', 'success', 'silent-crash', 'early-close'):
            child = Child()
            flag = tmp / ('startup-ready-' + scenario + '.flag')
            exitflag = tmp / ('startup-exit-' + scenario + '.flag')
            core,media,launch,messages,logpatch=prepare(child,flag,log)
            with core,media,launch as mocked_launch,messages as errors,logpatch:
                root = boot.Setup()
                assert root.state() == 'normal', scenario
                root.start()
                assert root.state() == 'withdrawn', 'Requirements appeared alongside Oracle'
                assert root.launching and not root._monitoring, scenario
                assert mocked_launch.call_count == 1
                if scenario == 'early-close':
                    exitflag.write_text('confirmed user close')
                    child.status = 0
                    root._check_child()
                    assert not errors.called, 'Early normal close reported as crash'
                    continue
                flag.write_text('ready')
                root._check_child()
                assert root._ready_seen_at is not None and root.state() == 'withdrawn'
                root._ready_seen_at -= 7
                root._check_child()
                assert root._monitoring and root._ready_verified
                assert root.state() == 'withdrawn', 'Setup was shown after successful handshake'
                if scenario == 'unexpected':
                    child.status = 1
                    root._monitor_child()
                    assert root.state() == 'normal', 'Requirements UI did not return after crash'
                    assert errors.called, 'Unexpected crash was not reported'
                    assert 'Synthetic crash' in str(errors.call_args)
                    root.destroy()
                elif scenario == 'silent-crash':
                    child.status = 0
                    root._monitor_child()
                    assert root.state() == 'normal', 'Exit code 0 without a close marker hid a crash'
                    assert errors.called
                    root.destroy()
                else:
                    exitflag.write_text('confirmed user close')
                    child.status = 0
                    root._monitor_child()
                    assert not errors.called, 'Intentional close was mistaken for a crash'
                    try: exists = root.winfo_exists()
                    except Exception: exists = False
                    assert not exists, 'Hidden setup did not close after Oracle quit'
    print('PASS: exclusive setup-to-Oracle handoff, intentional close and late crash reporting')


def test_process_group_isolation():
    if os.name == 'nt':
        return
    with TemporaryDirectory() as td:
        p = Path(td)
        log = p / 'app.log'
        with patch.object(boot, 'STATE_DIR', p), patch.object(boot,'STARTUP_LOG',log), \
             patch.object(boot,'configure_media_path'), patch.object(boot.subprocess, 'Popen') as popen:
            boot.launch_main(sys.executable)
            assert popen.call_args.kwargs.get('start_new_session') is True, \
                'The Oracle subprocess must be detached from the launcher session'
            assert popen.call_args.kwargs.get('stdin') == boot.subprocess.DEVNULL
            assert 'MARBLE_ORACLE_EXIT_FILE' in popen.call_args.kwargs['env']
    print('PASS: GUI process isolated from Linux launcher session')

if __name__ == '__main__':
    tests()
    test_process_group_isolation()
