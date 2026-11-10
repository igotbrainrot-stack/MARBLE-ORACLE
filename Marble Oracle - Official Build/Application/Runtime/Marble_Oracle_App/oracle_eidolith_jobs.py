"""EIDOLITH queue engine: stream planning, FFmpeg execution, logs, validation.

UI-independent so that batch behaviour can be tested without a display.
The Tk panel (oracle_eidolith.py) owns one QueueRunner and renders its jobs.

Safety rules carried over from 0.3 and kept here:
* sources are only ever read;
* output is written to a uniquely named temporary file owned by the job,
  probed, then published without overwriting anything;
* only files this engine created (``*.eidolith-<12 hex>-part*`` /
  ``-cover<n>*``) are ever deleted.

Queue rules (0.4):
* START runs jobs whose status is ``queued`` only, in list order, re-reading
  the list between jobs so items queued during a run are processed;
* a failing job (missing input, FFmpeg error, validation error) is marked
  FAILED and the queue continues with the next job;
* CANCEL CURRENT cancels one job and continues; STOP QUEUE cancels the
  current job and leaves the remaining jobs queued;
* failed / cancelled / interrupted jobs are re-queued only by an explicit
  RETRY.
"""
from __future__ import annotations

import json
import os
import platform
import queue as _queue
import re
import shlex
import signal
import subprocess
import threading
import time
import uuid

from oracle_eidolith_core import (PROFILES, RESOLUTIONS, encoding_args, fit_resolution, profile_support,
                                  progress_seconds, seconds_label, safe_piece)

ENGINE_VERSION = '0.4'
NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

ACTIVE = ('probing', 'converting', 'validating')
FINISHED = ('completed', 'failed', 'cancelled', 'interrupted')
RETRYABLE = ('failed', 'cancelled', 'interrupted')
OWNED_PART = re.compile(r'\.eidolith-[0-9a-f]{12}-(?:part|cover\d+)(?:\.[A-Za-z0-9]+)?$')
LOG_NAME = re.compile(r'^\d{8}-\d{6}-job\d+-.*\.log$')
MAX_LOG_FILES = 300

TEXT_SUBS = {'subrip', 'srt', 'ass', 'ssa', 'webvtt', 'mov_text', 'text'}
STYLED_SUBS = {'ass', 'ssa'}
MP4_BAD_AUDIO = {'truehd', 'mlp', 'wmav1', 'wmav2', 'wmapro', 'cook', 'ra_144', 'ra_288',
                 'sipr', 'atrac3', 'vorbis', 'comfortnoise'}
OPUS_LAYOUTS = {'mono', 'stereo', '3.0', 'quad', '5.0', '5.1', '6.1', '7.1'}
OPUS_BY_CHANNELS = {1: 'mono', 2: 'stereo', 3: '3.0', 4: 'quad', 5: '5.0', 6: '5.1', 7: '6.1', 8: '7.1'}
IMAGE_CODECS = {'png': ('png', 'image/png'), 'mjpeg': ('jpg', 'image/jpeg'),
                'bmp': ('bmp', 'image/bmp'), 'gif': ('gif', 'image/gif'),
                'webp': ('webp', 'image/webp')}
EXPECTED_VIDEO = {'libsvtav1': 'av1', 'av1_nvenc': 'av1', 'libaom-av1': 'av1',
                  'hevc_nvenc': 'hevc', 'libx265': 'hevc',
                  'h264_nvenc': 'h264', 'libx264': 'h264'}
PROGRESS_KEYS = ('frame', 'fps', 'bitrate', 'total_size', 'out_time_us', 'out_time_ms',
                 'out_time', 'dup_frames', 'drop_frames', 'speed', 'progress')


class PlanError(RuntimeError):
    """The source cannot be converted with this profile without losing content."""


# --------------------------------------------------------------- probing
def probe(ffprobe: str, path: str, timeout: float = 90) -> dict:
    if not ffprobe:
        raise RuntimeError('ffprobe is required to inspect tracks before and after encoding')
    run = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         errors='replace', timeout=timeout, creationflags=NOWIN)
    if run.returncode:
        last = (run.stderr or '').strip().splitlines()[-1:] or ['no error text']
        raise RuntimeError(f'ffprobe could not read {os.path.basename(path)}: {last[0]}')
    try:
        return json.loads(run.stdout or '{}')
    except ValueError as exc:
        raise RuntimeError(f'ffprobe returned unreadable data for {os.path.basename(path)}') from exc


def classify(streams) -> dict:
    """Group streams; cover art (attached_pic) is separate from the main video."""
    out = {k: [] for k in ('primary', 'cover', 'audio', 'subtitle', 'attachment', 'data', 'other')}
    video_index = 0
    for s in streams or []:
        kind = s.get('codec_type')
        if kind == 'video':
            entry = dict(s, _vindex=video_index)
            video_index += 1
            (out['cover'] if (s.get('disposition') or {}).get('attached_pic') else out['primary']).append(entry)
        elif kind in ('audio', 'subtitle', 'attachment', 'data'):
            out[kind].append(s)
        else:
            out['other'].append(s)
    return out


def _codecs(items):
    names = []
    for s in items:
        name = s.get('codec_name')
        if not name or name == 'unknown':
            tags = s.get('tags') or {}
            name = tags.get('filename') or tags.get('mimetype') or 'unknown'
        names.append(str(name))
    return ', '.join(names)


