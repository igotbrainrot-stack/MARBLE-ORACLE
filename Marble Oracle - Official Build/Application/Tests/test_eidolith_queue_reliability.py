"""EIDOLITH 0.4 queue reliability acceptance tests (real FFmpeg, synthetic media).

    xvfb-run -a python3 Application/Tests/test_eidolith_queue_reliability.py

Requires ffmpeg/ffprobe with libx264 and libsvtav1. Everything happens in a
temporary folder with a temporary MARBLE_ORACLE_STATE; sources are checked
byte-for-byte afterwards. Sections:

 1  batch fail-and-continue (missing input, corrupt input, truncated input
    failing validation, FFmpeg non-zero exit) with per-job logs
 2  track handling: MP4/MKV cover art, SRT->MP4, bitmap subs->MP4 blocked,
    timecode data stream reported, 10-bit verification
 3  cancel-current continues; stop-queue keeps the rest queued; START does
    not rerun cancelled/failed jobs; RETRY is explicit
 4  restart: interrupted job marked, orphaned FFmpeg stopped, only the
    job's own partial removed (Linux; skipped elsewhere)
 5  panel: persisted queue restored without auto-start, progress panel
    (determinate + indeterminate), Mr. Robot output name, diagnostics redaction
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(RUNTIME))
STATE = tempfile.mkdtemp(prefix='eidolith-reliability-state-')
os.environ['MARBLE_ORACLE_STATE'] = STATE

from oracle_eidolith_core import detect_encoders, output_name  # noqa: E402
from oracle_eidolith_jobs import QueueRunner, new_job, plan_streams, PlanError  # noqa: E402

FFMPEG, FFPROBE = shutil.which('ffmpeg'), shutil.which('ffprobe')
RESULTS = []


def check(name, condition, detail=''):
    RESULTS.append((name, bool(condition)))
    print(('PASS ' if condition else 'FAIL ') + name + (f' — {detail}' if detail and not condition else ''))


def ff(*args, timeout=120):
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', *args], check=True, timeout=timeout)


def streams(path):
    out = subprocess.run([FFPROBE, '-v', 'error', '-show_streams', '-of', 'json', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)['streams']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_media(folder: Path) -> dict:
    m = {}
    m['plain'] = folder / 'plain.mp4'
    ff('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=24:duration=3', '-f', 'lavfi', '-i', 'sine=f=300:duration=3',
       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(m['plain']))
    png = folder / 'art.png'
    ff('-f', 'lavfi', '-i', 'color=red:size=120x120:d=1', '-frames:v', '1', str(png))
    m['cover_mp4'] = folder / 'cover.mp4'
    ff('-i', str(m['plain']), '-i', str(png), '-map', '0', '-map', '1', '-c', 'copy',
       '-disposition:v:1', 'attached_pic', str(m['cover_mp4']))
    srt = folder / 'subs.srt'
    srt.write_text('1\n00:00:00,500 --> 00:00:02,000\nHello friend\n', encoding='utf-8')
    m['subs_cover_mkv'] = folder / 'subs_cover.mkv'
    ff('-i', str(m['plain']), '-i', str(srt), '-map', '0', '-map', '1', '-c', 'copy', '-c:s', 'srt',
       '-attach', str(png), '-metadata:s:t', 'mimetype=image/png', '-metadata:s:t', 'filename=cover.png',
       str(m['subs_cover_mkv']))
    m['tmcd_mov'] = folder / 'camera.mov'
    ff('-i', str(m['plain']), '-c', 'copy', '-timecode', '01:00:00:00', str(m['tmcd_mov']))
    m['long'] = folder / 'long.mkv'
    ff('-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=24:duration=40', '-f', 'lavfi', '-i', 'sine=duration=40',
       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(m['long']))
    data = m['long'].read_bytes()
    m['truncated'] = folder / 'truncated.mkv'
    m['truncated'].write_bytes(data[:len(data) * 55 // 100])
    m['corrupt'] = folder / 'corrupt.mkv'
    m['corrupt'].write_bytes(os.urandom(150_000))
    m['raw'] = folder / 'no_duration.h264'
    ff('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=24:duration=20', '-c:v', 'libx264', '-preset',
       'ultrafast', '-f', 'h264', str(m['raw']))
    m['scope'] = folder / 'scope_1080.mkv'
    ff('-f', 'lavfi', '-i', 'testsrc2=size=1920x804:rate=24:duration=3', '-f', 'lavfi', '-i', 'sine=duration=3',
       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(m['scope']))
    m['cover1080'] = folder / 'cover_1080.mp4'
    ff('-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=24:duration=3', '-i', str(png), '-map', '0', '-map', '1',
       '-c:v:0', 'libx264', '-preset', 'ultrafast', '-c:v:1', 'copy', '-disposition:v:1', 'attached_pic',
       str(m['cover1080']))
    m['robot'] = folder / 'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov (1080p BluRay x265 RCVR).mkv'
    shutil.copy2(m['subs_cover_mkv'], m['robot'])
    return m


def runner(out: Path):
    return QueueRunner(FFMPEG, FFPROBE, detect_encoders(FFMPEG), queue.Queue(), log_dir=str(out / 'logs'))


_SERIAL = iter(range(10_000))


def add(r, src, out: Path, profile, audio='copy', resolution='Original'):
    job_id = len(r.jobs)
    dst = out / f'{next(_SERIAL):03d} {output_name(str(src), profile, resolution=resolution)}'
    r.add(new_job(job_id, str(src), str(dst), profile, audio, resolution))
    return r.jobs[-1]


def no_partials(folder: Path):
    return not [p for p in folder.rglob('*') if '.eidolith-' in p.name]


def section_batch(m, out):
    r = runner(out)
    jobs = [add(r, m['plain'].with_name('missing.mp4'), out, 'Fast CPU H.264'),
            add(r, m['plain'], out, 'Fast CPU H.264'),
            add(r, m['corrupt'], out, 'Fast CPU H.264'),
            add(r, m['truncated'], out, 'Fast CPU H.264'),
            add(r, m['plain'], out, 'NVIDIA H.264 (fastest compatibility)') if 'h264_nvenc' in r.encoders else None,
            add(r, m['cover_mp4'], out, 'Lossless remux')]
    jobs = [j for j in jobs if j]
    order = []
    r.start()
    while r.running():
        if r.current is not None and (not order or order[-1] != r.current['id']):
            order.append(r.current['id'])
        time.sleep(0.02)
    statuses = [j['status'] for j in jobs]
    check('1 queue processed every job (no stop after first)', all(s in ('completed', 'failed') for s in statuses), statuses)
    check('1 jobs ran in list order', order == sorted(order), order)
    check('1 missing input -> FAILED, queue continued', jobs[0]['status'] == 'failed' and 'missing' in jobs[0]['error'])
    check('1 good job after a failure completed', jobs[1]['status'] == 'completed')
    check('1 corrupt input -> FAILED with ffprobe reason', jobs[2]['status'] == 'failed' and 'ffprobe' in jobs[2]['error'])
    check('1 truncated input -> FAILED by validation (duration)', jobs[3]['status'] == 'failed'
          and 'duration' in jobs[3]['error'], jobs[3]['error'])
    nv = [j for j in jobs if j['profile'].startswith('NVIDIA')]
    if nv:
        gpu = shutil.which('nvidia-smi') is not None
        if gpu:
            check('1 NVENC job ran on available NVIDIA hardware', nv[0]['status'] == 'completed', nv[0]['error'])
        else:
            check('1 NVENC without GPU -> FAILED with actionable cause', nv[0]['status'] == 'failed'
                  and 'NVIDIA encoder could not start' in nv[0]['error'], nv[0]['error'])
    check('1 last job completed after earlier failures', jobs[-1]['status'] == 'completed')
    log = Path(jobs[1]['log_path']).read_text(encoding='utf-8')
    check('1 per-job log has command, stderr, exit code, checks, output',
          all(k in log for k in ('COMMAND: ', '--- FFmpeg stderr ---', 'EXIT CODE: 0', 'VERIFIED track counts',
                                 'COMPLETED: ', 'FINAL STATUS: COMPLETED')))
    check('1 every started job has its own log file', len({j['log_path'] for j in jobs}) == len(jobs)
          and all(Path(j['log_path']).is_file() for j in jobs))
    check('1 no partial files left', no_partials(out))
    check('1 no FFmpeg child left running', r.active_proc is None)


def section_tracks(m, out):
    r = runner(out)
    a = add(r, m['cover_mp4'], out, 'Faster CPU AV1')
    b = add(r, m['cover_mp4'], out, 'Fast CPU H.264')
    c = add(r, m['subs_cover_mkv'], out, 'Fast CPU H.264')
    d = add(r, m['subs_cover_mkv'], out, 'Lossless remux')
    e = add(r, m['tmcd_mov'], out, 'Fast CPU H.264')
    r.start()
    r.wait(600)
    for job in (a, b, c, d, e):
        check(f'2 {Path(job["src"]).name} -> {job["profile"]} completed', job['status'] == 'completed', job['error'])

    def covers(path):
        return [s for s in streams(path) if s.get('disposition', {}).get('attached_pic')]
    if a['status'] == 'completed':
        sa = streams(a['dst'])
        cv = covers(a['dst'])
        check('2 MKV output keeps cover art as attachment', len(cv) == 1 and cv[0].get('tags', {}).get('mimetype') == 'image/png')
        main = [s for s in sa if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
        check('2 SVT-AV1 output is real 10-bit AV1', main and main[0]['codec_name'] == 'av1'
              and '10' in main[0].get('pix_fmt', ''), main and main[0].get('pix_fmt'))
    if b['status'] == 'completed':
        check('2 MP4 output keeps cover art', len(covers(b['dst'])) == 1)
    if c['status'] == 'completed':
        sc = streams(c['dst'])
        check('2 SRT converted to mov_text for MP4', any(s['codec_name'] == 'mov_text' for s in sc))
        check('2 report says subtitles were converted', any(x.startswith('CONVERT subtitles') for x in c['report']))
    if d['status'] == 'completed':
        sd = streams(d['dst'])
        check('2 remux keeps subtitles + cover', any(s['codec_type'] == 'subtitle' for s in sd) and len(covers(d['dst'])) == 1)
    check('2 timecode data stream dropped and reported', any(x.startswith('DROP data') for x in e['report']))
    # FFmpeg cannot synthesise bitmap subtitles from text, so the PGS rule is
    # checked against a probe result shaped like a Blu-ray remux.
    pgs = {'streams': [{'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'disposition': {}},
                       {'index': 1, 'codec_type': 'audio', 'codec_name': 'truehd'},
                       {'index': 2, 'codec_type': 'subtitle', 'codec_name': 'hdmv_pgs_subtitle'}]}
    try:
        plan_streams(pgs, 'Legacy compatibility', 'opus')
        check('2 PGS subtitles -> MP4 blocked before encoding', False)
    except PlanError as exc:
        check('2 PGS subtitles -> MP4 blocked before encoding', 'MKV profile' in str(exc))
    try:
        plan_streams(dict(pgs, streams=pgs['streams'][:2]), 'Legacy compatibility', 'copy')
        check('2 TrueHD copy -> MP4 blocked before encoding', False)
    except PlanError as exc:
        check('2 TrueHD copy -> MP4 blocked before encoding', 'opus' in str(exc))
    mkv = plan_streams(pgs, 'Balanced archive (default)')
    check('2 PGS subtitles copied in MKV plan', ['-c:s', 'copy'] == mkv['extra'][:2] and mkv['expected']['subtitle'] == 1)
    check('2 no partial or cover temp files left', no_partials(out))


def section_resolution(m, out):
    r = runner(out)
    scope = add(r, m['scope'], out, 'Fast AV1 (preset 8)', resolution='720p')
    cover = add(r, m['cover1080'], out, 'Fast CPU H.264', resolution='720p')
    small = add(r, m['plain'], out, 'Fast CPU H.264', resolution='720p')
    remux = add(r, m['cover1080'], out, 'Lossless remux', resolution='720p')
    r.start()
    r.wait(600)

    def size(path):
        v = [s for s in streams(path) if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
        return (v[0]['width'], v[0]['height'])
    check('6 2.39:1 1080p -> 720p keeps aspect (1280x536), preset-8 AV1', scope['status'] == 'completed'
          and size(scope['dst']) == (1280, 536) and '[AV1 720p]' in scope['dst'], scope['error'])
    check('6 1080p -> 1280x720 with cover art untouched', cover['status'] == 'completed'
          and size(cover['dst']) == (1280, 720)
          and [(s['width'], s['height']) for s in streams(cover['dst']) if s.get('disposition', {}).get('attached_pic')]
          == [(120, 120)], cover['error'])
    check('6 smaller source is not upscaled', small['status'] == 'completed' and size(small['dst']) == (320, 180)
          and any('already within 720p' in x for x in small['report']))
    check('6 Lossless remux + 720p blocked with reason', remux['status'] == 'failed' and 'cannot resize' in remux['error'])
    check('6 scaled size verified in report', any('VERIFIED video: av1 1280x536' in x for x in scope['report']))


def section_cancel(m, out):
    r = runner(out)
    slow = add(r, m['long'], out, 'High fidelity')
    nxt = add(r, m['plain'], out, 'Fast CPU H.264')
    r.start()
    deadline = time.monotonic() + 60
    while (slow['status'] != 'converting' or not slow.get('last_activity')) and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(1.5)
    check('3 progress observable while converting', slow['status'] == 'converting' and slow.get('percent') is not None
          and slow.get('last_activity'), slow['progress'])
    r.cancel_current()
    r.wait(120)
    check('3 CANCEL CURRENT cancels one job only', slow['status'] == 'cancelled')
    check('3 queue continued after cancel', nxt['status'] == 'completed')
    check('3 cancelled partial removed', no_partials(out))

    r = runner(out)
    slow = add(r, m['long'], out, 'High fidelity')
    rest = [add(r, m['plain'], out, 'Fast CPU H.264'), add(r, m['plain'], out, 'Lossless remux')]
    r.start()
    while slow['status'] != 'converting':
        time.sleep(0.05)
    time.sleep(1)
    r.stop_queue()
    r.wait(60)
    check('3 STOP QUEUE cancels current, rest stay queued', slow['status'] == 'cancelled'
          and [j['status'] for j in rest] == ['queued', 'queued'])
    r.start()
    r.wait(120)
    check('3 START runs queued jobs only (cancelled not rerun)', slow['status'] == 'cancelled'
          and all(j['status'] == 'completed' for j in rest))
    check('3 START with only cancelled jobs explains RETRY', 'RETRY FAILED' in r.start())
    check('3 RETRY is explicit and re-queues', r.retry() == 1 and slow['status'] == 'queued')


def section_restart(m, out):
    if not sys.platform.startswith('linux'):
        print('SKIP 4 restart/orphan test is Linux-only')
        return
    child = out / 'child.py'
    qfile = out / 'queue.json'
    child.write_text(textwrap.dedent(f'''
        import sys, json, os, queue, time
        sys.path.insert(0, {str(RUNTIME)!r})
        from oracle_eidolith_jobs import QueueRunner, new_job
        from oracle_eidolith_core import detect_encoders
        def persist(d):
            open({str(qfile)!r} + '.tmp', 'w').write(json.dumps(d)); os.replace({str(qfile)!r} + '.tmp', {str(qfile)!r})
        r = QueueRunner({FFMPEG!r}, {FFPROBE!r}, detect_encoders({FFMPEG!r}), queue.Queue(), None, persist)
        r.add(new_job(0, {str(m['long'])!r}, {str(out / 'long [AV1].mkv')!r}, 'High fidelity'))
        r.add(new_job(1, {str(m['plain'])!r}, {str(out / 'plain [H264].mp4')!r}, 'Fast CPU H.264'))
        r.start(); time.sleep(300)
    '''), encoding='utf-8')
    decoys = [out / 'unrelated.eidolith-notours.mkv', out / 'holiday.mkv', out / 'x.eidolith-0123456789ab-part.mkv.keep']
    for d in decoys:
        d.write_bytes(b'user data')
    proc = subprocess.Popen([sys.executable, str(child)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            saved = json.loads(qfile.read_text())
            if saved[0].get('pid') and saved[0].get('temp_path') and Path(saved[0]['temp_path']).exists():
                break
        except (OSError, ValueError, IndexError, KeyError):
            pass
        time.sleep(0.1)
    proc.kill()          # simulate a crash: FFmpeg is orphaned and keeps writing
    proc.wait()
    saved = json.loads(qfile.read_text())
    partial, pid = saved[0]['temp_path'], saved[0]['pid']
    check('4 crash left an orphaned FFmpeg + partial', Path(partial).exists() and Path(f'/proc/{pid}').exists())
    fresh = QueueRunner('', '', set(), queue.Queue())
    fresh.restore(saved)
    time.sleep(0.2)
    job0, job1 = fresh.jobs[0], fresh.jobs[1]
    check('4 running job marked INTERRUPTED', job0['status'] == 'interrupted')
    check('4 queued job restored as queued, not started', job1['status'] == 'queued' and not fresh.running())
    check('4 orphaned FFmpeg stopped', not Path(f'/proc/{pid}').exists() or
          os.fsencode(partial) not in Path(f'/proc/{pid}/cmdline').read_bytes())
    check('4 owned partial removed', not Path(partial).exists())
    check('4 unrelated / look-alike files untouched', all(d.read_bytes() == b'user data' for d in decoys))


def section_panel(m, out):
    import tkinter as tk
    from oracle_eidolith import EidolithPanel
    root = tk.Tk()
    root.geometry('1220x850')

    def pump(seconds=0.1):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            time.sleep(0.02)
    panel = EidolithPanel(root, on_home=lambda: None)
    panel.pack(fill='both', expand=True)
    pump(0.2)
    panel.output_var.set(str(out))
    panel.files = [str(m['robot']), str(m['raw']), str(m['long'])]
    panel._load_files()
    panel._set_nav('CONVERT')
    panel.convert_list.selection_clear(0, 'end')
    panel.convert_list.selection_set(0, 1)
    panel.profile.set('Fast CPU H.264')
    panel.queue_selected()
    pump(0.1)
    names = [Path(j['dst']).name for j in panel.queue_items]
    check('5 default output name is short (show, year, SxxEyy)',
          names[0] == 'Mr. Robot (2015) - S01E01.mp4', names[0])
    check('5 queue saved to state', (Path(STATE) / 'eidolith_queue.json').is_file())
    assert panel.shutdown()
    root.destroy()

    root = tk.Tk()
    root.geometry('1220x850')
    panel = EidolithPanel(root, on_home=lambda: None)
    panel.pack(fill='both', expand=True)
    pump(0.2)
    check('5 queue restored after restart, not auto-started',
          [j['status'] for j in panel.queue_items] == ['queued', 'queued'] and not panel.runner.running())
    panel._set_nav('QUEUE')
    panel.start_queue()
    saw_indeterminate = saw_headline = False
    deadline = time.monotonic() + 120
    while panel.runner.running() and time.monotonic() < deadline:
        pump(0.05)
        head = panel.job_headline.cget('text')
        detail = panel.job_detail.cget('text')
        if 'no_duration' in head and 'CONVERTING' in head:
            saw_headline = head.startswith('JOB 2 OF 2')
            saw_indeterminate |= ('duration unknown' in detail and '%' not in detail.split('·')[0]
                                  and bool(panel.progress_canvas.find_all()))
    check('5 headline shows job index/total and state', saw_headline)
    check('5 unknown duration shows indeterminate progress, no invented %', saw_indeterminate)
    statuses = [j['status'] for j in panel.queue_items]
    check('5 panel queue completed both jobs', statuses == ['completed', 'completed'], statuses)
    robot_out = panel.queue_items[0]['dst']
    check('5 Mr. Robot job keeps subtitles and cover in MP4',
          sum(s['codec_type'] == 'subtitle' for s in streams(robot_out)) == 1
          and sum(bool(s.get('disposition', {}).get('attached_pic')) for s in streams(robot_out)) == 1)
    # Determinate progress with a long CPU AV1 encode, then stop from the GUI.
    panel._set_nav('CONVERT')
    panel.convert_list.selection_clear(0, 'end')
    panel.convert_list.selection_set(2)
    panel.profile.set('High fidelity')
    panel.queue_selected()
    panel.start_queue()
    seen = ''
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        pump(0.1)
        detail = panel.job_detail.cget('text')
        if '%' in detail and 'elapsed' in detail and 'last FFmpeg activity' in detail and 'ETA' in detail:
            seen = detail
            break
    check('5 determinate progress shows %, elapsed, speed/ETA, last activity', bool(seen), panel.job_detail.cget('text'))
    panel.stop_queue()
    deadline = time.monotonic() + 30
    while panel.runner.running() and time.monotonic() < deadline:
        pump(0.05)
    check('5 GUI STOP QUEUE cancels the job', panel.queue_items[-1]['status'] == 'cancelled')
    panel.queue_list.selection_clear(0, 'end')
    panel.queue_list.selection_set(0)
    panel.copy_diagnostics()
    clip = root.clipboard_get()
    check('5 diagnostics copied without local folder paths', 'EIDOLITH 0.4 diagnostic report' in clip
          and str(out) not in clip and str(m['robot'].parent) not in clip and '<source folder>' in clip)
    panel.resolution.set('720p')
    panel.profile.set('Lossless remux')
    panel._set_nav('CONVERT')
    panel.convert_list.selection_clear(0, 'end')
    panel.convert_list.selection_set(0)
    before = len(panel.queue_items)
    panel.queue_selected()
    check('5 GUI refuses Lossless remux + 720p at queue time', len(panel.queue_items) == before
          and 'cannot resize' in panel.status_var.get())
    panel.profile.set('Fast CPU H.264')
    pump(0.1)
    check('5 name preview is short by default', panel.name_preview.cget('text').endswith('Mr. Robot (2015) - S01E01.mp4'),
          panel.name_preview.cget('text'))
    panel.name_format_tag.set(True)
    panel.name_episode_title.set(True)
    pump(0.1)
    check('5 opt-in episode title + 720p tag', panel.name_preview.cget('text').endswith(
          'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov [H264 720p].mp4'), panel.name_preview.cget('text'))
    panel.name_format_tag.set(False)
    panel.name_episode_title.set(False)
    check('5 log folder under state dir', Path(panel.log_dir).is_dir() and Path(panel.log_dir).parent == Path(STATE))
    assert panel.shutdown()
    root.destroy()


def main():
    if not FFMPEG or not FFPROBE:
        print('SKIP: ffmpeg/ffprobe not available')
        return
    enc = detect_encoders(FFMPEG)
    missing = {'libx264', 'libsvtav1'} - enc
    if missing:
        print('SKIP: FFmpeg lacks', ', '.join(sorted(missing)))
        return
    with tempfile.TemporaryDirectory(prefix='eidolith-reliability-') as tmp:
        tmp = Path(tmp)
        src = tmp / 'sources'
        src.mkdir()
        m = make_media(src)
        before = {p: sha(p) for p in src.iterdir()}
        for n, (name, fn) in enumerate((('batch', section_batch), ('tracks', section_tracks),
                                        ('cancel', section_cancel), ('restart', section_restart),
                                        ('panel', section_panel), ('resolution', section_resolution)), 1):
            out = tmp / f'out{n}-{name}'
            out.mkdir()
            fn(m, out)
        check('sources unchanged byte-for-byte', all(sha(p) == h for p, h in before.items()))
    passed = sum(ok for _, ok in RESULTS)
    print(f'\nEIDOLITH 0.4 queue reliability: {passed}/{len(RESULTS)} checks passed')
    if passed != len(RESULTS):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
