"""0.4.9.3: EIDOLITH never harms a source file. Runs without a display.

    python3 Application/Tests/test_eidolith_file_safety_0493.py

Drives the real queue engine (oracle_eidolith_jobs.QueueRunner) with real
FFmpeg on tiny synthetic clips and checks the promises the interface makes:

* a source is byte-for-byte unchanged after success, failure and cancellation;
* an existing file is never overwritten, including one that appears while a
  job is running, and including the source itself;
* a failed job does not stop the queue;
* a cancelled or failed job leaves no partial file behind;
* only files the engine created are ever deleted.

Skipped (exit 0, clearly reported) when FFmpeg/FFprobe are not installed.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

from oracle_eidolith_core import detect_encoders  # noqa: E402
from oracle_eidolith_jobs import QueueRunner, new_job, remove_owned_partial  # noqa: E402

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=''):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(name)
        print(f'FAIL {name} — {detail}')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_clip(ffmpeg, path, seconds=2, size='320x180'):
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', f'testsrc2=size={size}:rate=24:duration={seconds}',
                    '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest',
                    str(path)], check=True, timeout=120)


def leftovers(folder):
    return sorted(p.name for p in Path(folder).iterdir() if '.eidolith-' in p.name)


def run(runner, limit=180):
    runner.start()
    check('queue finished in time', runner.wait(limit))


def main():
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        print('SKIPPED: FFmpeg/FFprobe not installed; EIDOLITH file safety was NOT verified here.')
        return 0
    encoders = detect_encoders(ffmpeg)
    if 'libx264' not in encoders:
        print('SKIPPED: this FFmpeg has no libx264; EIDOLITH file safety was NOT verified here.')
        return 0
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        sources, out = work / 'sources', work / 'out'
        sources.mkdir()
        out.mkdir()
        good = sources / 'Show.Name.S01E02.720p.mkv'
        make_clip(ffmpeg, good)
        long_clip = sources / 'Long Film (1999).mkv'
        make_clip(ffmpeg, long_clip, seconds=90, size='1280x720')
        broken = sources / 'broken.mkv'
        broken.write_bytes(good.read_bytes()[:3000])
        before = {p: digest(p) for p in (good, long_clip, broken)}
        mtimes = {p: p.stat().st_mtime_ns for p in before}
        logs = work / 'logs'

        # 1. Success, a failure in the middle, and a missing input: the queue carries on.
        runner = QueueRunner(ffmpeg, ffprobe, encoders, log_dir=str(logs))
        jobs = [
            new_job(0, str(good), str(out / 'remux.mkv'), 'Lossless remux'),
            new_job(1, str(broken), str(out / 'broken-out.mp4'), 'Fast CPU H.264'),
            new_job(2, str(sources / 'does-not-exist.mkv'), str(out / 'missing-out.mkv'), 'Lossless remux'),
            new_job(3, str(good), str(out / 'encoded.mp4'), 'Fast CPU H.264'),
        ]
        for job in jobs:
            runner.add(job)
        run(runner)
        states = [job['status'] for job in jobs]
        check('good, broken, missing, good -> completed, failed, failed, completed',
              states == ['completed', 'failed', 'failed', 'completed'], states)
        check('both outputs were published', (out / 'remux.mkv').stat().st_size > 1000
              and (out / 'encoded.mp4').stat().st_size > 1000)
        check('failed jobs published nothing', not (out / 'broken-out.mp4').exists()
              and not (out / 'missing-out.mkv').exists())
        check('failed jobs explain themselves', all(jobs[i]['error'] for i in (1, 2)), [j['error'] for j in jobs])
        check('no partial files remain after success and failure', not leftovers(out), leftovers(out))

        # 2. Nothing is ever overwritten: an existing output, and the source itself.
        marker = out / 'precious.mkv'
        marker.write_bytes(b'user file that must survive')
        runner = QueueRunner(ffmpeg, ffprobe, encoders, log_dir=str(logs))
        over = new_job(0, str(good), str(marker), 'Lossless remux')
        onto_self = new_job(1, str(good), str(good), 'Lossless remux')
        runner.add(over)
        runner.add(onto_self)
        run(runner)
        check('an existing output is refused, not overwritten', over['status'] == 'failed'
              and marker.read_bytes() == b'user file that must survive', over['error'])
        check('converting a file onto itself is refused', onto_self['status'] == 'failed', onto_self['error'])

        # 3. A file that appears at the destination while the job runs is kept.
        runner = QueueRunner(ffmpeg, ffprobe, encoders, log_dir=str(logs))
        racing = new_job(0, str(long_clip), str(out / 'race.mp4'), 'Fast CPU H.264')
        runner.add(racing)
        runner.start()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and racing['status'] != 'converting':
            time.sleep(0.05)
        (out / 'race.mp4').write_bytes(b'appeared during the conversion')
        check('queue finished in time', runner.wait(240))
        check('a file that appeared during conversion is kept and the job fails cleanly',
              racing['status'] == 'failed' and (out / 'race.mp4').read_bytes() == b'appeared during the conversion',
              (racing['status'], racing['error']))
        check('no partial file remains after a refused publish', not leftovers(out), leftovers(out))

        # 4. Cancel while converting: partial removed, next job still runs.
        runner = QueueRunner(ffmpeg, ffprobe, encoders, log_dir=str(logs))
        slow = new_job(0, str(long_clip), str(out / 'slow.mkv'), 'High fidelity' if 'libsvtav1' in encoders
                       else 'Legacy compatibility')
        after = new_job(1, str(good), str(out / 'after-cancel.mkv'), 'Lossless remux')
        runner.add(slow)
        runner.add(after)
        runner.start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not (slow['status'] == 'converting' and leftovers(out)):
            time.sleep(0.05)
        saw_partial = bool(leftovers(out))
        runner.cancel_current()
        check('queue finished in time', runner.wait(240))
        check('the partial file existed while converting (the test really cancelled mid-encode)', saw_partial)
        check('cancelled job is marked cancelled', slow['status'] == 'cancelled', (slow['status'], slow['error']))
        check('cancelled job published nothing', not (out / 'slow.mkv').exists())
        check('cancelling one job lets the next one run', after['status'] == 'completed', after['status'])
        check('no partial file remains after cancel', not leftovers(out), leftovers(out))

        # 5. STOP QUEUE leaves the rest queued rather than failing or deleting them.
        runner = QueueRunner(ffmpeg, ffprobe, encoders, log_dir=str(logs))
        first = new_job(0, str(long_clip), str(out / 'stop-1.mkv'), slow['profile'])
        second = new_job(1, str(good), str(out / 'stop-2.mkv'), 'Lossless remux')
        runner.add(first)
        runner.add(second)
        runner.start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and first['status'] != 'converting':
            time.sleep(0.05)
        runner.stop_queue()
        check('queue finished in time', runner.wait(240))
        check('STOP cancels the current job and keeps the next queued',
              (first['status'], second['status']) == ('cancelled', 'queued'), (first['status'], second['status']))
        check('no partial file remains after stop', not leftovers(out), leftovers(out))

        # 6. Only the engine's own partial files can be removed by its cleanup.
        bystander = out / 'holiday.part.mkv'
        bystander.write_bytes(b'x')
        check('cleanup refuses a file it did not create', bool(remove_owned_partial(str(bystander))) and bystander.exists())
        check('cleanup refuses a source', bool(remove_owned_partial(str(good))) and good.exists())
        owned = out / 'film.eidolith-0123456789ab-part.mkv'
        owned.write_bytes(b'x')
        check('cleanup removes its own partial', remove_owned_partial(str(owned)) == '' and not owned.exists())

        # The sources: same bytes, same modification time, still there.
        for path, was in before.items():
            check(f'source unchanged: {path.name}', path.is_file() and digest(path) == was)
            check(f'source timestamp untouched: {path.name}', path.stat().st_mtime_ns == mtimes[path])
        check('nothing was written beside the sources', sorted(p.name for p in sources.iterdir())
              == sorted(p.name for p in before), sorted(p.name for p in sources.iterdir()))
        check('each job wrote a log', logs.is_dir() and len(list(logs.glob('*.log'))) >= 8, len(list(logs.glob('*.log'))))
    print(f'EIDOLITH FILE SAFETY: {CHECKS[0] - len(FAILURES)}/{CHECKS[0]} checks passed')
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
