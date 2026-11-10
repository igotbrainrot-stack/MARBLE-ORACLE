#!/usr/bin/env python3
"""Build stable, matched Elder Futhark flip sprites from one carved stone.

The original 24-rune source art and master are kept; this creates separate game
sprites and never modifies source PNGs. Uses Pillow/NumPy/OpenCV at build time.
Runtime needs only Python/Tk, not PIL or OpenCV.
"""
import io, os, json, zipfile, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops, ImageEnhance

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/'Runtime/Marble_Oracle_App'
OUT=ROOT/'data'/'rune_consistent_flips.zip'
FONT=os.environ.get('RUNE_BUILD_FONT') or subprocess.check_output(['fc-match','-f','%{file}','Noto Sans Runic'], text=True).strip()
# Exact glyph mapping as the app defines it (do not reinterpret from visual sheet indices).
import sys
sys.path.insert(0,str(ROOT))
from oracle_runes import RUNES

# The supplied high-resolution animation source already includes a 192px
# naturally textured, inscription-free rock. Unlike runes.zip 01-blank.png,
# it is the SAME carved rock silhouette as the revealed series. It has
# no engraving to inpaint, so there are no ghost runes on the back.
with zipfile.ZipFile(ROOT/'data'/'rune_flip_strips.zip') as source_archive:
    from_strip=Image.open(io.BytesIO(source_archive.read('strips/01_fehu_flip_8f.png'))).convert('RGBA')
    blank_rock=from_strip.crop((0,0,192,192))
blank_rock=blank_rock.crop(blank_rock.getbbox())
# The old thumbnail() call did not upscale a 171px source rock, leaving it
# occupying only ~66% of the sprite. Deliberately resize to a consistent
# 228px longest edge: 89% visible rock, with transparent edge clearance.
scale=228/max(blank_rock.size)
blank_rock=blank_rock.resize((round(blank_rock.width*scale),
                              round(blank_rock.height*scale)), Image.Resampling.LANCZOS)