def _describe_audio(items):
    parts = []
    for a in items:
        tags = a.get('tags') or {}
        bits = [str(a.get('codec_name') or '?')]
        if tags.get('language'):
            bits.append(tags['language'])
        if a.get('channels'):
            bits.append(f'{a["channels"]}ch')
        if tags.get('title'):
            bits.append(f'"{tags["title"]}"')
        parts.append(' '.join(bits))
    return ', '.join(parts)


def _is_10bit(pix_fmt: str) -> bool:
    pix_fmt = str(pix_fmt or '')
    return '10' in pix_fmt or pix_fmt.startswith('p010')


# ---------------------------------------------------------- stream plan
def plan_streams(info: dict, profile_name: str, audio_mode: str = 'copy', resolution: str = 'Original',
                 slim: bool = False) -> dict:
    """Decide exactly which tracks are kept, converted or dropped.

    Raises PlanError (before anything is written) when the profile cannot
    carry the source safely. Every decision is written to ``report`` so the
    log never claims fidelity for a track that was not carried.
    """
    profile = PROFILES[profile_name]
    container, vcodec = profile['container'], profile['codec']
    copy_all = vcodec == 'copy'
    groups = classify(info.get('streams', []))
    report, maps, extra, attach = [], ['-map', '0:V:0'], [], []
    expected = dict(primary=1, cover=0, audio=0, subtitle=0, attachment=0)

    if len(groups['primary']) != 1:
        raise PlanError(f'Found {len(groups["primary"])} main video tracks; EIDOLITH converts exactly one '
                        'and would otherwise drop pictures. Source unchanged.')
    video = groups['primary'][0]
    if not copy_all:
        if str(video.get('color_transfer', '')).lower() in ('smpte2084', 'arib-std-b67'):
            raise PlanError('HDR source detected: accurate HDR re-encoding is not yet verified. '
                            'Use Lossless remux or an HDR-aware workflow. Source unchanged.')
        if any('dolby vision' in str(v).lower() or 'dovi' in str(v).lower()
               for d in video.get('side_data_list', []) for v in d.values()):
            raise PlanError('Dolby Vision metadata detected; conversion blocked to avoid silent metadata loss.')
    if RESOLUTIONS.get(resolution or 'Original') and copy_all:
        raise PlanError(f'Lossless remux copies the video unchanged and cannot resize to {resolution}. '
                        'Set RESOLUTION to Original or choose an encoding profile. Source unchanged.')
    scale = None if copy_all else fit_resolution(video.get('width'), video.get('height'), resolution)
    target = 'copied' if copy_all else f'{EXPECTED_VIDEO.get(vcodec, vcodec)} via {vcodec}' + (
        f' ({profile.get("pix_fmt")})' if profile.get('pix_fmt') else '')
    if scale:
        target += f', scaled to {scale[0]}x{scale[1]}'
    elif RESOLUTIONS.get(resolution or 'Original'):
        target += f', already within {resolution} so size kept'
    report.append(f'KEEP video: {video.get("codec_name", "?")} {video.get("width", "?")}x{video.get("height", "?")} '
                  f'{video.get("pix_fmt", "")} -> {target}')

    audio_map = '0:a'
    meta_args = ['-map_metadata', '0', '-map_chapters', '0']
    if slim:
        # SLIM OUTPUT: main video + one audio track; everything else dropped
        # and listed, so nothing disappears unreported.
        if len(groups['audio']) > 1:
            keep = next((a for a in groups['audio'] if (a.get('disposition') or {}).get('default')),
                        groups['audio'][0])
            others = [a for a in groups['audio'] if a is not keep]
            report.append(f'DROP audio: {len(others)} extra track(s) [{_describe_audio(others)}] (slim output)')
            audio_map = f'0:a:{groups["audio"].index(keep)}'
            groups['audio'] = [keep]
        for kind, label in (('subtitle', 'subtitles'), ('attachment', 'attachments/fonts'), ('cover', 'cover art')):
            if groups[kind]:
                forced = sum(bool((x.get('disposition') or {}).get('forced')) for x in groups[kind])
                report.append(f'DROP {label}: {len(groups[kind])} [{_codecs(groups[kind])}] (slim output)'
                              + (f'; includes {forced} FORCED track(s) for foreign-language dialogue' if forced else ''))
                groups[kind] = []
        meta_args = ['-map_metadata', '-1', '-map_chapters', '-1']
        lang = ((groups['audio'][0].get('tags') or {}).get('language') if groups['audio'] else None)
        if lang:
            meta_args += ['-metadata:s:a:0', f'language={lang}']
        report.append('DROP chapters and title/tag metadata (slim output)'
                      + (f'; audio language "{lang}" kept' if lang else ''))

    if groups['audio']:
        if container == 'mp4' and audio_mode == 'copy' and not copy_all:
            bad = [a for a in groups['audio'] if str(a.get('codec_name')) in MP4_BAD_AUDIO
                   or str(a.get('codec_name', '')).startswith('pcm_')]
            if bad:
                raise PlanError(f'MP4 cannot hold copied {_codecs(bad)} audio. Choose an MKV profile '
                                'or set AUDIO to opus. Source unchanged.')
        maps += ['-map', audio_map]
        expected['audio'] = len(groups['audio'])
        how = 'copied' if audio_mode == 'copy' or copy_all else 'converted to Opus 128k'
        if audio_mode == 'opus' and not copy_all:
            # libopus only accepts its own channel layouts; DVD/Blu-ray AC3/DTS
            # are usually '5.1(side)', which made every Opus job fail in 0.3.
            for n, a in enumerate(groups['audio']):
                layout = str(a.get('channel_layout') or '')
                if layout in OPUS_LAYOUTS:
                    continue
                target = OPUS_BY_CHANNELS.get(int(a.get('channels') or 0), '7.1')
                extra += [f'-filter:a:{n}', f'aformat=channel_layouts={target}']
                report.append(f'CONVERT audio layout: track {n + 1} {layout or str(a.get("channels")) + "ch"} '
                              f'-> {target} (required by Opus)')
        report.append(f'KEEP audio: {len(groups["audio"])} track(s) [{_describe_audio(groups["audio"])}] {how}')

    if groups['subtitle']:
        maps += ['-map', '0:s']
        expected['subtitle'] = len(groups['subtitle'])
        if container == 'mkv':
            extra += ['-c:s', 'copy']
            report.append(f'KEEP subtitles: {len(groups["subtitle"])} track(s) [{_codecs(groups["subtitle"])}] copied')
        else:
            bitmap = [s for s in groups['subtitle'] if str(s.get('codec_name')) not in TEXT_SUBS]
            if bitmap:
                raise PlanError(f'MP4 cannot hold {_codecs(bitmap)} subtitles. Choose an MKV profile '
                                '(they are copied there unchanged). Source unchanged.')
            extra += ['-c:s', 'mov_text']
            styled = any(str(s.get('codec_name')) in STYLED_SUBS for s in groups['subtitle'])
            report.append(f'CONVERT subtitles: {len(groups["subtitle"])} text track(s) [{_codecs(groups["subtitle"])}] '
                          '-> mov_text for MP4' + ('; ASS/SSA styling is lost' if styled else ''))

    if groups['attachment']:
        if container != 'mkv':
            raise PlanError('Attachments (e.g. subtitle fonts) found; MP4 would discard them. '
                            'Use an MKV profile. Source unchanged.')
        maps += ['-map', '0:t']
        extra += ['-c:t', 'copy']
        expected['attachment'] = len(groups['attachment'])
        report.append(f'KEEP attachments: {len(groups["attachment"])} [{_codecs(groups["attachment"])}] copied')

    covers = []
    for cover in groups['cover']:
        codec = str(cover.get('codec_name'))
        if codec not in IMAGE_CODECS:
            report.append(f'DROP cover art: stream {cover.get("index")} uses {codec}, which cannot be carried safely')
            continue
        ext, mime = IMAGE_CODECS[codec]
        tags = cover.get('tags') or {}
        item = dict(vindex=cover['_vindex'], codec=codec, ext=ext,
                    mime=tags.get('mimetype') or mime,
                    filename=tags.get('filename') or f'cover{"" if not covers else len(covers) + 1}.{ext}')
        if container == 'mp4':
            out_index = 1 + len(covers)
            maps += ['-map', f'0:v:{cover["_vindex"]}']
            extra += [f'-c:v:{out_index}', 'copy', f'-disposition:v:{out_index}', 'attached_pic']
            item['mode'] = 'stream'
        else:
            # Matroska: a copied picture stream would become a 1-frame video
            # track. Extract it and store it as a real attachment instead.
            item['mode'] = 'attach'
            item['t_index'] = expected['attachment'] + len(attach)
            attach.append(item)
        covers.append(item)
    if covers:
        expected['cover'] = len(covers)
        report.append(f'KEEP cover art: {len(covers)} image(s) [{", ".join(c["codec"] for c in covers)}] '
                      + ('as Matroska attachments' if container == 'mkv' else 'as MP4 cover art'))

    if groups['data']:
        report.append(f'DROP data: {len(groups["data"])} stream(s) [{_codecs(groups["data"])}] '
                      '(timecode/metadata tracks are not carried; MP4 may regenerate timecode)')
    if groups['other']:
        report.append(f'DROP unknown: {len(groups["other"])} stream(s) of unsupported type')

    if copy_all:
        codec_args = ['-c', 'copy']
    else:
        codec_args, rename = [], {'-c:v': '-c:v:0', '-pix_fmt': '-pix_fmt:v:0', '-crf': '-crf:v:0',
                                  '-preset': '-preset:v:0', '-rc': '-rc:v:0', '-cq': '-cq:v:0', '-b:v': '-b:v:0'}
        args = encoding_args(profile_name, audio_mode)
        i = 0
        while i < len(args):
            key, val = args[i], args[i + 1]
            if key != '-c:s':                 # subtitles are decided above
                codec_args += [rename.get(key, key), val]
            i += 2
        if scale:
            # Applies to the main video only; copied cover art is untouched.
            codec_args += ['-filter:v:0', f'scale={scale[0]}:{scale[1]}:flags=lanczos']
    return dict(maps=maps, codec_args=codec_args, extra=extra, covers=covers, attach=attach,
                expected=expected, report=report, container=container, scale=scale, meta_args=meta_args)


