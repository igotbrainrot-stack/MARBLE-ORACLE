"""Marble Passphrase UI embedded in Marble Oracle as its Passphrase tab.

Offline Tkinter shell for the original Dicekey engine. No account, network,
password history, or external Python packages are required.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from oracle_dicekey import Dicekey, PARTS, PART_NAMES
from marble_uberata import FAMILY, apply_tk_fonts
from oracle_ogg_texture import frame as ogl_frame


ROOT = Path(__file__).resolve().parent
# Oggcultist Ember palette: one warm dark visual language across all three apps.
from oggcultist_design_system import COLOR as OGG
import oracle_shell as shell
BG = OGG["canvas"]
PANEL = OGG["raised"]
CARD = OGG["sunken_alt"]
BORDER = OGG["line_strong"]
TEXT = OGG["text"]
MUTED = OGG["text_2"]
CYAN = OGG["accent"]
AMBER = OGG["accent"]
INSET = OGG["sunken"]


CLIPBOARD_CLEAR_MS = 60_000
CARDS_COMPACT = 640      # card-row width (px) below which cards use tighter padding and gaps
CARDS_ONE_ROW = 540       # card-row width (px) below which the five parts wrap onto two rows


def action_button(parent, label, command, *, primary=False, **_legacy):
    """The suite button (oracle_shell). Extra legacy styling arguments are ignored."""
    return shell.button(parent, label, command, primary=primary)


class PassphrasePanel(tk.Frame):
    """Marble Passphrase in the suite page shell (oracle_shell).

    Rail: name, options, keyboard shortcuts, privacy notes and HOME at the
    foot, like every other workspace. Main: the page title with the strength
    badge, the five parts, the full phrase, the actions and the status line.
    The whole workspace stays embedded inside Oracle's overlay; it never
    spawns a second app window.
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
        # The rail holds extras only (options, keys, privacy), so in the
        # smallest windows it steps aside and the parts keep one row.
        self.shell = shell.Shell(self, collapsible=True)
        rail, main = self.shell.rail, self.shell.main

        self.home_button, _version = self.shell.home(self._home, "EFF WORDLIST · LOCAL")
        self.shell.brand("PASSPHRASE", "OFFLINE · NO HISTORY")

        self.shell.group("OPTIONS")
        dice = tk.Checkbutton(rail, text="SHOW DICE CODES", variable=self.show_dice,
                       command=self._refresh, bg=OGG["sidebar"], fg=OGG["text"],
                       activebackground=OGG["sidebar"], activeforeground=OGG["accent"],
                       selectcolor=OGG["sunken"], font=shell.font("body"), anchor="w",
                       borderwidth=0, highlightthickness=0, justify="left")
        dice.pack(fill="x", padx=shell.RAIL_PADX - 2)

        self.shell.group("KEYS")
        keys = ogl_frame(rail, bg=OGG["sidebar"])
        keys.pack(fill="x", padx=shell.RAIL_PADX)
        keys.grid_columnconfigure(0, minsize=64)
        meanings = []
        for row, (key, meaning) in enumerate((("R", "roll a new phrase"), ("S", "swap words 1, 2"),
                                              ("1 – 5", "reroll one part"), ("CTRL+C", "copy"))):
            shell.label(keys, key, "body_bold", "accent").grid(row=row, column=0, sticky="w", pady=1)
            meanings.append(shell.label(keys, meaning, "small", "text_2", justify="left"))
            meanings[-1].grid(row=row, column=1, sticky="w", pady=1)

        def fit_rail(_event=None):
            # A narrow rail wraps the key meanings and the option instead of cutting them off.
            room = keys.winfo_width()
            if room > 1:
                for meaning in meanings:
                    meaning.configure(wraplength=max(40, room - 68))
                dice.configure(wraplength=max(60, room - 28))
        keys.bind("<Configure>", fit_rail, add="+")

        self.shell.group("PRIVACY")
        self.shell.rail_text("Nothing is saved or sent. Copy is explicit, and the clipboard is cleared after 60 seconds.")

        self.bits_text = f"~{self.engine.bits:.1f} BITS"
        _title, _sub, right = self.shell.header(
            "YOUR PASSPHRASE",
            "Three words, a number and a symbol. Reroll any part, or roll a whole new phrase.")
        shell.chip(right, self.bits_text).pack(side="right")

        self.status_label = self.shell.status(textvariable=self.status, wraplength=1000)

        body = ogl_frame(main, bg=BG)
        body.pack(fill="both", expand=True, padx=shell.MAIN_PADX, pady=(0, 8))

        cards = ogl_frame(body, bg=BG)
        cards.pack(fill="x")
        self.part_labels = {}
        self.dice_labels = {}
        self._cards = []
        self._card_columns = None
        self._cards_frame = cards
        for i, part in enumerate(PARTS):
            card = ogl_frame(cards, bg=PANEL, highlightbackground=BORDER,
                             highlightthickness=1, padx=10, pady=12)
            self._cards.append(card)
            shell.label(card, PART_NAMES[part], "group", "text_3").pack(anchor="w")
            # width=1: the word never sets the card's width (the five columns
            # share the row equally); _part_font fits the word to the card.
            value = shell.label(card, "", "section", "text" if i < 3 else "accent", anchor="w", width=1)
            value.pack(fill="x", pady=(10, 2))
            value.bind("<Configure>", self._refit_parts, add="+")
            self.part_labels[part] = value
            dice = shell.label(card, " ", "small", "text_3", anchor="w", width=1)
            dice.pack(fill="x", pady=(0, 10))
            self.dice_labels[part] = dice
            # Pinned to the card's foot so the five buttons line up whatever size each word is drawn at.
            shell.button(card, f"REROLL {i + 1}", lambda p=part: self.reroll(p),
                         padx=6).pack(side="bottom", fill="x")
        self._arrange_cards(5)
        cards.bind("<Configure>", self._cards_resized, add="+")

        strip = ogl_frame(body, bg=BG)
        strip.pack(fill="x", pady=(18, 0))
        shell.label(strip, "FULL PHRASE", "group", "text_3").pack(anchor="w")
        self.entry = tk.Entry(strip, textvariable=self.full_phrase, state="readonly",
                              readonlybackground=INSET, fg=OGG["text_bright"],
                              selectbackground=OGG["accent_soft"],
                              font=(FAMILY, 18, "bold"), relief="flat", borderwidth=0,
                              highlightthickness=1, highlightbackground=BORDER)
        self.entry.pack(fill="x", ipady=10, pady=(6, 0))

        controls = ogl_frame(body, bg=BG)
        controls.pack(fill="x", pady=(14, 0))
        action_button(controls, "ROLL NEW   [R]", self.roll, primary=True).pack(side="left", padx=(0, 8))
        action_button(controls, "SWAP 1 / 2   [S]", self.swap).pack(side="left", padx=(0, 8))
        self.copy_button = action_button(controls, "COPY   [CTRL+C]", self.copy)
        self.copy_button.pack(side="left")
        self._build_strength(body)

    def _build_strength(self, body):
        """How the phrase's strength adds up, part by part (0.5.4): the engine's own figures, in the space
        that was left empty under the controls. Shown only when the page has the height for it."""
        box = ogl_frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        self.strength_box = box
        shell.label(box, "HOW STRONG IS IT", "group", "text_3").pack(anchor="w")
        parts = self.engine.breakdown()
        total = sum(bits for _part, bits, _how in parts)
        grid = ogl_frame(box, bg=PANEL)
        grid.pack(fill="x", pady=(8, 6))
        grid.grid_columnconfigure(2, weight=1)
        self._strength_bars = []
        for row, (part, bits, how) in enumerate(parts):
            shell.label(grid, PART_NAMES[part], "small", "text_2", anchor="w").grid(row=row, column=0, sticky="w",
                                                                                    padx=(0, 12), pady=2)
            shell.label(grid, f"{bits:.1f} bits", "small", "text", anchor="e").grid(row=row, column=1, sticky="e",
                                                                                     padx=(0, 12), pady=2)
            bar = tk.Canvas(grid, height=8, bg=PANEL, highlightthickness=0, bd=0)
            bar.grid(row=row, column=2, sticky="ew", pady=2)
            bar._share = bits / total if total else 0
            self._strength_bars.append(bar)
            bar.bind("<Configure>", lambda e, b=bar: self._draw_share(b), add="+")
            shell.label(grid, how, "small", "text_3", anchor="w").grid(row=row, column=3, sticky="w", padx=(12, 0),
                                                                        pady=2)
        note = shell.label(box, f"Total {total:.1f} bits: about 2^{total:.0f} equally likely phrases. That is the "
                                "strength of the method when a phrase is used as rolled, not a time to crack it; "
                                "rerolling parts you dislike lowers it a little.", "small", "text_2", anchor="w",
                           justify="left")
        note.pack(fill="x")
        box.bind("<Configure>", lambda e: note.configure(wraplength=max(200, e.width - 30)), add="+")
        body.bind("<Configure>", self._fit_strength, add="+")

    def _draw_share(self, bar):
        bar.delete("all")
        width = bar.winfo_width()
        if width <= 1:
            return
        bar.create_rectangle(0, 2, width, 6, fill=OGG["control"], outline="")
        bar.create_rectangle(0, 2, max(2, width * bar._share * 2.5), 6, fill=OGG["accent"], outline="")

    def _fit_strength(self, _event=None):
        """Shown below the controls when the page has room for it; a short window keeps its height for the
        phrase itself."""
        box = self.strength_box
        body = box.master
        used = sum(child.winfo_reqheight() + 14 for child in body.pack_slaves() if child is not box)
        fits = body.winfo_height() - used >= box.winfo_reqheight() + 24
        if fits and not box.winfo_manager():
            box.pack(fill="x", pady=(22, 0))
        elif not fits and box.winfo_manager():
            box.pack_forget()

    def _home(self):
        if self.on_home is not None:
            self.on_home()

    def _refresh(self):
        parts = self.engine.split(self.phrase)
        if parts is None:
            return
        for part, value in zip(PARTS, parts):
            label = self.part_labels[part]
            label.configure(text=value, font=self._part_font(label, value))
            code = self.engine.dice(value) if part.startswith("w") and self.show_dice.get() else ""
            self.dice_labels[part].configure(text=code if code else " ")
        self.full_phrase.set(self.phrase)

    def _cards_resized(self, event):
        # The widest list word ("mammogram") needs about 98 px at the 10 pt
        # minimum; tighter padding keeps it whole in the 640x460 window.
        compact = event.width < CARDS_COMPACT
        if compact != getattr(self, "_cards_compact", None):
            self._cards_compact = compact
            for card in self._cards:
                card.configure(padding=(5 if compact else 10, 12))
            self._card_columns = None
        self._arrange_cards(5 if event.width >= CARDS_ONE_ROW else 3)

    def _arrange_cards(self, columns):
        """Five cards in a row, or (in a narrow workspace) the three words above the number and symbol."""
        if columns == self._card_columns:
            return
        self._card_columns = columns
        gap = 5 if getattr(self, "_cards_compact", False) else 8
        for column in range(5):
            self._cards_frame.grid_columnconfigure(column, weight=1 if column < columns else 0,
                                                   uniform="parts" if column < columns else "")
        for i, card in enumerate(self._cards):
            row, column = divmod(i, columns)
            last = column == columns - 1 or i == len(self._cards) - 1
            card.grid(row=row, column=column, sticky="nsew",
                      padx=(0, 0 if last else gap), pady=(0 if row == 0 else gap, 0))

    def _part_font(self, label, value):
        """The largest of 18-10 pt (10 pt is the suite minimum) at which `value` fits its card."""
        width = label.winfo_width()
        if width <= 1:
            width = 120                      # not laid out yet; refitted on <Configure>
        for size in (18, 16, 14, 13, 12, 11, 10):
            spec = (FAMILY, size, "bold")
            # `font measure` keeps no Tk font object alive (see FontMeasure in AUGURSPEX).
            if int(self.tk.call("font", "measure", spec, value)) <= width - 1:
                return spec
        return (FAMILY, 10, "bold")

    def _refit_parts(self, _event=None):
        parts = self.engine.split(self.phrase) if self.phrase else None
        if parts is None:
            return
        for part, value in zip(PARTS, parts):
            label = self.part_labels[part]
            font = self._part_font(label, value)
            if str(label.cget("font")) != str(font):
                label.configure(font=font)

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

    def _clear_clipboard(self, copied):
        """Clear the clipboard only if it still holds the phrase we put there."""
        self.clip_clear = None
        try:
            top = self.winfo_toplevel()
            if top.clipboard_get() == copied:
                top.clipboard_clear()
                top.clipboard_append("")
                top.update_idletasks()
                self.status.set("Clipboard cleared.")
        except tk.TclError:
            pass

    def copy(self):
        self.winfo_toplevel().clipboard_clear()
        self.winfo_toplevel().clipboard_append(self.phrase)
        self.update_idletasks()
        self.status.set("Copied. The clipboard is cleared in 60 seconds. Nothing was saved to a file or sent online.")
        copied = self.phrase
        if getattr(self, "clip_clear", None) is not None:
            self.after_cancel(self.clip_clear)
        self.clip_clear = self.after(CLIPBOARD_CLEAR_MS, lambda: self._clear_clipboard(copied))
        self.copy_button.configure(text="COPIED")
        if self.copy_reset is not None:
            self.after_cancel(self.copy_reset)
        self.copy_reset = self.after(1600, lambda: self.copy_button.configure(text="COPY   [CTRL+C]"))


