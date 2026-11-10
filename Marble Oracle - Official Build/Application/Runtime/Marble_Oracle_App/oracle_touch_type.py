"""Touch Type: small, local-first keyboard tutor integrated into Marble Oracle.

Four no-network mini-games share a deterministic, testable typing engine. The
Tk panel is embedded in the same canvas/window as HOME, PASSPHRASE, OGGCULTIST.
No extra packages or stand-alone processes are required.
"""
from __future__ import annotations

import random
import time
import tkinter as tk

from marble_uberata import FAMILY
from oracle_ogg_texture import frame as ogl_frame, label as ogl_label, install as ogl_install
from oggcultist_design_system import COLOR as C
from oracle_assets import load_json, save_json

LESSONS = (
    ("F + J", "fj"),
    ("D + K", "fjd k".replace(" ", "")),
    ("S + L", "fjdksl"),
    ("A + ;", "asdfjkl;"),
    ("ALL ROWS", "asdfghjkl;"),
)
WORDS = ("ink", "marble", "open", "hand", "skill", "quiet", "index", "letter",
         "anchor", "copper", "stone", "typing", "early", "speed", "practice",
         "silver", "window", "learn", "orange", "signal", "simple", "keyboard",
         "frame", "answer", "needle", "refine", "bright", "fingers", "steady")
FALL_WORDS = ("ask", "fog", "red", "map", "key", "ink", "tap", "low", "sun", "oak",
              "dust", "hold", "arch", "glow", "rune", "type", "speed", "light")
SENTENCES = (
    "the steady hands find the home keys.",
    "slow and accurate typing becomes fast with practice.",
    "keep your wrists relaxed and your eyes on the words.",
    "a little progress each day builds a useful skill.",
    "the quick fox walks beside the old stone wall.",
    "return your index fingers to f and j after each word.",
)
MODES = ("keys", "words", "fall", "sentences")
MODE_NAMES = ("HOME ROW", "WORD SPRINT", "KEYFALL", "SENTENCE LAB")
MODE_DETAILS = (
    "Learn the home row. Start with F and J, then unlock more letters as you practise.",
    "Type as many words as you can in 60 seconds. Finish each word with Space.",
    "Type each falling word before it reaches the bottom. Four missed words ends the round.",
    "Build accuracy with three short sentences. Mistakes must be corrected before advancing.",
)


def finger_for(char):
    ch = (char or "").lower()
    if ch == ' ': return "THUMBS · SPACE"
    groups = (
        ("LEFT PINKY", "qaz1"), ("LEFT RING", "wsx2"),
        ("LEFT MIDDLE", "edc3"), ("LEFT INDEX", "rfvtgb45"),
        ("RIGHT INDEX", "yhnujm67"), ("RIGHT MIDDLE", "ik,8"),
        ("RIGHT RING", "ol.9"), ("RIGHT PINKY", "p;/0"),
    )
    for name, keys in groups:
        if ch in keys:
            return name
    return "RELAX · HOME ROW"


