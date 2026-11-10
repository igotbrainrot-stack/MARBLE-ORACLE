"""Regression tests for the miniature PLATE VAULT ASCII rendering.

Run: python test_ascii_visibility.py (Tk checks require an active display).
"""
from pathlib import Path
import sys
from io import BytesIO
from PIL import Image

APP = Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from oracle_media import Statue
from oracle_ascii_bitmap import render, MICRO, INKS

assert set('.,:;-=+*#%@') <= set(MICRO)
assert len(INKS) == 10
statue=Statue()
assert len(statue.plates)==14
n=0
for plate in range(len(statue.plates)):
    for frame in (0, 5, 10, 17, 24, 35):
        statue.set_fit(plate, 60, 40)
        cols, rows = statue.dims(plate)
        png = render(statue, plate, frame, 3, 6)
        with Image.open(BytesIO(png)) as im:
            assert im.size == (cols*3, rows*6), (plate, frame, im.size)
            a = im.convert('RGBA').getchannel('A')
            hist=a.histogram()
            visible = sum(hist[1:])
            assert visible >= 100, (plate, frame, visible)
            assert hist[255] == visible, 'No blurred semi-transparent strokes allowed'
        n+=1
print('ASCII BITMAP ASSET TEST PASSED:',n,'representative frames; opaque glyphs')

from marble_oracle import parse, WindowApp
app=WindowApp(vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame'])))
root=app.root
try:
    root.update()
    s=app.scene
    s.resized(app.canvas.winfo_width(),app.canvas.winfo_height())
    root.update()
    for plate in (0,1,6,13):
        s._arch_draw(plate,5)
        s._restack(force=True)
        root.update()
        canvas_ids=s.c.find_withtag('statue')
        assert len(canvas_ids)==1, (plate,len(canvas_ids))
        assert s.c.type(canvas_ids[0])=='image', (plate,s.c.type(canvas_ids[0]))
        fo,cw,ch=s._arch_fit(plate)
        cols,rows=s.statue.dims(plate)
        x0,y0,x1,y1=s.arch_box
        assert cols*cw <= (x1-x0) + 1 and rows*ch <= (y1-y0) + 1, (plate,cw,ch,cols,rows,s.arch_box)
    print('ASCII TK IMAGE TEST PASSED: real renderer, fit, and layering')
finally:
    app.quit()

# Text glyphs remain visible when the panel is narrow or very short.
from oracle_ascii_bitmap import MICRO
for cw,ch in ((1,2),(2,3),(2,4),(3,5),(3,6)):
    for glyph in MICRO:
        class One:
            step = {0:1}
            def dims(self, plate):return (1,1)
            def runs(self, plate, frame):return [(0,0,glyph,5)]
        with Image.open(BytesIO(render(One(),0,0,cw,ch))) as im:
            assert im.getchannel('A').getbbox(), (glyph,cw,ch)
print('ASCII MICRO-GLYPH RESIZE TEST PASSED')
