"""Regression for using actual Oggcultist 2.0.6 grain tiles everywhere.

This test lives with application sources, but is invoked under a virtual Tk display.
"""
from pathlib import Path
import sys, json, hashlib, importlib.util
from PIL import Image
from tkinter import ttk
HERE=Path(__file__).resolve().parent
APP=HERE.parent/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_ogg_texture import FILES, png_bytes
from oracle_skin import warm_grain, SkinMixin
from marble_oracle import WindowApp, parse

def source_tiles():
    manifest=json.loads((APP/'data/oggcultist_texture/SOURCE_MANIFEST.json').read_text())
    src=APP/'Oggcultist/oggcultist/gui/textures.py'
    assert hashlib.sha256(src.read_bytes()).hexdigest()==manifest['source_sha256']
    spec=importlib.util.spec_from_file_location('actual_ogg_source_tex', src)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    for role,metadata in manifest['tiles'].items():
        p=FILES[role]
        assert p.is_file(),p
        assert hashlib.sha256(p.read_bytes()).hexdigest()==metadata['sha256'],role
        image=Image.open(p).convert('RGB')
        expected=mod.grain(metadata['color'], (256,256), amount=metadata['amount'], seed=metadata['seed'],mottle=True)
        assert image.tobytes()==expected.tobytes(),role
    assert warm_grain('#261F1B') == png_bytes('card')
    assert warm_grain('#1D1714') == png_bytes('page')
    print('Actual Oggcultist grain and mottle PNGs: pixel-identical to source function')

def gui():
    opts=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
    opts['bezel']=False
    app=WindowApp(opts)
    root=app.root
    try:
        root.update();app.scene.resized(1216,848);root.update()
        class T(SkinMixin):pass
        s=T();s.c=app.canvas
        for role in ('page','card','side'):
            big=s.tiled(png_bytes(role),550,450)
            img=Image.open(FILES[role]).convert('RGB')
            for x,y in ((1,2),(200,250),(275,260),(540,440)):
                assert big.get(x,y)==img.getpixel((x%256,y%256)),(role,x,y)
        style=ttk.Style(root)
        for action in ('tab_passphrase','tab_touch_type','tab_oggcultist','tab_touch_type','tab_passphrase'):
            app.scene.act(action);root.update()
            assert app.scene._which_overlay() is not None
            if action!='tab_oggcultist':
                for role in ('page','card','side','sunken','sunken_alt'):
                    name=f'Marble.Ogg.Grain.{role}'
                    frame_layout=str(style.layout(f'MarbleOgg.{role}.TFrame'))
                    label_layout=str(style.layout(f'MarbleOgg.{role}.TLabel'))
                    assert name in frame_layout,(action,role,frame_layout)
                    assert name in label_layout,(action,role,label_layout)
        print('Tiled pixels and all tab theme-switch image layouts: PASS')
    finally:app.quit()

if __name__=='__main__':
    source_tiles();gui()