class TypingEngine:
    """Game state with injected monotonic clock for repeatable regression tests."""
    def __init__(self, mode="keys", lesson=0, rng=None, clock=None):
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self.round_id = 0
        self.mode = mode
        self.lesson = lesson
        self.reset()

    def reset(self):
        self.round_id += 1
        self.phase = "ready"
        self.elapsed = 0.0
        self._running_since = None
        self.prompt = ""
        self.index = 0
        self.correct = 0
        self.errors = 0
        self.completed = 0
        self.score = 0
        self.lives = 4
        self.streak = 0
        self.best_streak = 0
        self.fall_elapsed = 0.0
        self.fall_duration = 6.4
        self.message = "Select START GAME, then type using the keyboard."
        self._next_prompt()

    def set_mode(self, mode, lesson=None):
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        if lesson is not None:
            self.lesson = max(0, min(len(LESSONS)-1, int(lesson)))
        self.reset()

    def _next_prompt(self):
        if self.mode == "keys":
            chars = LESSONS[self.lesson][1]
            self.prompt = " ".join("".join(self.rng.choice(chars) for _ in range(4)) for _ in range(7))
        elif self.mode == "words":
            self.prompt = self.rng.choice(WORDS) + " "
        elif self.mode == "fall":
            self.prompt = self.rng.choice(FALL_WORDS)
            self.fall_elapsed = 0.0
            self.fall_duration = max(3.0, 6.4 - 0.21 * self.completed)
        else:
            self.prompt = SENTENCES[self.completed % len(SENTENCES)]
        self.index = 0

    def start(self, now=None):
        if self.phase == "complete":
            self.reset()
        if self.phase == "running":
            return
        if self.phase in ("ready", "paused"):
            self._running_since = self.clock() if now is None else now
            self.phase = "running"
            self.message = "Keep your eyes on the prompt. Find the next key."

    def pause(self, now=None):
        if self.phase == "running":
            self.tick(now)
            self.phase = "paused"
            self._running_since = None
            self.message = "Paused — select RESUME to continue."

    def _end(self, message):
        self.phase = "complete"
        self._running_since = None
        self.message = message

    def tick(self, now=None):
        if self.phase != "running":
            return
        now = self.clock() if now is None else now
        span = max(0.0, now - self._running_since)
        self._running_since = now
        self.elapsed += span
        if self.mode == "words" and self.elapsed >= 60:
            self.elapsed = 60
            self._end("Time! Your 60-second sprint is complete.")
        elif self.mode == "fall":
            self.fall_elapsed += span
            while self.phase == "running" and self.fall_elapsed >= self.fall_duration:
                self.lives -= 1
                self.streak = 0
                self.message = "Missed word — keep your fingers ready."
                if self.lives <= 0:
                    self._end("Round over. Retry to beat your score.")
                else:
                    self._next_prompt()

    def press(self, ch, now=None):
        if self.phase != "running":
            return "inactive"
        self.tick(now)
        if self.phase != "running":
            return "finished"
        if not ch or len(ch) != 1 or not ch.isprintable():
            return "ignored"
        expected = self.prompt[self.index]
        if ch != expected:
            self.errors += 1
            self.streak = 0 if self.mode != "fall" else self.streak
            self.message = "Try again: " + ("SPACE" if expected == " " else expected.upper()) + "."
            return "wrong"
        self.correct += 1
        self.index += 1
        self.message = "Good. Keep a relaxed rhythm."
        if self.index < len(self.prompt):
            return "correct"
        self.completed += 1
        self.score += 1
        self.streak += 1
        self.best_streak = max(self.streak, self.best_streak)
        if self.mode == "keys":
            self._end("Home-row drill complete. Move to the next lesson or repeat!")
        elif self.mode == "sentences" and self.completed >= 3:
            self._end("Three sentences complete. Great practice!")
        elif self.mode == "fall" and self.completed >= 12:
            self._end("You cleared all 12 falling words!")
        else:
            self._next_prompt()
        return "finished" if self.phase == "complete" else "advance"

    @property
    def expected(self):
        return self.prompt[self.index] if self.index < len(self.prompt) else ""

    @property
    def accuracy(self):
        total = self.correct + self.errors
        return 100.0 * self.correct / total if total else 100.0

    @property
    def wpm(self):
        return self.correct / 5.0 / (self.elapsed / 60.0) if self.elapsed >= 1.0 else 0.0

    @property
    def fall_progress(self):
        return min(1.0, self.fall_elapsed / self.fall_duration)


