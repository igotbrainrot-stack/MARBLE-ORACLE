"""Modern sliders (v1.9.0): a rounded, bevelled track filled with the drifting gradient up to a
round, anti-aliased thumb, plus the same look as a progress bar.

ttk's Scale can't fill the track up to the thumb, draw a round thumb or animate, so these are
small Canvas widgets. Each draw renders one Pillow image at ``SUPER``× size and scales it down,
so the curves are smooth on every platform; the background is the same film grain as the panel
behind, so the widget blends in.

:class:`GradientSlider` keeps the parts of the ttk.Scale interface Oggcultist uses
(``get``/``set``, ``cget``/``configure`` for ``from``/``to``, ``state``/``instate``, a
``variable``) and adds:

- click anywhere to jump there, and drag (``on_press`` / ``on_drag`` / ``on_release``);
- hover: the track thickens and the thumb grows, animated like the buttons;
- the arrow keys, Home/End and the mouse wheel;
- the filled part follows the gradient drift (``animation.GradientAnimator.on_frame``).

:class:`GradientBar` is the matching determinate progress bar (``bar['value'] = 40``).
"""
from __future__ import annotations

import tkinter as tk
from functools import lru_cache
from typing import Callable

SUPER = 4
TRACK = '#120E0C'           # the groove
TRACK_EDGE = '#3A2E27'
THUMB = '#FFF1DA'
THUMB_EDGE = '#000000'
DISABLED_FILL = ('#5E4A39', '#4C3426')
GROW_STEPS = 3
GROW_STEP_MS = 30
KEY_STEPS = 50              # the arrow keys move 1/50 of the range


def _scale_of(widget) -> float:
    try:
        return max(1.0, float(widget.winfo_fpixels('1i')) / 96.0)
    except tk.TclError:
        return 1.0


def render(width: int, height: int, fraction: float, *, behind: str, grain_amount: float,
           stops: tuple[str, ...], shift: float | None, track: float, thumb: float | None,
           disabled: bool = False, focus: bool = False, glow: float = 0.0, pad: float | None = None):
    """The whole widget as one RGB Pillow image.

    ``track`` is the groove thickness and ``thumb`` the thumb radius, in pixels (None: no thumb,
    as for the progress bar); ``glow`` (0..1) draws the hover halo around the thumb; ``pad`` is
    the space kept at each end (default: room for the thumb).
    """
    from PIL import Image, ImageDraw
    from . import textures
    w, h, k = max(2, width), max(2, height), SUPER
    out = _background(behind, w, h, grain_amount).copy()
    draw = ImageDraw.Draw(out)
    if pad is None:
        pad = (thumb + 2) if thumb else 1.0
    cy = h / 2
    x0, x1 = pad, w - pad
    half = track / 2
    box = [x0 * k, (cy - half) * k, x1 * k, (cy + half) * k]
    radius = min(2.5, half) * k
    # the groove: dark, with a 1 px rim, and sunken (shade above, a faint light line below)
    draw.rounded_rectangle(box, radius=radius, fill=textures._rgb(TRACK_EDGE))
    inner = [box[0] + k, box[1] + k, box[2] - k, box[3] - k]
    if inner[2] > inner[0] and inner[3] > inner[1]:
        draw.rounded_rectangle(inner, radius=max(0, radius - k), fill=textures._rgb(TRACK))
    # the fill: the gradient running along the whole track, shown up to the thumb
    fraction = max(0.0, min(1.0, fraction))
    fx = x0 + (x1 - x0) * fraction
    if fx - x0 > 0.5:
        stops_now = DISABLED_FILL if disabled else stops
        strip = Image.new('RGB', (w, 1))
        for x in range(w):
            f = (x - x0) / max(1.0, x1 - x0)
            strip.putpixel((x, 0), textures._stop_colour(stops_now, textures.drift(max(0.0, min(1.0, f)), shift)))
        gradient = strip.resize((w * k, h * k), Image.BILINEAR)
        mask = Image.new('L', (w * k, h * k), 0)
        ImageDraw.Draw(mask).rounded_rectangle([box[0], box[1], max(box[0] + 2 * radius, fx * k), box[3]],
                                               radius=radius, fill=255)
        out.paste(gradient, (0, 0), mask)
        # a soft light line along the top of the fill: the bevel
        sheen = Image.new('L', (w * k, h * k), 0)
        ImageDraw.Draw(sheen).rounded_rectangle([box[0] + k, box[1] + k, max(box[0] + 2 * radius, fx * k) - k,
                                                 box[1] + 2 * k], radius=k, fill=70)
        out.paste(Image.new('RGB', out.size, (255, 244, 225)), (0, 0), sheen)
    if thumb:
        cx = fx * k
        r = thumb * k
        if glow > 0:                                   # hover halo, blended into the background
            halo = Image.new('L', out.size, 0)
            g = r + 4 * k * glow
            ImageDraw.Draw(halo).ellipse([cx - g, cy * k - g, cx + g, cy * k + g], fill=int(70 * glow))
            out.paste(Image.new('RGB', out.size, textures._rgb(stops[1])), (0, 0), halo)
        # a soft drop shadow, then the black rim, then the cream knob: lighter at the top and a
        # little darker at the bottom (the bevel), with a small highlight
        draw.ellipse([cx - r, cy * k - r + k, cx + r, cy * k + r + k], fill=(10, 7, 5))
        draw.ellipse([cx - r, cy * k - r, cx + r, cy * k + r], fill=textures._rgb(THUMB_EDGE))
        rim = 1.2 * k
        knob = textures._rgb('#B9A994' if disabled else THUMB)
        inner_r = r - rim
        size = max(2, int(round(2 * inner_r)))
        shade = Image.new('RGB', (1, size))
        for y in range(size):
            f = y / max(1, size - 1)
            shade.putpixel((0, y), textures._mix(textures._mix(knob, (255, 255, 255), 0.30),
                                                 textures._mix(knob, (140, 112, 88), 0.30), f))
        circle = Image.new('L', (size, size), 0)
        ImageDraw.Draw(circle).ellipse([0, 0, size - 1, size - 1], fill=255)
        out.paste(shade.resize((size, size)), (int(round(cx - inner_r)), int(round(cy * k - inner_r))), circle)
        if focus:                                      # keyboard focus: a small accent dot
            d = max(1.2 * k, r * 0.28)
            draw.ellipse([cx - d, cy * k - d, cx + d, cy * k + d], fill=textures._rgb(stops[-1]))
    return out.resize((w, h), Image.BOX)


