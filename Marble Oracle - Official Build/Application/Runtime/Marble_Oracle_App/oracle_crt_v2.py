"""MARBLE_ORACLE default Rusted CRT V2: independent working hardware layers.

The approved photo is NOT a live screen source.  Its black CRT glass is alpha-
cut so the existing MARBLE_ORACLE Canvas paints behind it.  Every instrument
is generated on clean glass (not drawn over frozen example readouts).
The old pixel screenshot/barrel compositor is deliberately excluded in V2.
"""
from __future__ import annotations
import datetime
import io
import json
import math
import time
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / 'data' / 'crt_v2'
SOURCE_W, SOURCE_H = 1448, 1086
APERTURE = (369, 223, 1077, 817)
LABELS = ('GRID', 'CAST', 'LINGUA', 'DEAL', 'PSWRD', '', '', '')
ACTIONS = ('bz1', 'bz3', 'bz5', 'bz6', 'bz10', 'bz11', 'bz12', 'bz13')

@lru_cache(maxsize=1)
def layout():
    data = json.loads((ART / 'layout.json').read_text(encoding='utf-8'))
    if data['source_canvas_px'] != [SOURCE_W, SOURCE_H]:
        raise ValueError('CRT V2 source dimensions do not match approved art')
    ms = {m['id']: m for m in data['modules']}
    assert all('button_' + s in ms for s in LABELS[:5])
    return ms


def p(scene, x, y):
    sx, sy = scene._frame_scale
    return x * sx - scene.mg[0], y * sy - scene.mg[1]


def rect(scene, bounds):
    x0,y0,x1,y1 = bounds
    a = p(scene,x0,y0)
    b = p(scene,x1,y1)
    return a + b


def as_photo(scene, im):
    from PIL import ImageTk
    pic = ImageTk.PhotoImage(im, master=scene.c)
    scene.bz_imgs.append(pic)
    return pic


def _dial_frames(src, center, k):
    """Animate the INDEX, not the photograph's fixed directional lighting.

    Older builds rotated the entire photograph of this dial, so highlights,
    shadows and glass reflections revolved with the knob. The machined metal
    and its studio lighting must remain fixed in screen coordinates. A narrow
    physical pointer now revolves independently on top of the still dial.
    """
    from PIL import Image, ImageDraw
    x, y = center
    radius = 48
    base = src.crop((x-radius,y-radius,x+radius,y+radius)).convert('RGBA')
    # Preserve original transparent outside of the photographed circular face.
    alpha = Image.new('L', base.size, 0)
    ImageDraw.Draw(alpha).ellipse((1,1,base.width-2,base.height-2), fill=255)
    base.putalpha(alpha)
    size = max(22,round(base.width*k))
    base = base.resize((size,size),Image.Resampling.LANCZOS)
    cx=cy=(size-1)/2.0
    frames=[]
    for i in range(36):
        # Angle=0 at twelve o'clock; -90 left, +90 right.
        angle=math.radians(i*10)
        dx,dy=math.sin(angle),-math.cos(angle)
        inner,outer=size*.275,size*.414
        x0,y0=cx+dx*inner,cy+dy*inner
        x1,y1=cx+dx*outer,cy+dy*outer
        face=base.copy()
        d=ImageDraw.Draw(face,'RGBA')
        width=max(1,round(size*.022))
        d.line((x0+1,y0+1,x1+1,y1+1),fill=(10,9,7,220),width=width+2)
        d.line((x0,y0,x1,y1),fill=(255,169,65,235),width=width)
        d.ellipse((x1-width/2,y1-width/2,x1+width/2,y1+width/2),fill=(255,202,111,244))
        frames.append(face)
    return frames


@lru_cache(maxsize=8)
def _clock_sprites(w, h):
    """Approved stationary photographic tube with independent cathode layers.

    All ten numeral overlays share the unmodified 128x338 native canvas and
    a single (w, h) transform. The shell and its wiring never move or breathe.
    Cached nine-stage frames modulate only the active digit alpha and glow.
    """
    from PIL import Image
    from oracle_nixie import nixie_frames
    result = {}
    for digit in '0123456789':
        result[digit] = tuple(
            Image.open(io.BytesIO(png)).convert('RGBA')
            for png in nixie_frames(digit, w, h, steps=9)
        )
    return result


