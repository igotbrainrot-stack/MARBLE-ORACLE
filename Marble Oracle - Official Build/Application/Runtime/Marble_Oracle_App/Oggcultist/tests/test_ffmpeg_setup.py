"""Offline Windows installer and Linux launch tests for first-run setup."""
from __future__ import annotations
import hashlib
import io
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import setup_ffmpeg as sf


def archive_bytes():
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('ffmpeg-sample-essentials_build/bin/ffmpeg.exe', b'fake-ffmpeg-program')
        zf.writestr('ffmpeg-sample-essentials_build/bin/ffprobe.exe', b'fake-ffprobe-program')
        zf.writestr('ffmpeg-sample-essentials_build/doc/README', b'not needed')
    return raw.getvalue()


def fake_open(archive, good_sha=True):
    def opener(request, timeout=None):
        if request.full_url.endswith('.sha256'):
            digest = hashlib.sha256(archive).hexdigest() if good_sha else 'f'*64
            return io.BytesIO((digest + '  ffmpeg-release-essentials.zip\n').encode())
        assert request.full_url == sf.FFMPEG_BASE
        return io.BytesIO(archive)
    return opener


def test_windows_approved_download_verified_and_private(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': '/a'}
    messages = []
    downloaded = archive_bytes()
    def check(platform):
        b = sf.local_bin(platform, env)
        return all((b / n).is_file() for n in ('ffmpeg.exe', 'ffprobe.exe'))
    ok = sf.ensure_ffmpeg(platform='win32', env=env, input_fn=lambda _: '',
                          print_fn=messages.append, opener=fake_open(downloaded), check_fn=check)
    assert ok
    where = tmp_path / 'Oggcultist' / 'ffmpeg' / 'bin'
    assert (where / 'ffmpeg.exe').read_bytes() == b'fake-ffmpeg-program'
    assert (where / 'ffprobe.exe').read_bytes() == b'fake-ffprobe-program'
    assert not (where / 'README').exists()
    assert env['PATH'].startswith(str(where) + os.pathsep)
    assert 'installed successfully' in messages[-1]


def test_windows_relaunch_skips_download(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': '/a'}
    called = []
    assert sf.ensure_ffmpeg(platform='win32', env=env, print_fn=lambda m: called.append(m),
                            check_fn=lambda _: True,
                            input_fn=lambda _: pytest.fail('Unexpected prompt'),
                            opener=lambda *_args, **_kwargs: pytest.fail('Unexpected network'))
    assert 'available' in called[0]
    assert not (tmp_path / 'Oggcultist').exists()


def test_declining_install_has_zero_side_effects(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': '/a'}
    assert not sf.ensure_ffmpeg(platform='win32', env=env, print_fn=lambda _: None,
                                check_fn=lambda _: False, input_fn=lambda _: 'n',
                                opener=lambda *_args, **_kwargs: pytest.fail('Unexpected network'))
    assert not (tmp_path / 'Oggcultist').exists()


def test_download_checksum_failure_leaves_no_executable(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': '/a'}
    messages = []
    assert not sf.ensure_ffmpeg(platform='win32', env=env,
                                check_fn=lambda _: False, print_fn=messages.append,
                                input_fn=lambda _: 'yes', opener=fake_open(archive_bytes(), good_sha=False))
    assert not sf.local_bin('win32', env).exists()
    assert any('SHA-256 verification failed' in msg for msg in messages)


def test_invalid_zip_does_not_install(tmp_path):
    with pytest.raises(sf.SetupError):
        sf.install_windows(b'not zip bytes', tmp_path / 'bin')
    assert not (tmp_path / 'bin').exists()


def test_absent_ffprobe_also_requires_setup(monkeypatch):
    monkeypatch.setattr(sf.shutil, 'which', lambda name: '/mock/' + name if name == 'ffmpeg.exe' else None)
    assert not sf.binaries_available(platform='win32')


def test_apt_install_is_prompted_and_checked(monkeypatch):
    monkeypatch.setattr(sf.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(sf.os, 'geteuid', lambda: 1000)
    commands = []
    ok = sf.ensure_ffmpeg(platform='linux', env={'PATH':'/usr/bin'}, input_fn=lambda _: 'y',
                          print_fn=lambda _: None,
                          check_fn=lambda platform: bool(commands),
                          run_fn=lambda cmd, check: (commands.append(cmd), SimpleNamespace(returncode=0))[1])
    assert ok and commands == [['sudo', 'apt-get', 'install', '-y', 'ffmpeg']]


def test_archive_url_and_hash_are_official_https():
    assert sf.FFMPEG_BASE == 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    with pytest.raises(sf.SetupError):
        sf._expected_sha(b'not a SHA-256 digest')
