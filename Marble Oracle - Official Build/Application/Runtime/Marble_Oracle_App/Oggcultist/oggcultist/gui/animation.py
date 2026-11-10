"""Motion for the theme (v1.8.9): the slow gradient drift and button hover/press animations.

**Gradient drift.** Everything drawn with the amber → reddish-orange gradient (accent and play
buttons, the active page marker, the ⏮ ⏭ ■ icons, the rule above the player bar) slowly
slides up and down its gradient: a full cycle takes ``PERIOD_MS``. Each animated image is a
Tk PhotoImage that every widget shares; the :class:`GradientAnimator` renders ``PHASES``
frames for it in small idle-time batches after start-up (so start-up isn't slowed) and then
copies the current frame into it on a timer. Copying into a shared PhotoImage redraws every
widget that shows it, with no per-widget work.

**Hover and press.** ttk switches a button's image instantly when the pointer enters or
leaves. :class:`ButtonMotion` turns that into a short fade: for each animated button style it
steps the widget through in-between styles (``OgH1.<style>`` to ``OgH3.<style>``, made by
``theme.apply_theme``) over about 100 ms. Pressing sinks the label by one pixel (a ``pressed``
padding map) and releasing gives a brief brighter flash (``OgHF.<style>``) before settling.

Both are switched off together by the "Animations" setting; off means the still look of
earlier versions (phase 0, instant hover).
"""
from __future__ import annotations

import math
import tkinter as tk
from typing import Callable

PHASES = 24            # frames per up-and-down cycle
PERIOD_MS = 8000       # one full cycle: down the gradient and back up
BATCH = 6              # frames rendered per idle step while preparing
HOVER_LEVELS = 3       # in-between steps of the hover fade
HOVER_STEP_MS = 30
FLASH_MS = 90