def build_command(ffmpeg: str, src: str, dst: str, plan: dict) -> list:
    cmd = [ffmpeg, '-hide_banner', '-nostdin', '-n', '-stats_period', '1',
           '-progress', 'pipe:1', '-nostats', '-i', src]
    for item in plan['attach']:
        cmd += ['-attach', item['temp_path'],
                f'-metadata:s:t:{item["t_index"]}', f'mimetype={item["mime"]}',
                f'-metadata:s:t:{item["t_index"]}', f'filename={item["filename"]}']
    cmd += plan['maps'] + plan.get('meta_args', ['-map_metadata', '0', '-map_chapters', '0'])
    cmd += plan['codec_args'] + plan['extra']
    cmd.append(dst)
    return cmd


def validate_output(ffprobe: str, src_info: dict, dst: str, plan: dict, profile_name: str) -> list:
    """Re-probe the finished temporary file. Returns human-readable checks."""
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        raise RuntimeError('Output file is empty or missing')
    out = probe(ffprobe, dst)
    got = classify(out.get('streams', []))
    exp = plan['expected']
    lines = []
    for kind in ('primary', 'cover', 'audio', 'subtitle', 'attachment'):
        if len(got[kind]) != exp[kind]:
            label = 'main video' if kind == 'primary' else ('cover art' if kind == 'cover' else kind)
            raise RuntimeError(f'{label} track count {len(got[kind])}, expected {exp[kind]}')
    lines.append('VERIFIED track counts: ' + ', '.join(f'{k}={exp[k]}' for k in exp))
    profile = PROFILES[profile_name]
    video = got['primary'][0]
    if profile['codec'] == 'copy':
        want = classify(src_info.get('streams', []))['primary'][0].get('codec_name')
    else:
        want = EXPECTED_VIDEO.get(profile['codec'])
    if want and video.get('codec_name') != want:
        raise RuntimeError(f'Output video codec is {video.get("codec_name")}, expected {want}')
    if profile.get('pix_fmt') and _is_10bit(profile['pix_fmt']) and not _is_10bit(video.get('pix_fmt')):
        raise RuntimeError(f'Output is {video.get("pix_fmt")}, expected 10-bit')
    if plan.get('scale') and (int(video.get('width') or 0), int(video.get('height') or 0)) != tuple(plan['scale']):
        raise RuntimeError(f'Output is {video.get("width")}x{video.get("height")}, expected '
                           f'{plan["scale"][0]}x{plan["scale"][1]}')
    lines.append(f'VERIFIED video: {video.get("codec_name")} {video.get("width")}x{video.get("height")} {video.get("pix_fmt", "")}')
    a = float(src_info.get('format', {}).get('duration', 0) or 0)
    b = float(out.get('format', {}).get('duration', 0) or 0)
    if a > 0 and abs(a - b) > max(1.5, a * 0.01):
        raise RuntimeError(f'Output duration changed unexpectedly ({a:.1f}s -> {b:.1f}s)')
    lines.append(f'VERIFIED duration: {b:.2f}s (source {a:.2f}s)')
    if got['data']:
        lines.append(f'NOTE output contains {len(got["data"])} data stream(s) [{_codecs(got["data"])}] written by the muxer')
    return lines


