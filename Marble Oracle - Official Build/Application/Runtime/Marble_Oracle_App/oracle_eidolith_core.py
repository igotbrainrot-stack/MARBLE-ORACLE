"""UI-independent EIDOLITH encoding policy, progress parsing and safe names.

Only local paths and FFmpeg commands are used. Conversions never rename or
modify the input. Ambiguous episode naming defaults to recognisable source.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

PROFILES = {
    'High fidelity': dict(container='mkv', codec='libsvtav1', crf=24, preset='4', pix_fmt='yuv420p10le', desc='CPU AV1 10-bit · CRF 24 · preset 4 · very slow, maximum detail'),
    'Balanced archive': dict(container='mkv', codec='libsvtav1', crf=28, preset='5', pix_fmt='yuv420p10le', desc='CPU AV1 10-bit · CRF 28 · preset 5 · slow, smaller archives'),
    'Space saver': dict(container='mkv', codec='libsvtav1', crf=34, preset='6', pix_fmt='yuv420p10le', desc='CPU AV1 10-bit · CRF 34 · preset 6 · smaller, more visible loss possible'),
    'Fast AV1 (preset 8)': dict(container='mkv', codec='libsvtav1', crf=30, preset='8', pix_fmt='yuv420p10le', desc='CPU AV1 10-bit · CRF 30 · preset 8 · several times faster than Balanced, slightly larger files'),
    'Faster CPU AV1': dict(container='mkv', codec='libsvtav1', crf=30, preset='10', pix_fmt='yuv420p10le', desc='CPU AV1 10-bit · CRF 30 · preset 10 · faster, less compression efficiency'),
    'NVIDIA AV1 (fast)': dict(container='mkv', codec='av1_nvenc', cq=30, preset='p4', pix_fmt='p010le', desc='Hardware AV1 10-bit · NVIDIA NVENC · much faster when supported'),
    'NVIDIA HEVC (fast)': dict(container='mkv', codec='hevc_nvenc', cq=27, preset='p4', pix_fmt='yuv420p', desc='Hardware HEVC · NVIDIA NVENC · fast, broad device support'),
    'NVIDIA H.264 (fastest compatibility)': dict(container='mp4', codec='h264_nvenc', cq=23, preset='p4', pix_fmt='yuv420p', desc='Hardware AVC · NVIDIA NVENC · fast, widest device support'),
    'Fast CPU H.264': dict(container='mp4', codec='libx264', crf=23, preset='veryfast', pix_fmt='yuv420p', desc='CPU H.264 · CRF 23 · veryfast preset · good speed'),
    'Broad device compatibility': dict(container='mkv', codec='libx265', crf=25, preset='medium', pix_fmt='yuv420p', desc='CPU HEVC / x265 · CRF 25 · medium'),
    'Legacy compatibility': dict(container='mp4', codec='libx264', crf=21, preset='medium', pix_fmt='yuv420p', desc='CPU H.264 / x264 · CRF 21 · medium'),
    'Lossless remux': dict(container='mkv', codec='copy', desc='Stream copy · no re-encode · fast if streams are compatible'),
}
PROFILE_ORDER = tuple(PROFILES)
DEFAULT_PROFILE = 'Fast AV1 (preset 8)'
# The 0.3 name is still accepted (saved settings, saved queues, scripts) but
# is no longer listed: it stopped being the default in 0.4.5.
LEGACY_PROFILE_NAMES = {'Balanced archive (default)': 'Balanced archive'}
for _old, _new in LEGACY_PROFILE_NAMES.items():
    PROFILES[_old] = PROFILES[_new]
SUFFIXES = {
    'High fidelity': 'AV1', 'Balanced archive (default)': 'AV1', 'Balanced archive': 'AV1', 'Space saver': 'AV1',
    'Fast AV1 (preset 8)': 'AV1', 'Faster CPU AV1': 'AV1', 'NVIDIA AV1 (fast)': 'AV1',
    'NVIDIA HEVC (fast)': 'HEVC', 'NVIDIA H.264 (fastest compatibility)': 'H264',
    'Fast CPU H.264': 'H264', 'Broad device compatibility': 'HEVC',
    'Legacy compatibility': 'H264', 'Lossless remux': 'Remux',
}
NAME_MODES = ('Auto (TV / movie)', 'TV episode', 'Movie', 'Keep source name')
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
EPISODE = re.compile(
    r'(?i)(?<![a-z0-9])(?:s(?P<s>\d{1,2})[. _-]*e(?P<e>\d{1,3})(?:[. _-]*e(?P<e2>\d{1,3}))?'
    r'|(?P<sx>\d{1,2})[xX](?P<ex>\d{1,3})'
    r'|season[. _-]*(?P<ss>\d{1,2})[. _-]*(?:episode|ep)[. _-]*(?P<ee>\d{1,3}))(?![a-z0-9])')
YEAR = re.compile(r'(?<!\d)(?:19\d{2}|20\d{2})(?!\d)')
RELEASE = re.compile(r'(?i)(?:\b(?:2160p|1080p|720p|480p|4k|8k|bluray|brrip|web[ ._-]?dl|webrip|hdtv|hdrip|dvdrip|remux|proper|repack|x264|x265|h264|h265|hevc|av1|aac|dts|atmos|ddp5|ddp|hdr10|hdr|dv|10bit|8bit)\b|\b\d+(?:[.]\d+)?ch\b)')
# In names that already use spaces ("Show (2015) - S01E01 - Title"), only cut
# at tokens that are unambiguously technical. Words such as "Proper", "Remux"
# or "4K" may be part of a real episode title and are only treated as release
# tags inside brackets or in dotted scene names.
STRONG_RELEASE = re.compile(r'(?i)(?:\b(?:2160p|1080p|720p|576p|480p|bluray|blu-ray|brrip|bdrip|web[ ._-]?dl|webrip|hdtv|hdrip|dvdrip|x264|x265|h264|h265|hevc|ddp5|10bit|8bit)\b|\b\d+(?:[.]\d+)?ch\b)')
BRACKETED = re.compile(r'\[[^\]]*\]|\{[^}]*\}|\([^)]*\)')
RESERVED = {"con", "prn", "aux", "nul"} | {f'com{i}' for i in range(1,10)} | {f'lpt{i}' for i in range(1,10)}


def safe_piece(value: str, fallback: str = 'Untitled') -> str:
    value = INVALID.sub('', str(value or ''))
    value = re.sub(r'\s+', ' ', value).strip(' ._-')
    if not value:
        value = fallback
    if value.lower() in RESERVED:
        value = '_' + value
    return value[:112].rstrip(' .') or fallback


def _strip_release_groups(value: str) -> str:
    """Remove [..] / {..} tags and (..) groups that hold release details.

    A parenthesised year or ordinary words such as "(Part 2)" are kept.
    """
    def repl(match):
        text = match.group(0)
        if text[0] in '[{':
            return ' '
        inner = text[1:-1]
        return ' ' if (RELEASE.search(inner) or STRONG_RELEASE.search(inner)) else text
    return BRACKETED.sub(repl, value)


def _drop_unbalanced(value: str) -> str:
    """Cut a dangling opener left behind by a release-token split: 'Title (' -> 'Title'."""
    for opener, closer in (('(', ')'), ('[', ']'), ('{', '}')):
        while value.count(opener) > value.count(closer):
            value = value[:value.rfind(opener)]
    return value


def is_spaced_name(raw: str) -> bool:
    """True for human-formatted names that already separate words with spaces."""
    return ' ' in _strip_release_groups(raw).strip()


def clean_words(value: str, spaced: bool | None = None) -> str:
    if spaced is None:
        spaced = is_spaced_name(value)
    value = _strip_release_groups(value)
    value = (STRONG_RELEASE if spaced else RELEASE).split(value, maxsplit=1)[0]
    value = _drop_unbalanced(value)
    if not spaced:
        # Scene style (Show.Name.S01E02.Title): dots/underscores are separators.
        value = re.sub(r'[._]+', ' ', value)
    # Normalise separator dashes only; keep hyphens inside words
    # ("ones-and-zer0es", "Spider-Man") intact.
    value = re.sub(r'\s+[-–—]+\s*|\s*[-–—]+\s+', ' - ', value)
    value = re.sub(r'(?:\s+-)+\s*$|^\s*(?:-\s+)+', '', value)
    return safe_piece(value)


def parse_media_name(path: str) -> dict:
    raw = Path(path).stem
    spaced = is_spaced_name(raw)
    clean = lambda part: clean_words(part, spaced)  # noqa: E731
    match = EPISODE.search(raw)
    if match:
        season = match.group('s') or match.group('sx') or match.group('ss')
        episode = match.group('e') or match.group('ex') or match.group('ee')
        last_episode = match.group('e2')
        title = clean(raw[:match.start()])
        if title == 'Untitled':
            # 'S01E01.mkv': take the show from its folder rather than invent
            # 'Untitled'; with no usable folder the source name is kept.
            title = _folder_title(path)
            if not title:
                return dict(kind='Unknown', title=clean(raw), year=None,
                            season=None, episode=None, extra_episode=None, episode_title='')
        tail = clean(raw[match.end():])
        if tail == 'Untitled':
            tail = ''
        if re.fullmatch(r'(?i)\(?(?:19|20)\d{2}\)?', tail):
            tail = ''
        return dict(kind='TV', title=title, season=int(season), episode=int(episode),
                    extra_episode=int(last_episode) if last_episode else None, episode_title=tail, year=None)
    year = _pick_year(raw)
    if year:
        title = clean(raw[:year.start()])
        if title != 'Untitled':
            return dict(kind='Movie', title=title, year=int(year.group()),
                        season=None, episode=None, extra_episode=None, episode_title='')
    return dict(kind='Unknown', title=clean(raw), year=None,
                season=None, episode=None, extra_episode=None, episode_title='')


SEASON_FOLDER = re.compile(r'(?i)^(?:season|series|staffel|s)[ ._-]*\d+$|^specials?$|^extras?$|^eidolith outputs$')


GENERIC_FOLDERS = {'tv', 'tv shows', 'shows', 'series', 'video', 'videos', 'movies', 'films', 'media', 'downloads',
                   'download', 'desktop', 'documents', 'home', 'new folder', 'temp', 'tmp', 'torrents', 'complete'}


def _pick_year(raw: str):
    """The release year of a movie name, or None.

    A number that is part of the title must not win: '2001 A Space Odyssey
    (1968)', 'Blade Runner 2049 (2017)', '1917 (2019)'. A year in brackets is
    preferred; otherwise the last year before the first release tag.
    """
    cut = RELEASE.search(BRACKETED.sub(lambda m: ' ' * len(m.group(0)), raw))
    limit = cut.start() if cut else len(raw)
    found = [m for m in YEAR.finditer(raw)
             if not (raw[max(0, m.start() - 1):m.start()].lower() == 's' and raw[m.end():m.end() + 1].lower() == 'e')]
    bracketed = [m for m in found if raw[max(0, m.start() - 1):m.start()] in ('(', '[') and raw[m.end():m.end() + 1] in (')', ']')]
    if bracketed:
        return bracketed[-1]
    early = [m for m in found if m.start() < limit]
    return (early or found or [None])[-1]


def _folder_title(path: str) -> str:
    """Show name from the nearest parent folder that is not a season folder."""
    parts = [p for p in Path(path).parts[:-1] if p not in ('.', '', '/', '\\') and not p.endswith((':', ':\\', ':/'))]
    for name in reversed(parts[-2:]):
        if SEASON_FOLDER.match(name.strip()):
            continue
        title = clean_words(name)
        return '' if title == 'Untitled' or title.lower() in GENERIC_FOLDERS else title
    return ''


def standard_stem(src: str, mode: str='Auto (TV / movie)', title_override: str='',
                  season_override: str='', episode_override: str='', episode_title: bool = True) -> str:
    info = parse_media_name(src)
    original = safe_piece(Path(src).stem, 'Untitled')
    if mode == 'Keep source name':
        return original
    title = safe_piece(title_override, info['title']) if title_override.strip() else info['title']
    if mode == 'Movie' or (mode == 'Auto (TV / movie)' and info['kind'] == 'Movie'):
        year = info.get('year')
        return f'{title} ({year})' if year else title
    if mode == 'TV episode' or (mode == 'Auto (TV / movie)' and info['kind'] == 'TV'):
        sea = season_override.strip() or str(info.get('season') or '')
        epi = episode_override.strip() or str(info.get('episode') or '')
        if sea.isdigit() and epi.isdigit() and int(sea) <= 999 and int(epi) <= 9999:
            number = f'S{int(sea):02d}E{int(epi):02d}'
            if info.get('extra_episode') and not episode_override.strip():
                number += f'E{info["extra_episode"]:02d}'
            detail = info.get('episode_title', '') if episode_title else ''
            return f'{title} - {number}' + (f' - {detail}' if detail else '')
        # No episode info: don't fabricate S01E01.
        return title if title_override.strip() else original
    return original if info['kind'] == 'Unknown' and not title_override.strip() else title


# Maximum output size. The video is scaled down to fit inside the box, keeping
# its aspect ratio (a 2.39:1 film at "720p" becomes 1280x536); it is never
# scaled up. Portrait video uses the box rotated (720x1280).
RESOLUTIONS = {'Original': None, '1080p': (1920, 1080), '720p': (1280, 720), '480p': (854, 480)}
RESOLUTION_ORDER = tuple(RESOLUTIONS)


def fit_resolution(width, height, resolution='Original'):
    """Return (w, h) to scale to, or None when no scaling is needed."""
    box = RESOLUTIONS.get(resolution or 'Original')
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if not box or width <= 0 or height <= 0:
        return None
    box_w, box_h = box if width >= height else (box[1], box[0])
    if width <= box_w and height <= box_h:
        return None
    factor = min(box_w / width, box_h / height)
    out_w = max(2, int(round(width * factor / 2)) * 2)
    out_h = max(2, int(round(height * factor / 2)) * 2)
    return min(out_w, box_w), min(out_h, box_h)


def output_name(src, profile_name, mode='Auto (TV / movie)', title_override='', season_override='',
                episode_override='', resolution='Original', episode_title=True, format_tag=True):
    """Standard output filename.

    episode_title / format_tag add ' - <episode title>' and ' [AV1 720p]'.
    Both default to True for API compatibility; the EIDOLITH panel turns
    them off by default so names read 'Show (2015) - S01E01.mkv'.
    """
    stem = safe_piece(standard_stem(src, mode, title_override, season_override, episode_override, episode_title))
    ext = PROFILES[profile_name]['container']
    if not format_tag:
        return f'{stem}.{ext}'
    codec = SUFFIXES.get(profile_name, 'Encoded')
    if RESOLUTIONS.get(resolution or 'Original') and PROFILES[profile_name]['codec'] != 'copy':
        codec = f'{codec} {resolution}'
    return f'{stem} [{codec}].{ext}'


def encoding_args(profile_name: str, audio_mode='copy') -> list:
    profile = PROFILES[profile_name]
    codec = profile['codec']
    if codec == 'copy':
        return ['-c', 'copy']
    args = ['-c:v', codec]
    if 'crf' in profile:
        args.extend(('-crf', str(profile['crf'])))
    if 'cq' in profile:
        args.extend(('-rc', 'vbr', '-cq', str(profile['cq']), '-b:v', '0'))
    if profile.get('preset'):
        args.extend(('-preset', str(profile['preset'])))
    if profile.get('pix_fmt'):
        args.extend(('-pix_fmt', profile['pix_fmt']))
    args.extend(('-c:a', 'libopus', '-b:a', '128k') if audio_mode == 'opus' else ('-c:a', 'copy'))
    args.extend(('-c:s', 'copy'))
    return args


def detect_encoders(ffmpeg: str, timeout=8) -> set[str]:
    if not ffmpeg:
        return set()
    try:
        run = subprocess.run([ffmpeg, '-hide_banner', '-encoders'],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=timeout, check=True,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        return set()
    return {m.group(1) for line in run.stdout.splitlines()
            if (m := re.match(r'^\s*[VAS][.A-Z]{5}\s+(\S+)', line))}


def profile_support(name: str, installed: set[str]) -> tuple[bool, str]:
    codec = PROFILES[name]['codec']
    if codec == 'copy':
        return True, ''
    if not installed:
        return False, 'FFmpeg encoder capabilities unavailable'
    if codec not in installed:
        return False, f'FFmpeg does not contain {codec}'
    if name.startswith('NVIDIA'):
        return True, 'Requires a compatible NVIDIA GPU and driver; FFmpeg listing alone is insufficient'
    return True, ''


def progress_seconds(data: dict) -> float:
    try:
        if data.get('out_time') and data['out_time'] != 'N/A':
            parts = data['out_time'].split(':')
            if len(parts) == 3:
                return max(0.0, int(parts[0])*3600 + int(parts[1])*60 + float(parts[2]))
        if data.get('out_time_us'):
            return max(0.0, int(data['out_time_us']) / 1_000_000)
    except (TypeError, ValueError, OverflowError):
        pass
    return 0.0


def seconds_label(value: float) -> str:
    if value is None or value < 0 or value != value:
        return '?'
    sec = int(round(value))
    return f'{sec//3600:d}:{(sec%3600)//60:02d}:{sec%60:02d}'


def progress_label(data: dict, duration: float=0) -> str:
    elapsed = progress_seconds(data)
    speed_text = str(data.get('speed', '')).strip()
    try:
        speed = float(speed_text.rstrip('x'))
    except (TypeError, ValueError):
        speed = 0.0
    if duration > 0:
        fraction = min(1.0, elapsed/duration)
        eta = seconds_label(max(0.0, duration - elapsed)/speed) if speed > 0 else 'estimating'
        result = f'{fraction:.0%} · {seconds_label(elapsed)}/{seconds_label(duration)} · ETA {eta}'
    else:
        result = seconds_label(elapsed)
    if speed > 0:
        result += f' · {speed:.2f}x'
    return result
