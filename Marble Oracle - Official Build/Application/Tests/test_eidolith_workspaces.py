"""Regression tests for EIDOLITH's separated pages and embedded video preview.

Run on a machine with tkinter, FFmpeg and FFprobe, under a graphical desktop:
    xvfb-run -a python3 Application/Tests/test_eidolith_workspaces.py

Uses synthetic local video only; does not access the network or change sources.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp  # noqa: E402


def pump(root, seconds=0.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.018)


def exercise():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        print('SKIP: FFmpeg / FFprobe are not on PATH for this test')
        return
    with tempfile.TemporaryDirectory(prefix='marble-eidolith-test-') as folder:
        folder = Path(folder)
        os.environ['XDG_DATA_HOME'] = str(folder / 'user-data')
        os.environ['MARBLE_ORACLE_STATE'] = str(folder / 'state')
        video = folder / 'test_video.mp4'
        copy = folder / 'second_video.mp4'
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', 'testsrc2=size=256x144:rate=12:duration=2',
               '-f', 'lavfi', '-i', 'sine=frequency=400:duration=2',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2',
               '-c:a', 'aac', '-shortest', str(video)]
        subprocess.run(cmd, check=True, timeout=25)
        shutil.copy2(video, copy)
        app = WindowApp({'bezel': False, 'no_network': True, 'no_markets': True, 'selftest': True})
        root, scene = app.root, app.scene
        try:
            pump(root, 0.15)
            scene.resized(app.canvas.winfo_width(), app.canvas.winfo_height())
            scene.act('tab_eidolith')
            pump(root, .1)
            e = scene.eido.frame
            assert len(e.pages) == 4
            assert e.active_nav.get() == 'PLAYER'
            assert e.pages['PLAYER'].winfo_ismapped()
            assert not e.pages['CONVERT'].winfo_ismapped()
            e.files = [str(video), str(copy)]
            e._load_files()
            e.select_all()
            assert len(e.file_list.curselection()) == 2, 'PLAYER SELECT ALL failed'
            e.file_list.selection_clear(1)
            e._probe_selected()
            assert e.video.duration >= 1.8
            e.play_selected()
            assert e.video.phase == 'playing'
            assert '-f' in e.video.play_proc.args and 'image2pipe' in e.video.play_proc.args
            if e.video.audio_proc:
                args = e.video.audio_proc.args
                assert '-nodisp' in args or '--no-video' in args, args
            deadline = time.monotonic() + 4
            while e.video._drawn_frames < 5 and time.monotonic() < deadline:
                pump(root, .08)
            assert e.video._drawn_frames >= 5, 'No real video frames rendered inside Tk'
            assert e.video._photo is not None
            assert e.video._fullscreen is None, 'Unexpected automatic fullscreen'
            e.video.pause()
            assert e.video.phase == 'paused'
            e.video.seek(.75)
            assert .7 <= e.video.position <= .8
            e.video.play()
            e.video.open_fullscreen()
            pump(root, .1)
            assert e.video._fullscreen and e.video._fullscreen.winfo_exists()
            e.video.close_fullscreen()
            assert e.video._fullscreen is None
            e._set_nav('CONVERT')
            pump(root, .05)
            assert e.pages['CONVERT'].winfo_ismapped() and not e.pages['PLAYER'].winfo_ismapped()
            assert e.video.phase == 'paused', 'Page change did not pause playback'
            e.select_all()
            assert len(e.convert_list.curselection()) == 2, 'CONVERTER SELECT ALL failed'
            e.convert_list.selection_clear(1)
            e.profile.set('Lossless remux')
            e.output_var.set(str(folder / 'outputs'))
            e.queue_selected()
            pump(root, .08)
            assert e.active_nav.get() == 'QUEUE'
            assert e.pages['QUEUE'].winfo_ismapped() and not e.pages['CONVERT'].winfo_ismapped()
            assert len(e.queue_items) == 1
            e.start_queue()
            deadline = time.monotonic() + 25
            while e.queue_items[0]['status'] not in ('completed', 'cancelled', 'failed') and time.monotonic() < deadline:
                pump(root, .08)
            job = e.queue_items[0]
            assert job['status'] == 'completed', f"Job failed: {job} log={e.log_text.get('1.0','end')[-1000:]}"
            assert Path(job['dst']).is_file()
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name',
                                     '-of', 'csv=p=0', job['dst']], capture_output=True, text=True)
            assert result.returncode == 0 and 'h264' in result.stdout
            assert video.is_file() and copy.is_file(), 'Source was removed'
            e._set_nav('ABOUT')
            pump(root, .05)
            assert e.pages['ABOUT'].winfo_ismapped()
            e._set_nav('PLAYER')
            pump(root, .05)
            assert e.pages['PLAYER'].winfo_ismapped()
            print('EIDOLITH: 4 page views, select all, in-app video, controls, opt-in fullscreen, queue remux PASS')
        finally:
            app.quit()


if __name__ == '__main__':
    exercise()
