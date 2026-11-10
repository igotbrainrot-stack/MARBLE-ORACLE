"""Non-destructive maintenance checks. Run: python3 test_refinement.py"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent / 'Runtime'
APP = ROOT / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

with tempfile.TemporaryDirectory(prefix='marble-refinement-') as folder:
    os.environ['MARBLE_ORACLE_STATE'] = folder
    from oracle_assets import save_json, load_json
    assert load_json('preferences-test.json', {}) == {}
    save_json('preferences-test.json', {'window': [1024, 720], 'mode': 'runes'})
    assert load_json('preferences-test.json', {})['mode'] == 'runes'
    # In concurrent writes, the final result must still be complete JSON.
    def save(i):
        save_json('preferences-test.json', {'index': i, 'payload': 'x' * 5000})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(32)))
    result = json.loads((Path(folder) / 'preferences-test.json').read_text())
    assert len(result['payload']) == 5000 and 0 <= result['index'] < 32
    assert not list(Path(folder).glob('*.tmp'))
    assert not list(Path(folder).glob('.*.tmp'))

from oracle_runes import RuneDeck
runes = RuneDeck()
assert len(runes.runes) == 24
assert len(runes._flip_names) == 24
with zipfile.ZipFile(runes.flip_zip_path) as z:
    assert z.testzip() is None
    assert all(path in z.namelist() for path in runes._flip_names.values())
with zipfile.ZipFile(runes.zip_path) as z:
    assert z.testzip() is None
    for rune in runes.runes:
        assert rune['imageFront'] in z.namelist()
        assert rune['imageBack'] in z.namelist()
assert (APP/'fonts'/'Uberata-Clear.ttf').is_file()
assert (APP/'data'/'tarot_cards.zip').is_file()
assert (APP/'marble_passphrase_tab.py').is_file()
print('REFINEMENT TESTS OK: atomic settings, 24 rune archives, tarot/passphrase/font assets')