@lru_cache(maxsize=12)
def _nixie_pcb_strip(width, height):
    """One stationary PCB shared by all four Nixie tubes.

    The strip connects the visible lower leads and covers their open tips.
    It is rendered over, never into, the original approved digit/shell assets.
    Source artwork is designed at the fixed CRT V2 native-pixel geometry.
    """
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (224, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Recess shadow, oxidised fiberglass substrate, worn copper perimeter.
    d.rounded_rectangle((0, 1, 223, 23), radius=3, fill=(1, 1, 1, 94))
    d.rounded_rectangle((1, 3, 222, 22), radius=2,
                        fill=(16, 25, 21, 253), outline=(119, 63, 28, 255))
    d.line((4, 5, 219, 5), fill=(163, 91, 41, 235), width=1)
    d.line((4, 20, 219, 20), fill=(64, 35, 16, 235), width=1)
    # Socket pads line up with the four native tube centres, relative to x=50.
    for cx in (36, 88, 142, 194):
        for dx in (-9, -3, 3, 9):
            x = cx + dx
            d.rectangle((x - 1, 3, x + 1, 7), fill=(126, 72, 33, 255))
            d.point((x, 4), fill=(246, 155, 70, 255))
        d.line((cx - 9, 8, cx + 9, 8), fill=(123, 63, 30, 240))
        d.line((cx, 8, cx, 13), fill=(155, 79, 32, 210))
        d.ellipse((cx - 2, 12, cx + 2, 16), fill=(12, 14, 12, 255),
                  outline=(168, 99, 46, 255))
    # Tracks connect the sockets to the populated lower PCB, not free space.
    for y in (12, 17):
        d.line((10, y, 214, y), fill=(96, 48, 23, 210), width=1)
    for x in (19, 69, 122, 174, 207):
        d.line((x, 9, x, 20), fill=(159, 78, 30, 215), width=1)
        d.ellipse((x - 1, 15, x + 1, 17), fill=(196, 116, 50, 255))
    # Static mounted components. Stagger them between, not below, tube sockets.
    for x, w in ((52, 11), (105, 16), (158, 12)):
        d.rounded_rectangle((x, 10, x + w, 18), radius=1,
                            fill=(27, 23, 20, 255), outline=(91, 67, 45, 255))
        d.line((x + 2, 11, x + w - 2, 11), fill=(75, 61, 46, 250))
    for x in (10, 77, 131, 210):
        d.rectangle((x - 2, 11, x + 2, 18), fill=(79, 35, 19, 255),
                    outline=(173, 93, 44, 255))
        d.line((x - 1, 14, x + 1, 14), fill=(218, 151, 77, 255))
    # Four dark recessed screws fix the rail to the existing instrument bay.
    for x in (7, 82, 151, 217):
        d.ellipse((x - 3, 16, x + 3, 22), fill=(8, 9, 8, 255),
                  outline=(169, 102, 53, 255))
        d.line((x - 1, 19, x + 1, 19), fill=(200, 143, 90, 255))
    return im.resize((max(1, int(width)), max(1, int(height))), Image.Resampling.LANCZOS)


def _press_frames(im):
    """Photo-aligned button press: composite ONLY the cap surface.

    Never paste the rectangular photographic crop back over screws, chipped
    lettering, or its metal frame.  The source photograph supplies the
    unpressed hardware, while each transition sprite has *transparent* outer
    margins and a feathered cap-shaped alpha.  The source crop bounds come
    from the same layout map as the hit targets and emitted lamp points.
    """
    from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
    im = im.convert('RGBA')
    w, h = im.size
    x0, y0 = max(3, round(w*.16)), max(3, round(h*.17))
    x1, y1 = min(w-3, round(w*.85)), min(h-3, round(h*.85))
    mask = Image.new('L', (w,h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((x0,y0,x1,y1),radius=max(2,round(h*.11)),fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(max(.35, min(1.1,h*.016))))
    frames=[]
    for step in range(4):
        face=ImageEnhance.Brightness(im).enhance(1-.115*step)
        # Deepen the cap well rather than scaling or re-drawing its frame.
        if step:
            slight=Image.new('RGBA', (w,h), (0,0,0,0))
            dark=Image.new('RGBA', (w,h), (0,0,0,min(85,17*step)))
            dark.putalpha(mask.point(lambda a, strength=step: (a*strength*13)//255))
            face=Image.alpha_composite(face,dark)
        out=face.copy()
        out.putalpha(mask)
        frames.append(out)
    return frames


def install(scene):
    """Paint the one-piece V2 metal frame, then fresh hardware within calibrated bays."""
    from PIL import Image
    from oracle_nixie import NixieState
    c=scene.c
    W=scene.mg[0]+scene.W+scene.mg[2]
    H=scene.mg[1]+scene.H+scene.mg[3]
    sx,sy=W/SOURCE_W,H/SOURCE_H
    if abs(sx-sy)>.002:
        raise ValueError('CRT V2 frame must have uniform scaling')
    scene._frame_scale=(sx,sy)
    original=Image.open(ART/'frame.png').convert('RGBA')
    rendered=original.resize((W,H),Image.Resampling.LANCZOS) if (W,H)!=original.size else original
    frame=as_photo(scene,rendered)
    c.create_image(-scene.mg[0],-scene.mg[1],anchor='nw',image=frame,tags='bezel')
    scene._frame_im=rendered   # retained for new key-cap crops
    scene.bz_btns=[];scene.bz_dials=[];scene.dial_hot=[]
    animation={'start':time.time(),'time':None,'clock':[], 'sheets':{},'wave':[],
               'last_wave':0.,'last_metrics':0.,'lamps':[],'meter':{},'readouts':{},
               'power':None,'last_power':0.,'dial_last':-1, 'wave_previous':[0.0]*48}
    module=layout()
    # Approved fixed-shell photographic sprites; only cathode overlays animate.
    clock=NixieState()
    animation['nixie']=clock
    # Size the generated glass to the calibrated native rectangles, not the
    # former tall and thin 39x106 raster. This prevents an aspect mismatch
    # between the current artwork and the live clock sprites.
    native_sizes = [(module['nixie_tube_%d' % i]['rect_px'][2] - module['nixie_tube_%d' % i]['rect_px'][0],
                     module['nixie_tube_%d' % i]['rect_px'][3] - module['nixie_tube_%d' % i]['rect_px'][1])
                    for i in range(4)]
    if len(set(native_sizes)) != 1:
        raise ValueError('CRT V2 nixie tubes must have identical dimensions')
    tw, th = (max(18, round(native_sizes[0][0] * sx)),
              max(30, round(native_sizes[0][1] * sy)))
    bank={digit:tuple(as_photo(scene,im) for im in pair)
          for digit,pair in _clock_sprites(tw,th).items()}
    animation['sheets']=bank
    for i in range(4):
        r=module['nixie_tube_%d'%i]['rect_px']
        x,y=p(scene,(r[0]+r[2])/2,(r[1]+r[3])/2)
        item=c.create_image(x,y,image=bank['0'][5],anchor='center',tags='bezel')
        animation['clock'].append(dict(item=item,ch=None,index=-1, old=None,changed_at=-1000.))
    # A single shared, completely static circuit board hides open lead ends.
    # Start over the lower 4px of each tube, leaving a short visible wire run.
    # The PCB is painted AFTER the tubes so changed digits never move its
    # socket pads, traces, screws, or the fixed glass/cathode shell.
    board_bounds = (50, 277, 274, 301)
    bx0, by0, bx1, by1 = board_bounds
    pcb = _nixie_pcb_strip(round((bx1-bx0)*sx), round((by1-by0)*sy))
    pcb_photo = as_photo(scene, pcb)
    c.create_image(*p(scene, bx0, by0), image=pcb_photo, anchor='nw', tags='bezel')
    # Audio scope phosphor: three independently faded Canvas traces; no static waveform underneath.
    a=module['audio_waveform']['rect_px']
    for color,width in (('#15462b',4.0),('#208f49',2.4),('#80ffc0',1.1)):
        pts=rect(scene,(a[0]+8,(a[1]+a[3])//2,a[2]-8,(a[1]+a[3])//2))
        line=c.create_line(*pts,fill=color,width=max(1,round(width*sx)),
                           smooth=True,splinesteps=12,tags='bezel')
        animation['wave'].append(line)
    # One telemetry panel and two vertically climbing usage bars, never horizontal progress bars.
    def text(x,y,msg,color,size=15,weight='bold'):
        return c.create_text(*p(scene,x,y),text=msg,fill=color,
               font=('Uberata Clear',max(7,round(size*sx)),weight),anchor='center',tags='bezel')
    for kind,cx,cy in [('cpu',1276,223),('gpu',1276,341)]:
        base=cy
        text(cx,base-30,kind.upper(),'#58ff9e',17)
        animation['readouts'][kind+'_temp']=text(cx,base,'--', '#adffbf',23)
        text(cx,base+22,'USAGE','#51ca79',12)
        animation['readouts'][kind+'_pct']=text(cx,base+44,'--','#9effa9',18)
    for name in ('cpu','gpu'):
        # CPU track alignment corrected in layout.json (+7px in source art).
        # Both bar geometry and the drawing now derive from one live map.
        b=module[name+'_vertical_meter']['rect_px']
        segments=[]
        for i in range(18):
            yy=b[3]-9-i*12.1
            x0,y0,x1,y1=rect(scene,(b[0]+5,yy,b[2]-4,yy+8))
            item=c.create_rectangle(x0,y0,x1,y1,fill='#0c241b',outline='',tags='bezel')
            segments.append(item)
        animation['meter'][name]=segments
    # Off→on volume levels, lightly glowing glass and real dial motion.
    for idx,(x,y) in enumerate(module['volume_lamps']['centers_px']):
        x0,y0,x1,y1=rect(scene,(x-10,y-6,x+10,y+6))
        lid=c.create_rectangle(x0,y0,x1,y1,fill='#221808',outline='#553d16',width=1,tags='bezel')
        animation['lamps'].append(lid)
    v=getattr(scene.voice,'vol',0.8)
    v=max(0,min(1,float(v)))
    angle=-90+v*180
    dial_center=module['volume_knob']['center_px']
    frames=[as_photo(scene,im) for im in _dial_frames(original,dial_center,sx)]
    cx,cy=p(scene,*dial_center)
    idx=int(round(angle/10))%len(frames)
    knob=c.create_image(cx,cy,image=frames[idx],anchor='center',tags='bezel')
    radius=55*sx
    scene.dial_hot.append((cx-radius,cy-radius,cx+radius,cy+radius,'dial:vol'))
    scene.bz_dials.append(dict(name='dial:vol',item=knob,frames=frames,cx=cx,cy=cy,
                                 angle=angle,target=angle,fi=idx))
    # Five functional keys, three intentionally unassigned / blank keys.
    for number,(label,action) in enumerate(zip(LABELS,ACTIONS)):
        key='button_'+(label if label else 'BLANK_%d'%(number-4))
        bounds=module[key]['rect_px']
        x0,y0,x1,y1=rect(scene,bounds)
        # Two distinct surfaces: a generously tappable row and the *actual*
        # photographic actuator.  The former never becomes an animation sprite.
        bx0,by0,bx1,by1=module[key]['actuator_bounds_px']
        src_crop=original.crop((bx0,by0,bx1,by1)).convert('RGBA')
        patch=src_crop.resize((max(8,round((bx1-bx0)*sx)),max(8,round((by1-by0)*sy))),Image.Resampling.LANCZOS)
        sprites=[as_photo(scene,im) for im in _press_frames(patch)]
        px,py=p(scene,bx0,by0)
        item=c.create_image(px,py,image=sprites[0],anchor='nw',state='hidden',tags='bezel')
        scene.bz_btns.append(dict(name=action,down=False,until=0,release=False,fi=-1,
                      photo_overlay=item,frames=sprites,art=(sprites[0],sprites[-1]),
                      actuator_center=tuple(module[key]['actuator_center_px'])))
        scene.hot.append((x0,y0,x1,y1,action))
        # The small lens highlight is centered on the *measured switch*, not
        # x1-30 of a guessed full-row rectangle.  No square black backplate.
        ax,ay=p(scene,*module[key]['actuator_center_px'])
        rr=2.0*sx
        key_lamp=c.create_oval(ax-rr,ay-rr,ax+rr,ay+rr,
                    fill=('#fbc03e' if label else '#50371d'),outline='',tags='bezel')
        animation.setdefault('key_lamps',[]).append((key_lamp,action,bool(label)))
    # Restore the hardware window keys missing from the V2 redesign.
    # Their two compact, photographed caps are immediately LEFT of POWER;
    # the same exact layout rectangles drive both click targets and animation.
    for name, action in (('window_minimize', 'bz7'), ('window_fullscreen', 'bz8')):
        bounds = module[name]['rect_px']
        x0,y0,x1,y1 = bounds
        crop = original.crop(bounds).convert('RGBA')
        crop = crop.resize((max(12,round((x1-x0)*sx)),
                            max(12,round((y1-y0)*sy))), Image.Resampling.LANCZOS)
        sprites = [as_photo(scene, im) for im in _press_frames(crop)]
        px,py = p(scene,x0,y0)
        item = c.create_image(px,py,image=sprites[0],anchor='nw',
                              state='hidden',tags='bezel')
        scene.bz_btns.append(dict(name=action,down=False,until=0,release=False,
                              fi=-1,photo_overlay=item,frames=sprites,
                              art=(sprites[0],sprites[-1])))
        scene.hot.append((*rect(scene,bounds),action))
    # Power is a real separate photograph-based cap. Never paint a flat red
    # oval over the illuminated rocker. Mouse press animates for 220ms, then
    # closes only this application (not Windows).
    power=module['power_switch']['rect_px']
    px0,py0,px1,py1=power
    power_crop=original.crop((px0,py0,px1,py1))
    power_patch=power_crop.resize((max(8,round((px1-px0)*sx)),
                                   max(8,round((py1-py0)*sy))),Image.Resampling.LANCZOS)
    power_frames=[as_photo(scene,im) for im in _press_frames(power_patch)]
    pcx,pcy=p(scene,px0,py0)
    power_item=c.create_image(pcx,pcy,image=power_frames[0],anchor='nw',
                              state='hidden',tags='bezel')
    scene.bz_btns.append(dict(name='bz9',down=False,until=0,release=False,
                              fi=-1,photo_overlay=power_item,frames=power_frames,
                              art=(power_frames[0],power_frames[-1])))
    scene.hot.append((*rect(scene,power),'bz9'))
    animation['power']=power_item
    scene.photo_animate={'v2':animation}
    scene.crt_v2_animation=animation
    scene._frame_im=None
    return True


def tick(scene, now):
    """New independent instrument lifecycles; no old glass effects or fake sound."""
    a=getattr(scene,'crt_v2_animation',None)
    if not a:return
    c=scene.c
    from oracle_nixie import local_hhmm
    current=datetime.datetime.now()
    digits=local_hhmm(current)
    # Cathodes extinguish/re-ignite only when a digit changes. Otherwise the
    # glass stays still and its neon breathes softly instead of hard flickering.
    for i,ch in enumerate(digits):
        tube=a['clock'][i]
        if tube['ch'] != ch:
            tube['old'],tube['ch'],tube['changed_at'] = tube['ch'],ch,now
        age=max(0.0,now-tube['changed_at'])
        if age < 0.060 and tube['old'] is not None:
            show=tube['old']
            idx=max(0,round(6*(1.0-age/.060)))
        elif age < 0.180:
            show=ch
            idx=max(1,min(8,round(2 + 6*(age-.060)/.120)))
        else:
            show=ch
            idx=max(4,min(8,round(6.6+1.05*math.sin(now*.85+i*.43))))
        if (show,idx) != tube.get('last_shown'):
            c.itemconfigure(tube['item'], image=a['sheets'][show][idx])
            tube['last_shown']=(show,idx)
    if now-a['last_wave']>.065:
        a['last_wave']=now
        capture=getattr(getattr(scene,'host',None),'system_audio',None)
        samples,bands,status=(capture.snapshot() if capture else ((0.0,)*48,(0.0,)*20,'OFF'))
        # Real captured data ONLY: no oscillation when silent or disconnected.
        r=layout()['audio_waveform']['rect_px']
        xs=[r[0]+10+(r[2]-r[0]-20)*i/47.0 for i in range(48)]
        amp=(r[3]-r[1])*.43
        vals=[float(z) for z in samples[:48]] if status=='LIVE' else [0.0]*48
        previous=a['wave_previous']
        # Fast attack, moderate release for phosphor persistence; no synthetic
        # movement is introduced when speaker capture is OFF or silent.
        vals=[prev*.32+v*.68 if abs(v)>abs(prev) else prev*.58+v*.42
              for prev,v in zip(previous, vals)]
        a['wave_previous']=vals
        for i,line in enumerate(a['wave']):
            gain=(.85,1.0,1.0)[i]
            pts=[]
            for x,v in zip(xs,vals):pts.extend(p(scene,x,(r[1]+r[3])/2-v*amp*gain))
            c.coords(line,*pts)
    if now-a['last_metrics']>.9:
        a['last_metrics']=now
        try:
            from oracle_sysmetrics import cpu_percent,cpu_temp_c,gpu_temp_c,gpu_util
            metrics=dict(cpu=cpu_percent(),gpu=gpu_util(),cpu_t=cpu_temp_c(),gpu_t=gpu_temp_c())
        except Exception:metrics=dict(cpu=None,gpu=None,cpu_t=None,gpu_t=None)
        for kind in ('cpu','gpu'):
            value=metrics[kind]
            label='--' if value is None else '%d%%'%round(max(0,min(1,value))*100)
            temp=metrics[kind+'_t']
            display='--' if temp is None else '%d°C'%round(temp)
            c.itemconfigure(a['readouts'][kind+'_temp'],text=display)
            c.itemconfigure(a['readouts'][kind+'_pct'],text=label)
            for i,seg in enumerate(a['meter'][kind]):
                level=0 if value is None else max(0,min(18,round(value*18)))
                on=i<level
                color=('#26e7bd' if i<9 else '#baf345' if i<14 else '#ff7943') if on else '#0c241b'
                c.itemconfigure(seg,fill=color)
    volume=max(0,min(1,float(getattr(getattr(scene,'voice',None),'vol',0.8))))
    active=min(len(a['lamps']),round(volume*len(a['lamps'])))
    # Lamp centres are stored TOP to BOTTOM. Illuminate from the bottom UP.
    for i,item in enumerate(a['lamps']):
        lit = i >= len(a['lamps']) - active
        c.itemconfigure(item,fill='#ffbe31' if lit else '#221808',
                            outline='#ffc66a' if lit else '#553d16')
    for item,act,labeled in a['key_lamps']:
        state=next((b['down'] for b in scene.bz_btns if b['name']==act),False)
        selected = getattr(scene, '_v2_selected_button', None) == act
        c.itemconfigure(item,fill=('#fff0a0' if state else '#ffd06c' if selected else '#fbc03e') if labeled
                        else ('#ad7334' if state else '#50371d'))


def tick_dial(scene):
    """Use original tested knob drag/detent state machine, but new V2 artwork and lamps."""
    from oracle_photo_bezel import vol_angle
    voice=getattr(scene,'voice',None)
    for dial in scene.bz_dials:
        if dial['name']=='dial:vol' and getattr(scene,'dragging',None)!='dial:vol' and voice:
            dial['target']=vol_angle(float(voice.vol))
        delta=dial['target']-dial['angle']
        dial['angle']=dial['target'] if abs(delta)<0.35 else dial['angle']+max(-10,min(10,delta))
        idx=round(dial['angle']/10)%len(dial['frames'])
        if idx!=dial['fi']:
            scene.c.itemconfigure(dial['item'],image=dial['frames'][idx]);dial['fi']=idx
