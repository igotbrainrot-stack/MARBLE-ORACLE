"""2.0.0 "Ember": bundled Forge fonts, design tokens, upgrade path and the new layout.

Replaces the 1.8.6–1.9.13 font tests (test_v186_font, test_v187_fonts, test_v191_fonts,
test_v192_bundle, test_v193_*, test_v1911_original_typography, test_v195_titles,
test_v197_aero), which described font choices and a first-launch font build that 2.0 removed.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from oggcultist import fonts

ROOT = Path(__file__).resolve().parents[1]
needs_display = pytest.mark.skipif(not os.getenv('DISPLAY') and os.name != 'nt',
                                   reason='requires a graphical Tk display')


# ---------------------------------------------------------------------------- fonts: files
def test_forge_fonts_ship_ready_made_with_licences():
    fonts.require_complete_bundle(strict=True)
    assert [i.filename for i in fonts.FONTS] == ['Uberfonto-Refined-Regular.ttf',
                                                 'Oggcultist-Interface-Regular.ttf',
                                                 'Oggcultist-Interface-Bold.ttf']
    for info in fonts.FONTS:
        path = fonts.resource(info.filename)
        assert path == ROOT / 'oggcultist/resources/fonts' / info.filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info.sha256
    assert 'SIL OPEN FONT LICENSE' in fonts.resource('OFL-Uberfonto-Refined.txt').read_text('utf-8')
    assert 'Oggcultist' in fonts.resource('LICENSE-OGGCULTIST-FONTS.txt').read_text('utf-8')
    # nothing from 1.9 that no longer ships is left behind in the folder
    shipped = {p.name for p in (ROOT / 'oggcultist/resources/fonts').iterdir()}
    assert shipped == {*(i.filename for i in fonts.FONTS), *fonts.LICENCE_FILES, 'README.md'}


def test_font_names_weights_and_german_coverage():
    ttlib = pytest.importorskip('fontTools.ttLib')
    expected = {'Uberfonto-Refined-Regular.ttf': ('Uberfonto Refined', 400),
                'Oggcultist-Interface-Regular.ttf': ('Oggcultist Interface', 400),
                'Oggcultist-Interface-Bold.ttf': ('Oggcultist Interface', 700)}
    for name, (family, weight) in expected.items():
        font = ttlib.TTFont(fonts.resource(name))
        try:
            assert font['name'].getDebugName(1) == family
            assert font['OS/2'].usWeightClass == weight
            cmap = font.getBestCmap()
            assert all(ord(c) in cmap for c in 'ÄÖÜäöüßé…·')
        finally:
            font.close()


def test_a_changed_or_missing_font_stops_a_release(monkeypatch, tmp_path):
    real = fonts.resource
    fake = tmp_path / fonts.FONTS[1].filename
    fake.write_bytes(b'not the release')
    monkeypatch.setattr(fonts, 'resource', lambda n: fake if n == fonts.FONTS[1].filename else real(n))
    fonts.require_complete_bundle()                      # present: fine for running
    with pytest.raises(RuntimeError, match='changed'):
        fonts.require_complete_bundle(strict=True)       # but not for building a release
    monkeypatch.setattr(fonts, 'resource', lambda n: None if n == fonts.FONTS[0].filename else real(n))
    with pytest.raises(FileNotFoundError, match='missing'):
        fonts.require_complete_bundle()


def test_runtime_needs_neither_fonttools_nor_shapely():
    code = ('import sys; import oggcultist.fonts as f; f.require_complete_bundle(strict=True); '
            'print(any(m.split(".")[0] in ("fontTools", "shapely") for m in sys.modules))')
    out = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), capture_output=True, text=True, check=True)
    assert out.stdout.strip() == 'False'
    requirements = (ROOT / 'requirements.txt').read_text('utf-8').lower()
    assert 'fonttools' not in requirements and 'shapely' not in requirements


# ---------------------------------------------------------------------------- fonts: registration
def test_registration_is_private_and_one_bad_file_does_not_stop_the_rest():
    calls = []

    class Gdi32:
        def AddFontResourceExW(self, path, flags, reserved):
            calls.append((Path(path).name, flags))
            return 0 if Path(path).name == fonts.FONTS[1].filename else 1

    assert fonts.register_private_fonts(platform='win32', gdi32=Gdi32()) is False
    assert [name for name, _ in calls] == [i.filename for i in fonts.FONTS]   # all three tried
    assert {flags for _, flags in calls} == {0x10}                            # FR_PRIVATE only

    added = []

    class Fontconfig:
        def FcConfigAppFontAddFile(self, config, path):
            added.append(Path(path.decode()).name)
            return 1

    assert fonts.register_private_fonts(platform='linux', fontconfig=Fontconfig()) is True
    assert added == [i.filename for i in fonts.FONTS]


def test_legacy_font_settings_are_understood_and_ignored():
    for value in ('new', 'aero', 'old', 'uberata', 'garbage', None, 3, ['x']):
        assert fonts.heading_family(value) == fonts.HEADING_FAMILY == 'Uberfonto Refined'
        assert fonts.body_family(value) == fonts.BODY_FAMILY == 'Oggcultist Interface'
        assert fonts.normalise_heading_choice(value) == 'refined'
    assert fonts.font_file() == fonts.heading_file()


# ---------------------------------------------------------------------------- fonts: export
def test_export_makes_a_new_folder_and_never_overwrites(tmp_path):
    first = fonts.export_fonts(tmp_path)
    assert first.name == 'Oggcultist Fonts'
    assert {p.name for p in first.iterdir()} == {*(i.filename for i in fonts.FONTS), *fonts.LICENCE_FILES,
                                                 'HOW TO INSTALL.txt'}
    marker = first / 'HOW TO INSTALL.txt'
    marker.write_text('mine', encoding='utf-8')
    second = fonts.export_fonts(tmp_path)
    assert second.name == 'Oggcultist Fonts (2)' and marker.read_text('utf-8') == 'mine'
    one = fonts.export_fonts(tmp_path, font_key='uberfonto-refined')
    assert {p.name for p in one.iterdir()} == {'Uberfonto-Refined-Regular.ttf', 'OFL-Uberfonto-Refined.txt',
                                               'HOW TO INSTALL.txt'}
    with pytest.raises(ValueError):
        fonts.export_fonts(tmp_path, font_key='uberfonto-new')
    with pytest.raises(FileNotFoundError):
        fonts.export_fonts(tmp_path / 'missing')


def test_album_cover_titles_use_the_heading_font():
    from oggcultist.converter import artwork
    title = artwork._preferred_cover_font('Morning Tide', artwork.find_serif_font(), role='title')
    meta = artwork._preferred_cover_font('Harbour Lights', artwork.find_serif_font(), role='meta')
    assert Path(title).name == 'Uberfonto-Refined-Regular.ttf'
    assert Path(meta).name == 'Oggcultist-Interface-Bold.ttf'


# ---------------------------------------------------------------------------- tokens
def test_tokens_are_the_single_source_and_meet_contrast():
    from oggcultist.gui import design_system as ds
    from oggcultist.gui.theme import GRADIENT, PALETTE
    assert PALETTE['bg'] == ds.COLOR['canvas'] and PALETTE['accent'] == ds.COLOR['accent']
    assert GRADIENT == ds.ACCENT_GRADIENT
    c = ds.contrast
    for surface in ('canvas', 'raised', 'sunken'):
        assert c(ds.COLOR['text'], ds.COLOR[surface]) >= 7
        assert c(ds.COLOR['text_2'], ds.COLOR[surface]) >= 4.5
        assert c(ds.COLOR['text_3'], ds.COLOR[surface]) >= 4.3           # tertiary and disabled text
    assert c(ds.COLOR['text_3'], ds.COLOR['canvas']) >= 4.5
    assert c(ds.COLOR['sidebar_text'], ds.COLOR['sidebar']) >= 7
    assert c(ds.COLOR['text_on_accent'], ds.ACCENT_GRADIENT[1]) >= 7
    assert all(v % 2 == 0 for v in ds.SPACE.values())
    assert ds.MIN_WINDOW == (960, 600) and ds.SIDEBAR_WIDTH == 208 and ds.SIDEBAR_COMPACT_WIDTH == 64


def test_line_icons_render_every_shape():
    from oggcultist.gui import line_icons
    for name in line_icons.SHAPES:
        image = line_icons.render(name, 18, '#FB8E22')
        assert image.size == (18, 18) and image.mode == 'RGBA'
        alpha = image.getchannel('A')
        assert alpha.getextrema()[1] > 200, name                        # something is drawn
        assert sum(alpha.getdata()) < 18 * 18 * 255 * 0.6, name          # and it is a line icon, not a blob


# ---------------------------------------------------------------------------- the window
@pytest.fixture
def app(tmp_path, monkeypatch):
    pytest.importorskip('tkinter')
    if not os.getenv('DISPLAY') and os.name != 'nt':
        pytest.skip('requires a graphical Tk display')
    from oggcultist import paths
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'data'))
    config = paths.config_dir()
    config.mkdir(parents=True, exist_ok=True)
    # a 1.9.x settings file with font choices that no longer exist
    paths.settings_file().write_text(json.dumps({'heading_font': 'aero', 'body_font': 'uberata',
                                                 'volume': 55, 'animations': False}), encoding='utf-8')
    from oggcultist.gui.app import OggcultistApp
    window = OggcultistApp()
    window.update()
    yield window
    window._on_close()


@needs_display
def test_1_9_settings_upgrade_cleanly_and_keep_their_values(app):
    from tkinter import font as tkfont
    from oggcultist.gui.app import load_settings
    assert tkfont.nametofont('OgTitle', root=app).actual('family') == fonts.HEADING_FAMILY
    assert tkfont.nametofont('OgBody', root=app).actual('family') == fonts.BODY_FAMILY
    assert tkfont.nametofont('OgTitle', root=app).actual('weight') == 'normal'   # never a fake bold
    assert int(app.volume.get()) == 55
    saved = load_settings()
    assert saved['heading_font'] == 'aero' and saved['body_font'] == 'uberata'   # left for older versions


@needs_display
def test_type_scale_follows_the_tokens(app):
    from tkinter import font as tkfont
    from oggcultist.gui import design_system as ds
    size = lambda n: abs(int(tkfont.nametofont(n, root=app).actual('size')))
    body = size('OgBody')
    assert body >= ds.BODY_POINTS
    assert size('OgTitle') == ds.points('display_xl', body)
    assert size('OgNowTitle') == ds.points('display_l', body)
    assert size('OgHeading') == ds.points('title', body)
    assert size('OgColumn') == ds.points('label', body)
    assert tkfont.nametofont('OgHeading', root=app).actual('family') == fonts.BODY_FAMILY


@needs_display
def test_minimum_window_and_icon_rail(app):
    from oggcultist.gui import design_system as ds
    app.geometry('960x600')
    app.update()
    assert app.minsize() == ds.MIN_WINDOW
    assert app.compact and app._sidebar.winfo_width() == ds.SIDEBAR_COMPACT_WIDTH
    assert all(str(b.cget('image')) for b in app.nav.values())                 # icons carry the rail
    app.geometry('1280x800')
    app.update()
    assert not app.compact and app._sidebar.winfo_width() == ds.SIDEBAR_WIDTH
    assert app.nav['library'].cget('text') == 'Library'


@needs_display
def test_search_placeholder_never_enters_the_search(app):
    app.show_page('library')
    app.update()
    assert app._search_placeholder.winfo_ismapped()
    assert app.search.get() == ''
    app.search.set('heron')
    app.update()
    assert not app._search_placeholder.winfo_ismapped()
    app.search.set('')
    app.show_page('settings')                                                  # search is off there
    app.update()
    assert not app._search_placeholder.winfo_ismapped()


@needs_display
def test_settings_page_cards_and_font_export(app, tmp_path):
    page = app.pages['settings']
    assert set(page.cards) == {'appearance', 'playback', 'fonts', 'folder', 'about'}
    assert set(page.font_export_buttons) == set(fonts.FONT_BY_KEY)
    folder = page.save_fonts(tmp_path)
    assert folder is not None and (folder / 'Uberfonto-Refined-Regular.ttf').is_file()
    assert str(page.open_btn.cget('state')) == 'normal'
    again = page.save_fonts(tmp_path)
    assert again != folder


@needs_display
def test_disabled_text_is_readable(app):
    from tkinter import ttk
    from oggcultist.gui import design_system as ds
    style = ttk.Style(app)
    disabled = style.map('TButton', 'foreground')
    assert ('disabled', ds.COLOR['text_3']) in [(tuple(s)[0] if not isinstance(s, str) else s, c)
                                                for s, c in disabled]


@needs_display
def test_shuffle_all_turns_shuffle_on(app, monkeypatch):
    page = app.pages['library']
    played = []
    monkeypatch.setattr(app.player, 'play_list', lambda songs, index=0: played.append((list(songs), index)))
    assert not app.player.shuffle
    page.shuffle_all()
    assert app.player.shuffle and played


# ---------------------------------------------------------------------------- release
def test_version_is_consistent_everywhere():
    import importlib.util
    from oggcultist import __version__
    assert __version__ == '2.0.3'
    spec = importlib.util.spec_from_file_location('ogg_build', ROOT / 'packaging/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check_versions(__version__)


def test_program_archive_carries_the_fonts_and_no_handover(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('ogg_release', ROOT / 'packaging/source_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / 'program.zip'
    module.make_archive(target, complete=False)
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
        assert z.testzip() is None
        for info in fonts.FONTS:
            assert z.read(module.archive_name(f'oggcultist/resources/fonts/{info.filename}')) == \
                fonts.resource(info.filename).read_bytes()
        top = module.release_folder()
        assert {n for n in names if n.count('/') == 1} == {f'{top}/WINDOWS LAUNCHER.bat', f'{top}/LINUX LAUNCHER.sh'}
        assert all(n.startswith(f'{top}/Oggcultist/') for n in names if n.count('/') > 1)
        assert not any('/CLAUDE_' in n for n in names)
        assert not any('/branding/stone-knot/' in n for n in names)
        assert any(n.endswith('/tests/test_v200_ember.py') for n in names)


# ---------------------------------------------------------------------------- 2.0.1 folder layout
@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
def test_linux_launcher_explains_a_missing_program_folder(tmp_path):
    launcher = tmp_path / 'LINUX LAUNCHER.sh'
    launcher.write_bytes((ROOT.parent / 'LINUX LAUNCHER.sh').read_bytes())
    result = subprocess.run(['bash', str(launcher)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert 'Oggcultist" folder was not found' in result.stderr
    assert not (tmp_path / '.venv').exists()                     # it never sets up Python in the wrong place


def _launcher_copy(tmp_path):
    top = tmp_path / 'release'
    (top / 'Oggcultist').mkdir(parents=True)
    (top / 'Oggcultist' / 'launch.py').write_text('raise SystemExit(0)\n', encoding='utf-8')
    (top / 'Oggcultist' / 'requirements.txt').write_text('', encoding='utf-8')
    launcher = top / 'LINUX LAUNCHER.sh'
    launcher.write_bytes((ROOT.parent / 'LINUX LAUNCHER.sh').read_bytes())
    return top, launcher


def _fake_python(tmp_path, refuse: str):
    fake = tmp_path / 'python3'
    fake.write_text('#!/bin/bash\nfor a in "$@"; do case "$a" in *%s*) echo "No module named %s" >&2; exit 1;; esac; done\n'
                    'exec %s "$@"\n' % (refuse, refuse, sys.executable), encoding='utf-8')
    fake.chmod(0o755)
    return fake


@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
@pytest.mark.parametrize('refuse, package', [('tkinter', 'python3-tk'), ('ensurepip', 'python3-venv')])
def test_linux_launcher_names_the_missing_mint_package_and_logs_it(tmp_path, refuse, package):
    # no terminal and no zenity/pkexec: it cannot ask, so it explains the command instead
    top, launcher = _launcher_copy(tmp_path)
    empty_bin = tmp_path / 'emptybin'
    empty_bin.mkdir()
    for tool in ('bash', 'sh', 'cat', 'date', 'dirname', 'mv', 'rm', 'sed', 'tee', 'printf'):
        found = __import__('shutil').which(tool)
        if found:
            (empty_bin / tool).symlink_to(found)
    (empty_bin / 'apt-get').write_text('#!/bin/bash\nexit 1\n', encoding='utf-8')   # a Mint system, no way to ask
    (empty_bin / 'apt-get').chmod(0o755)
    env = dict(os.environ, PYTHON=str(_fake_python(tmp_path, refuse)), PATH=str(empty_bin))
    result = subprocess.run(['bash', str(launcher)], capture_output=True, text=True, timeout=60, env=env,
                            stdin=subprocess.DEVNULL)
    assert result.returncode == 1
    log = (top / 'Oggcultist' / 'launcher-log.txt').read_text('utf-8')
    assert f'sudo apt install' in log and package in log
    assert not (top / 'Oggcultist' / '.venv').exists()


@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
def test_linux_launcher_shows_a_window_when_double_clicked(tmp_path):
    top, launcher = _launcher_copy(tmp_path)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    shown = tmp_path / 'zenity.txt'
    (bin_dir / 'zenity').write_text(f'#!/bin/bash\necho "$@" > "{shown}"\n', encoding='utf-8')
    (bin_dir / 'zenity').chmod(0o755)
    env = dict(os.environ, PYTHON=str(_fake_python(tmp_path, 'tkinter')), PATH=f'{bin_dir}:/usr/bin:/bin')
    subprocess.run(['bash', str(launcher)], capture_output=True, text=True, timeout=60, env=env,
                   stdin=subprocess.DEVNULL)
    # zenity without pkexec: it cannot install, so it shows how
    assert 'python3-tk' in shown.read_text('utf-8') and '--error' in shown.read_text('utf-8')


def _install_fakes(tmp_path, answer_install: bool):
    """Fake apt-get/pkexec/zenity and a Python whose Tkinter appears once apt-get 'installs' it."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    flag = tmp_path / 'installed'
    calls = tmp_path / 'calls.txt'
    scripts = {
        'python3': f'#!/bin/bash\nfor a in "$@"; do case "$a" in *tkinter*|*ensurepip*) [ -f "{flag}" ] || exit 1;; esac; done\n'
                   f'exec {sys.executable} "$@"\n',
        'apt-get': f'#!/bin/bash\necho "apt-get $*" >> "{calls}"\n[ "$1" = install ] && touch "{flag}"\nexit 0\n',
        'apt-cache': '#!/bin/bash\nexit 0\n',
        'pkexec': f'#!/bin/bash\necho "pkexec $*" >> "{calls}"\nexec "$@"\n',
        'zenity': f'#!/bin/bash\necho "zenity $1" >> "{calls}"\n[ "$1" = --progress ] && cat >/dev/null\n'
                  f'[ "$1" = --question ] && exit {0 if answer_install else 1}\nexit 0\n',
        'ffplay': '#!/bin/bash\nexit 0\n', 'ffprobe': '#!/bin/bash\nexit 0\n',
    }
    for name, text in scripts.items():
        (bin_dir / name).write_text(text, encoding='utf-8')
        (bin_dir / name).chmod(0o755)
    return bin_dir, flag, calls