# ------------------------------------------------------------- helpers
def command_text(cmd) -> str:
    return subprocess.list2cmdline(cmd) if os.name == 'nt' else shlex.join(cmd)


def redact(text: str, paths=()) -> str:
    """Replace local folders / home with placeholders for shareable reports."""
    pairs = []
    for label, path in paths:
        if path:
            pairs.append((os.path.abspath(path), label))
    home = os.path.expanduser('~')
    if home and home not in ('/', '~'):
        pairs.append((home, '~'))
    for path, label in sorted(pairs, key=lambda p: -len(p[0])):
        text = text.replace(path, label)
        if os.name == 'nt':
            text = text.replace(path.replace('\\', '/'), label)
    return text


def tail_lines(path: str, count: int = 40, start: int = 0) -> list:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            if start:
                handle.seek(start)
            return handle.read().splitlines()[-count:]
    except OSError:
        return []


ERROR_HINT = re.compile(r'(?i)\b(?:error|cannot|could not|invalid|failed|not supported|no such|'
                        r'unknown encoder|not permitted|permission denied|unrecognized)\b')
NOISE = re.compile(r'(?i)^(?:frame=|size=|conversion failed!|error while filtering|'
                   r'\[out#\d+/\w+ @ [^\]]+\] nothing was written)')


def first_error_line(lines) -> str:
    """The most specific FFmpeg error line (first match is usually the cause)."""
    for line in lines:
        text = line.strip()
        if ERROR_HINT.search(text) and not NOISE.match(text):
            return text[:240]
    return lines[-1].strip()[:240] if lines else ''


def _pid_runs_path(pid, path) -> bool:
    """Linux only: does process `pid` still have our partial file in its command line?"""
    if not pid or os.name == 'nt':
        return False
    try:
        with open(f'/proc/{int(pid)}/cmdline', 'rb') as handle:
            return os.fsencode(path) in handle.read()
    except (OSError, ValueError):
        return False


def remove_owned_partial(path, pid=None) -> str:
    """Delete one partial file created by EIDOLITH. Returns '' or a reason."""
    if not path or not OWNED_PART.search(os.path.basename(path)):
        return 'not an EIDOLITH partial; left untouched'
    if not os.path.lexists(path):
        return ''
    if _pid_runs_path(pid, path):
        # An FFmpeg orphaned by a crash is still writing our partial: stop it.
        for sig, wait in ((signal.SIGTERM, 8.0), (getattr(signal, 'SIGKILL', signal.SIGTERM), 3.0)):
            try:
                os.kill(int(pid), sig)
            except OSError:
                break
            until = time.monotonic() + wait
            while time.monotonic() < until and _pid_runs_path(pid, path):
                time.sleep(0.1)
            if not _pid_runs_path(pid, path):
                break
    try:
        os.unlink(path)
        return ''
    except OSError as exc:
        return f'could not remove ({exc.strerror or exc}); will retry on next launch'


