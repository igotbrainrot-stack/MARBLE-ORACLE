"""v1.8.0: album art editor (colour and text of Oggcultist's generated covers).

Every test runs the real converter on synthetic FLAC sources (FFmpeg lavfi), so the
library, ledger and embedded covers are exactly what users have.
"""
from __future__ import annotations

import base64
import hashlib
import io
import shutil
import subprocess
import threading
from collections import Counter
from pathlib import Path

import pytest

pytest.importorskip('mutagen')
pytest.importorskip('PIL')

from mutagen.flac import FLAC, Picture  # noqa: E402
from mutagen.oggopus import OggOpus  # noqa: E402
from PIL import Image  # noqa: E402

from oggcultist.converter import core  # noqa: E402
from oggcultist.converter.artwork import ArtworkStore, draw_cover  # noqa: E402
from oggcultist.converter.cover_editor import (CoverDesign, CoverEditError, CoverEditor,  # noqa: E402
                                               _audio_md5)

needs_ffmpeg = pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')), reason='FFmpeg missing')


def _flac(path: Path, freq: int, **tags) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', f'sine=frequency={freq}:duration=0.6',
                    '-c:a', 'flac', '-y', str(path)], check=True)
    f = FLAC(path)
    for k, v in tags.items():
        f[k] = [v]
    f.save()