@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
def test_linux_first_launch_installs_missing_packages_after_asking(tmp_path):
    top, launcher = _launcher_copy(tmp_path)
    bin_dir, flag, calls = _install_fakes(tmp_path, answer_install=True)
    env = dict(os.environ, PYTHON=str(bin_dir / 'python3'), PATH=f'{bin_dir}:/usr/bin:/bin')
    result = subprocess.run(['bash', str(launcher), '--paths'], capture_output=True, text=True, timeout=180,
                            env=env, stdin=subprocess.DEVNULL)
    log = (top / 'Oggcultist' / 'launcher-log.txt').read_text('utf-8')
    called = calls.read_text('utf-8')
    assert called.index('zenity --question') < called.index('pkexec')          # asked before installing
    assert 'apt-get install -y python3-venv' in called
    assert flag.exists() and 'System packages installed.' in log
    assert result.returncode == 0, log


@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
def test_linux_first_launch_installs_nothing_when_declined(tmp_path):
    top, launcher = _launcher_copy(tmp_path)
    bin_dir, flag, calls = _install_fakes(tmp_path, answer_install=False)
    env = dict(os.environ, PYTHON=str(bin_dir / 'python3'), PATH=f'{bin_dir}:/usr/bin:/bin')
    result = subprocess.run(['bash', str(launcher)], capture_output=True, text=True, timeout=60,
                            env=env, stdin=subprocess.DEVNULL)
    called = calls.read_text('utf-8')
    assert result.returncode == 1
    assert 'pkexec' not in called and 'apt-get' not in called and not flag.exists()
    assert 'sudo apt install python3-tk' in (top / 'Oggcultist' / 'launcher-log.txt').read_text('utf-8')


