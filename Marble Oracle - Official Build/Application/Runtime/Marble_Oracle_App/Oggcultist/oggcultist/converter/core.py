"""Scan, plan, convert, verify, and safely publish a separate Opus library."""
from __future__ import annotations
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
import base64
import io
from PIL import Image
from .artwork import ArtworkStore, picture_comment
from ..metadata import EXTENSIONS, Track, year_of
from ..services.tools import no_window_kwargs

Progress = Callable[[str, int, int, float], None]


class Cancelled(Exception): pass


def safe_component(name: str) -> str:
    """Portable Windows/Linux directory component; never allow traversal."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', str(name))
    s = re.sub(r'\.{2,}', '.', s)
    s = re.sub(r'\s+', ' ', s).strip(' .')
    if not s or s in ('.','..'): s = 'Unknown'
    if s.upper().split('.')[0] in {'CON','PRN','AUX','NUL','COM1','COM2','COM3','COM4','COM5','COM6','COM7','COM8','COM9','LPT1','LPT2','LPT3','LPT4','LPT5','LPT6','LPT7','LPT8','LPT9'}:
        s = '_' + s
    return s[:130].rstrip(' .') or 'Unknown'


def source_files(folder: Path) -> Iterator[Path]:
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for file in sorted(files):
            p = Path(root)/file
            if p.suffix.lower() in EXTENSIONS and not p.is_symlink():
                yield p


def scan(folder: Path, notify: Callable[[int,str],None] | None = None, cancel: threading.Event | None = None) -> tuple[list[Track], list[tuple[str,str]]]:
    tracks: list[Track] = []
    problems: list[tuple[str,str]] = []
    for i, path in enumerate(source_files(folder),1):
        if cancel and cancel.is_set(): break
        try: tracks.append(Track.from_path(path))
        except Exception as exc: problems.append((str(path),str(exc)))
        if notify and (i % 5 == 0 or i == 1): notify(i, str(path.name))
    return tracks, problems


def primary_artist(artist: str) -> str:
    return re.split(r'\s+(?:feat\.?|ft\.?|featuring)\s+', artist, flags=re.I)[0].strip()


def infer_album_artists(tracks: list[Track]) -> None:
    """Only infer album artist inside the same source album directory, not from featured credits."""
    groups: dict[tuple[str,str],list[Track]] = defaultdict(list)
    for t in tracks: groups[t.album_group()].append(t)
    for group in groups.values():
        # Genuine explicitly tagged compilations. Do not equate 'feat.' with a compilation.
        tagged = {t.albumartist.strip() for t in group if t.albumartist.strip()}
        primaries = {primary_artist(t.artist).casefold() for t in group if t.artist}
        compilation = any(t.compilation for t in group) and len(primaries) > 1
        if compilation and not tagged:
            for t in group:
                t.albumartist = 'Various Artists'
                t.compilation = True
            continue
        if len({name.casefold() for name in tagged}) == 1:
            artist = next(iter(tagged))
            for t in group:
                if not t.albumartist: t.albumartist = artist
        elif not tagged and len(primaries) == 1:
            artist = next(primary_artist(t.artist) for t in group if t.artist)
            for t in group: t.albumartist = artist
        # If multiple album artists were explicitly given, do not rewrite their tags.
        if any(t.originaldate for t in group):
            years = {year_of(t.originaldate) for t in group if year_of(t.originaldate)}
            if len(years) == 1:
                y = next(iter(years))
                for t in group:
                    if not t.originaldate:
                        t.originaldate = y
                        t.year = y
        # Only fill unknown years from an unambiguous group consensus.
        years = {t.year for t in group if t.year}
        if len(years) == 1:
            y = next(iter(years))
            for t in group:
                if not t.year: t.year = y
        for t in group:
            if not t.track:
                stem = t.source.stem
                m = re.match(r'^\s*(?:[0-9]\s*[-.])?(\d{1,3})\s*[-._]\s+', stem)
                if m:
                    t.track = int(m.group(1))
                    t.inferred_track = True


def number_inferred_remixes(tracks: list[Track]) -> None:
    """Assign provisional numbers for untagged remixes in stable filename order.

    This is an ordering of the *selected scan*, not an assertion about release
    track numbers. Incremental subsets may need manual renumbering; existing
    destinations are never replaced automatically.
    """
    groups: dict[tuple[str, str, str], list[Track]] = defaultdict(list)
    for t in tracks:
        if t.filename_inferred:
            groups[(t.albumartist.casefold(), t.album.casefold(), t.year)].append(t)
    for group in groups.values():
        occupied = {t.track for t in group if t.track > 0}
        next_no = 1
        for t in sorted(group, key=lambda v: (v.source.name.casefold(), str(v.source).casefold())):
            if t.track > 0: continue
            while next_no in occupied: next_no += 1
            t.track = next_no
            occupied.add(next_no)
            next_no += 1


def file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): sha.update(block)
    return sha.hexdigest()


def validate_folders(input_dir: Path, output_dir: Path) -> tuple[Path,Path]:
    src = input_dir.expanduser().resolve()
    dest = output_dir.expanduser().resolve()
    if not src.is_dir(): raise ValueError('Input folder does not exist.')
    if src == dest or src in dest.parents or dest in src.parents:
        raise ValueError('Use separate, non-nested input and output folders to protect originals and avoid scan loops.')
    if dest.is_file(): raise ValueError('Output must be a folder.')
    return src, dest


def target_path(track: Track, dest: Path, multi_disc: bool = False) -> Path:
    album_artist = 'Various Artists' if track.compilation and track.albumartist.casefold() == 'various artists' else track.albumartist
    name = f'{track.year or "Unknown Year"} - {track.album}'
    prefix = f'{track.disc:02d}-{track.track:02d}' if multi_disc else f'{track.track:02d}'
    return dest / safe_component(album_artist) / safe_component(name) / f'{prefix} - {safe_component(track.title)}.opus'


def fingerprint(track: Track) -> str:
    stat = track.source.stat()
    identity = {
        'source':str(track.source.resolve()),'source_size':stat.st_size,'mtime_ns':stat.st_mtime_ns,
        'title':track.title,'artist':track.artist,'albumartist':track.albumartist,'album':track.album,
        'year':track.year,'date':track.date,'originaldate':track.originaldate,
        'track':track.track,'disc':track.disc,'disctotal':track.disc_total,'tracktotal':track.track_total,
        'compilation':track.compilation,'release_id':track.release_id,'releasegroup_id':track.releasegroup_id,
        'releasetype':track.release_type,'tags':track.tags,
        'encoding':'opus 96k libopus vbr on v1','cover':'600px times v1',
    }
    return hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def metadata_signature(track: Track) -> str:
    """Settings and metadata identity excluding file mtime (used for safe ledger reuse)."""
    identity = {
        'title':track.title,'artist':track.artist,'albumartist':track.albumartist,
        'album':track.album,'year':track.year,'date':track.date,
        'originaldate':track.originaldate,'track':track.track,'disc':track.disc,
        'disctotal':track.disc_total,'tracktotal':track.track_total,
        'compilation':track.compilation,'release_id':track.release_id,
        'releasegroup_id':track.releasegroup_id,'releasetype':track.release_type,
        'tags':track.tags,'encoding':'opus 96k libopus vbr on v1',
        'cover':'600px serif v2',
    }
    return hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def plan(tracks: list[Track], dest: Path, store: ArtworkStore | None = None) -> None:
    number_inferred_remixes(tracks)
    infer_album_artists(tracks)
    groups: dict[tuple[str,str],list[Track]] = defaultdict(list)
    for t in tracks: groups[t.album_group()].append(t)
    for t in tracks:
        t.duplicate_group = ''
        t.issues.clear()
        if t.lookup_issue: t.issues.append(t.lookup_issue)
        if not t.album: t.issues.append('Missing album')
        if not t.albumartist: t.issues.append('Missing album artist')
        if not t.year and not t.filename_inferred: t.issues.append('Missing original release year')
        if not t.title or t.unverified_title: t.issues.append('Missing or unverified title tag — review filename')
        if t.track < 1: t.issues.append('Missing track number')
        if t.inferred_track: t.issues.append('Track number inferred from filename — confirm in metadata editor')
        if t.disc < 1: t.issues.append('Invalid disc number')
        group = groups[t.album_group()]
        year_values = {q.year for q in group if q.year}
        artist_values = {q.albumartist.casefold() for q in group if q.albumartist}
        if len(year_values)>1: t.issues.append('Inconsistent album years — check reissue dates')
        if len(artist_values)>1: t.issues.append('Inconsistent album artists')
        primaries = {primary_artist(q.artist).casefold() for q in group if q.artist}
        if len(primaries)>1 and any(q.compilation for q in group) and artist_values and artist_values != {'various artists'}:
            t.issues.append('Multi-artist compilation conflicts with tagged album artist — review')
        # Multi-disc naming is resolved after all target album folders are known.
        t.target = target_path(t,dest,multi_disc=False) if not t.issues else None
        t.status = 'Review' if t.issues else 'Ready'
        t.note = '; '.join(t.issues)
        if not t.issues and t.filename_inferred:
            t.note = t.filename_inference_note
        elif not t.issues and not t.originaldate:
            t.note = 'Original date absent: year taken from release date; check remasters/reissues'
    # An output album is the authoritative grouping for filenames AND artwork.
    folders: dict[str, list[Track]] = defaultdict(list)
    for t in tracks:
        if t.albumartist and t.album and (t.year or t.filename_inferred) and t.track > 0:
            folder = target_path(t, dest).parent
            folders[str(folder).casefold()].append(t)
    for folder_tracks in folders.values():
        multi = max(q.disc for q in folder_tracks) > 1 or any(q.disc_total > 1 for q in folder_tracks)
        release_ids = {q.release_id.casefold() for q in folder_tracks if q.release_id}
        base = folder_tracks[0]
        # Base album identity is determined by the output directory, not by
        # whatever subset of release tags happened to be scanned this time.
        base_key = 'album:' + '|'.join([base.albumartist.casefold(), base.album.casefold(), base.year])
        keys = ['release:' + rid for rid in sorted(release_ids)]
        keys += ['album:' + '|'.join([base.albumartist.casefold(),base.album.casefold(),base.year,rt])
                 for rt in dict.fromkeys([q.release_type.casefold() for q in folder_tracks] + [''])]
        keys.append(base_key)
        cover_key = (store.folder_cover_key(target_path(base, dest).parent, keys,
                                           base.album,base.albumartist,base.year)
                     if store and len(release_ids) <= 1 else base_key)
        positions: dict[tuple[int, int], list[Track]] = defaultdict(list)
        for q in folder_tracks:
            q.cover_key = cover_key
            if q.target is not None:
                q.target = target_path(q, dest, multi_disc=multi)
            positions[(q.disc, q.track)].append(q)
            if len(release_ids) > 1:
                q.issues.append('Different MusicBrainz release IDs would merge into one folder — review editions')
        for q in folder_tracks:
            if q.issues:
                q.status = 'Review'
                q.note = '; '.join(dict.fromkeys(q.issues))
                if len(release_ids) > 1: q.target = None

    # Hash only files in same-size groups; this also finds exact repeats with different names.
    hash_cache: dict[Path,str] = {}
    size_groups: dict[int,list[Track]] = defaultdict(list)
    for t in tracks:
        if t.status=='Ready': size_groups[t.size].append(t)
    for same_size in size_groups.values():
        if len(same_size)<2: continue
        for t in same_size:
            try: hash_cache[t.source] = file_hash(t.source)
            except OSError: t.issues.append('Could not hash file for duplicate check')
    # Detect repeats within the SAME album identity, regardless of filename/track number.
    similar: dict[tuple[str,str],list[Track]] = defaultdict(list)
    for t in tracks:
        if t.status=='Ready' and t.source in hash_cache:
            similar[(t.cover_key or t.album_key(),hash_cache[t.source])].append(t)
    for (_album_key, digest), group in similar.items():
        if len(group)<2: continue
        for t in group:
            t.duplicate_group = digest
            t.status = 'Duplicate'
            t.issues.append('Identical source bytes found elsewhere in this album — choose which to keep')
            t.note = '; '.join(t.issues)
    # First give identical files the more specific Duplicate status. If sources
    # differ but occupy the same disc/track slot, require manual review instead.
    for folder_tracks in folders.values():
        positions: dict[tuple[int, int], list[Track]] = defaultdict(list)
        for q in folder_tracks:
            if q.status in ('Ready', 'Duplicate'):
                positions[(q.disc, q.track)].append(q)
        for same_position in positions.values():
            if len(same_position) <= 1 or all(q.status == 'Duplicate' for q in same_position):
                continue
            for q in same_position:
                if q.status == 'Duplicate': continue
                q.status = 'Review'
                q.issues.append('Duplicate disc/track number within album — check disc tags')
                q.note = '; '.join(q.issues)
    # Output path collisions can also represent distinct editions; never overwrite.
    paths: dict[str,list[Track]] = defaultdict(list)
    for t in tracks:
        if t.target is not None: paths[str(t.target).casefold()].append(t)
    for group in paths.values():
        if len(group)<2: continue
        for t in group:
            if t.status=='Duplicate': continue
            t.status = 'Collision'
            t.issues.append('Same output filename as another track — edit track or album metadata')
            t.note = '; '.join(t.issues)
    for t in tracks:
        if t.status != 'Ready' or not t.target: continue
        if t.target.exists():
            state = (store.output_state(str(t.source.resolve()), fingerprint(t),
                                        str(t.target.resolve()), t.source,
                                        metadata_signature(t)) if store else 'foreign')
            if state == 'done':
                t.status = 'Done'
                t.note = 'Previously completed; verified ledger entry'
            elif state == 'changed':
                t.status = 'Review'
                t.note = 'Output modified or damaged since conversion — will not overwrite'
                t.issues.append(t.note)
            elif state == 'outdated':
                t.status = 'Review'
                t.note = 'Previously generated output is outdated — manual review needed (no overwrite)'
                t.issues.append(t.note)
            else:
                t.status = 'Collision'
                t.note = 'Output exists but is not in the completion ledger: will not overwrite'
                t.issues.append(t.note)
    # Legacy mixed-art folders should remain untouched, but must be visible
    # even if they were already bound by a previous Oggcultist version.
    if store:
        for folder_tracks in folders.values():
            for t in folder_tracks:
                warning = store.folder_warning(target_path(t, dest).parent)
                if warning and warning not in t.note:
                    t.note = (t.note + '; ' if t.note else '') + warning


def _has_required_tools() -> None:
    for name in ('ffmpeg','ffprobe'):
        if not shutil.which(name):
            raise RuntimeError(f'{name} was not found in PATH. Install FFmpeg before converting.')


def probe(path: Path) -> dict:
    process = subprocess.run(['ffprobe','-v','error','-select_streams','a:0',
                              '-show_entries','stream=codec_name,duration:format=duration',
                              '-of','json',str(path)],capture_output=True,text=True,timeout=30,
                             **no_window_kwargs())
    if process.returncode: raise RuntimeError('ffprobe could not verify output: ' + process.stderr.strip()[:300])
    data = json.loads(process.stdout)
    streams = data.get('streams',[])
    if not streams or streams[0].get('codec_name')!='opus':
        raise RuntimeError('Output did not contain the required Opus audio stream')
    return data


def diagnose_source_stream(track: Track) -> tuple[bool | None, str]:
    """On an FFmpeg failure, inspect the *source* separately; never alter it.

    A failure here can mean the MP3/container is corrupt, rather than an Opus
    encoder or output verification defect. Running only after an error avoids
    the cost of a second complete decode for normally converted libraries.
    """
    command = ['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error',
               '-xerror', '-i', str(track.source), '-map', '0:a:0',
               '-f', 'null', '-']
    try:
        checked = subprocess.run(command, capture_output=True, text=True,
                                 errors='replace',
                                 timeout=max(60, int(track.duration / 3) + 20),
                                 **no_window_kwargs())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f'Source health check unavailable: {exc}'
    if checked.returncode:
        reason = (checked.stderr or checked.stdout or f'exit code {checked.returncode}').strip()
        return False, reason[-1500:]
    return True, 'The complete source audio stream decoded without an FFmpeg error.'


def describe_conversion_failure(track: Track, error: Exception) -> str:
    """Report which audio stream failed, instead of a generic input-stream error.

    Do not retry by ignoring invalid frames: damaged sources need review, and
    no unverified output is ever published.
    """
    raw = str(error).strip() or type(error).__name__
    lowered = raw.lower()
    if not any(term in lowered for term in ('input stream', 'ffmpeg failed',
                                            'decode failed', 'ffprobe could not verify')):
        return raw
    ok, detail = diagnose_source_stream(track)
    if ok is False:
        return ('SOURCE AUDIO DECODE ERROR: FFmpeg could not decode the original '
                'audio stream reliably. The source was not modified, and no '
                'unverified output was published. Try playing or checking this '
                'specific source file, and review it before converting. '
                f'Source diagnostic: {detail} | Conversion error: {raw}')
    if ok is True:
        return ('CONVERSION / OUTPUT VERIFICATION ERROR: The original audio '
                'decodes, but encoding or verification failed. No unverified '
                'output was published. Send this file’s report entry to diagnose '
                f'the FFmpeg stage. Error: {raw}')
    return ('AUDIO STREAM ERROR: The conversion failed; the source and any '
            'existing output were left unchanged. '
            f'{detail} | Conversion error: {raw}')

def _copy_without_reencode(track: Track) -> bool:
    # Ogg Opus only. A median bitrate near 96k is not proof of encode settings,
    # so exact Oggcultist encoder marker is the only automatic skip of re-encode.
    if track.source.suffix.lower() != '.opus': return False
    try:
        ogg = OggOpus(track.source)
        return ('96000' in ogg.get('oggcultist_target_bitrate',[]) and
                'on' in ogg.get('oggcultist_vbr',[]))
    except Exception: return False


def _encode(track: Track, dest: Path, cancel: threading.Event, progress: Callable[[float],None]) -> bool:
    copy_audio = _copy_without_reencode(track)
    args = ['ffmpeg','-hide_banner','-nostdin','-y','-v','error','-i',str(track.source),
            '-map','0:a:0','-map_metadata','-1','-vn','-sn','-dn']
    if copy_audio:
        args += ['-c:a','copy']
    else:
        # At a fixed 96 kbps target, surround should be downmixed for usable quality.
        # Preserve mono and stereo inputs without adding channels.
        details = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                                  '-show_entries', 'stream=channels', '-of', 'json',
                                  str(track.source)], capture_output=True, text=True, timeout=30,
                                 **no_window_kwargs())
        if details.returncode == 0:
            try:
                if int(json.loads(details.stdout)['streams'][0]['channels']) > 2:
                    args += ['-ac', '2']
            except (ValueError, KeyError, IndexError, TypeError): pass
        args += ['-c:a','libopus','-b:a','96k','-vbr','on', '-application','audio', '-compression_level','10']
    args += ['-progress','pipe:1','-nostats','-f','opus',str(dest)]
    with tempfile.TemporaryFile(mode='w+t',encoding='utf-8') as err:
        process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=err,text=True,
                                   encoding='utf-8',errors='replace',bufsize=1,
                                   **no_window_kwargs())
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if cancel.is_set():
                    process.terminate()
                    raise Cancelled()
                if line.startswith('out_time=') and track.duration:
                    duration_str = line.partition('=')[2].strip()
                    try:
                        h,m,s = duration_str.split(':')
                        sec = int(h)*3600+int(m)*60+float(s)
                        progress(min(0.98,sec/track.duration))
                    except (ValueError,TypeError): pass
            rc = process.wait()
            if cancel.is_set(): raise Cancelled()
            if rc:
                err.seek(0)
                raise RuntimeError('FFmpeg failed while encoding input to Opus: ' + err.read()[-2000:])
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return copy_audio


def _write_opus_tags(dest: Path, track: Track, cover: bytes) -> None:
    ogg = OggOpus(dest)
    if ogg.tags is None: ogg.add_tags()
    else: ogg.tags.clear()
    for k,vals in track.tags.items():
        if not k or not re.fullmatch('[a-zA-Z0-9_:+.-]{1,100}',k): continue
        if k.lower() in ('metadata_block_picture','coverart','coverartmime',
                          'oggcultist_target_bitrate','oggcultist_vbr',
                          'encoder','encoded_by','waveformatextensible_channel_mask'): continue
        if vals: ogg[k] = [str(v) for v in vals if str(v)]
    essential = {
        'title':track.title,'artist':track.artist or ('' if track.filename_inferred else track.albumartist),
        'albumartist':track.albumartist,'album':track.album,'date':track.date or track.year,
        'originaldate':track.originaldate,
        'originalyear':track.year if track.originaldate else '',
        'tracknumber':str(track.track),'discnumber':str(track.disc),
        'musicbrainz_albumid':track.release_id,'musicbrainz_releasegroupid':track.releasegroup_id,
        'releasetype':track.release_type,
    }
    for key, value in essential.items():
        if value:
            if key in ('artist', 'albumartist') and ogg.get(key) and ogg[key][0] == value:
                continue  # Retain the original multi-valued artist credits.
            ogg[key] = [value]
    if track.disc_total: ogg['totaldiscs'] = [str(track.disc_total)]
    if track.track_total: ogg['totaltracks'] = [str(track.track_total)]
    if track.compilation: ogg['compilation'] = ['1']
    ogg['oggcultist_target_bitrate'] = ['96000']
    ogg['oggcultist_vbr'] = ['on']
    ogg['metadata_block_picture'] = [picture_comment(cover)]
    ogg.save()


def verify(path: Path, track: Track) -> None:
    data = probe(path)
    loaded = OggOpus(path)
    checks = {'albumartist':track.albumartist,'album':track.album,
              'title':track.title,'tracknumber':str(track.track)}
    if track.originaldate:
        checks['originalyear'] = track.year
    for key,value in checks.items():
        if loaded.get(key,[''])[0] != value:
            raise RuntimeError('Output tag verification failed: ' + key)
    if len(loaded.get('metadata_block_picture',[])) != 1:
        raise RuntimeError('Output cover art was not embedded correctly')
    try:
        picture = Picture(base64.b64decode(loaded['metadata_block_picture'][0], validate=True))
        with Image.open(io.BytesIO(picture.data)) as cover:
            cover.verify()
        if picture.mime != 'image/png' or (picture.width, picture.height) != (600, 600):
            raise ValueError('unexpected cover format')
    except Exception as exc:
        raise RuntimeError('Output cover failed integrity verification') from exc
    duration = data.get('format',{}).get('duration') or data['streams'][0].get('duration')
    if duration and track.duration and abs(float(duration)-track.duration)>0.35:
        raise RuntimeError('Output duration differed from source by more than 350 ms')
    if path.stat().st_size < 200:
        raise RuntimeError('Output unexpectedly small')
    # Inspect the entire newly encoded audio stream before publishing it.
    decoded = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-xerror',
                              '-i', str(path), '-map', '0:a:0', '-f', 'null', '-'],
                             capture_output=True, text=True, timeout=max(60, int(track.duration / 3) + 10),
                             **no_window_kwargs())
    if decoded.returncode:
        raise RuntimeError('Full output audio decode failed (strict Opus verification): ' + decoded.stderr[-1200:])


def publish_no_overwrite(staged: Path, target: Path) -> None:
    """Publish staged bytes without ever overwriting another file."""
    # Ensure staged bytes are durable before exposing the final filename.
    # On Windows os.fsync() calls the CRT _commit(), which rejects read-only
    # file handles with EBADF. We own this verified staging file and open it
    # for read/write *without changing its contents* before the flush.
    with open(staged, 'r+b') as src:
        os.fsync(src.fileno())
    try:
        os.link(staged,target)  # Atomic no-overwrite on ordinary NTFS/ext4.
    except FileExistsError:
        raise RuntimeError('Output appeared while converting; refusing to overwrite')
    except OSError:
        # Filesystems without hard links: exclusive reservation and careful cleanup.
        created = False
        try:
            with open(target,'xb') as dst:
                created = True
                with open(staged,'rb') as src:
                    shutil.copyfileobj(src,dst,1024*1024)
                dst.flush()
                os.fsync(dst.fileno())
        except BaseException:
            if created: target.unlink(missing_ok=True)
            raise
    staged.unlink()
    # On POSIX, fsync the directory entry too (best effort on unsupported FS).
    if os.name == 'posix' and hasattr(os, 'O_DIRECTORY'):
        try:
            fd = os.open(str(target.parent), os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except OSError:
            pass


def convert_one(track: Track, store: ArtworkStore, cancel: threading.Event,
                progress: Callable[[float],None] = lambda _:None) -> tuple[int,bool]:
    if track.status != 'Ready' or track.target is None:
        raise RuntimeError('Track requires review or is already done')
    _has_required_tools()
    target = track.target
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise RuntimeError('Output already exists; refusing to overwrite')
    fd, tmpname = tempfile.mkstemp(prefix='.oggcultist-',suffix='.opus',dir=target.parent)
    os.close(fd)
    temp = Path(tmpname)
    try:
        if cancel.is_set(): raise Cancelled()
        before_stat = track.source.stat()
        original_fingerprint = fingerprint(track)
        original_sha = file_hash(track.source)
        copy_audio = _encode(track,temp,cancel,progress)
        if cancel.is_set(): raise Cancelled()
        album_key = track.cover_key or track.album_key()
        # an album that already has songs keeps its cover exactly (font/size changes don't mix looks)
        cover = (store.existing_cover(track.target.parent, album_key)
                 or store.cover_for(album_key, track.album, track.albumartist, track.year or 'Unknown Year'))
        _write_opus_tags(temp,track,cover)
        verify(temp,track)
        after_stat = track.source.stat()
        if (before_stat.st_size, before_stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns):
            raise RuntimeError('Source changed during conversion: output not published')
        if cancel.is_set(): raise Cancelled()
        publish_no_overwrite(temp,target)
        store.mark_complete(str(track.source.resolve()),original_fingerprint,
                            str(target.resolve()),target.stat().st_size,
                            source_sha256=original_sha,
                            metadata_signature=metadata_signature(track))
        return target.stat().st_size, copy_audio
    finally:
        temp.unlink(missing_ok=True)


def process(tracks: list[Track], output: Path, cancel: threading.Event,
            progress: Progress | None = None) -> dict:
    """Convert reviewed tracks. Failures remain local and never remove originals."""
    _has_required_tools()
    output.mkdir(parents=True,exist_ok=True)
    store = ArtworkStore(output)
    results = []
    try:
        plan(tracks,output,store)
        ready = [t for t in tracks if t.status=='Ready']
        for i,t in enumerate(ready,1):
            if cancel.is_set(): break
            if progress: progress(t.source.name,i,len(ready),0)
            try:
                outsize,copied = convert_one(t,store,cancel,lambda f: progress(t.source.name,i,len(ready),f) if progress else None)
                t.status = 'Done'
                t.note = 'Opus stream copied; new cover/tags added' if copied else 'Encoded 96k VBR and verified'
                if t.filename_inferred: t.note += '; ' + t.filename_inference_note
                results.append({'source':str(t.source),'output':str(t.target),'status':'done',
                                'input_bytes':t.size,'output_bytes':outsize,'savings_bytes':t.size-outsize,
                                'audio_copied':copied,'message':t.note})
            except Cancelled:
                t.status = 'Ready'
                break
            except Exception as exc:
                t.status = 'Error'
                t.note = describe_conversion_failure(t, exc)
                results.append({'source':str(t.source),'output':str(t.target),'status':'error',
                                'input_bytes':t.size,'output_bytes':0,'savings_bytes':0,
                                'audio_copied':False,'message':t.note})
            if progress: progress(t.source.name,i,len(ready),1)
        # Include every track, including entries waiting when cancellation occurred.
        recorded = {r['source'] for r in results}
        for t in tracks:
            if str(t.source) in recorded: continue
            status = ('cancelled' if cancel.is_set() and t.status == 'Ready' else
                      'already_done' if t.status == 'Done' else t.status.lower())
            results.append({'source':str(t.source),'output':str(t.target or ''),
                            'status':status,'input_bytes':t.size,'output_bytes':0,
                            'savings_bytes':0,'audio_copied':False,
                            'message':'Not processed: batch cancelled' if status == 'cancelled' else t.note})
        summary = {'created':datetime.now().isoformat(timespec='seconds'),
                   'cancelled':cancel.is_set(),'results':results,
                   'converted':sum(r['status']=='done' for r in results),
                   'errors':sum(r['status']=='error' for r in results),
                   'already_done':sum(r['status']=='already_done' for r in results),
                   'not_processed':sum(r['status'] not in ('done','error','already_done') for r in results),
                   'input_bytes':sum(r['input_bytes'] for r in results if r['status']=='done'),
                   'output_bytes':sum(r['output_bytes'] for r in results if r['status']=='done'),
                   'cover_warnings':[{'folder': k, 'message': v} for k, v in store.cover_warnings.items()]}
        json_report, csv_report = save_report(summary,store.state)
        summary['report_paths'] = (str(json_report), str(csv_report))
        return summary
    finally: store.close()


def save_report(summary: dict, state: Path) -> tuple[Path,Path]:
    reports = state/'reports'
    reports.mkdir(parents=True,exist_ok=True)
    stem = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    js,csvpath = reports/f'{stem}.json', reports/f'{stem}.csv'
    js.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    with csvpath.open('w',newline='',encoding='utf-8-sig') as f:
        fieldnames = ['source','output','status','input_bytes','output_bytes','savings_bytes','audio_copied','message']
        writer = csv.DictWriter(f,fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary['results'])
    return js,csvpath
