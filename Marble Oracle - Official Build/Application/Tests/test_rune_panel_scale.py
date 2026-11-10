"""Rune stones should fill their three columns, stay click-safe, and never crop.

Run: xvfb-run -a python3 Application/Tests/test_rune_panel_scale.py
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp
from oracle_runes import RuneDeck
from PIL import Image
from zipfile import ZipFile
from io import BytesIO

opts=dict(theme='EMBER',layout='CLASSIC',fps=30,crt=False,no_dicekey=False,
          no_markets=True,no_network=True,bezel=False,osframe=True,
          retro=False,flat=False,look=None,crt_v2=False,no_pixel_barrel=True,
          no_audio_scope=True,selftest=True,wire=None)
app=WindowApp(opts)
checks=0
try:
 root,s=app.root,app.scene
 for width,height,min_img in ((1216,848,112),(900,620,80),(760,550,64),(640,460,56)):
  root.geometry(f'{width}x{height}+16+16')
  root.update();s.resized(s.c.winfo_width(),s.c.winfo_height());root.update()
  s.divination_mode='runes'
  s.rune_drawn=[s.rune_deck.runes[i] for i in (4,9,10)]
  s.rune_revealed=3;s.rune_state='complete';s.rune_anim_index=-1;s.rune_sel=1
  s.draw_cards();root.update()
  x0,y0,x1,y1=s.rect['cards']
  reading_top=y1-max(75,int((y1-y0)*.30))+4
  boxes=[]
  for i,w in enumerate(s.rune_widgets):
   l,t,r,b=w.rune_bounds;box=w.rune_safe_box
   assert w.image.width() >= min_img,(width,height,i,'stone not expanded',w.image.width())
   assert box[0] <= l < r <= box[2] and box[1] <= t < b <= box[3]
   assert b < reading_top - 16,(width,height,'rune artwork touches the reading pane',b,reading_top)
   boxes.append((l,t,r,b))
   assert s.hit((l+r)//2,(t+b)//2)[4]==f'rune_select{i}'
   checks+=1
  for i in (0,1):
   assert boxes[i][2] < boxes[i+1][0],(width,height,'overlapping stone slots')
  if width<=900:
   # Keywords are intentionally suppressed on smaller layouts, leaving
   # readable labels rather than crowded text columns.
   text=[s.c.itemcget(item,'text') for item in s.c.find_withtag('cards')
         if s.c.type(item)=='text']
   assert not any('journey, rhythm' in val for val in text), (width,height,'crowded keywords')
 # The engraved rock fills 80%+ of the native sprite, rather than the old
 # ~65%; alpha still has a complete transparent band for safe positioning.
 with ZipFile(s.rune_deck.consistent_zip_path) as z:
  im=Image.open(BytesIO(z.read('120/blank.png'))).convert('RGBA')
  bb=im.getchannel('A').getbbox()
  assert bb is not None and .82 <= (bb[2]-bb[0])/120 <= .95,bb
  assert 0 < bb[0] and bb[2]<120 and bb[1]>0 and bb[3]<120,bb
 print('RUNE PANEL SCALE OK:',checks,'actual stone/click areas at four window sizes; large and safe visuals')
finally:
 app.quit()