base=Image.new('RGBA',(256,256),(0,0,0,0))
base.alpha_composite(blank_rock,((256-blank_rock.width)//2,(256-blank_rock.height)//2))
base.save(HERE/'new_rune_blank_256.png')

# Use identical texture and silhouette for each rune; engrave into the rock surface.
font=ImageFont.truetype(FONT,153)
runes={}
for r in RUNES:
 glyph=r['glyph']; ms=Image.new('L',(256,256),0); dr=ImageDraw.Draw(ms)
 bb=dr.textbbox((0,0),glyph,font=font,stroke_width=0)
 # Long/thin runes keep enough carved presence; fit max 102 x 130.
 target_w=min(104,256)
 xspan=bb[2]-bb[0];yspan=bb[3]-bb[1]
 glyph_block=Image.new('L',(max(1,xspan),max(1,yspan)),0)
 ImageDraw.Draw(glyph_block).text((-bb[0],-bb[1]),glyph,font=font,fill=255)
 glyph_block.thumbnail((106,127),Image.Resampling.LANCZOS)
 # Boost narrow strokes on modern screen sizes.
 if glyph_block.width<34:
  glyph_block=glyph_block.filter(ImageFilter.MaxFilter(3))
 ms.paste(glyph_block,((256-glyph_block.width)//2,(256-glyph_block.height)//2+2))
 # Stone alpha ensures engraving only inside stone
 stone_a=base.getchannel('A');ms=ImageChops.multiply(ms,stone_a)
 # Offset highlights produce a shallow chiseled inset, not a flat printed glyph.
 rim=ImageChops.subtract(ImageChops.offset(ms,-2,-2),ms).point(lambda v:min(255,int(v*.7)))
 dark_edge=ImageChops.subtract(ImageChops.offset(ms,2,2),ms).point(lambda v:min(255,int(v*.9)))
 front=base.copy()
 front.alpha_composite(Image.new('RGBA',front.size,(247,209,144,0)))
 front.paste((239,184,104,255),(0,0,256,256),rim)
 front.paste((41,23,16,255),(0,0,256,256),dark_edge)
 # Compose dark, wood-brown carved valley with subtle texture from stone.
 raw=Image.new('RGBA',front.size,(68,33,22,255))
 front.paste(raw,(0,0),ms)
 front.putalpha(stone_a)
 runes[r['name'].lower()]=front

# Reassuringly obvious turn: back rotates to edge, rune becomes visible
# only after crossing the 90-degree midline.
WIDTHS=[1.0,.96,.85,.64,.35,.10,.10,.35,.64,.85,.96,1.0]
NATIVE_SIZES=(24,32,40,48,56,64,72,80,88,96,104,112,120,128,144,160,176,192)
DURATION=100

def rotated(src,index):
    factor=WIDTHS[index]
    im=src.copy()
    # The stone darkens when edge-on and catches warm light toward the face.
    im=ImageEnhance.Brightness(im).enhance(0.68+0.32*factor)
    full=Image.new('RGBA',im.size,(0,0,0,0))
    slice_width=max(1,round(im.width*factor))
    im=im.resize((slice_width,im.height),Image.Resampling.LANCZOS)
    full.alpha_composite(im,((full.width-im.width)//2,0))
    return full

def _png_bytes(sprite):
    # LANCZOS can leave alpha=1..4 ringing on the outermost pixel at 24px.
    # These are invisible but violate the promised transparent safety band.
    alpha=sprite.getchannel('A').point(lambda a: a if a >= 8 else 0)
    sprite.putalpha(alpha)
    buf=io.BytesIO()
    sprite.save(buf,format='PNG',optimize=True)
    return buf.getvalue()

out=OUT
manifest={'version':2,'asset_source':'single carved-stone master and programmatic engraving; never mix stone back assets with face strips',
          'rune_count':24,'frame_count_per_rune':len(WIDTHS),'recommended_frame_duration_ms':DURATION,
          'sizes':list(NATIVE_SIZES),'reveal_starts_at_frame':6,
          'runes':[{'name':r['name'],'glyph':r['glyph']} for r in RUNES]}
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('manifest.json',json.dumps(manifest,indent=2))
 # Every sprite frame preserves 4%-6% transparent edge clearance while
 # filling most of its allocated panel cell; never crop a rock silhouette.
 for size in NATIVE_SIZES:
  im=base.resize((size,size),Image.Resampling.LANCZOS)
  z.writestr(f'{size}/blank.png',_png_bytes(im))
 for r in RUNES:
  k=r['name'].lower()
  for index in range(12):
   original = base if index<=5 else runes[k]
   rotated_img=rotated(original,index)
   for size in NATIVE_SIZES:
    im=rotated_img.resize((size,size),Image.Resampling.LANCZOS)
    z.writestr(f'{size}/{k}/{index:02}.png',_png_bytes(im))

# Preview animation and an asset contact sheet at actual game size.
fehu=runes['fehu']
previewframes=[]
for i in range(12):
  k=rotated(base if i<=5 else fehu,i).resize((116,116),Image.Resampling.LANCZOS)
  previewframes.append(k)
for i in range(3):previewframes += [previewframes[-1]]
previewframes[0].save(HERE/'Rune-Flip-Preview.gif',format='GIF',save_all=True,append_images=previewframes[1:],duration=110,loop=0,disposal=2,transparency=0)
W,H=4*184,6*180
sheet=Image.new('RGB',(W,H),'#201713');D=ImageDraw.Draw(sheet)
label=ImageFont.load_default(size=15)
for i,r in enumerate(RUNES):
 x=(i%4)*184;y=(i//4)*180
 im=runes[r['name'].lower()].resize((135,135),Image.Resampling.LANCZOS)
 sheet.paste(im,(x+24,y+6),im)
 D.text((x+12,y+141),r['name'],font=label,fill='#dfb18a')
sheet.save(HERE/'Rune-24-New-Stones.png')
print('NEW ASSETS',out,out.stat().st_size, '\nBLANK',HERE/'new_rune_blank_256.png')