def reconcile_jobs(jobs: list) -> list:
    """After a restart: mark jobs that were running as INTERRUPTED and remove
    only their own partial files. Queued jobs stay queued (not auto-started)."""
    messages = []
    for job in jobs:
        stale = list(job.get('stale_partials') or [])
        if job.get('status') in ACTIVE:
            job['status'] = 'interrupted'
            job['progress'] = 'interrupted by app exit or crash — original unchanged'
            job['percent'] = None
            job['finished_at'] = time.time()
            stale += [p for p in [job.get('temp_path')] + list(job.get('cover_temps') or []) if p]
            messages.append(f'Job {job.get("id")} was interrupted: {os.path.basename(job.get("src", ""))}')
        job['temp_path'] = None
        job['cover_temps'] = []
        keep = []
        for path in dict.fromkeys(stale):
            reason = remove_owned_partial(path, job.get('pid'))
            if reason.startswith('could not'):
                keep.append(path)
                messages.append(f'Partial {os.path.basename(path)}: {reason}')
            elif not reason and path:
                messages.append(f'Removed owned partial {os.path.basename(path)}')
        job['stale_partials'] = keep
        job['pid'] = None
    return messages


PERSIST_KEYS = ('id', 'src', 'dst', 'profile', 'audio_mode', 'resolution', 'slim', 'status', 'progress', 'percent', 'duration',
                'created_at', 'started_at', 'finished_at', 'error', 'log_path', 'temp_path', 'cover_temps',
                'stale_partials', 'pid', 'report', 'attempts')


def new_job(job_id, src, dst, profile, audio_mode='copy', resolution='Original', slim=False) -> dict:
    return dict(id=job_id, src=src, dst=dst, profile=profile, audio_mode=audio_mode, resolution=resolution, slim=bool(slim),
                status='queued', progress='', percent=None, duration=0.0,
                created_at=time.time(), started_at=None, finished_at=None,
                last_activity=None, last_advance=None, out_seconds=0.0, speed=0.0,
                eta=None, error='', log_path='', temp_path=None, cover_temps=[],
                stale_partials=[], pid=None, report=[], attempts=0)