def shift_for(phase: int, phases: int = PHASES) -> float:
    """0 → 1 → 0 over one cycle, eased (slow at the ends, like a breath)."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * (phase % phases) / phases)


def variant(level: int | str, style: str) -> str:
    """Name of the in-between style: level 1..HOVER_LEVELS or 'F' (release flash)."""
    return f'OgH{level}.{style}'


class GradientAnimator:
    """Owns the drift frames and the timer for one Tk root."""

    def __init__(self, root: tk.Misc, phases: int = PHASES, period_ms: int = PERIOD_MS):
        self.root = root
        self.phases = phases
        self.interval = max(16, period_ms // phases)
        self.targets: list[tuple[object, Callable]] = []    # (PhotoImage, factory(shift) -> PIL image)
        self.frames: list[list[object]] = []
        self.callbacks: list[Callable[[float], None]] = []
        self.phase = 0
        self.enabled = True
        self._job = None
        self._prepare_job = None
        self._pending: list[tuple[int, int]] = []

    # ------------------------------------------------------------------ registration
    def register(self, photo, factory: Callable) -> None:
        """Animate ``photo``: frame i is ``factory(shift_for(i))``. Frame 0 is the photo itself."""
        self.targets.append((photo, factory))
        self.frames.append([None] * self.phases)
        index = len(self.targets) - 1
        self._pending.extend((index, i) for i in range(1, self.phases))

    def on_frame(self, callback: Callable[[float], None]) -> None:
        """Call ``callback(shift)`` on every step (for canvas drawings such as the gradient rule)."""
        self.callbacks.append(callback)

    @property
    def ready(self) -> bool:
        return not self._pending

    # ------------------------------------------------------------------ running
    def start(self) -> None:
        if self._prepare_job is None and self._pending:
            self._prepare_job = self.root.after(200, self._prepare)
        if self._job is None and self.enabled:
            self._job = self.root.after(self.interval, self._tick)

    def stop(self) -> None:
        for name in ('_job', '_prepare_job'):
            job = getattr(self, name)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, name, None)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if self.enabled:
            self.start()
        else:
            if self._job is not None:
                try:
                    self.root.after_cancel(self._job)
                except tk.TclError:
                    pass
                self._job = None
            self.show(0)                     # the still look

    def prepare_all(self) -> None:
        """Render every frame now (tests, screenshots)."""
        while self._pending:
            self._render_one()

    def _render_one(self) -> None:
        from PIL import ImageTk
        index, phase = self._pending.pop(0)
        _photo, factory = self.targets[index]
        self.frames[index][phase] = ImageTk.PhotoImage(factory(shift_for(phase, self.phases)), master=self.root)

    def _prepare(self) -> None:
        self._prepare_job = None
        try:
            for _ in range(min(BATCH, len(self._pending))):
                self._render_one()
        except Exception:  # noqa: BLE001 - animation is cosmetic: stay still rather than fail
            self._pending.clear()
            self.targets.clear()
            self.frames.clear()
            return
        if self._pending:
            try:
                self._prepare_job = self.root.after(15, self._prepare)
            except tk.TclError:
                pass

    def _tick(self) -> None:
        self._job = None
        try:
            hidden = self.root.state() in ('iconic', 'withdrawn')
        except tk.TclError:
            return
        if self.enabled and self.ready and not hidden:
            self.show((self.phase + 1) % self.phases)
        if self.enabled:
            try:
                self._job = self.root.after(self.interval, self._tick)
            except tk.TclError:
                pass

    def show(self, phase: int) -> None:
        """Put frame ``phase`` into every animated image (frames not rendered yet are skipped)."""
        self.phase = phase
        for (photo, _factory), frames in zip(self.targets, self.frames):
            frame = frames[phase] if phase else frames[0]
            if phase == 0 and frame is None:
                frame = frames[0] = self._first_frame(photo, _factory)
            if frame is None:
                continue
            try:
                self.root.tk.call(str(photo), 'copy', str(frame), '-compositingrule', 'set')
            except tk.TclError:
                pass
        shift = shift_for(phase, self.phases)
        for callback in list(self.callbacks):
            try:
                callback(shift)
            except tk.TclError:
                self.callbacks.remove(callback)

    def _first_frame(self, photo, factory):
        from PIL import ImageTk
        return ImageTk.PhotoImage(factory(0.0), master=self.root)


class ButtonMotion:
    """Hover fades and a release flash for ttk buttons whose style has in-between variants."""

    def __init__(self, root: tk.Misc):
        self.root = root
        self.styles: set[str] = set()        # base styles that have OgH1..3/OgHF variants
        self.enabled = True
        self._state: dict[str, dict] = {}
        for sequence, handler in (('<Enter>', self._enter), ('<Leave>', self._leave),
                                  ('<ButtonRelease-1>', self._release)):
            root.bind_class('TButton', sequence, handler, add='+')

    def add_style(self, style: str) -> None:
        self.styles.add(style)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _base(widget) -> tuple[str, str]:
        """(value to restore, base style name) for the widget's current style."""
        raw = str(widget.cget('style'))
        return raw, (raw or 'TButton')

    def _ours(self, widget, info: dict) -> bool:
        """True if the widget still shows the base style or one of our variants of it."""
        try:
            current = str(widget.cget('style'))
        except tk.TclError:
            return False
        base = info['base']
        return current == info['restore'] or current in {variant(k, base) for k in (*range(1, HOVER_LEVELS + 1), 'F')}

    def _set(self, widget, info: dict, level) -> None:
        style = info['restore'] if level in (0, HOVER_LEVELS + 1) else variant(level, info['base'])
        try:
            widget.configure(style=style)
        except tk.TclError:
            pass

    def _cancel(self, info: dict) -> None:
        if info.get('job') is not None:
            try:
                self.root.after_cancel(info['job'])
            except tk.TclError:
                pass
            info['job'] = None

    def _info(self, widget) -> dict | None:
        if not self.enabled:
            return None
        key = str(widget)
        info = self._state.get(key)
        if info is not None and not self._ours(widget, info):
            self._cancel(info)                # the app changed the style: start again from it
            info = None
        if info is None:
            try:
                restore, base = self._base(widget)
            except tk.TclError:
                return None
            if base not in self.styles:
                return None
            info = self._state[key] = {'restore': restore, 'base': base, 'level': 0, 'job': None}
        return info

    # ------------------------------------------------------------------ the fade
    def _run(self, widget, info: dict, target: int) -> None:
        """Step the level towards ``target`` (0 = rest, HOVER_LEVELS + 1 = full hover)."""
        self._cancel(info)
        if not self._ours(widget, info):
            self._state.pop(str(widget), None)
            return
        level = info['level']
        if level == target:
            self._set(widget, info, level)
            return
        level += 1 if target > level else -1
        info['level'] = level
        self._set(widget, info, level)
        if level != target:
            try:
                info['job'] = self.root.after(HOVER_STEP_MS, lambda: self._run(widget, info, target))
            except tk.TclError:
                pass

    def _enter(self, event) -> None:
        info = self._info(event.widget)
        if info is None or str(event.widget.instate(['disabled'])) == 'True':
            return
        if info['level'] == 0:
            info['level'] = 0
            self._run(event.widget, info, HOVER_LEVELS + 1)

    def _leave(self, event) -> None:
        info = self._info(event.widget)
        if info is None:
            return
        if info['level'] == HOVER_LEVELS + 1:
            info['level'] = HOVER_LEVELS + 1
        self._run(event.widget, info, 0)

    def _release(self, event) -> None:
        widget = event.widget
        info = self._info(widget)
        if info is None:
            return
        try:
            inside = widget.winfo_containing(event.x_root, event.y_root) == widget
            disabled = bool(widget.instate(['disabled']))
        except (tk.TclError, KeyError):
            return
        if not inside or disabled:
            return
        self._cancel(info)
        info['level'] = HOVER_LEVELS + 1
        try:
            widget.configure(style=variant('F', info['base']))
            info['job'] = self.root.after(FLASH_MS, lambda: self._settle(widget, info))
        except tk.TclError:
            pass

    def _settle(self, widget, info: dict) -> None:
        info['job'] = None
        if self._ours(widget, info):
            self._set(widget, info, HOVER_LEVELS + 1)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            for key, info in list(self._state.items()):
                self._cancel(info)
                try:
                    widget = self.root.nametowidget(key)
                    if self._ours(widget, info):
                        widget.configure(style=info['restore'])
                except (KeyError, tk.TclError):
                    pass
            self._state.clear()
