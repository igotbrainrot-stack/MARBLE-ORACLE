"""Helper processes are really stopped, collected, and let go of the files they had open.

    python3 Application/Tests/test_eidolith_process_cleanup_0493.py      (no display needed)

Why this exists: EIDOLITH used to call terminate() and move on. On Linux every
pause or seek left a defunct process until the suite closed; on Windows, with
FFmpeg installed through a launcher (Chocolatey, Scoop), the real ffmpeg.exe
kept running and kept the video locked after STOP.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))

from oracle_eidolith_core import end_process, stop_process_tree  # noqa: E402

SLEEPER = 'import time; time.sleep(120)'


def spawn(code, *args):
    return subprocess.Popen([sys.executable, '-c', code, *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Cleanup(unittest.TestCase):
    def test_nothing_to_stop_is_fine(self):
        end_process(None)
        stop_process_tree(None)
        finished = spawn('pass')
        finished.wait(timeout=30)
        end_process(finished)
        self.assertEqual(finished.returncode, 0)

    def test_a_running_helper_is_stopped_and_collected(self):
        proc = spawn(SLEEPER)
        started = time.monotonic()
        end_process(proc)
        self.assertLess(time.monotonic() - started, 5, 'the caller waited far longer than the grace period')
        deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIsNotNone(proc.poll(), 'process still running')
        if os.name != 'nt':
            # Collected, not left defunct: a second wait is answered from the saved status.
            with self.assertRaises(ChildProcessError):
                os.waitpid(proc.pid, os.WNOHANG)

    @unittest.skipIf(os.name == 'nt', 'Windows has no ignorable termination request')
    def test_a_helper_that_ignores_the_request_is_killed(self):
        proc = spawn('import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); time.sleep(120)')
        time.sleep(0.8)                      # let it install the handler
        started = time.monotonic()
        end_process(proc, grace=0.3)
        self.assertLess(time.monotonic() - started, 3, 'the caller must not wait for a stubborn process')
        deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(proc.poll(), -9)

    @unittest.skipUnless(os.name == 'nt', 'launcher-and-child process trees are the Windows case')
    def test_windows_launcher_child_releases_the_file(self):
        # A launcher that starts the real worker as its child, like a package-manager shim.
        with tempfile.TemporaryDirectory(prefix='marble-proc-') as folder:
            video = Path(folder) / 'held.bin'
            video.write_bytes(b'x' * 1024)
            worker = 'import sys, time; handle = open(sys.argv[1], "rb"); time.sleep(120)'
            launcher = ('import subprocess, sys; '
                        'subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2]]).wait()')
            proc = spawn(launcher, worker, str(video))
            time.sleep(2.0)                  # both processes up, file open
            with self.assertRaises(PermissionError):
                os.remove(video)             # proves the worker really holds it
            end_process(proc)
            deadline, removed = time.monotonic() + 6, False
            while time.monotonic() < deadline and not removed:
                try:
                    os.remove(video)
                    removed = True
                except PermissionError:
                    time.sleep(0.1)
            self.assertTrue(removed, 'the file was still locked after the launcher was stopped')


if __name__ == '__main__':
    unittest.main(verbosity=1)