def test_windows_launcher_is_well_formed_and_asks_before_installing_python():
    import re
    text = (ROOT.parent / 'WINDOWS LAUNCHER.bat').read_bytes().decode('ascii')
    lines = text.split('\r\n')
    labels = {line[1:].split()[0].lower() for line in lines if line.startswith(':') and not line.startswith('::')}
    targets = {t.lower() for t in re.findall(r'(?:goto|call) :?([A-Za-z_]+)', text)} - {'eof'}
    assert targets <= labels, targets - labels
    lower = text.lower()
    assert lower.index('choice /c yn') < lower.index('winget install')
    assert 'winget install --exact --id python.python.3.12 --scope user' in lower   # no admin needed
    assert 'tkinter' in lower and 'rmdir /s /q ".venv"' in lower
    # every rmdir is limited to the private environment inside the program folder
    assert all('".venv"' in line for line in lines if 'rmdir' in line.lower())
    # nothing new inside parenthesised blocks (cmd expands those early and breaks on ")" in text)
    depth = 0
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(('rem', 'echo')) and depth == 0:
            continue
        depth += stripped.count('(') - stripped.count(')') if stripped.lower().startswith('if ') or depth else 0
        assert depth >= 0


@pytest.mark.skipif(os.name == 'nt', reason='runs the Linux launcher with bash')
def test_linux_launcher_rebuilds_a_half_made_environment(tmp_path):
    top, launcher = _launcher_copy(tmp_path)
    broken = top / 'Oggcultist' / '.venv' / 'bin'
    broken.mkdir(parents=True)
    # stop right after the repair decision: a venv module that refuses to run
    fake = tmp_path / 'python3'
    fake.write_text('#!/bin/bash\nif [ "$1" = "-m" ] && [ "$2" = "venv" ]; then echo "venv refused" >&2; exit 1; fi\n'
                    f'exec {sys.executable} "$@"\n', encoding='utf-8')
    fake.chmod(0o755)
    env = dict(os.environ, PYTHON=str(fake), PATH='/usr/bin:/bin')
    result = subprocess.run(['bash', str(launcher), '--version'], capture_output=True, text=True, timeout=60,
                            env=env, stdin=subprocess.DEVNULL)
    log = (top / 'Oggcultist' / 'launcher-log.txt').read_text('utf-8')
    assert result.returncode == 1
    assert 'incomplete' in log and 'rebuilding' in log
    assert 'python3-venv' in log
    assert not (top / 'Oggcultist' / '.venv').exists()          # the broken one is gone, nothing half-made left


def test_launchers_keep_everything_inside_the_program_folder():
    linux = (ROOT.parent / 'LINUX LAUNCHER.sh').read_text('utf-8')
    assert os.access(ROOT.parent / 'LINUX LAUNCHER.sh', os.X_OK)
    assert 'APP="$HERE/Oggcultist"' in linux and linux.index('cd "$APP"') < linux.index('-m venv .venv')
    windows = (ROOT.parent / 'WINDOWS LAUNCHER.bat').read_text('utf-8').lower()
    assert windows.index('cd /d "%oggcultist_home%"') < windows.index('-m venv .venv')