@pytest.fixture
def library(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'Mÿ Library'
    for album, artist, year, count in (('Salt Hymns', 'Tide Choir', '2001', 3), ('Ash Lanes', 'Kiln', '1999', 2)):
        for n in range(1, count + 1):
            _flac(src / album / f'{n:02}.flac', 300 + n * 40, title=f'{album} {n}', album=album, albumartist=artist,
                  artist=artist, date=year, tracknumber=str(n))
    tracks, errors = core.scan(src)
    assert not errors
    core.plan(tracks, out)
    result = core.process(tracks, out, threading.Event())
    assert result['converted'] == 5 and result['errors'] == 0, result
    return src, out


def _picture(path: Path):
    return Picture(base64.b64decode(OggOpus(path)['metadata_block_picture'][0]))


def _replan(src: Path, out: Path):
    tracks, _ = core.scan(src)
    store = ArtworkStore(out)
    try:
        core.plan(tracks, out, store)
        warnings = {store.folder_warning(t.target.parent) for t in tracks if t.target} - {''}
    finally:
        store.close()
    return Counter(t.status for t in tracks), warnings


# ---------------------------------------------------------------------------- drawing
def test_draw_cover_custom_lines_and_ink():
    default = draw_cover('A', 'B', '2000', '102030')
    assert draw_cover('A', 'B', '2000', '102030', lines=None, ink='auto') == default
    custom = draw_cover('A', 'B', '2000', '102030', lines=['Only one line', '', ''], ink='FFD154')
    with Image.open(io.BytesIO(custom)) as im:
        rgb = im.convert('RGB')
        assert rgb.getpixel((0, 0)) == (0x10, 0x20, 0x30)
        assert (0xFF, 0xD1, 0x54) in {c for _, c in rgb.getcolors(1 << 20)}
    blank = draw_cover('A', 'B', '2000', '102030', lines=['', '', ''])
    with Image.open(io.BytesIO(blank)) as im:
        assert len(im.convert('RGB').getcolors()) == 1          # no text at all: plain colour


def test_unsupported_characters_give_a_clear_message():
    with pytest.raises(CoverEditError, match='can.t draw'):
        CoverDesign('112233', ['Night ✦']).png()
    with pytest.raises(CoverEditError, match='not a colour'):
        CoverEditor(Path('.')).free_colour('red')


# ---------------------------------------------------------------------------- listing
def test_folder_without_database_has_nothing_to_edit(tmp_path):
    editor = CoverEditor(tmp_path)
    assert not editor.available and editor.albums() == []


@needs_ffmpeg
def test_lists_converted_albums_with_their_current_cover(library):
    _src, out = library
    albums = CoverEditor(out).albums()
    assert [a.album for a in albums] == ['Ash Lanes', 'Salt Hymns']
    salt = albums[1]
    assert salt.artist == 'Tide Choir' and salt.year == '2001' and salt.file_count == 3
    assert salt.design.lines == ['Salt Hymns', 'Tide Choir', '2001'] and salt.design.ink == 'auto'
    assert not salt.customised
    first = sorted(salt.folder.glob('*.opus'))[0]
    with Image.open(io.BytesIO(_picture(first).data)) as im:
        assert ''.join(f'{c:02X}' for c in im.convert('RGB').getpixel((0, 0))) == salt.design.colour


# ---------------------------------------------------------------------------- applying
@needs_ffmpeg
def test_apply_changes_only_the_cover_and_converter_still_recognises_files(library):
    src, out = library
    editor = CoverEditor(out)
    salt = [a for a in editor.albums() if a.album == 'Salt Hymns'][0]
    files = sorted(salt.folder.glob('*.opus'))
    before = {p: (_audio_md5(p), {k: list(v) for k, v in OggOpus(p).tags.items()
                                  if k.lower() != 'metadata_block_picture'}) for p in files}
    design = CoverDesign('1B4D3E', ['SALT HYMNS', 'tide choir', ''], 'F2E8DE')
    plan = editor.plan(salt, design)
    assert len(plan.eligible) == 3 and not plan.skipped and not plan.colour_note
    result = editor.apply(plan)
    assert len(result.updated) == 3 and not result.failed
    expected = design.png(salt.album, salt.artist, salt.year)
    for p in files:
        assert _picture(p).data == expected
        audio, tags = before[p]
        assert _audio_md5(p) == audio                                       # audio untouched
        assert {k: list(v) for k, v in OggOpus(p).tags.items()
                if k.lower() != 'metadata_block_picture'} == tags            # other tags untouched
    statuses, warnings = _replan(src, out)
    assert statuses == Counter({'Done': 5}) and not warnings                # still its own finished outputs
    again = [a for a in CoverEditor(out).albums() if a.album == 'Salt Hymns'][0]
    assert again.design.colour == '1B4D3E' and again.design.lines == ['SALT HYMNS', 'tide choir', '']
    assert again.design.ink == 'F2E8DE' and again.customised
    replan = editor.plan(again, again.design)
    assert not replan.eligible and len(replan.already) == 3                 # re-applying is a no-op


@needs_ffmpeg
def test_new_conversions_into_an_edited_album_use_the_design(library):
    _src, out = library
    editor = CoverEditor(out)
    ash = [a for a in editor.albums() if a.album == 'Ash Lanes'][0]
    design = CoverDesign('302010', ['Ash', '', 'MCMXCIX'], 'auto')
    editor.apply(editor.plan(ash, design))
    store = ArtworkStore(out)
    try:
        assert store.cover_for(ash.album_key, ash.album, ash.artist, ash.year) == design.png(ash.album, ash.artist, ash.year)
    finally:
        store.close()


@needs_ffmpeg
def test_colour_already_used_by_another_album_is_nudged_to_stay_unique(library):
    _src, out = library
    editor = CoverEditor(out)
    ash, salt = editor.albums()
    plan = editor.plan(salt, CoverDesign(ash.design.colour, salt.design.lines))
    assert plan.design.colour != ash.design.colour
    assert 'Kiln' in plan.colour_note and 'nearly identical' in plan.colour_note
    a, b = (int(ash.design.colour[i:i + 2], 16) for i in (0, 2)), (int(plan.design.colour[i:i + 2], 16) for i in (0, 2))
    assert all(abs(x - y) <= 1 for x, y in zip(a, b))
    editor.apply(plan)
    assert len({x.design.colour for x in CoverEditor(out).albums()}) == 2


@needs_ffmpeg
def test_files_that_are_not_untouched_oggcultist_outputs_are_skipped(library):
    src, out = library
    editor = CoverEditor(out)
    salt = [a for a in editor.albums() if a.album == 'Salt Hymns'][0]
    files = sorted(salt.folder.glob('*.opus'))
    edited, photo = files[0], files[1]
    tags = OggOpus(edited)
    tags['comment'] = ['edited elsewhere']
    tags.save()                                                     # no longer matches the ledger
    image = Image.new('RGB', (600, 600), (10, 20, 30))
    image.paste((200, 100, 50), (100, 100, 500, 500))               # a "real" cover: not one flat colour
    raw = io.BytesIO(); image.save(raw, 'PNG')
    pic = Picture(); pic.type = 3; pic.mime = 'image/png'; pic.width = pic.height = 600; pic.depth = 24
    pic.data = raw.getvalue()
    tags = OggOpus(photo)
    tags['metadata_block_picture'] = [base64.b64encode(pic.write()).decode()]
    tags.save()
    snapshot = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (edited, photo)}
    plan = editor.plan(salt, CoverDesign('0A0B0C', salt.design.lines))
    reasons = dict(plan.skipped)
    assert plan.eligible == [files[2]]
    assert 'not recorded' in reasons[edited] and 'not this album' in reasons[photo]
    editor.apply(plan)
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (edited, photo)} == snapshot   # untouched


@needs_ffmpeg
def test_resetting_to_default_text_forgets_the_custom_design(library):
    _src, out = library
    editor = CoverEditor(out)
    salt = [a for a in editor.albums() if a.album == 'Salt Hymns'][0]
    editor.apply(editor.plan(salt, CoverDesign(salt.design.colour, ['Custom'], 'FFFFFF')))
    salt = [a for a in editor.albums() if a.album == 'Salt Hymns'][0]
    assert salt.customised
    editor.apply(editor.plan(salt, CoverDesign(salt.design.colour, salt.default_lines(), 'auto')))
    salt = [a for a in editor.albums() if a.album == 'Salt Hymns'][0]
    assert not salt.customised and salt.design.lines == salt.default_lines()
    expected = draw_cover(salt.album, salt.artist, salt.year, salt.design.colour)
    assert all(_picture(p).data == expected for p in salt.folder.glob('*.opus'))


@needs_ffmpeg
def test_original_sources_are_never_touched(library):
    src, out = library
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*.flac')}
    editor = CoverEditor(out)
    for album in editor.albums():
        editor.apply(editor.plan(album, CoverDesign(editor.random_colour(album.album_key), ['x'])))
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*.flac')} == before
