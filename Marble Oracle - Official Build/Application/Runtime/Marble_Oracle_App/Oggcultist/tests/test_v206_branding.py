"""v2.0.6 approved triple-G/O art integration smoke checks."""
from pathlib import Path
import io
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'oggcultist' / 'resources'
ART = ROOT / 'branding' / 'original-identity'


def test_approved_brand_assets_present_and_legible():
    assert (ART / 'ORIGINAL-USER-APPROVED-REFERENCE.png').is_file()
    for filename in ('symbol.svg', 'wordmark-outlined.svg', 'horizontal-lockup.svg'):
        data = (ART / filename).read_text(encoding='utf-8')
        assert '<svg' in data and '<path' in data
    for filename in ('brand_symbol.png', 'brand_wordmark.png'):
        with Image.open(RES / filename) as im:
            assert im.mode == 'RGBA'
            assert im.getbbox() is not None
            assert im.getbbox()[0] >= 0
    with Image.open(RES / 'brand_symbol.png') as im:
        assert im.width >= 400 and im.height >= 400
    with Image.open(RES / 'brand_wordmark.png') as im:
        assert im.width > im.height * 3


def test_icon_contains_individual_windows_sizes():
    with Image.open(RES / 'icon.ico') as image:
        assert set(image.info['sizes']) >= {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)}
    for n in (16, 32, 48):
        with Image.open(RES / f'icon-{n}.png') as im:
            assert im.size == (n, n)
    with Image.open(RES / 'icon.png') as image:
        assert image.size == (256, 256)


def test_active_brand_controller_uses_approved_images():
    from oggcultist.gui import brand
    assert brand.SYMBOL == 'brand_symbol.png'
    assert brand.WORDMARK == 'brand_wordmark.png'
    image = brand.compose_lockup(64, 35, 12)
    assert image.mode == 'RGBA'
    assert image.width > image.height * 2
    assert image.getbbox() is not None


def test_packaging_explicitly_preserves_approved_assets():
    release = (ROOT / 'packaging/source_release.py').read_text()
    for name in ('brand_symbol.png', 'brand_wordmark.png', 'icon.ico'):
        assert name in release
    spec = (ROOT / 'packaging/oggcultist.spec').read_text()
    assert "'icon.ico'" in spec
    assert (ROOT.parent / 'INSTALL_LINUX_MINT_MENU.sh').read_text().find('resources/icon.png') >= 0
