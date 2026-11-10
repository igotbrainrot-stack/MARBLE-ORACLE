"""Regression cases for the Windows 'Error in input stream' report.

These deliberately do not conceal source decoder faults or publish output that
has not passed the existing Opus verification pipeline.
"""
from __future__ import annotations

import hashlib
import subprocess
import threading
from pathlib import Path

import pytest

import oggcultist.core as core
from oggcultist.core import describe_conversion_failure, diagnose_source_stream, process, scan
from test_audit import BASE, flac, needs_ffmpeg


@needs_ffmpeg
def test_diagnose_valid_source_without_mutating_it(tmp_path):
    source = flac(tmp_path / 'source' / 'a.flac', title='A', tracknumber='1', **BASE)
    before = (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_mtime_ns)
    tracks, problems = scan(tmp_path / 'source')
    assert not problems
    okay, description = diagnose_source_stream(tracks[0])
    assert okay is True, description
    assert (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_mtime_ns) == before


@needs_ffmpeg
def test_input_error_report_identifies_unhealthy_source(tmp_path, monkeypatch):
    source = flac(tmp_path / 'source' / 'album' / '01.flac', title='A', tracknumber='1', **BASE)
    original = source.read_bytes()
    tracks, _ = scan(tmp_path / 'source')
    monkeypatch.setattr(core, '_encode', lambda *args: (_ for _ in ()).throw(RuntimeError('FFmpeg failed: Error in input stream')))
    monkeypatch.setattr(core, 'diagnose_source_stream', lambda t: (False, 'Invalid data found when processing input'))
    out = tmp_path / 'dest'
    result = process(tracks, out, threading.Event())
    assert result['errors'] == 1 and result['converted'] == 0
    assert 'SOURCE AUDIO DECODE ERROR' in result['results'][0]['message']
    assert 'Error in input stream' in result['results'][0]['message']
    assert not list(out.rglob('*.opus'))
    assert source.read_bytes() == original
    assert Path(result['report_paths'][0]).is_file()
    assert Path(result['report_paths'][1]).is_file()


@needs_ffmpeg
def test_input_error_report_distinguishes_healthy_source(tmp_path, monkeypatch):
    flac(tmp_path / 'source' / 'album' / '01.flac', title='A', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'source')
    monkeypatch.setattr(core, '_encode', lambda *args: (_ for _ in ()).throw(RuntimeError('FFmpeg failed: Error in input stream')))
    monkeypatch.setattr(core, 'diagnose_source_stream', lambda t: (True, 'Source decodes'))
    result = process(tracks, tmp_path / 'dest', threading.Event())
    assert result['errors'] == 1
    assert 'CONVERSION / OUTPUT VERIFICATION ERROR' in result['results'][0]['message']
    assert not list((tmp_path / 'dest').rglob('*.opus'))


@needs_ffmpeg
def test_real_mp3_encodes_after_diagnostics_change(tmp_path):
    from mutagen.easyid3 import EasyID3
    source = tmp_path / 'source' / 'album' / '01.mp3'
    source.parent.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=1',
                    '-c:a', 'libmp3lame', str(source)], check=True)
    tags = EasyID3(source)
    tags.update({'title': 'A', 'album': 'Album', 'albumartist': 'Band',
                 'artist': 'Band', 'date': '1975', 'tracknumber': '1'})
    tags.save()
    original = source.read_bytes()
    tracks, problems = scan(tmp_path / 'source')
    assert not problems
    result = process(tracks, tmp_path / 'dest', threading.Event())
    assert result['converted'] == 1, result
    assert source.read_bytes() == original
