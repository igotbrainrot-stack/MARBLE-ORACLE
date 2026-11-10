"""EIDOLITH in-tab video viewer.

Uses FFmpeg's ordinary PPM image pipe to draw decoded video frames directly into
Tk; there is no external video window, third-party Tk widget or libmpv runtime
requirement. FFplay, if present, runs **audio only** (-nodisp -vn) beside the
viewer. This is a simple, CPU-based preview backend and not frame-accurate
HDR / A-V sync playback. It deliberately never launches a graphical ffplay
window. Fullscreen is shown only after the user presses FULLSCREEN.
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
import tkinter as tk


FRAME_RATE = 12
PPM_MAX_SIZE = 12 * 1024 * 1024


def _no_console():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def _ppm_frame(stream):
    """Read one binary P6 PPM frame from ffmpeg image2pipe (strict size limits)."""
    def token():
        b = bytearray()
        while True:
            c = stream.read(1)
            if not c:
                return None
            if c == b'#':
                stream.readline()
                continue
            if not c.isspace():
                b.extend(c)
                break
        while True:
            c = stream.read(1)
            if not c or c.isspace():
                break
            b.extend(c)
        return bytes(b)
    magic = token()
    if magic is None:
        return None
    if magic != b'P6':
        raise ValueError('FFmpeg returned a non-PPM video frame')
    fields = (token(), token(), token())
    if any(f is None for f in fields):
        return None
    w, h, maxval = map(int, fields)
    size = w * h * 3
    if not 0 < w <= 1920 or not 0 < h <= 1080 or maxval != 255 or size > PPM_MAX_SIZE:
        raise ValueError('Unsupported FFmpeg video frame dimensions')
    data = bytearray(size)
    view = memoryview(data)
    n = 0
    while n < size:
        block = stream.read(size - n)
        if not block:
            return None
        view[n:n + len(block)] = block
        n += len(block)
    return b'P6\n%d %d\n255\n' % (w, h) + bytes(data)


class InTabVideoPlayer:
    def __init__(self, parent, *, ffmpeg, ffplay, colors, font):
        self.parent, self.ffmpeg, self.ffplay, self.C, self.font = parent, ffmpeg, ffplay, colors, font
        self.path = ''
        self.duration = 0.0
        self.position = 0.0
        self.phase = 'stopped'
        self.play_proc = None  # decoded video frames (stdout PPM)
        self.audio_proc = None  # FFplay with -nodisp and -vn; never creates a video window
        self._generation = 0
        self._frames = queue.Queue(maxsize=3)
        self._after = None
        self._photo = None
        self._full_photo = None
        self._fullscreen = None
        self._fullscreen_canvas = None
        self._decode_thread = None
        self._session_start = 0.0
        self._drawn_frames = 0
        self._decoder_done = False
        self._last_frame = None
        self._seeking = False
        self._target_w, self._target_h = 576, 324
        self._build_ui()
        self._schedule()

    def _build_ui(self):
        c = self.C
        self.root = tk.Frame(self.parent, bg=c['raised'])
        self.root.pack(fill='both', expand=True)
        self.file_title = tk.Label(self.root, text='NO VIDEO LOADED', anchor='w', bg=c['raised'], fg=c['text_2'],
                                   font=(self.font, 11, 'bold'))
        self.file_title.pack(fill='x', padx=10, pady=(8, 5))
        surround = tk.Frame(self.root, bg='#070606', highlightthickness=1, highlightbackground=c['line_strong'])
        surround.pack(fill='both', expand=True, padx=10)
        self.canvas = tk.Canvas(surround, bg='#090807', highlightthickness=0, bd=0, height=255)
        self.canvas.pack(fill='both', expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor='center')
        self.placeholder_id = self.canvas.create_text(0, 0, anchor='center',
                                                      text='EIDOLITH VIEWER\n\nChoose a video and press PLAY',
                                                      justify='center', fill=c['text_3'], font=(self.font, 13, 'bold'))
        self.canvas.bind('<Configure>', self._recenter)
        self.canvas.bind('<Button-1>', lambda _e: self.toggle_pause())
        self.time_var = tk.StringVar(value='00:00 / 00:00')
        timebar = tk.Frame(self.root, bg=c['raised'])
        timebar.pack(fill='x', padx=10, pady=(8, 0))
        self.seek_var = tk.DoubleVar(value=0)
        self.seek_slider = tk.Scale(timebar, from_=0, to=1000, orient='horizontal', showvalue=False,
                                    bd=0, highlightthickness=0, troughcolor=c['sunken'],
                                    bg=c['raised'], fg=c['text'], activebackground=c['accent'],
                                    command=self._seek_dragged, sliderlength=14, width=9,
                                    relief='flat')
        self.seek_slider.pack(side='left', fill='x', expand=True)
        self.seek_slider.bind('<ButtonPress-1>', lambda _e: setattr(self, '_seeking', True), add='+')
        self.seek_slider.bind('<ButtonRelease-1>', self._seek_released, add='+')
        tk.Label(timebar, textvariable=self.time_var, bg=c['raised'], fg=c['text_2'],
                 font=(self.font, 10)).pack(side='right', padx=(8, 0))
        # Two short rows keep every transport control visible on compact CRT
        # layouts. The former single row clipped the FULLSCREEN button.
        commands = (
            (('PLAY / RESUME', self.play), ('PAUSE', self.pause), ('STOP', self.stop)),
            (('−10 SEC', lambda: self.seek(self.position - 10)),
             ('+10 SEC', lambda: self.seek(self.position + 10)),
             ('FULLSCREEN', self.open_fullscreen)),
        )
        for idx, items in enumerate(commands):
            controls = tk.Frame(self.root, bg=c['raised'])
            controls.pack(fill='x', padx=10, pady=(8 if idx == 0 else 3, 1))
            for label, callback in items:
                primary = label == 'PLAY / RESUME'
                tk.Button(controls, text=label, command=callback, relief='flat', bd=0,
                          bg=c['accent'] if primary else c['control'],
                          fg=c['text_on_accent'] if primary else c['text'],
                          activebackground=c['accent_deep'] if primary else c['hover'],
                          activeforeground=c['text_on_accent'] if primary else c['text'],
                          padx=8, pady=5, font=(self.font, 9, 'bold'), cursor='hand2').pack(side='left', padx=(0, 6))
        self.volume_var = tk.IntVar(value=85)
        volume = tk.Frame(self.root, bg=c['raised'])
        volume.pack(fill='x', padx=10, pady=(7, 5))
        tk.Label(volume, text='AUDIO', bg=c['raised'], fg=c['text_3'],
                 font=(self.font, 9)).pack(side='left')
        self.volume_slider = tk.Scale(volume, from_=0, to=100, variable=self.volume_var,
                                      orient='horizontal', showvalue=True, length=125,
                                      bd=0, highlightthickness=0, troughcolor=c['sunken'],
                                      bg=c['raised'], fg=c['text'], sliderlength=12,
                                      width=8, relief='flat')
        self.volume_slider.pack(side='left', padx=(5, 0))
        # FFplay's CLI has no live volume API. Apply the new level when the
        # user releases the slider by restarting only the audio process.
        self.volume_slider.bind('<ButtonRelease-1>', lambda _e: self._apply_volume())
        # Playback limitations are documented on ABOUT instead of placing a
        # long label under the controls, where small windows clipped it.

    @staticmethod
    def _stamp(seconds):
        minutes, sec = divmod(max(0, int(seconds)), 60)
        hours, minutes = divmod(minutes, 60)
        return f'{hours:02d}:{minutes:02d}:{sec:02d}' if hours else f'{minutes:02d}:{sec:02d}'

    def _recenter(self, _event=None):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self.canvas.coords(self.image_id, width // 2, height // 2)
        self.canvas.coords(self.placeholder_id, width // 2, height // 2)
        if self._fullscreen_canvas:
            self._fullscreen_canvas.coords('video', self._fullscreen_canvas.winfo_width() // 2,
                                           self._fullscreen_canvas.winfo_height() // 2)

    def load(self, path, duration=0.0):
        self.stop()
        self.path = str(path)
        self.duration = max(0.0, float(duration))
        self.position = 0.0
        self.file_title.config(text=os.path.basename(path).upper())
        self.canvas.itemconfigure(self.placeholder_id, text='READY TO PLAY\n\nPress PLAY / RESUME', state='normal')
        self._update_time()

    def _video_dimensions(self):
        viewer = self._fullscreen_canvas if self._fullscreen_canvas else self.canvas
        w = max(256, min(1152, viewer.winfo_width() - 12))
        h = max(144, min(648, viewer.winfo_height() - 12))
        # Stay within the bounding frame; FFmpeg preserves source aspect ratio.
        return w, h

    def _start_decoder(self):
        if not self.path or not self.ffmpeg:
            self.canvas.itemconfigure(self.placeholder_id, text='FFmpeg is required for embedded playback', state='normal')
            return False
        self._generation += 1
        token = self._generation
        self._decoder_done = False
        self._drawn_frames = 0
        self._session_start = self.position
        self._frames = queue.Queue(maxsize=3)
        w, h = self._video_dimensions()
        # Avoid a separate ffplay video window. FFmpeg pipes image frames to Tk.
        cmd = [self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-ss', f'{self.position:.3f}',
               '-i', self.path, '-map', '0:v:0', '-an', '-sn', '-dn',
               '-vf', f'fps={FRAME_RATE},scale={w}:{h}:force_original_aspect_ratio=decrease',
               '-f', 'image2pipe', '-vcodec', 'ppm', '-']
        try:
            self.play_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                              stdin=subprocess.DEVNULL, bufsize=0, creationflags=_no_console())
        except Exception as exc:
            self.canvas.itemconfigure(self.placeholder_id, text=f'Video decoder failed:\n{exc}', state='normal')
            return False
        proc, outq = self.play_proc, self._frames
        def read_frames():
            try:
                while token == self._generation and proc.poll() is None:
                    frame = _ppm_frame(proc.stdout)
                    if frame is None:
                        break
                    while token == self._generation:
                        try:
                            outq.put(frame, timeout=0.12)
                            break
                        except queue.Full:
                            pass
            except (OSError, ValueError):
                pass
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                if token == self._generation:
                    self._decoder_done = True
        self._decode_thread = threading.Thread(target=read_frames, daemon=True)
        self._decode_thread.start()
        self.canvas.itemconfigure(self.placeholder_id, state='hidden')
        return True

    def _start_audio(self):
        # Audio only, never a video window. This lightweight fallback does not
        # guarantee lip-sync accuracy under heavy CPU loads.
        if not self.ffplay or not self.path:
            return
        if os.path.basename(self.ffplay).lower().startswith('mpv'):
            cmd = [self.ffplay, '--no-video', '--really-quiet', '--audio-display=no',
                   '--volume='+str(self.volume_var.get()), f'--start={self.position:.3f}', self.path]
        else:
            cmd = [self.ffplay, '-hide_banner', '-loglevel', 'quiet', '-nodisp', '-vn', '-autoexit',
                   '-volume', str(self.volume_var.get()), '-ss', f'{self.position:.3f}', '-i', self.path]
        try:
            self.audio_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                               stdin=subprocess.DEVNULL, creationflags=_no_console())
        except OSError:
            self.audio_proc = None

    def _apply_volume(self):
        if self.phase == 'playing' and self.ffplay:
            if self.audio_proc and self.audio_proc.poll() is None:
                try:
                    self.audio_proc.terminate()
                except OSError:
                    pass
            self.audio_proc = None
            self._start_audio()

    def _kill_processes(self):
        self._generation += 1
        for proc in (self.play_proc, self.audio_proc):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
        self.play_proc = None
        self.audio_proc = None
        # Old decode workers own old queues; new sessions create new queues.
        self._decoder_done = False

    def play(self):
        if not self.path:
            self.canvas.itemconfigure(self.placeholder_id, text='Import a video, select it, then press PLAY', state='normal')
            return
        if self.phase == 'playing':
            return
        if self.duration and self.position >= self.duration - 0.2:
            self.position = 0.0
        self._kill_processes()
        if self._start_decoder():
            self._start_audio()
            self.phase = 'playing'

    def pause(self):
        if self.phase != 'playing':
            return
        self.phase = 'paused'
        self._kill_processes()
        self._update_time()

    def toggle_pause(self):
        self.pause() if self.phase == 'playing' else self.play()

    def stop(self):
        self.phase = 'stopped'
        self._kill_processes()
        self.position = 0.0
        self._drawn_frames = 0
        self._update_time()

    def seek(self, position):
        if not self.path:
            return
        position = max(0.0, min(float(position), max(self.duration - 0.01, 0.0))) if self.duration else max(0, float(position))
        was_playing = self.phase == 'playing'
        self._kill_processes()
        self.position = position
        self.phase = 'paused'
        self._update_time()
        if was_playing:
            self.play()

    def _seek_dragged(self, value):
        if self._seeking and self.duration:
            self.time_var.set(f'{self._stamp(float(value) / 1000 * self.duration)} / {self._stamp(self.duration)}')

    def _seek_released(self, _event):
        self._seeking = False
        if self.duration:
            self.seek(self.seek_slider.get() / 1000 * self.duration)

    def _update_time(self):
        self.time_var.set(f'{self._stamp(self.position)} / {self._stamp(self.duration)}')
        if not self._seeking:
            self.seek_slider.set(int(self.position / self.duration * 1000) if self.duration else 0)

    def _draw_frame(self, ppm):
        try:
            # Native Tk PPM decoder, no Pillow/ImageTk dependency.
            photo = tk.PhotoImage(master=self.canvas, data=ppm, format='PPM')
            self._photo = photo
            self.canvas.itemconfigure(self.image_id, image=photo)
            self._recenter()
            self._last_frame = ppm
            if self._fullscreen_canvas and self._fullscreen_canvas.winfo_exists():
                photo2 = tk.PhotoImage(master=self._fullscreen_canvas, data=ppm, format='PPM')
                self._full_photo = photo2
                self._fullscreen_canvas.itemconfigure('video', image=photo2)
        except tk.TclError:
            self.pause()
            self.canvas.itemconfigure(self.placeholder_id, text='Unable to display the decoded video frame', state='normal')

    def _tick(self):
        self._after = None
        if self.phase == 'playing':
            try:
                ppm = self._frames.get_nowait()
            except queue.Empty:
                ppm = None
            if ppm is not None:
                self._draw_frame(ppm)
                self._drawn_frames += 1
                self.position = self._session_start + self._drawn_frames / FRAME_RATE
                self._update_time()
            elif self._decoder_done and self._frames.empty():
                if self._drawn_frames == 0:
                    self.canvas.itemconfigure(self.placeholder_id,
                                              text='Unable to decode this video with FFmpeg',
                                              state='normal')
                self.phase = 'stopped'
                self._kill_processes()
        if self.root.winfo_exists():
            self._schedule()

    def _schedule(self):
        self._after = self.root.after(round(1000 / FRAME_RATE), self._tick)

    def open_fullscreen(self):
        # User request only: NEVER start on an external monitor or fullscreen.
        if self._fullscreen is not None:
            return
        top = tk.Toplevel(self.root)
        self._fullscreen = top
        top.title('EIDOLITH · Fullscreen viewer')
        top.configure(bg='#070606')
        # Place the fullscreen host over the main application first, so a
        # multi-monitor window manager selects its current display.
        top.geometry('+%d+%d' % (self.root.winfo_rootx(), self.root.winfo_rooty()))
        top.attributes('-fullscreen', True)
        top.update_idletasks()
        canvas = tk.Canvas(top, bg='#070606', bd=0, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        canvas.create_image(0, 0, anchor='center', tags='video')
        canvas.bind('<Configure>', lambda e: canvas.coords('video', e.width // 2, e.height // 2))
        self._fullscreen_canvas = canvas
        bar = tk.Frame(top, bg='#130F0D')
        bar.pack(side='bottom', fill='x')
        for label, action in (('PLAY / PAUSE', self.toggle_pause), ('−10s', lambda: self.seek(self.position - 10)),
                              ('+10s', lambda: self.seek(self.position + 10)),
                              ('EXIT FULLSCREEN', self.close_fullscreen)):
            tk.Button(bar, text=label, command=action, bg='#2F2620', fg='#E8DDD0',
                      activebackground='#3A2E27', activeforeground='#FFFFFF',
                      relief='flat', font=(self.font, 11, 'bold'), bd=0, padx=14, pady=9).pack(side='left', padx=4)
        top.bind('<Escape>', lambda _e: self.close_fullscreen())
        top.bind('<space>', lambda _e: self.toggle_pause())
        top.protocol('WM_DELETE_WINDOW', self.close_fullscreen)
        top.update_idletasks()
        if self._last_frame is not None:
            self._draw_frame(self._last_frame)
        if self.phase == 'playing':
            self.pause()
            self.play()  # restart decoder sized for fullscreen viewer
        top.focus_set()

    def close_fullscreen(self):
        if self._fullscreen is None:
            return
        was_playing = self.phase == 'playing'
        if was_playing:
            self.pause()
        top, self._fullscreen = self._fullscreen, None
        self._fullscreen_canvas = None
        self._full_photo = None
        try:
            top.destroy()
        except tk.TclError:
            pass
        if was_playing:
            self.play()  # return to embedded viewport dimensions

    def suspend(self):
        self.pause()

    def destroy(self):
        if self._after is not None:
            try:
                self.root.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None
        self.phase = 'stopped'
        self._kill_processes()
        self.close_fullscreen()
