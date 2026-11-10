"""Rebuild the exact Oggcultist 2.0.6 texture PNG assets for Marble Oracle.

Run from any folder: python Application/Tools/export_actual_oggcultist_textures.py
Requires Pillow only while REGENERATING the files. Normal launch uses native Tk.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util
import hashlib
import json

BASE = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
SOURCE = BASE / 'Oggcultist' / 'oggcultist' / 'gui' / 'textures.py'
OUT = BASE / 'data' / 'oggcultist_texture'

SURFACES = {
    'page': ('#1D1714', 0.20, 0),
    'card': ('#261F1B', 0.18, 1),
    'side': ('#130F0D', 0.22, 2),
    'sunken': ('#16110F', 0.20, 3),
    'sunken_alt': ('#1A1512', 0.18, 4),
    'control': ('#2F2620', 0.18, 5),
    'accent_soft': ('#4A2C18', 0.20, 6),
}


def main():
    if not SOURCE.is_file():
        raise SystemExit('Oggcultist 2.0.6 textures.py is missing')
    spec = importlib.util.spec_from_file_location('actual_oggcultist_texture_source', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        'source': 'Oggcultist 2.0.6 / oggcultist/gui/textures.py',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'method': 'source module grain(base, (256,256), amount, seed, mottle=True) without any recreated texture algorithm',
        'tiles': {},
    }
    for role, (colour, amount, seed) in SURFACES.items():
        output = OUT / (role + '.png')
        module.grain(colour, (256,256), amount=amount, seed=seed, mottle=True).save(output, 'PNG', optimize=True)
        manifest['tiles'][role] = {
            'color': colour, 'amount': amount, 'seed': seed,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        }
        print('Exported', output.name)
    (OUT / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