# --------------------------------------------------------------- runner
class QueueRunner:
    def __init__(self, ffmpeg, ffprobe, encoders, events=None, log_dir=None, persist=None):
        self.ffmpeg, self.ffprobe, self.encoders = ffmpeg, ffprobe, set(encoders or ())
        self.events = events if events is not None else _queue.Queue()
        self.log_dir = log_dir
        self.persist = persist
        self.jobs: list = []
        self.lock = threading.RLock()
        self.thread = None
        self.stop_event = threading.Event()
        self.skip_event = threading.Event()
        self.active_proc = None
        self.current = None
        self._ffmpeg_version = None

    # ---- list management
    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def save(self):
        if self.persist:
            with self.lock:
                data = [{k: j.get(k) for k in PERSIST_KEYS} for j in self.jobs]
            try:
                self.persist(data)
            except Exception as exc:  # persistence must never stop encoding
                self.emit('log', f'WARNING: queue state could not be saved: {exc}')

    def restore(self, saved) -> list:
        jobs = []
        for raw in saved or []:
            if not isinstance(raw, dict) or not raw.get('src') or not raw.get('dst') or raw.get('profile') not in PROFILES:
                continue
            job = new_job(raw.get('id', 0), raw['src'], raw['dst'], raw['profile'], raw.get('audio_mode', 'copy'),
                          raw.get('resolution') if raw.get('resolution') in RESOLUTIONS else 'Original')
            job.update({k: raw[k] for k in PERSIST_KEYS if k in raw})
            jobs.append(job)
        messages = reconcile_jobs(jobs)
        # Completed work is history (its log remains); everything else returns.
        jobs = [j for j in jobs if j.get('status') != 'completed']
        with self.lock:
            self.jobs[:] = jobs
        self.save()
        return messages

    def next_id(self) -> int:
        with self.lock:
            return 1 + max((int(j.get('id') or 0) for j in self.jobs), default=-1)

    def add(self, job):
        with self.lock:
            self.jobs.append(job)
        self.save()
        self.emit('refresh')

    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def pending(self):
        with self.lock:
            return [j for j in self.jobs if j['status'] == 'queued']

    def retry(self, statuses=RETRYABLE, ids=None) -> int:
        count = 0
        with self.lock:
            for job in self.jobs:
                if job['status'] in statuses and (ids is None or job['id'] in ids):
                    job.update(status='queued', progress='', percent=None, error='', eta=None,
                               started_at=None, finished_at=None, out_seconds=0.0, speed=0.0)
                    count += 1
        self.save()
        self.emit('refresh')
        return count

    def clear_finished(self) -> int:
        with self.lock:
            before = len(self.jobs)
            self.jobs[:] = [j for j in self.jobs if j['status'] not in FINISHED]   # in place: the worker sees it
            removed = before - len(self.jobs)
        self.save()
        self.emit('refresh')
        return removed

    def position(self, job):
        """(1-based index, total) of a job within the current list."""
        with self.lock:
            try:
                return self.jobs.index(job) + 1, len(self.jobs)
            except ValueError:
                return 0, len(self.jobs)

    # ---- control
    def start(self) -> str:
        if self.running():
            return 'Queue already running.'
        pending = self.pending()
        if not pending:
            retry = sum(j['status'] in RETRYABLE for j in self.jobs)
            return (f'No queued jobs. Use RETRY FAILED to re-queue {retry} failed/cancelled/interrupted job(s).'
                    if retry else 'No queued jobs to start.')
        self.stop_event.clear()
        self.skip_event.clear()
        self.thread = threading.Thread(target=self._run, name='eidolith-queue', daemon=True)
        self.thread.start()
        return f'Queue started: {len(pending)} job(s).'

    def _terminate_active(self):
        proc = self.active_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def cancel_current(self) -> str:
        if not self.running() or self.current is None:
            return 'No job is converting.'
        self.skip_event.set()
        self._terminate_active()
        return 'Cancelling current job; the queue will continue with the next job.'

    def stop_queue(self) -> str:
        if not self.running():
            return 'Queue is not running.'
        self.stop_event.set()
        self.skip_event.set()
        self._terminate_active()
        return 'Stopping queue: current job cancelled, remaining jobs stay queued.'

    def wait(self, timeout=None) -> bool:
        if self.thread:
            self.thread.join(timeout)
        return not self.running()

    # ---- worker
    def _next(self):
        with self.lock:
            return next((j for j in self.jobs if j['status'] == 'queued'), None)

    def _run(self):
        done = failed = cancelled = 0
        try:
            while not self.stop_event.is_set():
                job = self._next()
                if job is None:
                    break
                self.skip_event.clear()
                self.current = job
                try:
                    self._run_job(job)
                except Exception as exc:  # never let one job end the queue
                    job.update(status='failed', error=f'Internal error: {exc}', progress=f'Internal error: {exc}'[:160])
                    self.emit('log', f'FAILED (internal): {job["src"]} — {exc}')
                finally:
                    self.current = None
                    job['finished_at'] = time.time()
                    done += job['status'] == 'completed'
                    failed += job['status'] == 'failed'
                    cancelled += job['status'] == 'cancelled'
                    self.save()
                    self.emit('refresh')
        finally:
            left = len(self.pending())
            stopped = self.stop_event.is_set()
            summary = (f'Queue {"stopped" if stopped else "finished"}: {done} completed, {failed} failed, '
                       f'{cancelled} cancelled' + (f', {left} still queued' if left else '') + '. Originals retained.')
            self.emit('log', summary)
            self.emit('status', summary)
            self.emit('done', summary)

    def _ffmpeg_version_line(self):
        if self._ffmpeg_version is None:
            try:
                out = subprocess.run([self.ffmpeg, '-hide_banner', '-version'], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, timeout=8, creationflags=NOWIN)
                self._ffmpeg_version = (out.stdout.splitlines() or ['unknown'])[0]
            except (OSError, subprocess.SubprocessError):
                self._ffmpeg_version = 'unknown'
        return self._ffmpeg_version

    def _open_log(self, job):
        folder = self.log_dir
        if not folder:
            return None
        os.makedirs(folder, exist_ok=True)
        stem = safe_piece(os.path.splitext(os.path.basename(job['src']))[0], 'job')[:60]
        path = os.path.join(folder, f'{time.strftime("%Y%m%d-%H%M%S")}-job{int(job["id"]):04d}-{stem}.log')
        job['log_path'] = path
        self._prune_logs(folder)
        return open(path, 'a', encoding='utf-8', errors='replace')

    @staticmethod
    def _prune_logs(folder):
        try:
            names = sorted(n for n in os.listdir(folder) if LOG_NAME.match(n))
            for name in names[:-MAX_LOG_FILES]:
                os.unlink(os.path.join(folder, name))
        except OSError:
            pass

    def _log(self, handle, text, *, ui=True):
        if handle:
            handle.write(text + '\n')
            handle.flush()
        if ui:
            self.emit('log', text)

    def _set(self, job, status, progress=None, *, save=True):
        job['status'] = status
        if progress is not None:
            job['progress'] = progress
        job['last_activity'] = time.time()
        if save:
            self.save()
        self.emit('refresh')

    def _run_job(self, job):
        job.update(attempts=int(job.get('attempts') or 0) + 1, started_at=time.time(), finished_at=None,
                   percent=None, eta=None, error='', out_seconds=0.0, speed=0.0, report=[], pid=None,
                   last_activity=time.time(), last_advance=None)
        log = None
        temp_path = None
        cover_paths = []
        ffmpeg_offset = 0
        try:
            log = self._open_log(job)
            index, total = self.position(job)
            self._log(log, f'=== EIDOLITH {ENGINE_VERSION} job {job["id"]} ({index}/{total}) — '
                           f'{time.strftime("%Y-%m-%d %H:%M:%S")} ===', ui=False)
            self._log(log, f'Platform: {platform.platform()} · Python {platform.python_version()}', ui=False)
            self._log(log, f'FFmpeg: {self.ffmpeg or "MISSING"} · {self._ffmpeg_version_line() if self.ffmpeg else ""}', ui=False)
            self._log(log, f'SOURCE: {job["src"]}')
            self._log(log, f'OUTPUT: {job["dst"]}')
            self._log(log, f'PROFILE: {job["profile"]} · audio {job.get("audio_mode", "copy")} · '
                           f'resolution {job.get("resolution", "Original")} · slim {"on" if job.get("slim") else "off"}')
            if job.get('log_path'):
                self.emit('log', f'LOG FILE: {job["log_path"]}')
            self._set(job, 'probing', 'probing source tracks')

            if not self.ffmpeg:
                raise RuntimeError('ffmpeg is not available. Install FFmpeg (see MEDIA_TOOLS_INSTALLER.md).')
            ok, reason = profile_support(job['profile'], self.encoders)
            if not ok:
                raise RuntimeError(f'Encoder unavailable: {reason}')
            if not os.path.isfile(job['src']):
                raise FileNotFoundError('Source is missing: ' + job['src'])
            if os.path.exists(job['dst']):
                raise FileExistsError('Output name already exists; originals and existing outputs are never overwritten')
            info = probe(self.ffprobe, job['src'])
            job['duration'] = max(0.0, float(info.get('format', {}).get('duration', 0) or 0))
            plan = plan_streams(info, job['profile'], job.get('audio_mode', 'copy'), job.get('resolution', 'Original'),
                                bool(job.get('slim')))
            job['report'] = list(plan['report'])
            for line in plan['report']:
                self._log(log, 'PLAN ' + line)
            if self.skip_event.is_set():
                raise _Cancelled()

            out_dir = os.path.dirname(os.path.abspath(job['dst']))
            os.makedirs(out_dir, exist_ok=True)
            token = uuid.uuid4().hex[:12]
            stem, ext = os.path.splitext(job['dst'])
            temp_path = f'{stem}.eidolith-{token}-part{ext}'
            job['temp_path'] = temp_path
            for n, item in enumerate(plan['attach']):
                item['temp_path'] = f'{stem}.eidolith-{token}-cover{n}.{item["ext"]}'
                cover_paths.append(item['temp_path'])
            job['cover_temps'] = list(cover_paths)
            self.save()
            for item in plan['attach']:
                extract = [self.ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-n', '-i', job['src'],
                           '-map', f'0:v:{item["vindex"]}', '-c', 'copy', '-frames:v', '1', '-f', 'image2',
                           item['temp_path']]
                self._log(log, 'EXTRACT cover: ' + command_text(extract), ui=False)
                run = subprocess.run(extract, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     errors='replace', timeout=120, creationflags=NOWIN)
                if run.returncode or not os.path.isfile(item['temp_path']):
                    self._log(log, run.stdout.strip(), ui=False)
                    raise RuntimeError(f'Could not extract cover art (exit {run.returncode}); see log')

            cmd = build_command(self.ffmpeg, job['src'], temp_path, plan)
            self._log(log, 'COMMAND: ' + command_text(cmd))
            if job['profile'] in ('High fidelity', 'Balanced archive (default)', 'Space saver'):
                self._log(log, 'NOTE: CPU 10-bit SVT-AV1 at this preset is often slower than real time. '
                               'Progress below shows whether FFmpeg is advancing.')
            self._log(log, '--- FFmpeg stderr ---', ui=False)
            ffmpeg_offset = log.tell() if log else 0
            self._set(job, 'converting', 'starting FFmpeg')
            self._encode(job, cmd, log)
            rc = self.active_proc.returncode if self.active_proc else -1
            if log:
                log.flush()
            ff_tail = [line for line in tail_lines(job['log_path'], 40, ffmpeg_offset) if line.strip()] \
                if job.get('log_path') else []
            self._log(log, '--- end FFmpeg stderr ---', ui=False)
            self._log(log, f'EXIT CODE: {rc}')
            if self.skip_event.is_set():
                raise _Cancelled()
            if rc:
                for line in ff_tail[-8:]:
                    self.emit('log', '  ffmpeg: ' + line)
                cause = first_error_line(ff_tail) or 'no FFmpeg error text (see log)'
                hint = ''
                if 'nvenc' in PROFILES[job['profile']]['codec']:
                    hint = (' — the NVIDIA encoder could not start on this machine (GPU, driver or '
                            'CUDA library missing/unsupported). Choose a CPU profile.')
                raise RuntimeError(f'FFmpeg exited with status {rc}: {cause}{hint}')

            self._set(job, 'validating', 'checking output tracks, codec and duration')
            checks = validate_output(self.ffprobe, info, temp_path, plan, job['profile'])
            for line in checks:
                self._log(log, line)
            job['report'] += checks
            self._publish(temp_path, job['dst'])
            temp_path = None
            job['temp_path'] = None
            size_src = os.path.getsize(job['src']) or 1
            saved = 100.0 * (1 - os.path.getsize(job['dst']) / size_src)
            job['percent'] = 1.0
            self._set(job, 'completed', f'finished in {seconds_label(time.time() - job["started_at"])} · '
                                        f'{saved:+.1f}% storage saved', save=False)
            self._log(log, f'COMPLETED: {job["dst"]} · storage saved {saved:+.1f}%')
        except _Cancelled:
            job['error'] = 'cancelled by user'
            self._set(job, 'cancelled', 'cancelled — original unchanged', save=False)
            self._log(log, f'CANCELLED: {job["src"]} (original retained)')
        except Exception as exc:
            if self.skip_event.is_set():
                job['error'] = 'cancelled by user'
                self._set(job, 'cancelled', 'cancelled — original unchanged', save=False)
                self._log(log, f'CANCELLED: {job["src"]} (original retained)')
            else:
                job['error'] = str(exc)
                kind = 'blocked' if isinstance(exc, PlanError) else 'failed'
                self._set(job, 'failed', f'{kind}: {exc}'[:180], save=False)
                self._log(log, f'FAILED: {job["src"]} — {exc} (original retained)')
        finally:
            self._finish_process()
            job['pid'] = None
            for path in [temp_path] + cover_paths:
                if path:
                    reason = remove_owned_partial(path)
                    if reason:
                        job.setdefault('stale_partials', []).append(path)
                        self._log(log, f'WARNING: partial {path}: {reason}')
            job['temp_path'] = None
            job['cover_temps'] = []
            self._log(log, f'FINAL STATUS: {job["status"].upper()}', ui=False)
            if log:
                log.close()

    def _encode(self, job, cmd, log):
        self.active_proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=log if log else subprocess.DEVNULL,
                                            text=True, errors='replace', bufsize=1, creationflags=NOWIN)
        job['pid'] = self.active_proc.pid
        self.save()
        if self.skip_event.is_set():
            self._terminate_active()
        block, last_out = {}, -1.0
        for raw in self.active_proc.stdout:
            line = raw.strip()
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            if key not in PROGRESS_KEYS:
                continue
            block[key] = val.strip()
            if key != 'progress':
                continue
            now = time.time()
            job['last_activity'] = now
            seconds = progress_seconds(block)
            if seconds > last_out:
                job['last_advance'] = now
                last_out = seconds
            job['out_seconds'] = seconds
            try:
                job['speed'] = float(str(block.get('speed', '')).rstrip('x'))
            except ValueError:
                job['speed'] = 0.0
            duration = job.get('duration') or 0
            if duration > 0:
                job['percent'] = min(1.0, seconds / duration)
                job['eta'] = (duration - seconds) / job['speed'] if job['speed'] > 0 else None
                text = f'{job["percent"]:.0%} · {seconds_label(seconds)}/{seconds_label(duration)}'
                text += f' · ETA {seconds_label(job["eta"])}' if job['eta'] is not None else ' · ETA estimating'
            else:
                job['percent'], job['eta'] = None, None
                text = f'{seconds_label(seconds)} encoded (duration unknown)'
            if job['speed'] > 0:
                text += f' · {job["speed"]:.2f}x'
            if block.get('frame'):
                text += f' · frame {block["frame"]}'
            job['progress'] = text
            self.emit('refresh')
            block = {}
        try:
            self.active_proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self._terminate_active()
            self.active_proc.wait(timeout=20)

    def _finish_process(self):
        proc = self.active_proc
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
        self.active_proc = None

    @staticmethod
    def _publish(temp_path, dst):
        """Move the verified temporary file into place without overwriting."""
        if os.path.exists(dst):
            raise FileExistsError('Output destination became occupied during conversion')
        try:
            os.link(temp_path, dst)          # atomic, refuses to overwrite
            os.unlink(temp_path)
            return
        except FileExistsError:
            raise
        except OSError as hardlink_error:
            # exFAT / some Windows volumes cannot hard-link: claim the name with
            # O_EXCL, then replace only our own empty placeholder.
            if os.path.exists(dst):
                raise FileExistsError('Output destination already exists') from hardlink_error
            fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            try:
                os.replace(temp_path, dst)
            except OSError:
                if os.path.exists(dst) and os.path.getsize(dst) == 0:
                    os.unlink(dst)
                raise


