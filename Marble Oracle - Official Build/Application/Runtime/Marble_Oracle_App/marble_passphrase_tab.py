"""Marble Passphrase UI embedded in Marble Oracle as its Passphrase tab.

Offline Tkinter shell for the original Dicekey engine. No account, network,
password history, or external Python packages are required.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

from oracle_dicekey import Dicekey, NoWords, PARTS, PART_NAMES
from marble_uberata import FAMILY, apply_tk_fonts
from oracle_ogg_texture import frame as ogl_frame, label as ogl_label


ROOT = Path(__file__).resolve().parent
# Oggcultist Ember palette: one warm dark visual language across all three apps.
from oggcultist_design_system import COLOR as OGG
BG = OGG["canvas"]
PANEL = OGG["raised"]
CARD = OGG["sunken_alt"]
BORDER = OGG["line_strong"]
TEXT = OGG["text"]
MUTED = OGG["text_2"]
CYAN = OGG["accent"]
AMBER = OGG["accent"]
INSET = OGG["sunken"]


def action_button(parent, label, command, *, color=TEXT, fill="#2F2620", pady=8, primary=False):
    """Oggcultist Ember: boxed, restrained secondary actions and one orange primary."""
    if primary:
        color, fill = "#2B1405", "#FB8E22"
    btn = tk.Button(
        parent, text=label, command=command, font=(FAMILY, 11, "bold"),
        fg=color, bg=fill, activeforeground="#FFF4E6" if not primary else "#2B1405",
        activebackground="#372A23" if not primary else "#FDA629",
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground="#59473B" if not primary else "#FB8E22",
        highlightcolor="#FB8E22", cursor="hand2", padx=16, pady=pady,
        takefocus=True,
    )
    return btn


class PassphrasePanel(tk.Frame):
    """Original Marble Passphrase five-card layout in the Oracle Ember palette.

    The whole passphrase workspace stays embedded inside Oracle's existing
    overlay; the Back button is supplied by Oracle rather than spawning a
    second app window.
    """
    def __init__(self, master, engine: Dicekey, on_home=None):
        super().__init__(master, bg=BG)
        apply_tk_fonts(self.winfo_toplevel())
        self.engine = engine
        self.on_home = on_home
        self.phrase = ""
        self.has_rerolled = False
        self.copy_reset = None
        self.show_dice = tk.BooleanVar(master=self, value=False)
        self.status = tk.StringVar(master=self, value="Ready. Every new roll uses the system's cryptographic random source.")
        self.full_phrase = tk.StringVar(master=self)
        self._draw()
        self.roll()

    def _draw(self):
        # Same hierarchy as original marble_passphrase.py: header, five
        # horizontal parts, complete phrase, bottom actions and status.
        outer = ogl_frame(self, bg=BG, padx=20, pady=13)
        outer.pack(fill="both", expand=True)
        top = ogl_frame(outer, bg=BG)
        top.pack(fill="x")
        heading = ogl_frame(top, bg=BG)
        heading.pack(side="left", fill="x", expand=True)
        ogl_label(heading, text="MARBLE  /  PASSPHRASE", fg=TEXT, bg=BG,
                 font=(FAMILY, 23, "bold")).pack(anchor="w")
        ogl_label(heading, text="OFFLINE PASSWORD GENERATOR     •     EFF LONG WORDLIST     •     NO HISTORY",
                 fg=CYAN, bg=BG, font=(FAMILY, 10)).pack(anchor="w", pady=(3, 0))
        self.home_button = action_button(top, "←  BACK TO ORACLE", self._home,
                                         color=TEXT, fill=CARD, pady=8)
        self.home_button.pack(side="right", anchor="n", padx=(12, 0))

        main = ogl_frame(outer, bg=PANEL, highlightbackground=BORDER,
                        highlightthickness=1, padx=15, pady=13)
        main.pack(fill="both", expand=True, pady=(13, 10))
        header = ogl_frame(main, bg=PANEL)
        header.pack(fill="x", pady=(0, 10))
        ogl_label(header, text="YOUR PASSPHRASE", fg=AMBER, bg=PANEL,
                 font=(FAMILY, 12, "bold")).pack(side="left")
        ogl_label(header, text=f"~{self.engine.bits:.1f} BITS / ORIGINAL PATTERN",
                 fg=MUTED, bg=PANEL, font=(FAMILY, 9)).pack(side="right")

        cards = ogl_frame(main, bg=PANEL)
        cards.pack(fill="both", expand=True)
        cards.grid_rowconfigure(0, weight=1)
        self.part_labels = {}
        self.dice_labels = {}
        for i, part in enumerate(PARTS):
            cards.grid_columnconfigure(i, weight=1, uniform="parts")
            card = ogl_frame(cards, bg=CARD, highlightbackground=BORDER,
                            highlightthickness=1, padx=8, pady=10)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 6 if i < 4 else 0))
            ogl_label(card, text=PART_NAMES[part], fg=MUTED, bg=CARD,
                     font=(FAMILY, 9, "bold")).pack(anchor="w")
            value = ogl_label(card, text="", fg=TEXT if i < 3 else AMBER,
                             bg=CARD, font=(FAMILY, 17, "bold"),
                             anchor="w", pady=12)
            value.pack(fill="x")
            self.part_labels[part] = value
            dice = ogl_label(card, text="", fg=CYAN, bg=CARD,
                            font=(FAMILY, 9), anchor="w")
            dice.pack(fill="x", pady=(0, 8))
            self.dice_labels[part] = dice
            action_button(card, f"REROLL {i + 1}", lambda p=part: self.reroll(p),
                          color=TEXT, fill=OGG["control"], pady=6).pack(fill="x", side="bottom")

        strip = ogl_frame(main, bg=PANEL)
        strip.pack(fill="x", pady=(12, 0))
        ogl_label(strip, text="FULL PHRASE", bg=PANEL, fg=MUTED,
                 font=(FAMILY, 9, "bold")).pack(anchor="w")
        self.entry = tk.Entry(strip, textvariable=self.full_phrase, state="readonly",
                              readonlybackground=INSET, fg=TEXT,
                              selectbackground=OGG["accent_soft"],
                              font=(FAMILY, 15), relief="flat", borderwidth=0,
                              highlightthickness=1, highlightbackground=BORDER)
        self.entry.pack(fill="x", ipady=9, pady=(5, 0))

        controls = ogl_frame(outer, bg=BG)
        controls.pack(fill="x")
        action_button(controls, "ROLL NEW   [R]", self.roll, primary=True).pack(side="left", padx=(0, 8))
        action_button(controls, "SWAP 1 / 2   [S]", self.swap, color=TEXT).pack(side="left", padx=(0, 8))
        self.copy_button = action_button(controls, "COPY   [CTRL+C]", self.copy)
        self.copy_button.pack(side="left")
        tk.Checkbutton(controls, text="SHOW DICE CODES", variable=self.show_dice,
                       command=self._refresh, bg=BG, fg=MUTED, activebackground=BG,
                       activeforeground=CYAN, selectcolor=BG, font=(FAMILY, 9),
                       borderwidth=0, highlightthickness=0).pack(side="right")
        ogl_label(outer, textvariable=self.status, bg=BG, fg=CYAN,
                 font=(FAMILY, 10), anchor="w", wraplength=1000).pack(fill="x", pady=(8, 3))
        ogl_label(outer, text="1–5 reroll one part   •   Swap only changes word order   •   Copy is explicit   •   No network or saved phrases",
                 bg=BG, fg=MUTED, font=(FAMILY, 9), anchor="w").pack(fill="x")

    def _home(self):
        if self.on_home is not None:
            self.on_home()

    @staticmethod
    def _shortcut(fn):
        fn()
        return "break"

    def _refresh(self):
        parts = self.engine.split(self.phrase)
        if parts is None:
            return
        for part, value in zip(PARTS, parts):
            label = self.part_labels[part]
            label.configure(text=value, font=(FAMILY, 14 if len(value) > 12 else 18, "bold"))
            code = self.engine.dice(value) if part.startswith("w") and self.show_dice.get() else ""
            self.dice_labels[part].configure(text=code if code else " ")
        self.full_phrase.set(self.phrase)

    def roll(self):
        self.phrase = self.engine.roll()
        self.has_rerolled = False
        self.status.set("New phrase generated. SWAP changes order without drawing new values.")
        self._refresh()

    def swap(self):
        self.phrase = self.engine.swap_first_two(self.phrase)
        self.status.set("Swapped words 1 and 2. Word 3, number and symbol are unchanged.")
        self._refresh()

    def reroll(self, part):
        self.phrase, note = self.engine.reroll(self.phrase, part)
        self.has_rerolled = True
        self.status.set(note or f"Re-rolled {PART_NAMES[part].lower()}. Personal rerolls change the original selection distribution.")
        self._refresh()

    def copy(self):
        self.winfo_toplevel().clipboard_clear()
        self.winfo_toplevel().clipboard_append(self.phrase)
        self.update_idletasks()
        self.status.set("Copied to clipboard. Nothing was saved to a file or sent online.")
        self.copy_button.configure(text="COPIED")
        if self.copy_reset is not None:
            self.after_cancel(self.copy_reset)
        self.copy_reset = self.after(1600, lambda: self.copy_button.configure(text="COPY   [CTRL+C]"))