class TouchTypePanel(tk.Frame):
    """Embedded teaching/game UI using only native Tk widgets and shared Ember tokens."""
    def __init__(self, master, on_home):
        super().__init__(master, bg=C['sidebar'], highlightthickness=0)
        self.on_home = on_home
        self.engine = TypingEngine()
        self.stats = load_json('touch_type_scores.json', {})
        if not isinstance(self.stats, dict):
            self.stats = {}
        self._after_id = None
        self._saved_round_id = None
        self._last_status = None
        self._last_render = None
        self._recent_keys = ""
        self._make_ui()
        self._paint()
        self._schedule()
        self.after_idle(self.focus_input)

    def _label(self, parent, txt, size=12, colour='text', bold=False, **kwargs):
        return ogl_label(parent, text=txt, fg=C[colour],
                        font=(FAMILY, size, 'bold' if bold else 'normal'), **kwargs)

    def _button(self, parent, text, callback, primary=False):
        btn = tk.Button(parent, text=text, command=lambda: self._invoke(callback), cursor='hand2',
                        relief='flat', bd=0, padx=12, pady=8,
                        font=(FAMILY, 11, 'bold'),
                        bg=C['accent'] if primary else C['control'],
                        fg=C['text_on_accent'] if primary else C['text'],
                        activebackground=C['accent_deep'] if primary else C['hover'],
                        activeforeground=C['text_on_accent'] if primary else C['text'],
                        highlightthickness=1, highlightbackground=C['control_line'])
        return btn

    def _invoke(self, callback):
        callback()
        self._paint()
        self.after_idle(self.focus_input)

    def _make_ui(self):
        root = ogl_frame(self, bg=C['sidebar'])
        root.pack(fill='both', expand=True)
        self.rail = ogl_frame(root, bg=C['sidebar'], width=225)
        self.rail.pack(side='left', fill='y')
        self.rail.pack_propagate(False)
        tk.Frame(root, bg=C['line'], width=1).pack(side='left', fill='y')
        main = ogl_frame(root, bg=C['canvas'])
        main.pack(side='left', fill='both', expand=True)

        self.rail_title = self._label(self.rail, 'TOUCH TYPE', 19, 'text_bright', bold=True)
        self.rail_title.pack(anchor='w', padx=18, pady=(12, 2))
        self.rail_subtitle = self._label(self.rail, 'LEARN · PLAY · IMPROVE', 10, 'text_3')
        self.rail_subtitle.pack(anchor='w', padx=18, pady=(0, 13))
        self._label(self.rail, 'TRAINING GAMES', 10, 'text_3', bold=True).pack(anchor='w', padx=18, pady=(0, 6))
        self.mode_buttons = {}
        for i, mode in enumerate(MODES):
            btn = self._button(self.rail, '%02d   %s' % (i+1, MODE_NAMES[i]),
                               lambda m=mode: self.set_mode(m))
            btn.configure(anchor='w', padx=14)
            btn.pack(fill='x', padx=12, pady=2)
            self.mode_buttons[mode] = btn

        self._label(self.rail, 'CURRENT LESSON', 10, 'text_3', bold=True).pack(anchor='w', padx=18, pady=(13, 5))
        self.lesson_value = tk.StringVar(value=LESSONS[0][0])
        self.lesson_menu = tk.OptionMenu(self.rail, self.lesson_value, *(l[0] for l in LESSONS), command=self.change_lesson)
        self.lesson_menu.configure(bg=C['control'], fg=C['text'], activebackground=C['hover'],
                                   activeforeground=C['text'], highlightthickness=0, bd=0,
                                   font=(FAMILY, 12), anchor='w', relief='flat')
        self.lesson_menu['menu'].configure(bg=C['raised'], fg=C['text'],
                                           activebackground=C['accent_soft'],
                                           activeforeground=C['text'])
        self.lesson_menu.pack(fill='x', padx=14)
        self._label(self.rail, 'HOME ROW · QWERTY', 10, 'text_3').pack(anchor='w', padx=18, pady=(5, 0))
        ogl_frame(self.rail, bg=C['sidebar']).pack(fill='both', expand=True)
        self.best_label = self._label(self.rail, 'BEST  —', 11, 'text_2')
        self.best_label.pack(anchor='w', padx=18, pady=(4, 6))
        self._button(self.rail, '← BACK TO ORACLE', self.on_home).pack(fill='x', padx=12, pady=(0, 7))

        head = ogl_frame(main, bg=C['canvas'])
        head.pack(fill='x', padx=20, pady=(9, 1))
        self.mode_title = self._label(head, 'HOME ROW', 18, 'text_bright', bold=True)
        self.mode_title.pack(side='left')
        self.phase_label = ogl_label(head, bg=C['accent_soft'], fg=C['accent'],
                                    font=(FAMILY, 10, 'bold'), padx=12, pady=4, text='READY')
        self.phase_label.pack(side='right')
        self.description = self._label(main, MODE_DETAILS[0], 11, 'text_2', wraplength=720, justify='left')
        self.description.pack(fill='x', padx=20, pady=(0, 6))

        stats_row = ogl_frame(main, bg=C['raised'], pady=5)
        stats_row.pack(fill='x', padx=18, pady=(0, 7))
        self.stat_labels = {}
        for key, title in [('wpm','SPEED / WPM'), ('accuracy','ACCURACY'), ('score','COMPLETED'), ('time','TIME')]:
            cell = ogl_frame(stats_row, bg=C['raised'])
            cell.pack(side='left', expand=True, fill='x')
            self._label(cell, title, 9, 'text_3', bold=True).pack()
            val = self._label(cell, '—', 15, 'text_bright', bold=True)
            val.pack(pady=(0,0))
            self.stat_labels[key] = val

        prompt_panel = ogl_frame(main, bg=C['sunken'], highlightthickness=1, highlightbackground=C['line_strong'])
        prompt_panel.pack(fill='x', padx=18, pady=(0, 7))
        top = ogl_frame(prompt_panel, bg=C['sunken'])
        top.pack(fill='x', padx=12, pady=(4, 0))
        self._label(top, 'TYPE THE HIGHLIGHTED CHARACTER', 10, 'text_3', bold=True).pack(side='left')
        self.progress_label = self._label(top, '0 / 0', 10, 'text_2')
        self.progress_label.pack(side='right')
        self.prompt_text = tk.Text(prompt_panel, height=2, wrap='word', bd=0, relief='flat',
                                   font=(FAMILY, 16), bg=C['sunken'], fg=C['text'],
                                   padx=10, pady=5, cursor='arrow', takefocus=0,
                                   highlightthickness=0, spacing2=3)
        self.prompt_text.pack(fill='x', padx=8, pady=(0, 2))
        self.prompt_text.tag_configure('done', foreground=C['done'])
        self.prompt_text.tag_configure('next', foreground=C['accent'], underline=True)
        self.prompt_text.tag_configure('remaining', foreground=C['text_2'])
        self.prompt_text.configure(state='disabled')
        self.fall_area = tk.Canvas(main, bg=C['sunken'], height=90, highlightthickness=1,
                                  highlightbackground=C['line_strong'])
        self.fall_area.bind('<Configure>', lambda e: self._draw_falling())

        capture = ogl_frame(main, bg=C['canvas'])
        capture.pack(fill='x', padx=18, pady=(0, 5))
        self.input_var = tk.StringVar()
        self.typing_entry = tk.Entry(capture, textvariable=self.input_var, width=10,
                                     font=(FAMILY, 15), bg=C['sunken_alt'], fg=C['text_bright'],
                                     insertbackground=C['accent'], relief='flat', bd=0,
                                     highlightthickness=2, highlightbackground=C['control_line'],
                                     highlightcolor=C['accent'])
        self.typing_entry.pack(side='left', fill='x', expand=True, ipady=6)
        self.typing_entry.bind('<KeyPress>', self._on_key)
        self.typing_entry.bind('<Button-1>', lambda e: self.after_idle(self.focus_input), add='+')
        self.start_button = self._button(capture, 'START GAME', self._start, primary=True)
        self.start_button.pack(side='left', padx=(10,0))
        self.reset_button = self._button(capture, 'RESET', self._reset)
        self.reset_button.pack(side='left', padx=(6,0))

        self.keyboard = tk.Canvas(main, bg=C['canvas'], highlightthickness=0, height=147)
        self.keyboard.pack(fill='x', padx=18, pady=(2, 0))
        self.keyboard.bind('<Configure>', lambda e: self._draw_keyboard())
        info = ogl_frame(main, bg=C['canvas'])
        info.pack(fill='x', padx=20, pady=(1, 2))
        self.finger_label = self._label(info, 'INDEX FINGERS · F / J', 11, 'accent', bold=True)
        self.finger_label.pack(side='left')
        self.info_label = self._label(info, 'Focus: typing field', 10, 'text_2')
        self.info_label.pack(side='right')
        self.status = self._label(main, '', 11, 'text_2', wraplength=650, justify='left')
        # Feedback is displayed on the compact bottom line; an extra row would
        # be clipped by the original Oracle CRT's short glass aperture.
        self._main = main
        self._info_row = info
        self._compact = False
        self.bind('<Configure>', self._fit_layout)
        main.bind('<Button-1>', lambda e: self.after_idle(self.focus_input), add='+')

    def _fit_layout(self, event):
        """Compact the game UI when the actual Oracle viewport is small."""
        compact = event.height < 415
        narrow = event.width < 850
        if (compact, narrow) == getattr(self, '_fit_state', None):
            return
        self._fit_state = (compact, narrow)
        self._compact = compact
        self.rail.configure(width=175 if narrow else 225)
        self.rail_title.configure(font=(FAMILY, 15 if narrow else 19, 'bold'))
        self.rail_subtitle.configure(text='LEARN · PLAY' if narrow else 'LEARN · PLAY · IMPROVE')
        short_names = ('HOME ROW', 'SPRINT', 'KEYFALL', 'SENTENCES')
        for i, mode in enumerate(MODES):
            self.mode_buttons[mode].configure(text='%02d  %s' % (i + 1, short_names[i])
                                              if narrow else '%02d   %s' % (i + 1, MODE_NAMES[i]))
        if compact:
            self.keyboard.pack_forget()
            self.description.pack_forget()
        else:
            self.description.pack(fill='x', padx=20, pady=(0, 6),
                                  after=self._main.winfo_children()[0])
            self.keyboard.pack(fill='x', padx=18, pady=(2, 0), before=self._info_row)
        if narrow:
            self.reset_button.pack_forget()
            self.info_label.pack_forget()
        else:
            self.reset_button.pack(side='left', padx=(6, 0))
            self.info_label.pack(side='right')
        self._paint()
        self.after_idle(self.focus_input)

    def set_mode(self, mode):
        self.engine.set_mode(mode)
        self._saved_round_id = None
        self._recent_keys = ''
        self._paint()

    def change_lesson(self, name):
        self.engine.lesson = next((i for i,x in enumerate(LESSONS) if x[0] == name), 0)
        if self.engine.mode == 'keys':
            self.set_mode('keys')
        self.after_idle(self.focus_input)

    def _start(self):
        self.engine.pause() if self.engine.phase == 'running' else self.engine.start()

    def _reset(self):
        self.engine.reset()
        self._saved_round_id = None
        self._recent_keys = ''

    def focus_input(self):
        try:
            if self.winfo_ismapped():
                self.typing_entry.focus_set()
                self.typing_entry.icursor('end')
        except tk.TclError:
            pass

    def _on_key(self, event):
        if event.keysym == 'Escape':
            self.on_home()
            return 'break'
        if event.keysym == 'Tab':
            # Keep keyboard navigation available for switching controls.
            return None
        if event.keysym in ('BackSpace', 'Delete'):
            # No text correction via backspace: wrong attempts don't advance.
            return 'break'
        ch = event.char if event.char and event.char.isprintable() else ''
        if ch:
            result = self.engine.press(ch)
            if result != 'inactive':
                self._recent_keys = (self._recent_keys + ('·' if ch == ' ' else ch))[-32:]
                self._paint()
        return 'break'

    def _save_result(self):
        e = self.engine
        if e.phase != 'complete' or self._saved_round_id == e.round_id:
            return
        # A score is meaningful only after some input; keep one record per run.
        row = self.stats.get(e.mode, {})
        if not isinstance(row, dict):
            row = {}
        row['sessions'] = int(row.get('sessions', 0)) + 1
        row['best_wpm'] = round(max(float(row.get('best_wpm', 0)), e.wpm), 1)
        row['best_accuracy'] = round(max(float(row.get('best_accuracy', 0)), e.accuracy if e.correct else 0), 1)
        row['best_score'] = max(int(row.get('best_score', 0)), e.score)
        self.stats[e.mode] = row
        save_json('touch_type_scores.json', self.stats)
        self._saved_round_id = e.round_id

    def _paint_target(self):
        e = self.engine
        # Use middle-dot for whitespace: the prompt and its logical indices still match.
        visual = e.prompt.replace(' ', '·')
        widget = self.prompt_text
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('end', visual[:e.index], 'done')
        if e.index < len(visual):
            widget.insert('end', visual[e.index], 'next')
            widget.insert('end', visual[e.index+1:], 'remaining')
        widget.configure(state='disabled')
        self.progress_label.configure(text='%d / %d' % (e.index, len(e.prompt)))

    def _draw_falling(self):
        e = self.engine
        c = self.fall_area
        if not c.winfo_exists():
            return
        c.delete('all')
        w = max(200,c.winfo_width())
        h = max(90,c.winfo_height())
        frac = e.fall_progress if e.mode == 'fall' else 0
        c.create_line(12, h-15, w-12, h-15, fill=C['failed'], width=2)
        c.create_text(w/2, 12+(h-42)*frac, text=e.prompt.replace(' ', '·'),
                      anchor='n', fill=C['text_bright'], font=(FAMILY, 18, 'bold'))
        c.create_rectangle(12,h-7,12+(w-24)*frac,h-4,fill=C['accent'],outline='')

    def _draw_keyboard(self):
        c = self.keyboard
        if not c.winfo_exists():
            return
        c.delete('all')
        w = max(200, c.winfo_width())
        e = self.engine
        unit = min(57.0, (w-14)/11.0)
        kw = max(13,unit-5)
        rows = [('qwertyuiop',0.1),('asdfghjkl;',0.52),('zxcvbnm,./',0.23)]
        for ri,(chars,offset) in enumerate(rows):
            row_w = len(chars)*unit
            x0 = (w-row_w)/2 + offset*unit
            y0 = 2+ri*39
            for j,ch in enumerate(chars):
                x = x0+j*unit
                active = ch == e.expected
                home = ch in 'asdfjkl;'
                bg = C['accent'] if active else C['control'] if home else C['raised']
                fg = C['text_on_accent'] if active else C['text_bright'] if home else C['text_2']
                c.create_rectangle(x,y0,x+kw,y0+33,fill=bg,
                                   outline=C['accent'] if active else C['control_line'],width=1)
                c.create_text(x+kw/2,y0+17,text=ch.upper(),font=(FAMILY,11,'bold'),fill=fg)
        space_on = e.expected == ' '
        ww = min(w*0.4, 250)
        x = (w-ww)/2
        c.create_rectangle(x,122,x+ww,145,fill=C['accent'] if space_on else C['control'],
                           outline=C['accent'] if space_on else C['control_line'])
        c.create_text(w/2,133,text='SPACE · THUMBS',font=(FAMILY,10,'bold'),
                      fill=C['text_on_accent'] if space_on else C['text_2'])

    def _paint(self):
        e = self.engine
        self._save_result()
        self.mode_title.configure(text=MODE_NAMES[MODES.index(e.mode)])
        self.description.configure(text=MODE_DETAILS[MODES.index(e.mode)])
        self.phase_label.configure(text=e.phase.upper(),
                                   foreground=C['done'] if e.phase == 'complete' else C['accent'])
        for mode, b in self.mode_buttons.items():
            chosen = mode == e.mode
            b.configure(bg=C['accent_soft'] if chosen else C['control'],
                        fg=C['accent'] if chosen else C['text'],
                        highlightbackground=C['accent'] if chosen else C['control_line'])
        self.lesson_menu.configure(state='normal' if e.mode == 'keys' else 'disabled')
        self.stat_labels['wpm'].configure(text='%.0f' % e.wpm)
        self.stat_labels['accuracy'].configure(text='%.0f%%' % e.accuracy)
        self.stat_labels['score'].configure(text=str(e.completed))
        if e.mode == 'words':
            time_text = '%02d s' % max(0,int(60-e.elapsed))
        elif e.mode == 'fall':
            time_text = '%d ♥' % e.lives
        else:
            time_text = '%02d s' % int(e.elapsed)
        self.stat_labels['time'].configure(text=time_text)
        action = ('PAUSE' if e.phase == 'running' else
                  'RESUME' if e.phase == 'paused' else
                  'PLAY AGAIN' if e.phase == 'complete' else 'START GAME')
        if getattr(self, '_fit_state', (False,False))[1]:
            action = {'START GAME':'START', 'PLAY AGAIN':'AGAIN'}.get(action, action)
        self.start_button.configure(text=action)
        self.finger_label.configure(text=finger_for(e.expected))
        self.status.configure(text=e.message)
        self.info_label.configure(text=e.message if len(e.message) < 33 else e.message[:30] + '…')
        self.input_var.set(self._recent_keys if e.phase in ('running','paused') else
                           'TYPE HERE · SELECT START GAME' if e.phase == 'ready' else
                           'ROUND COMPLETE · PLAY AGAIN')
        best = self.stats.get(e.mode, {})
        self.best_label.configure(text='BEST  %s WPM  ·  %s pts' %
                                  (best.get('best_wpm','—'),best.get('best_score','—')))
        self._paint_target()
        self._draw_keyboard()
        if e.mode == 'fall':
            if not self.fall_area.winfo_manager():
                self.fall_area.pack(fill='x', padx=18, pady=(0,9), before=self.typing_entry.master)
            self._draw_falling()
        elif self.fall_area.winfo_manager():
            self.fall_area.pack_forget()

    def _schedule(self):
        if self._after_id is not None:
            return
        self._after_id = self.after(80, self._tick)

    def _tick(self):
        self._after_id = None
        if not self.winfo_exists():
            return
        e = self.engine
        if e.phase == 'running':
            e.tick()
            self._paint()
        if self.winfo_ismapped():
            self._schedule()

    def suspend(self):
        self.engine.pause()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def resume_panel(self):
        ogl_install(self)  # Oggcultist may have switched ttk to its clam theme.
        self._paint()
        self._schedule()
        self.after_idle(self.focus_input)

    def shutdown(self):
        self.suspend()


class EmbeddedTouchType:
    def __init__(self, canvas, on_home):
        self.canvas = canvas
        self.frame = TouchTypePanel(canvas, on_home=on_home)
        self.window = canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                           tags=('touchwin', 'touch-type-tab'))
        self._box = None

    def layout(self, box):
        self._box = box
        x0,y0,x1,y1 = box
        if not self.canvas.type(self.window):
            self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                                    tags=('touchwin', 'touch-type-tab'))
        self.canvas.coords(self.window, x0, y0)
        self.canvas.itemconfigure(self.window, width=max(100,x1-x0),
                                  height=max(100,y1-y0),state='normal')
        self.canvas.tag_raise(self.window)
        self.frame.resume_panel()

    def clear(self):
        self.frame.suspend()
        if self.canvas.type(self.window):
            self.canvas.itemconfigure(self.window,state='hidden')

    def shutdown(self):
        self.frame.shutdown()

    def key(self, keysym, char=''):
        if keysym.lower() in ('escape','esc'):
            return 'close'
        return None
