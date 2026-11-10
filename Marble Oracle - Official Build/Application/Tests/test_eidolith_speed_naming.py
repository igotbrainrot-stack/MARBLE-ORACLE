"""EIDOLITH 0.3 regression tests: safe filenames, encoder policy, real queue output."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk

# Keep EIDOLITH settings, persisted queue and logs out of the user's real state.
os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='eidolith-test-state-')

RUNTIME = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(RUNTIME))

from oracle_eidolith_core import (parse_media_name, output_name, standard_stem,
    profile_support, encoding_args, progress_label, NAME_MODES)
from oracle_eidolith import EidolithPanel


def check(name, actual, expected):
    if actual != expected:
        raise AssertionError(f'{name}: expected {expected!r}, got {actual!r}')


check('TV dots', output_name('The.Office.US.S02E03.Office.Olympics.1080p.WEB-DL.mkv',
                             'Balanced archive (default)'),
      'The Office US - S02E03 - Office Olympics [AV1].mkv')
check('TV x format', output_name('Severance - 1x04 - The You You Are.mp4',
                              'NVIDIA HEVC (fast)'),
      'Severance - S01E04 - The You You Are [HEVC].mkv')
check('Movie year', output_name('Dune.Part.Two.2024.2160p.BluRay.x265.mkv',
                              'NVIDIA AV1 (fast)'),
      'Dune Part Two (2024) [AV1].mkv')
check('Unknown remains recognisable', output_name('my_home_movie.mp4', 'Fast CPU H.264'),
      'my_home_movie [H264].mp4')
check('Sanitised override', output_name('show.s01e02.mkv', 'Fast CPU H.264',
    title_override='A/B:C*D?'), 'ABCD - S01E02 [H264].mp4')
check('No invented episode', standard_stem('mystery.mkv', 'TV episode'), 'mystery')
check('Season override', standard_stem('Example.s01e07.mkv', 'TV episode', episode_override='12'),
      'Example - S01E12')
assert profile_support('NVIDIA AV1 (fast)', {'libsvtav1'})[0] is False
assert profile_support('NVIDIA AV1 (fast)', {'av1_nvenc'})[0] is True
assert '-preset' in encoding_args('Faster CPU AV1') and '10' in encoding_args('Faster CPU AV1')
assert '-cq' in encoding_args('NVIDIA HEVC (fast)')
assert 'ETA 0:00:15' in progress_label({'out_time':'0:00:15.000','speed':'2.0x'}, duration=45)
print('EIDOLITH 0.3: filename/parser/encoder/progress unit tests passed')

ffmpeg = shutil.which('ffmpeg')
ffprobe = shutil.which('ffprobe')
if not ffmpeg or not ffprobe:
    print('Skipping actual encode test: ffmpeg/ffprobe unavailable')
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix='eidolith_standard_') as folder:
    source = Path(folder) / 'Example.Show.S01E02.The.Visit.480p.mp4'
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
           'testsrc2=size=256x144:rate=20', '-f', 'lavfi', '-i',
           'sine=frequency=300:sample_rate=44100', '-t', '2', '-c:v', 'mpeg4',
           '-q:v', '7', '-c:a', 'aac', str(source)]
    subprocess.run(cmd, check=True, timeout=30)
    before = source.read_bytes()
    root = tk.Tk()
    root.geometry('1220x850')
    panel = EidolithPanel(root, on_home=lambda: None)
    panel.pack(fill='both', expand=True)
    root.update_idletasks()
    panel.files = [str(source)]
    panel._load_files()
    panel._set_nav('CONVERT')
    panel.convert_list.selection_set(0)
    panel.rename_mode.set(NAME_MODES[0])
    panel.profile.set('Fast CPU H.264')
    # 0.4 defaults to short names; opt in to the full form this test checks.
    panel.name_episode_title.set(True)
    panel.name_format_tag.set(True)
    panel.output_var.set(str(Path(folder) / 'Encoded'))
    panel.queue_selected()
    root.update_idletasks()
    assert len(panel.queue_items) == 1
    job = panel.queue_items[0]
    check('Organised job destination', Path(job['dst']).name,
          'Example Show - S01E02 - The Visit [H264].mp4')
    panel.start_queue()
    until = time.monotonic()+40
    while panel.worker_thread.is_alive() and time.monotonic() < until:
        root.update()
        time.sleep(0.04)
    assert not panel.worker_thread.is_alive(), 'Encode hung'
    for _ in range(5):
        root.update(); time.sleep(0.02)
    print('Actual encoding status:', job['status'], job['progress'])
    if job['status'] != 'completed':
        print('LOG:', panel.log_text.get('1.0','end')[-6000:])
    assert job['status'] == 'completed', job
    assert Path(job['dst']).exists()
    assert source.read_bytes() == before, 'Original source changed'
    assert not list(Path(job['dst']).parent.glob('*eidolith-*-part*')), 'Incomplete temp file left behind'
    # Check collision-safe naming on queueing a second job.
    panel._set_nav('CONVERT')
    panel.convert_list.selection_set(0)
    # 0.4.6 skips already converted files by default; this checks the collision-safe ' (2)' path.
    panel.skip_converted.set(False)
    panel.queue_selected()
    assert panel.queue_items[1]['dst'] != job['dst']
    assert Path(panel.queue_items[1]['dst']).name.endswith(' (2).mp4')
    assert panel.shutdown()
    root.destroy()
print('EIDOLITH 0.3: real FFmpeg encode, stream verification, naming collisions and original preservation PASSED')