@lru_cache(maxsize=16)
def _background(behind: str, w: int, h: int, amount: float):
    """The panel's film grain at SUPER× size, cached per size (it never changes)."""
    from PIL import Image
    from . import textures
    return textures.grain(behind, (w, h), amount=amount, seed=17, mottle=False).resize((w * SUPER, h * SUPER),
                                                                                         Image.NEAREST)


class _GradientCanvas(tk.Canvas):
    """Shared plumbing: background, drift following, one image item, coalesced redraws."""

    def __init__(self, parent, *, behind: str, grain_amount: float, height: int, width: int):
        super().__init__(parent, height=height, width=width, highlightthickness=0, borderwidth=0,
                         background=behind)
        self._behind = behind
        self._grain = grain_amount
        self._shift = 0.0
        self._photo = None
        self._item = None
        self._job = None
        self.bind('<Configure>', lambda _e: self.redraw(), add='+')
        anim = getattr(self.winfo_toplevel(), '_og_anim', None)
        if anim is not None:
            anim.on_frame(self._on_shift)

    def _stops(self) -> tuple[str, ...]:
        from .theme import GRADIENT
        return GRADIENT

    def _on_shift(self, shift: float) -> None:
        self._shift = shift
        if self.winfo_ismapped():
            self.redraw(now=True)

    def redraw(self, now: bool = False) -> None:
        if now:
            self._draw()
            return
        if self._job is None:
            try:
                self._job = self.after_idle(self._draw)
            except tk.TclError:
                pass

    def _draw(self) -> None:
        self._job = None
        try:
            width, height = self.winfo_width(), self.winfo_height()
        except tk.TclError:
            return
        if width < 4 or height < 4:
            return
        try:
            from PIL import ImageTk
            image = self._image(width, height)
            photo = ImageTk.PhotoImage(image, master=self)
        except Exception:  # noqa: BLE001 - no Pillow: fall back to plain shapes
            self._fallback(width, height)
            return
        self._photo = photo
        if self._item is None:
            self._item = self.create_image(0, 0, anchor='nw', image=photo)
        else:
            self.itemconfigure(self._item, image=photo)

    def _image(self, width: int, height: int):  # pragma: no cover - overridden
        raise NotImplementedError

    def _fallback(self, width: int, height: int) -> None:
        self.delete('all')
        self._item = None
        fraction = self._fraction()
        self.create_rectangle(2, height // 2 - 2, width - 2, height // 2 + 2, fill=TRACK, outline=TRACK_EDGE)
        self.create_rectangle(2, height // 2 - 2, 2 + (width - 4) * fraction, height // 2 + 2,
                              fill=self._stops()[1], width=0)

    def _fraction(self) -> float:  # pragma: no cover - overridden
        return 0.0


class GradientSlider(_GradientCanvas):
    """A modern horizontal slider; see the module docstring."""

    def __init__(self, parent, from_: float = 0.0, to: float = 1.0, variable: tk.Variable | None = None,
                 length: int | None = None, behind: str | None = None, grain_amount: float = 0.18,
                 on_press: Callable | None = None, on_drag: Callable | None = None,
                 on_release: Callable | None = None, takefocus: bool = True):
        from .theme import PALETTE
        scale = _scale_of(parent)
        self.track_rest, self.track_hover = 4 * scale, 6 * scale
        self.thumb_rest, self.thumb_hover = 6 * scale, 8 * scale
        height = round(22 * scale)
        super().__init__(parent, behind=behind or PALETTE['surface'], grain_amount=grain_amount,
                         height=height, width=length or round(160 * scale))
        self.configure(takefocus=1 if takefocus else 0, cursor='hand2')
        self._from, self._to = float(from_), float(to)
        self.variable = variable if variable is not None else tk.DoubleVar(master=self, value=self._from)
        self.on_press, self.on_drag, self.on_release = on_press, on_drag, on_release
        self._states: set[str] = set()
        self._grow = 0.0                # 0 = at rest, 1 = hovered / dragging
        self._grow_target = 0.0
        self._grow_job = None
        self._focus = False
        self._trace = self.variable.trace_add('write', lambda *_: self.redraw())
        for sequence, handler in (('<ButtonPress-1>', self._press), ('<B1-Motion>', self._motion),
                                  ('<ButtonRelease-1>', self._release), ('<Enter>', self._enter),
                                  ('<Leave>', self._leave), ('<Left>', lambda e: self._key(-1)),
                                  ('<Right>', lambda e: self._key(1)), ('<Down>', lambda e: self._key(-1)),
                                  ('<Up>', lambda e: self._key(1)), ('<Home>', lambda e: self._key(None, 0.0)),
                                  ('<End>', lambda e: self._key(None, 1.0)), ('<MouseWheel>', self._wheel),
                                  ('<Button-4>', lambda e: self._key(1)), ('<Button-5>', lambda e: self._key(-1)),
                                  ('<FocusIn>', lambda e: self._set_focus(True)),
                                  ('<FocusOut>', lambda e: self._set_focus(False))):
            self.bind(sequence, handler)
        self.bind('<Destroy>', self._destroyed, add='+')

    # ------------------------------------------------------------------ ttk.Scale-like interface
    def get(self, x: int | None = None, y: int | None = None) -> float:
        if x is not None:
            return self.value_at(x)
        try:
            return float(self.variable.get())
        except (tk.TclError, ValueError):
            return self._from

    def set(self, value: float) -> None:
        low, high = sorted((self._from, self._to))
        self.variable.set(max(low, min(high, float(value))))

    def cget(self, key: str):
        if key in ('from', 'from_'):
            return self._from
        if key == 'to':
            return self._to
        return super().cget(key)

    def configure(self, cnf=None, **kw):
        changed = False
        for key in ('from_', 'from'):
            if key in kw:
                self._from = float(kw.pop(key)); changed = True
        if 'to' in kw:
            self._to = float(kw.pop('to')); changed = True
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        if changed:
            self.redraw()
        return result

    config = configure

    def state(self, spec=None):
        if spec is None:
            return tuple(sorted(self._states))
        for flag in spec:
            if flag.startswith('!'):
                self._states.discard(flag[1:])
            else:
                self._states.add(flag)
        self.configure(cursor='' if 'disabled' in self._states else 'hand2')
        self.redraw()
        return ()

    def instate(self, spec) -> bool:
        return all((flag[1:] not in self._states) if flag.startswith('!') else (flag in self._states)
                   for flag in spec)

    # ------------------------------------------------------------------ geometry
    def _pad(self) -> float:
        return self.thumb_hover + 2

    def value_at(self, x: float) -> float:
        width = max(1, self.winfo_width())
        pad = self._pad()
        f = (x - pad) / max(1.0, width - 2 * pad)
        f = max(0.0, min(1.0, f))
        return self._from + (self._to - self._from) * f

    def _fraction(self) -> float:
        span = self._to - self._from
        return 0.0 if not span else (self.get() - self._from) / span

    def _image(self, width: int, height: int):
        g = self._grow
        track = self.track_rest + (self.track_hover - self.track_rest) * g
        thumb = self.thumb_rest + (self.thumb_hover - self.thumb_rest) * g
        # the same end space at rest and on hover, so the thumb grows in place
        return render(width, height, self._fraction(), behind=self._behind, grain_amount=self._grain,
                      stops=self._stops(), shift=self._shift, track=track, thumb=thumb,
                      disabled='disabled' in self._states, focus=self._focus, glow=g, pad=self._pad())

    # ------------------------------------------------------------------ hover growth
    def _motion_enabled(self) -> bool:
        motion = getattr(self.winfo_toplevel(), '_og_motion', None)
        return motion is None or motion.enabled

    def _grow_to(self, target: float) -> None:
        self._grow_target = target
        if not self._motion_enabled():
            self._grow = target
            self.redraw()
            return
        if self._grow_job is None:
            self._grow_step()

    def _grow_step(self) -> None:
        self._grow_job = None
        if abs(self._grow - self._grow_target) < 1e-6:
            return
        step = 1.0 / GROW_STEPS
        self._grow = (min(self._grow_target, self._grow + step) if self._grow_target > self._grow
                      else max(self._grow_target, self._grow - step))
        self.redraw(now=True)
        if abs(self._grow - self._grow_target) > 1e-6:
            try:
                self._grow_job = self.after(GROW_STEP_MS, self._grow_step)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ events
    def _enabled(self) -> bool:
        return 'disabled' not in self._states

    def _press(self, event):
        if not self._enabled():
            return 'break'
        self.focus_set()
        self._states.add('pressed')
        self._grow_to(1.0)
        self.set(self.value_at(event.x))
        if self.on_press:
            self.on_press()
        if self.on_drag:
            self.on_drag()
        return 'break'

    def _motion(self, event):
        if 'pressed' not in self._states:
            return 'break'
        self.set(self.value_at(event.x))
        if self.on_drag:
            self.on_drag()
        return 'break'

    def _release(self, event):
        if 'pressed' not in self._states:
            return 'break'
        self._states.discard('pressed')
        self.set(self.value_at(event.x))
        if self.on_release:
            self.on_release()
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if not inside:
            self._grow_to(0.0)
        return 'break'

    def _enter(self, _event):
        if self._enabled():
            self._grow_to(1.0)

    def _leave(self, _event):
        if 'pressed' not in self._states:
            self._grow_to(0.0)

    def _key(self, direction, absolute: float | None = None):
        if not self._enabled():
            return 'break'
        if absolute is not None:
            value = self._from + (self._to - self._from) * absolute
        else:
            value = self.get() + direction * (self._to - self._from) / KEY_STEPS
        if self.on_press:
            self.on_press()
        self.set(value)
        if self.on_drag:
            self.on_drag()
        if self.on_release:
            self.on_release()
        return 'break'

    def _wheel(self, event):
        return self._key(1 if event.delta > 0 else -1)

    def _set_focus(self, focused: bool) -> None:
        self._focus = focused
        self.redraw()

    def _destroyed(self, event) -> None:
        if event.widget is self:
            try:
                self.variable.trace_remove('write', self._trace)
            except (tk.TclError, ValueError):
                pass


class GradientBar(_GradientCanvas):
    """A determinate progress bar in the slider's style: ``bar['value'] = 40`` (of ``maximum``)."""

    def __init__(self, parent, maximum: float = 100.0, behind: str | None = None, grain_amount: float = 0.20):
        from .theme import PALETTE
        scale = _scale_of(parent)
        self.thickness = 8 * scale
        super().__init__(parent, behind=behind or PALETTE['bg'], grain_amount=grain_amount,
                         height=round(14 * scale), width=round(200 * scale))
        self._value = 0.0
        self._maximum = float(maximum)

    def __setitem__(self, key, value) -> None:
        if key in ('value', 'maximum'):
            self.configure(**{key: value})
        else:
            super().__setitem__(key, value)

    def __getitem__(self, key):
        if key == 'value':
            return self._value
        if key == 'maximum':
            return self._maximum
        return super().__getitem__(key)

    def configure(self, cnf=None, **kw):
        changed = False
        if 'value' in kw:
            self._value = float(kw.pop('value')); changed = True
        if 'maximum' in kw:
            self._maximum = float(kw.pop('maximum')); changed = True
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        if changed:
            self.redraw()
        return result

    config = configure

    def _fraction(self) -> float:
        return 0.0 if not self._maximum else self._value / self._maximum

    def _image(self, width: int, height: int):
        return render(width, height, self._fraction(), behind=self._behind, grain_amount=self._grain,
                      stops=self._stops(), shift=self._shift, track=self.thickness, thumb=None)