class _Cancelled(Exception):
    pass


def diagnostics_report(job: dict, max_ffmpeg_lines: int = 80) -> str:
    """A shareable report with local folders replaced by placeholders."""
    lines = [f'EIDOLITH {ENGINE_VERSION} diagnostic report',
             f'Job {job.get("id")} · status {str(job.get("status", "")).upper()} · attempts {job.get("attempts", 0)}',
             f'Source: {job.get("src", "")}', f'Output: {job.get("dst", "")}',
             f'Profile: {job.get("profile")} · audio {job.get("audio_mode", "copy")} · '
             f'resolution {job.get("resolution", "Original")}',
             f'Platform: {platform.platform()}']
    if job.get('error'):
        lines.append(f'Error: {job["error"]}')
    lines += ['', 'Track plan / checks:'] + [f'  {r}' for r in job.get('report') or []]
    path = job.get('log_path')
    if path and os.path.isfile(path):
        body = tail_lines(path, 100000)
        cmd = [l for l in body if l.startswith('COMMAND: ')]
        if cmd:
            lines += ['', cmd[-1]]
        if '--- FFmpeg stderr ---' in body:
            start = len(body) - 1 - body[::-1].index('--- FFmpeg stderr ---')
            ff = body[start + 1:]
            lines += ['', f'FFmpeg output (last {max_ffmpeg_lines} lines):'] + ff[-max_ffmpeg_lines:]
        lines += ['', f'Full local log: {os.path.basename(path)}']
    src_dir = os.path.dirname(os.path.abspath(job.get('src', ''))) if job.get('src') else ''
    dst_dir = os.path.dirname(os.path.abspath(job.get('dst', ''))) if job.get('dst') else ''
    return redact('\n'.join(lines), [('<source folder>', src_dir), ('<output folder>', dst_dir)])
