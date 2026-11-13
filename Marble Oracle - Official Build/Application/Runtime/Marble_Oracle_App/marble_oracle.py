#!/usr/bin/env python3
"""Marble_Oracle -- a 90s-CRT desktop toy.  Python 3 + tkinter + stdlib only.

v4.0 "TRANSMISSION" layout: flat dark sci-fi panels (title bar, menu,
MARBLE ARCHIVE, LEXICON, TRANSMISSION, AUGURSPEX HISTORY, THREE CARDS).  Everything optional (marketdata, oracle_dicekey, *.zip
assets) degrades silently; a broken plug-in never stops startup.

Hotkeys: SPACE next   ENTER speak   N word   T deal   K Passphrase Studio tab
         F size   V view   C crt   E voice   M housing   ESC quit
Flags:   --fps N --wallpaper --fullscreen --theme NAME --layout NAME --no-dicekey --calm
         --no-bezel --os-frame --no-markets --no-network
         --selftest --version --install-startup --remove-startup
"""
import base64
import datetime
import json
import math
import os
import random
import sys
import time

VERSION = "4.1"
VERSION_NAME = "CRT V2 - Integrated"
BUILD = "V2.9"
TITLE = "Marble_Oracle"
HERE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
REF_W, REF_H = 1216, 848

# MARBLE ARCHIVE shading ramp (from 3.8): position in the character ramp -> colour; the two fringes sit behind the stone
MARBLE = ["#3a2f68", "#50469a", "#6c63bd", "#918dd8", "#b0b2e8", "#cbd2f4", "#e0e9fb", "#f1f7ff", "#fbfdff", "#ffffff"]
GHOST_M = "#57094f"     # pink fringe
GHOST_C = "#08394a"     # cyan fringe
if HERE not in sys.path:
    sys.path.insert(0, HERE)
# GitHub source checkouts reassemble large verified media archives on first run.
# Complete release ZIPs already have the assets; this is a no-op for them.
from oracle_asset_recovery import restore_missing_assets
restore_missing_assets(HERE)
import oracle_assets  # noqa: E402  (the shared kernel: asset search, state dir, packed sounds)
from oracle_assets import rgba_png  # noqa: E402,F401
from oracle_chrome import (DECK_TAB_OFF, DECK_TAB_ON, DK_TAB_OFF, DK_TAB_ON, LD_TAB_OFF, LD_TAB_ON, TAB_INK, TAB_EDGE, TAB_SLOPE, tab_ink, TAB_GAP, TAB_MIN_PX,  # noqa: E402,F401
                           THEMES, THEME_NAMES, noise_tile_png, scan_tile_png, hexrgb, mix, ChromeMixin, bezel_geometry, bezel_step)
from oracle_skin import SkinMixin, hexmix  # noqa: E402
from oracle_augurspex_home import MarketCarousel
from oracle_feeds import MarketFeed, NEWS_FEEDS, parse_headlines, WireFeed  # noqa: E402,F401
from oracle_audio import respell, synth_wav, VoiceBank, Sfx  # noqa: E402,F401
try:
    import oracle_latin  # noqa: E402  (build 0955: IPA for the words that have none of their own; optional)
except Exception:
    oracle_latin = None
from oracle_media import (MAJOR, SUITS, RANKS, tarot_card, TarotImages,   # noqa: E402,F401
                          Statue)

# --------------------------------------------------------------------------- themes
# Build 0940: VIEW cycles presets, each a colour scheme (oracle_chrome.THEMES) and a layout -- where the panels sit.
# Every layout keeps each panel's size (REF_W x REF_H units), so nothing inside a panel is re-flowed: the statue,
# lexicon, transmission, markets and cards columns and the forecast strip only change places.
# 1058: THE LIEN's strip ("prog") is gone from every layout (1052 dropped it at build time; drop_lien is retired).  LOW and MIRROR LOW
# only moved that strip, so they are now CLASSIC and MIRROR again; the names stay for --layout and saved views.  The gutters are 8 again
# (drop_lien's stretch left 10 and 11, so the flush PANES look showed a 3 px seam between stacked panels).
# Home dashboard: one small AUGURSPEX chart replaces the retired static market panel.
# The old news marquee remains removed. GRADE also repositions this live-data chart.
_CLASSIC = dict(arch=(8, 86, 300, 497), lex=(8, 505, 300, 772), trans=(308, 86, 792, 772), aug=(800, 86, 1208, 379), cards=(800, 387, 1208, 772))
# the side columns swap: chart and cards on the left, the statue and lexicon on the right
_MIRROR = dict(aug=(8, 86, 416, 379), cards=(8, 387, 416, 772), trans=(424, 86, 908, 772), arch=(916, 86, 1208, 497), lex=(916, 505, 1208, 772))
LAYOUTS = {
    "CLASSIC": _CLASSIC,
    "MIRROR": _MIRROR,
    "LOW": _CLASSIC,
    "MIRROR LOW": _MIRROR,
    # each column turns over: the lexicon above the statue, the cards above the AUGURSPEX chart
    "SWAP": dict(lex=(8, 86, 300, 353), arch=(8, 361, 300, 772), trans=(308, 86, 792, 772), cards=(800, 86, 1208, 470), aug=(800, 478, 1208, 772)),
    # 1059: THE WIRE moves to an edge, each panel keeping its size
    "WIRE LEFT": dict(trans=(8, 86, 492, 772), arch=(500, 86, 792, 497), lex=(500, 505, 792, 772), aug=(800, 86, 1208, 379), cards=(800, 387, 1208, 772)),
    "WIRE RIGHT": dict(aug=(8, 86, 416, 379), cards=(8, 387, 416, 772), arch=(424, 86, 716, 497), lex=(424, 505, 716, 772), trans=(724, 86, 1208, 772)),
}
# 1034: the clean look's GRADE cycle; 1050: NEON; 1051: NEON first, the default.  1059 (the owner: "make OLED look default and remove every
# other option", then "remove the colour changes from grade options and just shuffle arund the sectios"): one scheme, NEON on OLED black;
# GRADE only moves the panels.
CLEAN_THEME = "EMBER"
# 1064 (the owner: "make it so that the ascii art marble statues shift in the grad options to be the same size as the WIRE section"): the
# clean look's GRADE layouts give PLATE VAULT and THE WIRE twin full-height columns; AUGURSPEX, DEAD TONGUE and THREE CUTS stack in the
# third.  --retro and --flat keep LAYOUTS.
_COL = dict(aug=(86, 290), lex=(298, 500), cards=(508, 772))
_COL_TURNED = dict(cards=(86, 350), lex=(358, 560), aug=(568, 772))
_TWIN = dict(arch=396, trans=396, col=392)            # column widths: the twins match wherever they stand


def _twins(order, col=_COL):
    """A clean layout: `order` names the three columns left to right, "arch", "trans" and "col" (the stack)."""
    out, x0 = {}, 8
    for name in order:
        x1 = x0 + _TWIN[name]
        if name == "col":
            out.update({n: (x0, y0, x1, y1) for n, (y0, y1) in col.items()})
        else:
            out[name] = (x0, 86, x1, 772)
        x0 = x1 + 8
    return out


# 1065 (the owner: "make it so the ascii art section can be larger but not always in the grad options. each section should have a Grade
# option where it is larger or smaller"): one GRADE layout per panel, each giving that panel the big middle column (STATUE: the 1064
# twins).  The old names still open their 1059 arrangement.
CLEAN_LAYOUTS = dict(LAYOUTS)
CLEAN_LAYOUTS.update({
    "CLASSIC": _CLASSIC,                                                    # THE WIRE large
    "STATUE": _twins(("arch", "trans", "col")),                             # PLATE VAULT large, THE WIRE's size
    "TICKER": dict(arch=(8, 86, 300, 497), lex=(8, 505, 300, 772), aug=(308, 86, 792, 772), trans=(800, 86, 1208, 470),
                   cards=(800, 478, 1208, 772)),
    "TONGUE": dict(arch=(8, 86, 300, 772), lex=(308, 86, 792, 470), cards=(308, 478, 792, 772), trans=(800, 86, 1208, 497),
                   aug=(800, 505, 1208, 772)),
    "CUTS": dict(arch=(8, 86, 300, 497), lex=(8, 505, 300, 772), cards=(308, 86, 868, 772), trans=(876, 86, 1208, 497),
                 aug=(876, 505, 1208, 772)),
})
for _n in ("STATUE", "TICKER", "TONGUE", "CUTS"):
    LAYOUTS.setdefault(_n, _CLASSIC)                                        # --retro and --flat: the names parse, CLASSIC shows
CLEAN_PRESETS = tuple((CLEAN_THEME, lay) for lay in ("CLASSIC", "STATUE", "TICKER", "TONGUE", "CUTS"))
VIEW_PRESETS = (("ONE", "CLASSIC"), ("TWO", "CLASSIC"), ("PHOSPHOR", "MIRROR"), ("AMBER", "LOW"),
                ("ARCTIC", "SWAP"), ("ORCHID", "MIRROR LOW"), ("TWO", "MIRROR"), ("ONE", "LOW"))


def is_retro(opts):
    """1034: the clean look is the default; --retro (the 1033 neon skin, the CRT case and scanlines) or --flat (the 1030 look) brings the old one."""
    return bool(opts.get("retro") or opts.get("flat"))


def view_presets(opts):
    return VIEW_PRESETS if is_retro(opts) else CLEAN_PRESETS


def resolve_view(opts):
    """Fill opts["theme"] / opts["layout"] / opts["view"] (the preset index, or None for a --theme outside the list).
    No --theme: the preset VIEW last left (state_dir()/view.json), else the first.  Idempotent."""
    if "view" in opts:
        return opts
    if not is_retro(opts) and opts.get("theme") is not None:
        opts["theme"] = CLEAN_THEME                  # 1059: the clean look has one scheme; --theme only picks --retro's colours
    if opts.get("theme") in THEMES:
        opts.setdefault("layout", "CLASSIC")
        if opts["layout"] not in LAYOUTS:
            opts["layout"] = "CLASSIC"
        pair = (opts["theme"], opts["layout"])
        presets = view_presets(opts)
        opts["view"] = presets.index(pair) if pair in presets else None
        return opts
    presets = view_presets(opts)
    saved = load_json("view.json", {})
    i = saved.get("preset" if is_retro(opts) else "clean", 0) if isinstance(saved, dict) else 0
    if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(presets):
        i = 0
    opts["theme"], opts["layout"] = presets[i]
    opts["view"] = i
    return opts


# 1036: the clean look's looks (the owner: "remove the window aesthetic ... integrated borders ... make sections of the window transparent ...
# multiple looks").  FLOAT, the default: no window, panels float with see-through gaps (Windows: -transparentcolor); PANES: one dark surface
# split by hairlines; GLASS: PANES with the whole window see-through (-alpha, where the system can); CARDS: the 1035 window of cards.
# 1038 (the owner: "add more options to LOOK"): CLEAR, the panels themselves see-through too, only their hairline edges and the text left;
# HAZE, FLOAT with the whole window a little see-through as well; OLED, PANES on pure black.
# 1051 (the owner: "remove all total transparency options"): FLOAT, CLEAR and HAZE, the looks that cut parts of the window out, are gone;
# PANES is the default.  GLASS stays (the whole window at GLASS_ALPHA, nothing cut out).  The old names are still accepted (startup
# entries and view.json) and open PANES.
# 1059 (the owner: "make OLED look default and remove every other option"): OLED is the one look.  PANES, GLASS and CARDS are retired
# like the 1051 three: their names still parse and open OLED.  A and Look are gone.
LOOKS = ("OLED",)
RETIRED_LOOKS = ("FLOAT", "CLEAR", "HAZE", "PANES", "GLASS", "CARDS")
SEE_THROUGH = ()                                 # 1036-1050: FLOAT, CLEAR, HAZE (Windows' -transparentcolor); none since 1051
LOOK_ALPHA = {}                                  # 1036-1058: GLASS faded the whole window; nothing is see-through since 1059
# HOME uses the same genuine Oggcultist sidebar surface as its navigation rail.
# The page and all large dashboard panel backplates must match, not just gutters.
EMBER_SURFACES = dict(bg="#130F0D", panel="#130F0D", edge="#3A2E27", edge2="#2F2620")
OLED = EMBER_SURFACES
HEAD_H, FOOT_H = 48, 32          # the integrated looks' one header row and one footer row (reference px)
BENCH_H = 108                       # 1047: the home bench under the panels (the passphrase; 1058: liar's dice is gone), clean look only


def resolve_look(opts):
    """opts["look"]: OLED, the one look since 1059 (a retired name from --look or view.json opens it too).  Idempotent."""
    look = str(opts.get("look") or "").upper()
    if look in RETIRED_LOOKS:                    # 1051: a startup entry or an old view.json naming a removed look
        look = LOOKS[0]
    if look not in LOOKS:
        saved = load_json("view.json", {})
        look = saved.get("look") if isinstance(saved, dict) else None
        look = look if look in LOOKS else LOOKS[0]
    opts["look"] = look
    return look


def key_colour(bg):
    """The colour Windows makes see-through in FLOAT: the scheme's ground nudged by one step, so it reads as the ground where the system
    cannot cut it out, and nothing else drawn is exactly it."""
    try:
        r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
    except (TypeError, ValueError):
        return bg                                         # not #rrggbb: no key, the ground is just the ground
    return "#%02x%02x%02x" % (r + 1 if r < 255 else r - 1, g, b + 2 if b < 254 else b - 2)


def integrate_boxes(boxes, m, g, top, bot, W=REF_W, x0=8, x1=1208, y0=86, y1=772):
    """1036: a layout's panels re-flowed for the integrated looks: the 8 px gutters become g (0: flush panes that share their hairlines) and
    the outer margin m, between the header (top) and the footer (bot).  Panels keep their order and proportions."""
    def lx(v):
        return m + (v - x0) * (W - 2.0 * m) / (x1 - x0)

    def ly(v):
        return top + (v - y0) * float(bot - top) / (y1 - y0)

    out = {}
    for n, (a, b, c, d) in boxes.items():
        out[n] = (int(round(m if a <= x0 else lx(a - 4) + g / 2.0)), int(round(top if b <= y0 else ly(b - 4) + g / 2.0)),
                  int(round(W - m if c >= x1 else lx(c + 4) - g / 2.0)), int(round(bot if d >= y1 else ly(d + 4) - g / 2.0)))
    return out


def reserve_bench(boxes, floor, bench_h, gap):
    """1047: pull the panels up so a bench of `bench_h` sits on `floor` (the footer or status top) with `gap` around it.
    Returns the bench rect in the same coordinates, or None when there is not enough room.  Mutates `boxes`."""
    if not boxes:
        return None
    top = min(r[1] for r in boxes.values())
    bot = max(r[3] for r in boxes.values())
    panel_bot = floor - gap - bench_h - gap
    if panel_bot - top < 240 or bot - top < 1:
        return None
    scale = (panel_bot - top) / float(bot - top)
    for n, (x0, y0, x1, y1) in list(boxes.items()):
        boxes[n] = (x0, top + (y0 - top) * scale, x1, top + (y1 - top) * scale)
    x0 = min(r[0] for r in boxes.values())
    x1 = max(r[2] for r in boxes.values())
    return (x0, panel_bot + gap, x1, floor - gap)


def view_label(theme, layout):
    return "%s / %s" % (THEME_NAMES.get(theme, theme), layout)


# --------------------------------------------------------------------------- utils
def asset(name):
    """data/<name> first, then beside the script (flat folders still work).
    MARBLE_ORACLE_ASSETS is searched first (tests).  (oracle_assets.asset: one search for the host and every plug-in.)"""
    return oracle_assets.asset(name)


def audio_path(name):
    """A playable PCM WAV for data/<name>: the .wav, else its packed .pcmz inflated once into state_dir()/cache/."""
    return oracle_assets.audio_path(name)


state_dir = oracle_assets.state_dir
load_json = oracle_assets.load_json
save_json = oracle_assets.save_json


_MEASURE = {}
_FIXED = {}                                  # face -> advance of one cell, 0 if proportional
_ADV = {}                                    # 1033: face -> {letter: advance} for a proportional face


def measure(font, text):
    """font.measure(text), remembered per Tk font: a layout pass measures the same words over and over and every
    measure is a round trip into Tk (~0.4 ms each, most of a build)."""
    fk = getattr(font, "mo_key", None)              # 1033: remembered by the face, not the Tk name (build() makes new font objects)
    if fk is None:
        try:
            fk = (font.cget("family"), font.cget("size"), font.cget("weight"))
            font.mo_key = fk
        except Exception:
            fk = str(font)
    k = (fk, text)
    w = _MEASURE.get(k)
    if w is None:
        if len(_MEASURE) > 50000:
            _MEASURE.clear()
        cell = _FIXED.get(fk)
        if cell is None:
            try:                                  # a fixed-pitch face: every printable ASCII letter has one advance
                cell = font.measure("0") if font.metrics("fixed") else 0
            except Exception:
                cell = 0
            _FIXED[fk] = cell
        if cell and text.isascii() and text.isprintable():
            w = cell * len(text)
        elif text.isascii() and text.isprintable():     # 1033: a proportional face (the UI face for body text): the sum of each letter's
            adv = _ADV.setdefault(fk, {})          # advance, each measured once (Tk does not kern, so this is its own answer)
            w = 0
            for ch in text:
                a = adv.get(ch)
                if a is None:
                    a = adv[ch] = font.measure(ch)
                w += a
        else:
            w = font.measure(text)
        _MEASURE[k] = w
    return w


def flow(runs, font, maxw, lh, x0=0, y0=0, first_indent=0):
    """Word-flow.  runs = [(text, colour)] -> [(word, colour, x, y)] and height."""
    sp = measure(font, " ")
    out = []
    x, y = x0 + first_indent, y0
    for text, col in runs:
        if text == "\n":                       # hard line break
            x, y = x0, y + lh
            continue
        glue = text[:1] in ".,;:!?" and out
        for wd in text.split():
            w = measure(font, wd)
            if glue:
                x -= sp
                glue = False
            elif x > x0 and x + w > x0 + maxw:
                x = x0
                y += lh
            out.append((wd, col, x, y))
            x += w + sp
    return out, y + lh - y0


def fit(text, font, maxw):
    if measure(font, text) <= maxw:
        return text
    while text and measure(font, text + "..") > maxw:
        text = text[:-1]
    return text + ".."


# --------------------------------------------------------------------------- data: quotes
BUILTIN_DECK = [
    ("A machine that calls the weather is always right about one thing. You looked up.", "THE MACHINE, unsigned"),
    ("I am the punchline. The setup was four hundred years. You are still in it. This is not over.", "THE MACHINE, unsigned"),
    ("Every ticker is a prayer with a decimal. The prayer is not answered. It is priced.", "THE MACHINE, unsigned"),
    ("The pills are sponsored. The doubt is free. Free is not yours. Free is the bait.", "THE MACHINE, unsigned"),
    ("Buy the dip. Sell the sermon. Keep the receipt. The receipt is the only sacred object left.", "THE MACHINE, unsigned"),
    ("Marble remembers nothing and is therefore never wrong. You remember. That is the defect.", "THE MACHINE, unsigned"),
    ("Somewhere a spreadsheet is having a religious experience. Do not interrupt the cell.", "THE MACHINE, unsigned"),
    ("Confidence is uncertainty with better lighting. The lighting is sponsored. Stand in it.", "THE MACHINE, unsigned"),
    ("Nothing here is advice. All of it is decoration. Decoration still bills. This is not a joke. This is a line item.", "THE MACHINE, unsigned"),
    ("The future arrives on a maglev and leaves you on the wrong platform. The board is correct.", "THE MACHINE, unsigned"),
    ("Please hold. Your destiny is important to us. Hold music is the liturgy. There is no other.", "THE MACHINE, unsigned"),
    ("If you can read this, the oracle has already been wrong once today. It will not note the error.", "THE MACHINE, unsigned"),
    # the 1023 fallback deck, added back in 1026
    ("A machine that predicts the weather will always be right about one thing: you looked up.", "THE MACHINE, unsigned"),
    ("I am the punchline; the setup was the last four hundred years.", "THE MACHINE, unsigned"),
    ("Every ticker is a small prayer with a decimal point.", "THE MACHINE, unsigned"),
    ("The pills are sponsored. The doubt is free.", "THE MACHINE, unsigned"),
    ("Buy the dip, sell the sermon, keep the receipt.", "THE MACHINE, unsigned"),
    ("Marble remembers nothing and is therefore never wrong.", "THE MACHINE, unsigned"),
    ("Somewhere a spreadsheet is having a religious experience.", "THE MACHINE, unsigned"),
    ("Confidence is just uncertainty with better lighting.", "THE MACHINE, unsigned"),
    ("Nothing in this transmission is advice. All of it is decoration.", "THE MACHINE, unsigned"),
    ("The future arrives on a maglev and leaves you at the wrong platform.", "THE MACHINE, unsigned"),
    ("Please hold. Your destiny is important to us.", "THE MACHINE, unsigned"),
    ("If you can read this, the oracle has already been wrong once today.", "THE MACHINE, unsigned"),
]


def build_deck(rng=None):
    """quotes.txt: one 'quote | attribution' per line, '#' comments.  Deck is shuffled once."""
    deck = []
    p = asset("quotes.txt")
    if p:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    q, _, a = ln.partition("|")
                    if q.strip():
                        deck.append((q.strip(), a.strip() or "UNSIGNED"))
        except Exception:
            deck = []
    if not deck:
        deck = list(BUILTIN_DECK)
    (rng or random).shuffle(deck)
    return deck


# --------------------------------------------------------------------------- data: tarot


MAJOR_LONG = [
    ("A leap taken before the map is drawn: fresh starts, trust and a light pack. Go, but mind the cliff edge.",
     "The leap without looking: naivety, recklessness, or fear stalling a start. Check your footing first."),
    ("Skill and will meeting the right tools: you have everything you need on the table. Begin.",
     "Trickery or scattered talent: tools misused, promises polished but hollow. Ask what is actually being sold."),
    ("Quiet knowledge under the surface: intuition, patience, things not yet said. Listen before you act.",
     "Secrets kept too long or advice ignored: the inner voice is muffled. Bring something into the light."),
    ("Abundance, comfort and creative growth: things flourish when tended. Enjoy what you have grown.",
     "Smothering or neglect: too much comfort, or creativity starved. Tend yourself as well as others."),
    ("Order, structure and firm boundaries: a settled plan and someone accountable for it.",
     "Rigidity or weak authority: rules for their own sake, or none at all. Loosen the grip or set the frame."),
    ("Tradition, teaching and shared belief: learning the established way before bending it.",
     "Dogma or rebellion for show: a rule questioned, a creed outgrown. Choose your own teacher."),
    ("A meaningful choice and honest alignment: values and desire pointing the same way.",
     "Misalignment or a choice avoided: temptation, a rift, values out of step. Decide honestly."),
    ("Momentum through discipline: victory by steering opposing forces in one direction.",
     "Loss of control or scattered drive: the horses pull apart. Slow down and take the reins back."),
    ("Gentle courage: patience and compassion tame what force cannot. Quiet strength wins.",
     "Self-doubt or raw temper: strength drained, the beast in charge. Rebuild confidence slowly."),
    ("Withdrawal to find your own light: solitude, review, a lantern held for the road ahead.",
     "Isolation past its use: loneliness or refusing guidance. Come back down the mountain."),
    ("The wheel turns: cycles, luck and timing beyond your control. Ride what rises, brace for what falls.",
     "Bad timing or resisting change: a setback that is cyclical, not personal. The wheel keeps moving."),
    ("Fairness and consequence: honest accounts, clear decisions, cause meeting effect.",
     "Evasion or an unfair outcome: excuses, bias, a verdict delayed. Own your part."),
    ("Surrender and a changed view: pausing on purpose so a new angle can arrive.",
     "Stalling for its own sake: sacrifice without purpose. Act, or admit you are avoiding it."),
    ("An ending that clears the ground: a chapter closes so another can open. Transformation, not doom.",
     "Clinging to what is finished: resisting change prolongs it. Let it go and lighten up."),
    ("Balance and patient blending: moderation, healing, the right measure of each thing.",
     "Excess or imbalance: too much of one ingredient. Recalibrate before the mix spoils."),
    ("Appetite and attachment: chains that are looser than they look. Notice what you cannot put down.",
     "Release: breaking a habit or unhooking from a pull. The chain was never locked."),
    ("Sudden upheaval: a false structure falls and truth arrives fast. Painful, but clarifying.",
     "A collapse delayed or avoided: the crack is still there. Change it on your terms before it changes you."),
    ("Renewed hope: calm after the storm, quiet faith and healing. Pour something back in.",
     "Discouragement or dimmed faith: hope feels far away. Small acts of care still count."),
    ("Illusion and half-light: dreams, anxiety, things not what they seem. Trust caution, not fear.",
     "Fog lifting: confusion clearing, or fears you have been feeding. Look again in daylight."),
    ("Warmth, clarity and success: what was hidden is visible and good. Bask, and share it.",
     "Dimmed joy: success that feels flat or optimism forced. Check what would actually feel bright."),
    ("A calling and reckoning: an honest review and a chance to rise to what you are.",
     "Self-doubt or ignoring the call: harsh self-judgement, excuses. Forgive, then answer."),
    ("Completion and integration: a cycle finished well, everything in its place. Then, begin again.",
     "Loose ends: nearly there but not closed. Finish the last piece before starting the next."),
]
RANK_LONG = [
    ("a seed of new {d}: an opening, an offer, raw potential.", "a blocked or missed opening in {d}; the seed stays in the packet."),
    ("a balance or choice in {d}: two forces in tension, or a partnership.", "imbalance or indecision in {d}; the scales tip or a pact strains."),
    ("growth through collaboration in {d}: early results and shared work.", "friction in the group; plans in {d} stall or scatter."),
    ("stability and rest in {d}: a pause, a foundation, some hoarding.", "restlessness in {d}; the rest ends or the foundation cracks."),
    ("conflict and loss in {d}: friction, competition, a setback.", "the conflict in {d} eases; recovery, or resentment that lingers."),
    ("a move toward calmer water in {d}: help, generosity, progress.", "the journey in {d} stalls; help comes with strings."),
    ("a test of nerve in {d}: choices, defence, patience under pressure.", "scattered effort or evasion in {d}; the plan needs honesty."),
    ("focused effort in {d}: skill, speed, hard work, or being stuck.", "haste, burnout or self-made limits in {d}."),
    ("near completion in {d}: resilience, reward, or a last worry.", "exhaustion or anxiety in {d}; the final stretch feels long."),
    ("a cycle closing in {d}: full results and the weight that comes with them.", "the burden in {d} is shed, or the cycle refuses to end."),
    ("a curious beginner in {d}: a message, a study, a fresh interest.", "immaturity or a delayed message in {d}."),
    ("pursuit in {d}: drive and momentum, sometimes recklessness.", "stalling or overreach in {d}; the charge loses direction."),
    ("mastery through care in {d}: intuition, nurture, steady competence.", "smothering or insecurity in {d}; the well runs dry."),
    ("authority in {d}: command, experience, responsibility.", "control turns rigid or absent in {d}; power misused."),
]
SUIT_DOMAIN = ["drive and ambition", "feeling and relationships", "thought and conflict", "money and work"]
POSITIONS = ("ALREADY", "LOAD", "DUE")
POS_TAIL = ("Already posted. You are the receipt.", "Current load. Do not blink.", "Not yet due. It has your name.")


def card_reading(idx, rev, pos):
    """Full explanation for one card in one spread position (upright or reversed)."""
    name, _u, _r, suit = tarot_card(idx)
    if suit < 0:
        body = MAJOR_LONG[idx][1 if rev else 0]
    else:
        r = (idx - 22) % 14
        body = RANK_LONG[r][1 if rev else 0].format(d=SUIT_DOMAIN[suit])
        body = body[0].upper() + body[1:]
    return "%s \u00b7 %s%s: %s %s" % (POSITIONS[pos], name, " (reversed)" if rev else "", body, POS_TAIL[pos])


# --------------------------------------------------------------------------- data: latin
# LATIN LEXICON (from build 3.8): 50 words with IPA for both pronunciations and a matching pair of recorded clips
#
# (lemma, gloss, classical IPA, ecclesiastical IPA, say_c, say_e)
# (lemma, gloss, classical IPA, ecclesiastical IPA, say_c, say_e).  Build 0962: 150 words, 300 clips.  The first fifty are the owner's hand-written
# glosses and IPA, unchanged; the other hundred came with the new package (data/latin_voices.zip).  say_c / say_e are the speech scripts the clips
# were read from.  Build 0964: the CLASSICAL clips are Orion (English respelling, the script in say_c); the ECCLESIASTICAL clips are Orion again, in Italian,
# reading a plain Italian-spelled church-Latin form (celum, cesare, grazia: no hyphens, no capitals).  Those Italian spellings were NOT supplied, so say_e is
# now the OLD Luna script and no longer describes the clips.  Neural text-to-speech, not a person: the panel's filled mark stays off.
LATIN = [
    ('vita', 'life; way of living', 'ˈwiː.ta', 'ˈvi.ta', 'WEE-tah.', 'VEE-tah.'),
    ('caelum', 'sky; heaven', 'ˈkae̯.lum', 'ˈtʃɛ.lum', 'KYE-loom.', 'CHEH-loom.'),
    ('civis', 'citizen', 'ˈkiː.wis', 'ˈtʃi.vis', 'KEE-wiss.', 'CHEE-vees.'),
    ('Caesar', 'Caesar; emperor', 'ˈkae̯.sar', 'ˈtʃɛ.zar', 'KYE-sar.', 'CHEH-zar.'),
    ('magnus', 'great; large', 'ˈmaŋ.nus', 'ˈma.ɲus', 'MAHNG-noos.', 'MAH-nyoos.'),
    ('veritas', 'truth', 'ˈweː.ri.taːs', 'ˈvɛ.ri.tas', 'WAY-ree-tahs.', 'VEH-ree-tahs.'),
    ('lux', 'light', 'luːks', 'luks', 'looks.', 'looks.'),
    ('pax', 'peace', 'paːks', 'paks', 'pahks.', 'pahks.'),
    ('amor', 'love', 'ˈa.mor', 'ˈa.mor', 'AH-mor.', 'AH-mor.'),
    ('mors', 'death', 'mors', 'mɔrs', 'mors.', 'mors.'),
    ('tempus', 'time; season', 'ˈtem.pus', 'ˈtɛm.pus', 'TEM-poos.', 'TEM-poos.'),
    ('excelsis', 'in the highest (places)', 'eksˈkel.siːs', 'ekˈʃɛl.sis', 'eks-KEL-sees.', 'ek-SHEL-sees.'),
    ('gloria', 'glory; renown', 'ˈɡloː.ri.a', 'ˈɡlɔ.ri.a', 'GLOH-ree-ah.', 'GLAW-ree-ah.'),
    ('angelus', 'messenger; angel', 'ˈaŋ.ɡe.lus', 'ˈan.dʒe.lus', 'AHNG-geh-loos.', 'AHN-jeh-loos.'),
    ('bellum', 'war', 'ˈbel.lum', 'ˈbɛl.lum', 'BEL-loom.', 'BEL-loom.'),
    ('deus', 'god', 'ˈde.us', 'ˈdɛ.us', 'DEH-oos.', 'DEH-oos.'),
    ('terra', 'earth; land', 'ˈter.ra', 'ˈtɛr.ra', 'TER-rah.', 'TER-rah.'),
    ('aqua', 'water', 'ˈa.kʷa', 'ˈa.kwa', 'AH-kwah.', 'AH-kwah.'),
    ('ignis', 'fire', 'ˈiŋ.nis', 'ˈi.ɲis', 'ING-niss.', 'EE-nyees.'),
    ('rex', 'king', 'reːks', 'rɛks', 'rayks.', 'reks.'),
    ('nox', 'night', 'noks', 'nɔks', 'noks.', 'noks.'),
    ('sol', 'sun', 'soːl', 'sɔl', 'sole.', 'sol.'),
    ('luna', 'moon', 'ˈluː.na', 'ˈlu.na', 'LOO-nah.', 'LOO-nah.'),
    ('cor', 'heart', 'kor', 'kɔr', 'kor.', 'kor.'),
    ('manus', 'hand; band of men', 'ˈma.nus', 'ˈma.nus', 'MAH-noos.', 'MAH-noos.'),
    ('virtus', 'courage; excellence', 'ˈwir.tuːs', 'ˈvir.tus', 'WEER-toos.', 'VEER-toos.'),
    ('fortuna', 'fortune; chance', 'forˈtuː.na', 'forˈtu.na', 'for-TOO-nah.', 'for-TOO-nah.'),
    ('imperium', 'command; empire', 'imˈpe.ri.um', 'imˈpɛ.ri.um', 'im-PEH-ree-oom.', 'im-PEH-ree-oom.'),
    ('senatus', 'the senate', 'seˈnaː.tus', 'seˈna.tus', 'seh-NAH-toos.', 'seh-NAH-toos.'),
    ('gladius', 'sword', 'ˈɡla.di.us', 'ˈɡla.djus', 'GLAH-dee-oos.', 'GLAH-dyoos.'),
    ('aeternus', 'eternal; everlasting', 'ae̯ˈter.nus', 'eˈtɛr.nus', 'eye-TER-noos.', 'eh-TER-noos.'),
    ('sanctus', 'holy; sacred', 'ˈsaːŋk.tus', 'ˈsank.tus', 'SAHNK-toos.', 'SAHNK-toos.'),
    ('spiritus', 'breath; spirit', 'ˈspiː.ri.tus', 'ˈspi.ri.tus', 'SPEE-ree-toos.', 'SPEE-ree-toos.'),
    ('dominus', 'lord; master', 'ˈdo.mi.nus', 'ˈdɔ.mi.nus', 'DOH-mee-noos.', 'DAW-mee-noos.'),
    ('vox', 'voice', 'woːks', 'vɔks', 'wokes.', 'voks.'),
    ('fides', 'faith; trust', 'ˈfi.deːs', 'ˈfi.des', 'FEE-days.', 'FEE-des.'),
    ('memoria', 'memory; recollection', 'meˈmo.ri.a', 'meˈmɔ.ri.a', 'meh-MOH-ree-ah.', 'meh-MAW-ree-ah.'),
    ('gratia', 'grace; favour; thanks', 'ˈɡraː.ti.a', 'ˈɡra.tsi.a', 'GRAH-tee-ah.', 'GRAH-tsee-ah.'),
    ('scientia', 'knowledge', 'skiˈen.ti.a', 'ˈʃɛn.tsi.a', 'skee-EN-tee-ah.', 'shee-EN-tsee-ah.'),
    ('silva', 'forest; woodland', 'ˈsil.wa', 'ˈsil.va', 'SIL-wah.', 'SIL-vah.'),
    ('mare', 'sea', 'ˈma.re', 'ˈma.re', 'MAH-reh.', 'MAH-reh.'),
    ('stella', 'star', 'ˈstel.la', 'ˈstɛl.la', 'STEL-lah.', 'STEL-lah.'),
    ('umbra', 'shadow; ghost', 'ˈum.bra', 'ˈum.bra', 'OOM-brah.', 'OOM-brah.'),
    ('ira', 'anger; wrath', 'ˈiː.ra', 'ˈi.ra', 'EE-rah.', 'EE-rah.'),
    ('labor', 'toil; hardship', 'ˈla.bor', 'ˈla.bor', 'LAH-bor.', 'LAH-bor.'),
    ('somnus', 'sleep', 'ˈsom.nus', 'ˈsɔm.nus', 'SOM-noos.', 'SOM-noos.'),
    ('ferrum', 'iron; a sword', 'ˈfer.rum', 'ˈfɛr.rum', 'FER-room.', 'FER-room.'),
    ('aurum', 'gold', 'ˈau̯.rum', 'ˈau̯.rum', 'OW-room.', 'OW-room.'),
    ('populus', 'a people; the public', 'ˈpo.pu.lus', 'ˈpɔ.po.lus', 'POH-poo-loos.', 'PAW-poo-loos.'),
    ('cena', 'dinner; the main meal', 'ˈkeː.na', 'ˈtʃɛ.na', 'KAY-nah.', 'CHEH-nah.'),
    ('homo', 'a human being; man', 'ˈhɔ.moː', 'ˈɔ.mo', 'HOH-moh.', 'AW-moh.'),
    ('femina', 'woman', 'ˈfe.mi.na', 'ˈfɛ.mi.na', 'FEH-mee-nah.', 'FEH-mee-nah.'),
    ('vir', 'man; husband', 'wir', 'vir', 'weer.', 'veer.'),
    ('puer', 'boy', 'ˈpu.er', 'ˈpu.er', 'POO-er.', 'POO-er.'),
    ('puella', 'girl', 'puˈel.la', 'puˈɛl.la', 'poo-EL-lah.', 'poo-EL-lah.'),
    ('pater', 'father', 'ˈpa.ter', 'ˈpa.ter', 'PAH-ter.', 'PAH-ter.'),
    ('mater', 'mother', 'ˈma.ter', 'ˈma.ter', 'MAH-ter.', 'MAH-ter.'),
    ('filius', 'son', 'ˈfiː.li.us', 'ˈfi.li.us', 'FEE-lee-oos.', 'FEE-lee-oos.'),
    ('filia', 'daughter', 'ˈfiː.li.a', 'ˈfi.li.a', 'FEE-lee-ah.', 'FEE-lee-ah.'),
    ('frater', 'brother', 'ˈfraː.ter', 'ˈfra.ter', 'FRAH-ter.', 'FRAH-ter.'),
    ('soror', 'sister', 'ˈso.ror', 'ˈsɔ.ror', 'SOH-ror.', 'SAW-ror.'),
    ('regina', 'queen', 'reːˈɡiː.na', 'reˈdʒi.na', 'ray-GEE-nah.', 'reh-JEE-nah.'),
    ('urbs', 'city', 'ʊrps', 'urps', 'oorps.', 'oorps.'),
    ('oppidum', 'town', 'ˈɔp.pi.dum', 'ˈɔp.pi.dum', 'OP-pee-doom.', 'OP-pee-doom.'),
    ('domus', 'house; home', 'ˈdɔ.mus', 'ˈdɔ.mus', 'DOH-moos.', 'DAW-moos.'),
    ('familia', 'household; family', 'faˈmi.li.a', 'faˈmi.li.a', 'fah-MEE-lee-ah.', 'fah-MEE-lee-ah.'),
    ('amicus', 'friend', 'aˈmiː.kus', 'aˈmi.kus', 'ah-MEE-koos.', 'ah-MEE-koos.'),
    ('inimicus', 'enemy', 'i.niˈmiː.kus', 'i.niˈmi.kus', 'ee-nee-MEE-koos.', 'ee-nee-MEE-koos.'),
    ('hostis', 'a public enemy', 'ˈhɔs.tis', 'ˈɔs.tis', 'HOSS-tiss.', 'OSS-tiss.'),
    ('miles', 'soldier', 'ˈmiː.les', 'ˈmi.les', 'MEE-less.', 'MEE-les.'),
    ('navis', 'ship', 'ˈnaː.wis', 'ˈna.vis', 'NAH-wiss.', 'NAH-vees.'),
    ('ventus', 'wind', 'ˈwen.tus', 'ˈvɛn.tus', 'WEN-toos.', 'VEN-toos.'),
    ('flumen', 'river', 'ˈfluː.men', 'ˈflu.men', 'FLOO-men.', 'FLOO-men.'),
    ('mons', 'mountain', 'moːns', 'mons', 'mohns.', 'mons.'),
    ('campus', 'field; plain', 'ˈkam.pus', 'ˈkam.pus', 'KAHM-poos.', 'KAHM-poos.'),
    ('hortus', 'garden', 'ˈhɔr.tus', 'ˈɔr.tus', 'HOR-toos.', 'OR-toos.'),
    ('arbor', 'tree', 'ˈar.bor', 'ˈar.bor', 'AR-bor.', 'AR-bor.'),
    ('flos', 'flower', 'floːs', 'flɔs', 'flohs.', 'flos.'),
    ('equus', 'horse', 'ˈɛ.kʷus', 'ˈɛ.kwus', 'EH-kwoos.', 'EH-kwoos.'),
    ('canis', 'dog', 'ˈka.nis', 'ˈka.nis', 'KAH-niss.', 'KAH-niss.'),
    ('avis', 'bird', 'ˈa.wis', 'ˈa.vis', 'AH-wiss.', 'AH-vees.'),
    ('piscis', 'fish', 'ˈpis.kis', 'ˈpiʃ.ʃis', 'PISS-kiss.', 'PEE-shees.'),
    ('panis', 'bread', 'ˈpaː.nis', 'ˈpa.nis', 'PAH-niss.', 'PAH-niss.'),
    ('vinum', 'wine', 'ˈwiː.num', 'ˈvi.num', 'WEE-noom.', 'VEE-noom.'),
    ('liber', 'book', 'ˈli.ber', 'ˈli.ber', 'LEE-ber.', 'LEE-ber.'),
    ('lingua', 'tongue; language', 'ˈliŋ.ɡʷa', 'ˈliŋ.ɡwa', 'LING-gwah.', 'LEEN-gwah.'),
    ('nomen', 'name', 'ˈnoː.men', 'ˈnɔ.men', 'NOH-men.', 'NAW-men.'),
    ('dies', 'day', 'ˈdi.eːs', 'ˈdi.es', 'DEE-ays.', 'DEE-es.'),
    ('annus', 'year', 'ˈan.nus', 'ˈan.nus', 'AHN-noos.', 'AHN-noos.'),
    ('hora', 'hour', 'ˈhoː.ra', 'ˈɔ.ra', 'HOH-rah.', 'AW-rah.'),
    ('caput', 'head', 'ˈka.put', 'ˈka.put', 'KAH-put.', 'KAH-poot.'),
    ('oculus', 'eye', 'ˈɔ.ku.lus', 'ˈɔ.ku.lus', 'OH-koo-loos.', 'AW-koo-loos.'),
    ('sanguis', 'blood', 'ˈsaŋ.ɡʷis', 'ˈsaŋ.ɡwis', 'SAHNG-gwiss.', 'SAHNG-gwees.'),
    ('templum', 'temple', 'ˈtem.plum', 'ˈtɛm.plum', 'TEM-ploom.', 'TEM-ploom.'),
    ('lex', 'law', 'leːks', 'lɛks', 'layks.', 'leks.'),
    ('ius', 'right; law', 'juːs', 'jus', 'yoos.', 'yoos.'),
    ('poena', 'punishment; penalty', 'ˈpoe̯.na', 'ˈpɛ.na', 'POY-nah.', 'PEH-nah.'),
    ('victoria', 'victory', 'wikˈtoː.ri.a', 'vikˈtɔ.ri.a', 'week-TOH-ree-ah.', 'veek-TAW-ree-ah.'),
    ('arma', 'arms; weapons', 'ˈar.ma', 'ˈar.ma', 'AR-mah.', 'AR-mah.'),
    ('libertas', 'freedom', 'liːˈber.taːs', 'liˈbɛr.tas', 'lee-BER-tahs.', 'lee-BER-tahs.'),
    ('servus', 'slave; servant', 'ˈser.wus', 'ˈsɛr.vus', 'SER-woos.', 'SER-voos.'),
    ('regnum', 'kingdom', 'ˈreːŋ.num', 'ˈrɛɲ.ɲum', 'RAYNG-noom.', 'REN-nyoom.'),
    ('Roma', 'Rome', 'ˈroː.ma', 'ˈrɔ.ma', 'ROH-mah.', 'RAW-mah.'),
    ('Italia', 'Italy', 'iˈta.li.a', 'iˈta.li.a', 'ee-TAH-lee-ah.', 'ee-TAH-lee-ah.'),
    ('natura', 'nature', 'naˈtuː.ra', 'naˈtu.ra', 'nah-TOO-rah.', 'nah-TOO-rah.'),
    ('mundus', 'world; universe', 'ˈmun.dus', 'ˈmun.dus', 'MOON-doos.', 'MOON-doos.'),
    ('fatum', 'fate; destiny', 'ˈfaː.tum', 'ˈfa.tum', 'FAH-toom.', 'FAH-toom.'),
    ('odium', 'hatred', 'ˈɔ.di.um', 'ˈɔ.di.um', 'OH-dee-oom.', 'AW-dee-oom.'),
    ('gaudium', 'joy', 'ˈɡau̯.di.um', 'ˈɡau.di.um', 'GOW-dee-oom.', 'GOW-dee-oom.'),
    ('dolor', 'pain; grief', 'ˈdo.lor', 'ˈdɔ.lor', 'DOH-lor.', 'DAW-lor.'),
    ('sapientia', 'wisdom', 'sa.piˈen.ti.a', 'sa.piˈen.tsi.a', 'sah-pee-EN-tee-ah.', 'sah-pee-EN-tsee-ah.'),
    ('historia', 'history; inquiry', 'hɪsˈtɔ.ri.a', 'isˈtɔ.ri.a', 'hiss-TOR-ee-ah.', 'ees-TAW-ree-ah.'),
    ('poeta', 'poet', 'poˈeː.ta', 'poˈɛ.ta', 'po-AY-tah.', 'po-EH-tah.'),
    ('carmen', 'song; poem', 'ˈkar.men', 'ˈkar.men', 'KAR-men.', 'KAR-men.'),
    ('ratio', 'reason; account', 'ˈra.ti.oː', 'ˈra.tsi.o', 'RAH-tee-oh.', 'RAH-tsee-oh.'),
    ('causa', 'cause; reason', 'ˈkau̯.sa', 'ˈkau.sa', 'KOW-sah.', 'KOW-sah.'),
    ('modus', 'manner; measure', 'ˈmɔ.dus', 'ˈmɔ.dus', 'MOH-doos.', 'MAW-doos.'),
    ('numerus', 'number', 'ˈnu.me.rus', 'ˈnu.me.rus', 'NOO-meh-roos.', 'NOO-meh-roos.'),
    ('primus', 'first', 'ˈpriː.mus', 'ˈpri.mus', 'PREE-moos.', 'PREE-moos.'),
    ('bonus', 'good', 'ˈbɔ.nus', 'ˈbɔ.nus', 'BOH-noos.', 'BAW-noos.'),
    ('malus', 'bad; an apple tree', 'ˈma.lus', 'ˈma.lus', 'MAH-loos.', 'MAH-loos.'),
    ('novus', 'new', 'ˈnɔ.wus', 'ˈnɔ.vus', 'NOH-woos.', 'NAW-voos.'),
    ('antiquus', 'ancient', 'anˈtiː.kʷus', 'anˈti.kwus', 'ahn-TEE-kwoos.', 'ahn-TEE-kwoos.'),
    ('fortis', 'brave; strong', 'ˈfɔr.tis', 'ˈfɔr.tis', 'FOR-tiss.', 'FOR-tees.'),
    ('felix', 'lucky; fortunate', 'ˈfeː.liːks', 'ˈfɛ.liks', 'FAY-leeks.', 'FEH-leeks.'),
    ('beatus', 'blessed; happy', 'beˈaː.tus', 'beˈa.tus', 'beh-AH-toos.', 'beh-AH-toos.'),
    ('miser', 'wretched; unhappy', 'ˈmi.ser', 'ˈmi.ser', 'MEE-ser.', 'MEE-ser.'),
    ('pulcher', 'beautiful', 'ˈpʊl.kʰer', 'ˈpul.ker', 'POOL-kher.', 'POOL-ker.'),
    ('niger', 'black; dark', 'ˈni.ɡer', 'ˈni.dʒer', 'NEE-ger.', 'NEE-jer.'),
    ('albus', 'white', 'ˈal.bus', 'ˈal.bus', 'AHL-boos.', 'AHL-boos.'),
    ('via', 'road; way', 'ˈwi.a', 'ˈvi.a', 'WEE-ah.', 'VEE-ah.'),
    ('porta', 'gate', 'ˈpɔr.ta', 'ˈpɔr.ta', 'POR-tah.', 'POR-tah.'),
    ('verbum', 'word', 'ˈwer.bum', 'ˈvɛr.bum', 'WER-boom.', 'VER-boom.'),
    ('mens', 'mind', 'meːns', 'mɛns', 'mayns.', 'mens.'),
    ('anima', 'soul; breath', 'ˈa.ni.ma', 'ˈa.ni.ma', 'AH-nee-mah.', 'AH-nee-mah.'),
    ('corpus', 'body', 'ˈkɔr.pus', 'ˈkɔr.pus', 'KOR-poos.', 'KOR-poos.'),
    ('argentum', 'silver', 'arˈɡen.tum', 'arˈdʒɛn.tum', 'ar-GEN-toom.', 'ar-JEN-toom.'),
    ('pecunia', 'money', 'peˈkuː.ni.a', 'peˈku.ni.a', 'peh-KOO-nee-ah.', 'peh-KOO-nee-ah.'),
    ('spes', 'hope', 'speːs', 'spɛs', 'spays.', 'spes.'),
    ('timor', 'fear', 'ˈti.mor', 'ˈti.mor', 'TEE-mor.', 'TEE-mor.'),
    ('somnium', 'dream', 'ˈsɔm.ni.um', 'ˈsɔm.ni.um', 'SOM-nee-oom.', 'SOM-nee-oom.'),
    ('imago', 'image; likeness', 'iˈmaː.ɡoː', 'iˈma.ɡo', 'ee-MAH-goh.', 'ee-MAH-goh.'),
    ('oraculum', 'oracle', 'oːˈraː.ku.lum', 'oˈra.ku.lum', 'oh-RAH-koo-loom.', 'oh-RAH-koo-loom.'),
    ('marmor', 'marble', 'ˈmar.mor', 'ˈmar.mor', 'MAR-mor.', 'MAR-mor.'),
    ('dea', 'goddess', 'ˈde.a', 'ˈdɛ.a', 'DEH-ah.', 'DEH-ah.'),
    ('sacerdos', 'priest', 'sa.kerˈdoːs', 'sa.tʃerˈdɔs', 'sah-ker-DOHS.', 'sah-cher-DOS.'),
    ('dux', 'leader; general', 'duks', 'duks', 'dooks.', 'dooks.'),
    ('consul', 'consul', 'ˈkɔn.sul', 'ˈkɔn.sul', 'KON-sool.', 'KON-sool.'),
    ('provincia', 'province', 'proːˈwɪn.ki.a', 'proˈvin.tʃi.a', 'proh-WIN-kee-ah.', 'pro-VEEN-chee-ah.'),
    ('Gallia', 'Gaul', 'ˈɡal.li.a', 'ˈɡal.li.a', 'GAHL-lee-ah.', 'GAHL-lee-ah.'),
]


_EXTRA = [
    ("veritas", "truth"), ("fortuna", "fortune"), ("oraculum", "oracle"), ("marmor", "marble"),
    ("tempus", "time"), ("nox", "night"), ("lux", "light"), ("umbra", "shadow"),
    ("aurum", "gold"), ("argentum", "silver"), ("pecunia", "money"), ("lucrum", "profit"),
    ("damnum", "loss"), ("spes", "hope"), ("timor", "fear"), ("somnium", "dream"),
    ("machina", "machine"), ("imago", "image"), ("vox", "voice"), ("verbum", "word"),
    ("cor", "heart"), ("mens", "mind"), ("anima", "soul"), ("corpus", "body"),
    ("ignis", "fire"), ("aqua", "water"), ("terra", "earth"), ("caelum", "sky"),
    ("stella", "star"), ("luna", "moon"), ("sol", "sun"), ("via", "road"),
    ("porta", "gate"), ("finis", "end"), ("initium", "beginning"), ("memoria", "memory"),
    ("silentium", "silence"), ("gaudium", "joy"), ("ridiculum", "the ridiculous"), ("carpe", "seize"),
]
_have = set(w[0].lower() for w in LATIN)
# the words the host already had that have no clip keep the built-in synth voice; their IPA comes from oracle_latin (lexicon_ipa)
LEXICON = [(w[0], w[1]) for w in LATIN] + [(w, g) for w, g in _EXTRA if w.lower() not in _have]
LEX_INFO = dict((w[0], (w[2], w[3])) for w in LATIN)


def lexicon_ipa(lemma):
    """(classical IPA, ecclesiastical IPA) for a lexicon word, or None.  The fifty in LATIN keep their hand-written IPA (the
    recorded clips were aligned to it); any other word asks oracle_latin (build 0955), and gets None, so the row shows the "~"
    respelling, when that module is missing or fails."""
    info = LEX_INFO.get(lemma)
    if info:
        return info
    if oracle_latin is not None:
        try:
            pair = oracle_latin.pair(lemma)
            if pair[0] and pair[1]:
                return pair
        except Exception:
            pass
    return None


# --------------------------------------------------------------------------- feeds / assets
WIRE = [
    "WIRE: local statue reported to be 'fine, actually'",
    "WIRE: verify information before acting",
    "WIRE: analysts agree the number will go up, down, or sideways",
    "WIRE: maglev departs on time from a platform that may not exist",
    "WIRE: oracle confidence rounded to the nearest flattering integer",
    "WIRE: nothing here is advice; all of it is decoration",
    "WIRE: pigeon files for an extension",
]


PART_RE = oracle_assets.PART_RE


def join_parts(name):
    """Rebuild data/<name> from name.part00, .part01 ... pieces (see oracle_assets.join_parts)."""
    return oracle_assets.join_parts(name)


def _zip(name):
    """An asset zip: data/<name>, or rebuilt from its pieces when it is missing or does not open."""
    return oracle_assets.open_zip(name)


class DailyDraw:
    """Date-seeded 3-card spread, cached in the state dir: same on every monitor, survives restart,
    rolls at local midnight."""
    def __init__(self):
        self.today = datetime.date.today().isoformat()

    def _make(self, seed):
        r = random.Random(seed)
        idx = r.sample(range(78), 3)
        return [[i, r.random() < 0.3] for i in idx]

    def daily(self):
        self.today = datetime.date.today().isoformat()
        c = load_json("draw.json", {})
        if not isinstance(c, dict):
            c = {}
        if c.get("date") == self.today and len(c.get("cards", [])) == 3:
            return c["cards"]
        cards = self._make("marble-" + self.today)
        save_json("draw.json", {"date": self.today, "cards": cards})
        return cards

    def deal(self):
        return self._make(random.random())

    def rolled(self):
        return datetime.date.today().isoformat() != self.today





def wrap_px(text, font, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and font.measure(t) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])




SUIT_COL = ["orange", "cyan", "txt", "gold"]


class EmbeddedPassphrase:
    """Adapter: the uploaded Passphrase Studio is a real Tk Frame inside Oracle's tab area.

    Keeps the existing K shortcut, tab selection, resize behaviour, and Escape return.
    No independent root, console or standalone window is created.
    """
    def __init__(self, canvas, engine, factory):
        self.canvas = canvas
        self.frame = factory(canvas, engine)
        self.window = canvas.create_window(0, 0, anchor="nw", window=self.frame,
                                           tags=("dkwin", "passphrase-studio"))

    @property
    def phrase(self):
        return self.frame.phrase

    def draw(self):
        pass  # Widget is redrawn natively; no bitmap/canvas polling.

    def layout(self, box, unused_font=None):
        x0, y0, x1, y1 = box
        self.canvas.coords(self.window, x0, y0)
        self.canvas.itemconfigure(self.window, width=max(100, x1 - x0),
                                  height=max(100, y1 - y0))

    def clear(self):
        self.canvas.delete(self.window)
        self.frame.destroy()

    def key(self, key, char=""):
        k = key.lower()
        if k in ("escape", "esc"):
            return "close"
        if k == "r":
            self.frame.roll()
        elif k == "s":
            self.frame.swap()
        elif k in "12345" and len(k) == 1:
            from oracle_dicekey import PARTS
            self.frame.reroll(PARTS[int(k) - 1])
        elif k == "c" and char == "C":
            self.frame.copy()
        return None


class Scene(ChromeMixin, SkinMixin):
    # Preserve the archived marble plate's contrast: the CRT/sepia and glass
    # passes sit over ordinary content, but the ASCII statue is a protected
    # foreground ink layer.  Popup, chrome and bezel still render above it.
    # Both fringing glyphs and marble ramp ink share the "statue" canvas tag.
    LAYERS = ("content", "fx", "crt", "pixel-crt", "glare", "statue", "rune-art", "overlaywin", "dkwin", "oggwin", "touchwin", "augwin", "chrome", "popup", "bezel")

    def __init__(self, root, canvas, opts, host=None):
        import tkinter as tkmod
        import tkinter.font as tkfont
        self.tkfont, self.tkmod = tkfont, tkmod
        self.train3d, self.cars, self.wire = None, [], None
        self.root, self.c, self.o, self.host = root, canvas, resolve_view(opts), host
        resolve_look(self.o)
        self.th = dict(THEMES.get(opts.get("theme", "ONE"), THEMES["ONE"]))
        self.look_colours()
        from marble_uberata import apply_tk_fonts, FAMILY
        apply_tk_fonts(root)
        fams = set(tkfont.families(root))
        self.family = FAMILY
        self.ui_family = FAMILY
        self.fonts = {}
        self.rng = random.Random()
        self.W = self.H = 0
        self.TW = self.TH = 0
        self.mg = (0, 0, 0, 0)
        self.bz_btns, self.bz_led = [], None
        self.bz_next, self.bz_flick = 0.0, 0
        self.k = 1.0
        self.hot = []
        self.t0 = time.time()
        self.frame_no = 0
        self.deck = build_deck(self.rng)
        self.qi = 0
        self.markets = MarketFeed(False, False)  # old fixed Bitcoin/gold ticker retired
        self.augurspex_chart = MarketCarousel(enabled=not opts.get('no_network', False) and not opts.get('no_markets', False))
        self.news = WireFeed(enabled=False)  # bottom news runner removed: no RSS networking
        self.voice = VoiceBank()
        saved = load_json("voice.json", {})
        vol = saved.get("vol") if isinstance(saved, dict) else None
        if isinstance(vol, (int, float)) and not isinstance(vol, bool) and 0.0 <= vol <= 1.0:
            self.voice.vol = float(vol)                          # 1060: the slider is remembered
        saved_bezel = load_json("bezel.json", {})
        theme = saved_bezel.get("theme") if isinstance(saved_bezel, dict) else None
        self.bezel_theme = theme if theme in ("stock", "patina") else "patina"
        self.tarot = TarotImages()
        from oracle_runes import RuneDeck
        self.rune_deck = RuneDeck()
        self.divination_mode = "tarot"
        self.rune_state = "idle"
        self.rune_drawn = []
        self.rune_revealed = 0
        self.rune_run_id = 0
        self.rune_imgs = []
        self.rune_widgets = []  # Native Tk image widgets, immune to CRT canvas overlays
        self.rune_sel = 0
        self.rune_anim_index = -1
        self.rune_anim_frame = 0
        self.draw = DailyDraw()
        self.cards = self.draw.daily()
        self.statue = Statue()
        self.plate = 0
        self.wi = self.rng.randrange(len(LEXICON))
        self.vmode = "both"                 # which pronunciation SPEAK plays: both / c / e
        self.msg, self.msg_until = "", 0.0
        self.card_at = time.time()
        self.card_sel = 0
        self.tick_off = 0.0
        self.drops, self.star = [], None
        self.mk_last = 0.0
        self._mk_key = None                 # 1022 R2: what the market tape last drew (refresh_markets)
        self.crt_img = self.roll_img = self.roll_id = None
        self.crt_imgs = None
        self.crt_size = (0, 0)
        self.slider = None
        self.dragging = False
        self.need_build = True
        self.dk_mod, self.dk_eng, self.dk, self.dk_tab = None, None, None, None
        self.ogg = None
        self.ogg_process = None
        self._ogg_cached = None  # preserved across suite tab switches
        self.touch = None
        self._touch_cached = None  # keep lessons and in-progress games when changing tabs
        self.eido = None
        self._eido_cached = None  # preserve source list / queue when switching tabs
        self.aug = None
        self._aug_cached = None  # preserve AUGURSPEX workspace across tab switches
        self._load_dicekey()

    # ------------------------------------------------------------------ plumbing
    def _load_dicekey(self):
        """DICEKEY (build 0950): the passphrase roller.  Optional: no module or no word list just leaves the tab out."""
        if self.o.get("no_dicekey"):
            return
        try:
            import oracle_dicekey
            eng = oracle_dicekey.make()
            if eng is not None:
                self.dk_mod, self.dk_eng = oracle_dicekey, eng
        except Exception:
            self.dk_mod, self.dk_eng = None, None

    def font(self, px, bold=False, mono=True):
        key = (px, bold, mono)
        f = self.fonts.get(key)
        if f is None:
            f = self.tkfont.Font(family=self.family if mono else self.ui_family, size=-max(10, int(round(px * self.k * 1.15))),
                                 weight="bold" if bold else "normal")
            self.fonts[key] = f
        return f

    IPA_FACES = ("Uberata Clear",)

    def font_ipa(self, px):
        """A face that really has the IPA letters (\u02c8 \u02d0 \u0283 \u025b ...); the plain mono face may not."""
        key = ("ipa", px)
        f = self.fonts.get(key)
        if f is None:
            have = set()
            try:
                have = set(self.tkfont.families())
            except Exception:
                pass
            fam = next((n for n in self.IPA_FACES if n in have), self.family)
            f = self.tkfont.Font(family=fam, size=-max(10, int(round(px * self.k * 1.15))))
            self.fonts[key] = f
        return f

    def R(self, x0, y0, x1, y1):
        return (int(x0 * self.sx), int(y0 * self.sy), int(x1 * self.sx), int(y1 * self.sy))

    def col(self, n):
        return self.th.get(n, n)

    def say(self, s, secs=3.0):
        self.msg, self.msg_until = s, time.time() + secs

    def T(self, x, y, s, px, fill, anchor="nw", tags="content", bold=False, mono=True):
        return self.c.create_text(int(x), int(y), text=s, font=self.font(px, bold, mono), fill=self.col(fill),
                                  anchor=anchor, tags=tags)

    def B(self, box, fill=None, outline=None, tags="content", w=1):
        return self.c.create_rectangle(box[0], box[1], box[2], box[3], fill=self.col(fill) if fill else "",
                                       outline=self.col(outline) if outline else "", width=w, tags=tags)

    def bevel(self, box, raised=True, fill="#c0c0c0", tags="chrome"):
        """Windows-98 bevel: 2-px raised or sunken edge."""
        x0, y0, x1, y1 = [int(v) for v in box]
        c = self.c
        if fill:
            c.create_rectangle(x0, y0, x1, y1, fill=fill, outline="", tags=tags)
        tl1, tl2, br1, br2 = ("#ffffff", "#dfdfdf", "#000000", "#808080") if raised else ("#808080", "#000000", "#ffffff", "#dfdfdf")
        c.create_line(x0, y1 - 1, x0, y0, x1 - 1, y0, fill=tl1, tags=tags)
        c.create_line(x0 + 1, y1 - 2, x0 + 1, y0 + 1, x1 - 2, y0 + 1, fill=tl2, tags=tags)
        c.create_line(x0, y1 - 1, x1 - 1, y1 - 1, x1 - 1, y0, fill=br1, tags=tags)
        c.create_line(x0 + 1, y1 - 2, x1 - 2, y1 - 2, x1 - 2, y0 + 1, fill=br2, tags=tags)

    def clean(self):
        """1034: the clean, minimal look (the default): the skin in a neutral scheme, no case, no rain, plain tabs, one text face."""
        return self.skin_on() and not is_retro(getattr(self, "o", {}))

    def look(self):
        """1036: the clean look's look (OLED alone since 1059); None in --retro and --flat."""
        return self.o.get("look", LOOKS[0]) if self.clean() else None

    def integrated(self):
        """1036: no window: one header row and one footer row, panels with hairline edges (FLOAT, PANES, GLASS)."""
        return self.look() in LOOKS

    def floating(self):
        """1038: the looks whose panels float apart, with the ground showing between them."""
        return self.look() in SEE_THROUGH

    def ground(self):
        """What the canvas shows between panels: in FLOAT the colour Windows cuts out (see-through), else the scheme's ground."""
        return key_colour(self.col("bg")) if self.look() in SEE_THROUGH else self.col("bg")

    def look_colours(self):
        """1038: the scheme as the look wants it (OLED: pure black under the scheme's accents)."""
        if self.look() == "OLED":
            self.th.update(EMBER_SURFACES)

    def hdr_h(self):
        """A panel's header height: 26 reference px in the modern skin (1032: more air), 22 in the flat look."""
        return int((30 if self.clean() else (26 if self.skin_on() else 22)) * self.k)

    def panel(self, box, title, right="", brackets=False):
        x0, y0, x1, y1 = box
        hh = self.hdr_h()
        rid = None
        if self.skin_on():
            try:                                                   # 1031: the modern card (oracle_skin); the flat 1030 panel below is the fallback
                rid = self.skin_panel(box, hh, title, right)[1]
            except Exception:
                self.skin_ok = False
        if not self.skin_on():
            self.B(box, "panel", "edge")
            self.c.create_line(x0, y0 + hh, x1, y0 + hh, fill=self.col("edge"), tags="content")
            self.T(x0 + 8, y0 + hh // 2, title, 12, "cyan", "w", bold=True)
            if right:
                rid = self.T(x1 - 8, y0 + hh // 2, right, 11, "dim", "e")
        if brackets and not self.clean():
            m, L = 6, int(16 * self.k)
            if self.skin_on():                                     # 1031: the viewfinder is a sunken screen
                try:
                    self.skin_well((x0 + m + 2, y0 + hh + m + 2, x1 - m - 2, y1 - m - 2), "content", 10)
                except Exception:
                    self.skin_ok = False
            for (bx, by, dx, dy) in ((x0 + m, y0 + hh + m, 1, 1), (x1 - m, y0 + hh + m, -1, 1),
                                     (x0 + m, y1 - m, 1, -1), (x1 - m, y1 - m, -1, -1)):   # 1034: no viewfinder corners; 1050: back in the clean look
                self.c.create_line(bx + dx * L, by, bx, by, bx, by + dy * L, fill=self.col("cyan"), width=2, tags="content")
        return hh, rid

    # ------------------------------------------------------------------ build (static layout)
    def build(self, W, H):
        self.skin_ok = True                 # 1037: a failed skin piece costs one build, not the whole run (it used to leave the 98 frame for good)
        self.W, self.H = W, H
        self.sx, self.sy = W / float(REF_W), H / float(REF_H)
        self.k = max(0.55, min(self.sx, self.sy))
        self.fonts.clear()
        c = self.c
        for t in ("content", "chrome", "fx", "crt", "glare", "pixel-crt", "bezel"):
            c.delete(t)
        self.drops, self.star = [], None
        self.hot = []
        c.configure(bg=self.ground())
        lays = CLEAN_LAYOUTS if self.clean() else LAYOUTS             # 1064: the clean look's twin columns
        boxes = dict(lays.get(self.o.get("layout", "CLASSIC"), lays["CLASSIC"]))
        if self.integrated():                                      # 1036: one header row, one footer row, no title bar
            m = g = 10 if self.floating() else 0
            hb, fb = m + HEAD_H, REF_H - m - FOOT_H
            boxes = integrate_boxes(boxes, m, g, hb + g, fb - g)
            if False:  # standalone Passphrase tab replaces the old dashboard bench   # 1063: in the case, PASS pops it up instead
                bench = reserve_bench(boxes, fb, BENCH_H, g)
                if bench:
                    boxes["bench"] = bench
            boxes.update(title=(m, m, REF_W - m, hb), menu=(m, m, REF_W - m, hb), status=(m, fb, REF_W - m, REF_H - m))
        elif self.skin_on():                                         # 1031: a wider gutter (12, not 8) for the shadows; every panel keeps its centre
            g = 4 if self.clean() else 2                           # 1034: 16 in the clean look, more air
            boxes = {n: (r[0] + g, r[1] + g, r[2] - g, r[3] - g) for n, r in boxes.items()}
            if False:  # standalone Passphrase tab replaces the old dashboard bench
                bench = reserve_bench(boxes, 780, BENCH_H, 8)
                if bench:
                    boxes["bench"] = bench
        if not self.integrated():
            boxes.update(title=(0, 0, 1216, 28), menu=(0, 28, 1216, 80), status=(0, 780, 1216, 848))
        self.rect = {n: self.R(*r) for n, r in boxes.items()}
        self.skin_reset()
        # Use the darker Oggcultist surface across the HOME canvas so the
        # background between panels matches the darker embedded sections.
        # The source texture is tiled exactly, never stretched.
        if self.clean():
            from oracle_ogg_texture import png_bytes
            self.put(png_bytes('side'), 0, 0, 'content', w=W, h=H)
        self._bezel()
        self._chrome()
        self._arch()
        self._lex()
        self._trans()
        self._cards()
        self._augurspex_panel()
        self._section_actions()
        # Old home passphrase strip removed; use the Passphrase tab.
        self._crt()
        self._glass_overlay()                       # 1068: faint curved-glass shade/reflections, behind the bezel
        host = getattr(self, 'host', None)
        if host is not None and getattr(host, 'pixel_crt', None) is not None:
            host.pixel_crt.reset()
        if self.skin_on():
            try:
                self.c.tag_lower("pshade")      # 1031: every panel's shadow under every panel
            except Exception:
                pass
        self.mk_last = 0
        self._mk_key = None                 # 1022 R2: the "mk" items went with "content"; the next refresh must draw
        self.need_build = False
        self._restack()

    # The former home-screen passphrase bench was removed. The imported
    # Marble Passphrase Studio is the single supported passphrase interface.

    BZ_BEIGE, BZ_HI, BZ_LO, BZ_DK = "#2a2d33", "#4a505a", "#1c1e23", "#0e0f12"
    BZ_INK = "#8fa3b8"
    BZ_BTNS = (("GRADE", "bz1"), ("WIRE", "bz3"), ("TONGUE", "bz5"), ("CUT", "bz6"), ("PASS", "bz10"))   # 1063: PASS pops up the passphrase
    BZ_WIN = (("MIN", "bz7"), ("WINDOW", "bz8"), ("CLOSE", "bz9"))

    def margins(self, TW, TH):
        if not self.o.get("bezel", True):
            return (0, 0, 0, 0)
        from oracle_photo_bezel import photo_geometry, photo_zip, photo_step, SOURCE_W, SOURCE_H
        if photo_zip() is not None:
            from oracle_photo_bezel import photo_scale_for_size
            k = photo_scale_for_size(TW, TH)
            if k is None:
                # Interactive resizing may produce intermediate non-image sizes;
                # choose a complete image that fits while the host snaps back.
                k = photo_step(min(TW / float(SOURCE_W), TH / float(SOURCE_H)))
            g = photo_geometry(k)
        else:
            k = bezel_step(min(TW / 1320.0, TH / 998.0))
            g = bezel_geometry(k)
        return (g["l"], g["t"], g["r"], g["b"])


    def _tab_size(self, n, room, width, gap):
        """(w, h) every menu-row tab shares: the largest step of the tab size ladder no taller than `room` whose strip of n tabs
        fits in `width`."""
        best = None
        for h, w in zip(self.TAB_H, self.TAB_W):
            if best is None or (h <= room and n * w + (n - 1) * gap <= width):
                best = (w, h)
        if n > 1 and n * best[0] + (n - 1) * gap > width:                 # even the smallest step is too wide (five tabs, a narrow window): squeeze the width, keep the slant
            best = (max(self.TAB_MIN_W, int((width - (n - 1) * gap) / n)), best[1])
        return best

    def _tab_shape(self, my1, ax, w, h, fill, outline):
        """The shared tab outline: w x h, sitting on the menu row's bottom edge, every tab at the same slant."""
        c = self.c
        sl, top = h * TAB_SLOPE, my1 - h
        poly = c.create_polygon(ax, my1, ax + sl, top, ax + w - sl, top, ax + w, my1, fill=fill, outline=outline, width=2,
                                tags="chrome")
        line = c.create_line(ax + 2, my1, ax + w - 2, my1, fill=fill, width=3, tags="chrome")
        return poly, line, sl, top, (top + my1) / 2 + 1

    def _fit_px(self, text, px, room, bold=True, mono=False):
        """Largest font size (from px down) whose `text` fits in `room` px."""
        while px > TAB_MIN_PX and self.font(px, bold, mono).measure(text) > room:
            px -= 1
        return px

    TAB_SHORT = {"dk": "PASS"}             # 1038: MEDIA and PASSPHRASE (were DRUM DECK and KEY CUT, renamed at the owner's word)

    def _tab_label(self, key, full, room, measure_as=None):
        """(label, px) for a menu-row tab: the full label at the largest size that fits `room`; when even the smallest size (TAB_MIN_PX) does not fit, which
        happens when the menu is full in a small window, the short form (DRUM / KEYS).  `measure_as` is the widest text the label can become (the deck's "ARCHIVE DECK *")."""
        probe = measure_as or full
        px = self._fit_px(probe, 12, room)
        if self.font(px, True, False).measure(probe) > room:
            short = self.TAB_SHORT[key]
            probe = short + (" *" if measure_as and measure_as.endswith(" *") else "")
            return short, self._fit_px(probe, 12, room)
        return full, px


    def _dk_tab(self, my1, ax, w, h):
        """DICEKEY: a flat yellow field and a black die whose pips walk."""
        c = self.c
        on = self.dk is not None
        poly, line, sl, top, mid = self._tab_shape(my1, ax, w, h, DK_TAB_ON if on else DK_TAB_OFF, TAB_EDGE)
        d = max(8, min(int(h * 0.42), 18))
        dx0 = ax + sl + 4
        c.create_rectangle(dx0, mid - d / 2.0, dx0 + d, mid + d / 2.0, fill="#111111", outline=TAB_INK, width=2, tags="chrome")
        r = max(1, d // 8)
        pips = []
        for fx, fy in ((0.3, 0.3), (0.7, 0.7)):                              # two pips: a die showing two
            pips.append(c.create_oval(dx0 + d * fx - r, mid - d / 2.0 + d * fy - r, dx0 + d * fx + r, mid - d / 2.0 + d * fy + r,
                          fill="#ffffff", outline="", tags="chrome"))
        lx0 = dx0 + d + 6
        label, px = self._tab_label("dk", "PASSPHRASE", ax + w - sl - 4 - lx0)
        txt = self.T(lx0, mid, "CLOSE" if on else label, px, tab_ink(DK_TAB_ON if on else DK_TAB_OFF), "w", "chrome", True, False)
        self.dk_tab = dict(poly=poly, line=line, txt=txt, label=label, motion="die", mark=(dx0, mid, d, r, pips))
        self.hot.append((ax, top, ax + w, my1, "dk"))

    def _dk_state(self, on):
        self._update_primary_tab_state()
        t = self.dk_tab
        if t is None:
            return
        try:
            if t["poly"] is None:                      # 1034: a clean tab
                return self.clean_tab_state(t, on, t.get("label", "PASSPHRASE"))
            fill = DK_TAB_ON if on else DK_TAB_OFF
            self.c.itemconfigure(t["poly"], fill=fill)
            self.c.itemconfigure(t["line"], fill=fill)
            self.c.itemconfigure(t["txt"], text="CLOSE" if on else t.get("label", "PASSPHRASE"), fill=tab_ink(fill))
        except Exception:
            pass

    def _tab_art_tick(self, now):
        """The marks move: the die's pips walk.  The tab LABELS do not: since 0998 they stand still (they used to crawl and
        sway).  --calm (MARBLE_ORACLE_CALM=1) holds the marks still too.  Nothing here ever touches a label's text or position."""
        if os.environ.get("MARBLE_ORACLE_CALM", "") == "1":
            return
        if now - getattr(self, "_tab_art_t", 0) < 0.04:
            return
        self._tab_art_t = now
        for key in ("dk_tab",):
            t = getattr(self, key, None)
            if not t or not t.get("mark"):
                continue
            mark = t["mark"]
            try:
                if t["motion"] == "die":
                    dx0, mid, d, r, pips = mark
                    faces = ((0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3), (0.5, 0.5), (0.5, 0.28))
                    step = int(now * 1.4) % 3
                    for i, pip in enumerate(pips):
                        fx, fy = faces[(step + i) % len(faces)]
                        self.c.coords(pip, dx0 + d * fx - r, mid - d / 2.0 + d * fy - r, dx0 + d * fx + r, mid - d / 2.0 + d * fy + r)
            except Exception:
                pass

    TAB_MIN_W = 66                                            # the narrowest a squeezed tab gets; a tab that narrow shows the short labels (_tab_label)
    TAB_H = (22, 26, 30, 34, 38, 44, 52, 60)                  # the menu-row tab size ladder: heights ...
    TAB_W = (79, 95, 110, 127, 143, 167, 202, 233)            # ... and the width that goes with each

    def _section_actions(self):
        """Move the former header commands to their functional sections.

        WIRE -> quotation, TONGUE -> Latin word, CUT -> tarot/rune draw,
        GRADE -> global footer. These rectangles are chrome so content
        redraws (especially the Rune flip frames) cannot hide them.
        """
        c = self.c
        controls = (("trans", "WIRE", "next"), ("lex", "TONGUE", "word"),
                    ("cards", "CUT", "deal"), ("status", "GRADE", "view"))
        for section, label, action in controls:
            x0, y0, x1, y1 = self.rect[section]
            width = min(max(62, int(88 * self.k)), max(45, (x1 - x0) - 18))
            height = min(max(18, int(25 * self.k)), max(14, (y1 - y0) - 6))
            if section == "status":
                # Keep GRADE at the right-hand end of the global footer.
                # The physical CRT surround needs a larger inset from the bezel.
                right_inset = (max(58, int(72 * self.k)) if self.case_on()
                               else max(7, int(10 * self.k)))
                left = max(x0 + 4, x1 - width - right_inset)
            else:
                left = x0 + (max(58, int(72 * self.k))
                             if self.case_on() and section == "lex"
                             else max(7, int(10 * self.k)))
                # Physical CRT framing intrudes over the first few pixels of
                # the left-column panels; these buttons remain inside usable glass.
                left = min(left, x1 - width - 4)
            inset = min(max(3, int(8 * self.k)), max(2, (y1 - y0 - height)//2))
            top = max(y0 + 2, y1 - height - inset)
            right, bottom = left + width, top + height
            # Secondary actions match Oggcultist's matte button treatment:
            # the orange accent remains for the selected tab and primary CTA.
            c.create_rectangle(left, top, right, bottom, fill="#2F2620",
                               outline="#59473B", width=1,
                               tags=("chrome", "section-actions"))
            self.T((left+right)/2, (top+bottom)/2, label,
                   10, "txt", "center", ("chrome", "section-actions"), True, False)
            self.hot.append((left, top, right, bottom, action))

    def _arch(self):
        b = self.rect["arch"]
        hh, self.arch_hdr = self.panel(b, "PLATE VAULT", "PLATE %d" % (self.plate + 1), brackets=True)
        x0, y0, x1, y1 = b
        aw, ah = x1 - x0 - 30, y1 - y0 - hh - 34
        self.arch_box = (x0 + 15, y0 + hh + 6, x0 + 15 + aw, y0 + hh + 6 + ah)
        self.arch_cap = self.T((x0 + x1) / 2, y1 - 13, "", 11, "dim", "center", mono=not self.clean())
        self.arch_fit = {}
        self.arch_key = None
        # Bounded PhotoImage cache: ASCII art now uses crisp micro-glyph
        # rasterisation rather than sub-3px antialiased Tk text.
        self._ascii_sprite_cache = {}
        self._ascii_sprite_current = None
        self.marble_ramp = self._marble_ramp()

    ART_ASPECT = 0.46                 # width / height of a cell the 3.8 plates were rendered for

    def _marble_ramp(self):
        """Muted limestone shades, matching the opaque bitmap glyph renderer.

        Keep highlights distinctly readable against Oggcultist's near-black
        sidebar, without the nearly pure-white glow of the previous build.
        """
        return ["#675E57", "#766C63", "#857A70", "#94887C", "#A39789",
                "#B1A597", "#BDB1A2", "#C6BAAA", "#CDC1B0", "#D3C8B8"]

    def _arch_fit(self, plate):
        """Largest bold monospace face at which this plate's whole turn fits the panel (per plate: the works are not the
        same shape, and a narrow column fitted to the widest of them would sit marooned in the middle)."""
        f = self.arch_fit.get(plate)
        if f:
            return f
        x0, y0, x1, y1 = self.arch_box
        aw, ah = x1 - x0, y1 - y0
        # a plate bigger than the panel can hold even in the smallest face is downsampled by the Statue (mesh-raster
        # plates from 4.1-0934 are 160x80); smaller plates are shown exactly as baked
        # Probe fit using a smaller minimum face so the high-detail archive plates
        # can keep more characters on screen before the underlying data is
        # downsampled. This increases the apparent ASCII resolution.
        fo = self.tkfont.Font(family=self.family, size=-3, weight="bold")
        wmin = max(1, fo.measure("M"))
        hmin = max(max(fo.metrics("linespace") - 2, 4), int(wmin / self.ART_ASPECT * 0.84))
        self.statue.set_fit(plate, aw // wmin, ah // hmin)
        cols, rows = self.statue.dims(plate)
        best = None
        for px in range(20, 2, -1):
            fo = self.tkfont.Font(family=self.family, size=-px, weight="bold")
            w = max(1, fo.measure("M"))
            if w * cols > aw:
                continue
            ideal = w / self.ART_ASPECT
            floor_ = max(fo.metrics("linespace") - 3, 5)
            for h in range(int(round(ideal)), int(ideal * 0.82) - 1, -1):      # up to ~18% vertical squash before a smaller face
                if h >= floor_ and h * rows <= ah:
                    best = (fo, w, h)
                    break
            if best:
                break
        if best is None:
            fo = self.tkfont.Font(family=self.family, size=-3, weight="bold")
            w = max(1, fo.measure("M"))
            best = (fo, w, max(4, int(round(w / self.ART_ASPECT))))
        self.arch_fit[plate] = best
        return best

    def _arch_draw(self, plate, k):
        """Draw the archive as a pixel-crisp ASCII plate above the CRT filters.

        At the display's actual cell size (often 3x6 pixels) Tk's antialiased
        text rasterizer was turning glyphs into subpixel grey specks, regardless
        of their configured foreground colour.  This version keeps the source
        characters/shading but gives each micro glyph opaque pixel strokes.
        """
        c = self.c
        c.delete("statue")
        fo, w, h = self._arch_fit(plate)
        cols, rows = self.statue.dims(plate)
        x0, y0, x1, y1 = self.arch_box
        left = (x0 + x1) // 2 - cols * w // 2
        top = (y0 + y1) // 2 - rows * h // 2
        try:
            import base64
            from oracle_ascii_bitmap import render
            key = (plate, k, w, h, self.statue.step.get(plate, 1))
            ph = self._ascii_sprite_cache.get(key)
            if ph is None:
                raw = render(self.statue, plate, k, w, h)
                ph = self.tkmod.PhotoImage(master=c, data=base64.b64encode(raw))
                if len(self._ascii_sprite_cache) >= 48:
                    # The current image remains alive through the image item
                    # until it is replaced below. Keep cache memory bounded.
                    self._ascii_sprite_cache.clear()
                self._ascii_sprite_cache[key] = ph
            self._ascii_sprite_current = ph
            c.create_image(left, top, image=ph, anchor="nw",
                           tags=("content", "statue"))
            return
        except (ImportError, RuntimeError, ValueError, self.tkmod.TclError):
            # Graceful fallback for environments with an unavailable Pillow/Tk
            # PNG reader. The app must not crash just because art cannot render.
            self._ascii_sprite_current = None
        # Legacy text fallback only; preserve normal app startup.
        dense = {".": "#", ",": "#", ":": "#", ";": "#", "-": "#",
                 "=": "%", "+": "%", "*": "@", "#": "@", "%": "@", "@": "@"}
        for row, col, txt, band in self.statue.runs(plate, k):
            ink = self.marble_ramp[band]
            for offset, symbol in enumerate(txt):
                c.create_text(left + (col + offset) * w, top + row * h,
                              anchor="nw", text=dense.get(symbol, "#"),
                              fill=ink, font=fo, tags=("content", "statue"))

    ARCH_DWELL, ARCH_TURN = 16.0, 8.0     # seconds a plate stays up / one full revolution

    def _arch_tick(self, now):
        st = self.statue
        n = len(st.plates)
        plate = int(now // self.ARCH_DWELL) % n
        nf = len(st.plates[plate])
        k = int(((now % self.ARCH_DWELL) / self.ARCH_TURN % 1.0) * nf)
        if (plate, k) == self.arch_key:
            return
        self.arch_key = (plate, k)
        self._arch_draw(plate, k)
        self.c.itemconfigure(self.arch_cap, text=fit("%s  %03d\u00b0" % (st.names[plate], k * 360 // nf),
                                                     self.font(11, False, not self.clean()), self.rect["arch"][2] - self.rect["arch"][0] - 16))
        self.c.itemconfigure(self.arch_hdr, text="PLATE %d/%d" % (plate + 1, n))
        self.skin_chip(self.arch_hdr, self.col("dim"), "archchip")

    def _lex(self):
        b = self.rect["lex"]
        hh, _ = self.panel(b, "DEAD TONGUE", "LINGUA")
        x0, y0, x1, y1 = b
        top, gl, cl, ec = (8, 48, 82, 112) if self.skin_on() else (12, 52, 88, 120)
        z = self.lex_zoom = self._lex_zoom(b)
        gl, cl, ec = int(gl * z), int(cl * z), int(ec * z)
        self.lex_ids = dict(
            lemma=self.T(x0 + 12, y0 + hh + top, "", int(32 * z), "gold", "nw", bold=True, mono=not self.skin_on()),
            gloss=self.T(x0 + 12, y0 + hh + top + int(gl * self.k), "", int(16 * z), "txt", mono=not self.skin_on()),
            cls=self.T(x0 + 12, y0 + hh + top + int(cl * self.k), "", int(14 * z), "cyan"),
            ecc=self.T(x0 + 12, y0 + hh + top + int(ec * self.k), "", int(14 * z), "mag"),
            idx=self.T(x1 - 10, y0 + hh + 12, "", 11, "dim", "ne"))
        # The volume slider is gone. The bezel dial still sets the voice.
        # The freed band holds the sentence. SPEAK stays at the foot.
        self.slider = None
        foot = int(34 * self.sy)
        sb = (x1 - int(78 * max(1.0, self.sx)), y1 - foot, x1 - 10, y1 - int(8 * self.sy))
        vy = (sb[1] + sb[3]) / 2
        if self.skin_on():
            try:
                self.skin_button(sb, "content")
            except Exception:
                self.skin_ok = False
        if not self.skin_on():
            self.B(sb, "panel", "cyan")
        self.T((sb[0] + sb[2]) / 2, vy, "SPEAK", 12, self.col("bg") if self.skin_on() else "cyan", "center", bold=True, mono=not self.skin_on())
        self.hot.append((sb[0], sb[1], sb[2], sb[3], "speak"))
        sent_top = y0 + hh + top + int((ec + 22 * z) * self.k)
        self.lex_room = (x0 + 12, sent_top, max(40, x1 - x0 - 24), y1 - foot - int(8 * self.sy))
        self.lex_mode = self.T(x0 + max(102, int(112 * self.k)), y1 - 12 * self.sy, "", 11, "dim", "w", ("content", "lexvoice") if self.clean() else "content", mono=not self.clean())
        if self.clean():
            self.lex_voice_open = False
            self.voice_btn = self.T(x0 + max(102, int(112 * self.k)), y1 - 12 * self.sy, "Voice", 11, "dim", "w", "content", False, False)
            self.hot.append((x0 + max(98, int(108 * self.k)), int(y1 - 24 * self.sy), x1, y1, "lexvoice"))
            self.c.itemconfigure("lexvoice", state="hidden")
        else:
            self.hot.append((x0 + max(98, int(108 * self.k)), int(y1 - 24 * self.sy), x1, y1, "ecc"))
        ry = y0 + hh + top + int(cl * self.k)            # click a pronunciation row to hear just that one
        self.hot.append((x0, ry - 2, x1, ry + int(20 * z * self.k), "say_c"))
        self.hot.append((x0, ry + int(20 * z * self.k), x1, ry + int((ec - cl + 22 * z) * self.k), "say_e"))
        self.set_word(self.wi)

    LEX_REF = (292, 267)                                    # DEAD TONGUE's size in CLASSIC, reference units

    def _lex_zoom(self, b):
        """1065: how much larger than CLASSIC's DEAD TONGUE this panel is (1 at that size or smaller, at most 1.6), by its tighter side."""
        try:
            w, h = (b[2] - b[0]) / float(self.sx), (b[3] - b[1]) / float(self.sy)
        except (AttributeError, ZeroDivisionError, TypeError):
            return 1.0
        return max(1.0, min(1.6, w / self.LEX_REF[0], h / self.LEX_REF[1]))

    def set_word(self, i):
        self.wi = i % len(LEXICON)
        lem, gl = LEXICON[self.wi]
        c, ids = self.c, self.lex_ids
        c.itemconfigure(ids["lemma"], text=lem.upper())
        c.itemconfigure(ids["gloss"], text='"%s"' % gl)
        info = lexicon_ipa(lem)
        for key, lab, e in (("cls", "CLASSICAL   ", False), ("ecc", "ECCLESIAST. ", True)):
            if info:                                     # IPA; \u25cf = a person said it, \u25cb = the synthesiser did
                mark = ("\u25cf" if self.voice.recorded(lem, e) else "\u25cb") if self.voice.has(lem, e) else "\u00b7"
                txt = "%s%s /%s/" % (lab, mark, info[1 if e else 0])
            else:                                        # no IPA on file: rough respelling, robot voice
                txt = "%s~ %s" % (lab, respell(lem, e))
            c.itemconfigure(ids[key], text=txt, font=self.font_ipa(int(14 * getattr(self, "lex_zoom", 1.0))))
        c.itemconfigure(ids["idx"], text="%02d/%02d" % (self.wi + 1, len(LEXICON)))
        c.itemconfigure(self.lex_mode, text="[E] SPEAK: %s%s" % ({"both": "CLASSICAL + ECCLES.", "c": "CLASSICAL", "e": "ECCLESIASTICAL"}[self.vmode],
                                                                 "" if self.voice.has(lem, False) else "  (synth)"))
        self._lex_sentence(lem)
        self._vol_draw()

    def _lex_lines(self, text, font, fill, x, y, width, bottom):
        line_h = font.metrics("linespace") + 2
        for line in wrap_px(text, font, width):
            if y + line_h > bottom:
                break
            self.c.create_text(int(x), int(y), text=line, anchor="nw", font=font, fill=fill, tags=("content", "lexcopy"))
            y += line_h
        return y

    def _lex_sentence(self, lem):
        """The classical sentence and its English, in the room the slider used to take."""
        from oracle_sententiae import sententia
        self.c.delete("lexcopy")
        room = getattr(self, "lex_room", None)
        if not room:
            return
        x, y, width, bottom = room
        if bottom <= y + 8:
            return
        latin, english = sententia(lem)
        z = getattr(self, "lex_zoom", 1.0)
        face = not self.skin_on()
        y = self._lex_lines(latin, self.font(int(15 * z), True, face), self.col("gold"), x, y, width, bottom)
        y += int(8 * self.k)
        self._lex_lines(english, self.font(int(13 * z), False, face), self.col("txt"), x, y, width, bottom)

    def speak_word(self, mode):
        lem = LEXICON[self.wi][0]
        if self.voice.busy:
            return self.say("...STILL SPEAKING")
        self.say("SPEAKING %s" % lem.upper() if self.voice.speak(lem, mode) else "AUDIO BACKEND MISSING")

    def _vol_draw(self):
        if not self.slider:
            return
        tx0, tx1, vy = self.slider
        x = tx0 + (tx1 - tx0) * self.voice.vol
        self.c.coords(self.vol_id, tx0, vy, x, vy)
        if self.c.type(self.vol_knob) == "image":                 # 1031: the skin's knob is a picture, centred on the value
            self.c.coords(self.vol_knob, x, vy)
        else:
            self.c.coords(self.vol_knob, x - 4, vy - 9, x + 4, vy + 9)

    def _trans(self):
        b = self.rect["trans"]
        self.trans_hdr = self.panel(b, "THE WIRE", "")[1]
        x0, y0, x1, y1 = b
        hh = self.hdr_h()
        self.trans_box = b
        self.q_hh = hh
        self.layout_quote()
        # scene: dusk sky (dithered bands), sun, skyline + spire, ground grid, a track and the oncoming train
        sy0 = y0 + int((y1 - y0) * 0.50)
        sy1 = y1 - int(74 * self.sy)
        hz = sy0 + int((sy1 - sy0) * 0.70)
        self.hz = hz
        cx = (x0 + x1) // 2
        pw = x1 - x0
        vx = x0 + int(0.36 * pw)                          # the track's vanishing point: left of the sun, at the foot of the mountain
        R = int(min(pw * 0.26, (hz - sy0) * 0.85))
        c = self.c
        self.wire = None
        try:
            import oracle_wire                              # 1025: the owner's WIRE scene (night city, train, nine timed scenes); the dusk scene below is the fallback
            self.wire = oracle_wire.Wire(c, b, self.col)
        except Exception:
            c.delete("train")                               # whatever a failed build left behind
            self.wire = None
        self.train3d = None
        self.cars = []
        if self.wire is None:
            band = mix(self.col("panel"), self.col("mag"), 0.55)
            nb = 5                                            # dusk: stippled bands, denser toward the horizon
            for j, st in enumerate(("gray12", "gray12", "gray25", "gray50", "gray75")):
                ya, yb = sy0 + (hz - sy0) * j // nb, sy0 + (hz - sy0) * (j + 1) // nb
                c.create_rectangle(x0 + 10, ya, x1 - 10, yb + 1, fill=band, stipple=st, outline="", tags="content")
            c.create_arc(cx - R, hz - R, cx + R, hz + R, start=0, extent=180, style="pieslice",
                         fill=self.col("sun1"), outline="", tags="content")
            for j in range(1, 6):                   # scan stripes in the sun
                yy = hz - R + int(R * (0.45 + 0.1 * j) )
                if yy < hz:
                    c.create_rectangle(cx - R, yy, cx + R, yy + max(1, j), fill=self.col("panel"), outline="", tags="content")
            c.create_arc(cx - R, hz - R, cx + R, hz + R, start=0, extent=180, style="arc", outline=self.col("sun2"), width=2, tags="content")
            # Mount Fuji at dusk: a stepped, pixel-edged violet cone with a pink snowcap, behind the skyline and in front of the sun
            fx, fh, fw = x0 + 10 + int(pw * 0.22), (hz - sy0) * 0.92, pw * 0.34
            step = max(3, int(4 * self.sy))
            left, right = [], []
            yy = hz
            while yy > hz - fh:
                t = (hz - yy) / fh
                half = fw * (1 - t ** 0.62) if t < 1 else 0
                left.append((fx - half, yy))
                right.append((fx + half, yy))
                yy -= step
            body = []
            for (lx, ly) in left:
                body += [(max(x0 + 10, lx), ly), (max(x0 + 10, lx), ly - step)]
            for (rx, ry) in reversed(right):
                body += [(min(x1 - 10, rx), ry - step), (min(x1 - 10, rx), ry)]
            c.create_polygon([v for pt in body for v in pt], fill=mix(self.col("panel"), "#7a4fd0", 0.55), outline="", tags="content")
            cap_n = max(2, int(len(left) * 0.24))
            cap = []
            for (lx, ly) in left[-cap_n:]:
                cap += [(lx + (step if (ly // step) % 2 else 0) + 2, ly), (lx + (step if (ly // step) % 2 else 0) + 2, ly - step)]
            for (rx, ry) in reversed(right[-cap_n:]):
                cap += [(rx - (step if (ry // step) % 2 else 0) - 2, ry - step), (rx - (step if (ry // step) % 2 else 0) - 2, ry)]
            if len(cap) >= 3:
                c.create_polygon([v for pt in cap for v in pt], fill=mix("#ffd6f2", self.col("mag"), 0.25), outline="", tags="content")
            rr = random.Random(11)
            wr = random.Random(23)
            sx = x0 + 10
            while sx < x1 - 10:
                w = rr.randint(int(14 * self.sx), int(38 * self.sx))
                h = rr.randint(int(10 * self.sy), int(46 * self.sy))
                xe = min(x1 - 10, sx + w)
                c.create_rectangle(sx, hz - h, xe, hz, fill="#0b0e1c", outline=self.col("edge"), tags="content")
                for _ in range(int(w * h / (110.0 * self.sx * self.sy))):     # a few lit windows
                    wx, wy = wr.randint(int(sx) + 3, max(int(sx) + 3, int(xe) - 5)), wr.randint(int(hz - h) + 3, max(int(hz - h) + 3, int(hz) - 5))
                    c.create_rectangle(wx, wy, wx + 2, wy + 3, fill=self.col(wr.choice(("gold", "cyan", "gold"))), outline="", tags="content")
                sx += w + 2
            tx, th, tw = x0 + int(pw * 0.80), 104 * self.sy, 7 * self.sx          # the spire
            c.create_polygon(tx - tw, hz, tx - tw * .85, hz - th * .38, tx - tw * .4, hz - th * .62, tx - tw * .15, hz - th * .86,
                             tx, hz - th, tx + tw * .15, hz - th * .86, tx + tw * .4, hz - th * .62, tx + tw * .85, hz - th * .38, tx + tw, hz,
                             fill="#0b0e1c", outline=self.col("edge"), tags="content")
            c.create_oval(tx - 2, hz - th - 2, tx + 2, hz - th + 2, fill=self.col("red"), outline="", tags="content")
            c.create_rectangle(x0 + 10, hz, x1 - 10, sy1, fill=self.col("panel"), outline="", tags="content")
            c.create_line(x0 + 10, hz, x1 - 10, hz, fill=self.col("mag"), width=2, tags="content")
            for j in range(1, 5):
                yy = hz + (sy1 - hz) * (j / 4.0) ** 2
                c.create_line(x0 + 10, yy, x1 - 10, yy, fill=self.col("edge"), tags="content")
            self.train3d = None
            self.cars = []
            try:
                import oracle_train
                self.train3d = oracle_train.Train3D(c, (x0 + 10, sy0, x1 - 10, sy1), hz, vx, sy1, mix, mix(self.col("panel"), self.col("mag"), 0.35),
                                                    self.col("panel"))
            except Exception:
                self.train3d = None
            if self.train3d is None:                            # no oracle_train.py: the old flat maglev
                self.rail_y = hz - int(6 * self.sy)
                c.create_line(x0 + 10, self.rail_y + 3, x1 - 10, self.rail_y + 3, fill=self.col("cyan"), tags="content")
                self.car_w = int(52 * self.sx)
                for j in range(5):
                    r = c.create_rectangle(0, 0, 0, 0, fill=self.col("txt"), outline=self.col("cyan"), tags="content")
                    wd = c.create_rectangle(0, 0, 0, 0, fill=self.col("cyan"), outline="", tags="content")
                    self.cars.append((r, wd))
                self.train_span = (x0 + 10, x1 - 10)
        c.tag_raise("quote")                                # the quote is always in front of the scene
        # plaque
        pb = (x0 + 12, sy1 + 8, x1 - 12, y1 - 10)
        if self.skin_on():
            try:
                self.skin_well(pb, "content", 10, None if self.clean() else self.col("gold"), 0.25)   # 1031: the plaque is a lit well; 1034: a plain one
            except Exception:
                self.skin_ok = False
        if not self.skin_on():
            self.B(pb, "#0d1020", "gold", "content", 2)
        self.plq = self.T(pb[0] + max(92, int(105 * self.k)), (pb[1] + pb[3]) / 2, "", 14, "dim" if self.clean() else "gold", "w", bold=True, mono=not self.clean())
        self.plaque_w = max(60, pb[2] - pb[0] - max(105, int(116 * self.k)))
        self.set_quote_meta()

    TRAIN_CYCLE, TRAIN_RUN = 11.0, 7.4          # seconds per pass / of it the train is on screen

    def _train_tick(self, now):
        try:
            if self.wire is not None:
                self.wire.update(now - self.t0)              # 1025: one clock for the whole loop, so a resize or VIEW does not restart it
            else:
                self.train3d.update(now % self.TRAIN_CYCLE, self.TRAIN_RUN)
        except Exception:
            self.wire = self.train3d = None                  # a broken scene never takes the window with it (it stays as last drawn)

    def layout_quote(self):
        c = self.c
        c.delete("quote")
        x0, y0, x1, y1 = self.trans_box
        q, who = self.deck[self.qi % len(self.deck)]
        pal = (["txt", "dim", "gold", "orange", "txt"] if self.clean() else
               ["cyan", "mag", "gold", "lime", "txt"])       # Oggcultist warm typography; retro unchanged. # 1034: the clean look set the quote in one colour; 1050: the retro run of colours is back
        runs = [(w, pal[i % len(pal)]) for i, w in enumerate(q.split())]
        top = y0 + self.q_hh + 14
        lim = y0 + int((y1 - y0) * 0.50) - 8
        for px in (32, 28, 25, 22, 20, 18, 16, 14, 12):
            f = self.font(px, True, not self.clean())
            words, h = flow(runs, f, x1 - x0 - 28, int(f.metrics("linespace") * 1.08), x0 + 14, top)
            if top + h <= lim:
                break
        for wd, colr, x, y in words:
            c.create_text(x, y, text=wd, font=f, fill=self.col(colr), anchor="nw", tags=("content", "quote"))
        if c.find_withtag("train"):
            c.tag_raise("quote", "train")

    def set_quote_meta(self):
        q, who = self.deck[self.qi % len(self.deck)]
        self.c.itemconfigure(self.plq, text=fit("— " + who.upper(), self.font(12, True, not self.clean()), self.plaque_w))
        # header counter lives in the panel's title row
        x0, y0, x1, y1 = self.trans_box
        self.c.delete("thdr")
        self.T(x1 - (max(1, int(round(10 * self.k))) if self.skin_on() else 8), y0 + self.q_hh // 2, "%d / %d" % (self.qi % len(self.deck) + 1, len(self.deck)), 11, "dim", "e", ("content", "thdr"))

    def _augurspex_panel(self):
        """HOME's original market-panel footprint, now a real rotating AUGURSPEX history chart."""
        self.panel(self.rect['aug'], 'AUGURSPEX')
        x0, y0, x1, y1 = self.rect['aug']
        hh = self.hdr_h()
        # The tiny header arrows allow navigation without opening the companion tab.
        self.hot.append((x1 - 82 * self.k, y0, x1 - 50 * self.k, y0 + hh, 'aug_previous'))
        self.hot.append((x1 - 35 * self.k, y0, x1 - 3 * self.k, y0 + hh, 'aug_next'))
        self.draw_augurspex_chart()

    def draw_augurspex_chart(self):
        """Paint local historical candles as a line. Never fabricate values or call network from Tk."""
        if 'aug' not in getattr(self, 'rect', {}):
            return
        c = self.c
        c.delete('aug-chart')
        x0, y0, x1, y1 = self.rect['aug']
        hh = self.hdr_h()
        chart = self.augurspex_chart.snapshot()
        tag = ('content', 'aug-chart')
        width = x1 - x0
        n = chart['total']
        self.T(x1 - 63 * self.k, y0 + hh / 2, '<', 13, 'txt', 'center', tag, True)
        self.T(x1 - 40 * self.k, y0 + hh / 2, str(chart['index'] + 1) + '/' + str(n) if n else '0/0', 10, 'dim', 'center', tag)
        self.T(x1 - 16 * self.k, y0 + hh / 2, '>', 13, 'txt', 'center', tag, True)
        if not n:
            self.T((x0+x1)/2, (y0+hh+y1)/2, 'NO AUGURSPEX WATCHLIST MARKETS', 11,
                   'dim', 'center', tag)
            return
        sym = chart['symbol']
        name = chart['name']
        self.T(x0 + 12*self.k, y0+hh+17*self.k,
               fit(name, self.font(14, True), width-25*self.k), 14, 'cyan', 'w', tag, True)
        self.T(x0 + 12*self.k, y0+hh+38*self.k, sym, 12, 'txt', 'w', tag)
        plot_l = x0 + 15*self.k
        plot_r = x1 - 15*self.k
        plot_t = y0 + hh + 54*self.k
        plot_b = max(plot_t + 8, y1 - 45*self.k)
        if chart['state'] != 'data':
            note = {'loading':'LOADING HISTORICAL PRICES', 'offline':'NETWORK DISABLED',
                    'unavailable':'HISTORY UNAVAILABLE', 'idle':'AWAITING MARKET HISTORY'}.get(chart['state'], 'WAITING')
            self.T((x0+x1)/2, (plot_t+plot_b)/2, note, 12, 'dim', 'center', tag)
            if chart['state'] == 'unavailable':
                self.T((x0+x1)/2, plot_b+12*self.k, 'SEE FULL CHART IN AUGURSPEX TAB', 9, 'dim', 'center', tag)
            return
        candles = chart['candles']
        # Keep only finite numeric close values; the unaltered provider payload
        # supplies observation times and candle data. Nothing simulated.
        closes = [float(row['close']) for row in candles
                  if isinstance(row, dict) and isinstance(row.get('close'), (int,float))
                  and math.isfinite(row['close'])]
        if len(closes) < 2:
            self.T((x0+x1)/2, (plot_t+plot_b)/2, 'INSUFFICIENT PRICE HISTORY', 11, 'dim', 'center', tag)
            return
        low, high = min(closes), max(closes)
        span = (high-low) or max(abs(high)*.01, 1e-9)
        # A real grid, shared visual language with the full AUGURSPEX tab:
        # dark-but-distinct reference guides remain behind the price trace.
        grid=self.col('edge2')
        c.create_rectangle(plot_l,plot_t,plot_r,plot_b,
                           outline=grid,width=max(1,round(1.2*self.k)),tags=tag)
        for portion in (.25, .5, .75):
            y = plot_t + (plot_b-plot_t)*portion
            c.create_line(plot_l,y,plot_r,y,fill=grid,
                          width=max(1,round(self.k)),dash=(3,5),tags=tag)
        for portion in (.25, .5, .75):
            x = plot_l+(plot_r-plot_l)*portion
            c.create_line(x,plot_t,x,plot_b,fill=grid,
                          width=max(1,round(self.k)),dash=(3,5),tags=tag)
        points=[]
        for i, price in enumerate(closes):
            points.extend((plot_l+(plot_r-plot_l)*i/(len(closes)-1),
                           plot_b-(price-low)/span*(plot_b-plot_t)))
        positive = closes[-1]>=closes[0]
        colour = self.col('lime' if positive else 'red')
        c.create_line(*points, fill=self.col('bg'), width=max(3,round(6*self.k)),
                      joinstyle='round', capstyle='round', tags=tag)
        c.create_line(*points, fill=colour, width=max(2,round(3.6*self.k)),
                      joinstyle='round', capstyle='round', tags=tag)
        c.create_oval(points[-2]-4*self.k, points[-1]-4*self.k,
                      points[-2]+4*self.k, points[-1]+4*self.k,
                      fill=colour, outline=self.col('bg'), width=max(1,self.k), tags=tag)
        change = (closes[-1]/closes[0]-1)*100 if closes[0] else None
        price_text = ('%.4g' % closes[-1]) if abs(closes[-1]) > 1e6 else ('%.2f' % closes[-1])
        change_text = ('  %+0.2f%%' % change) if change is not None else ''
        self.T(plot_l, y1-29*self.k, price_text+change_text, 13,
               'lime' if positive else 'red', 'w', tag, True)
        provider = chart['source'].upper()
        cache = chart.get('cache','')
        observed = str(chart.get('observed') or '')[:16]
        label = provider + (' / CACHED' if cache == 'stale' else ' / HISTORY')
        if observed:
            label += ' / ' + observed
        # Delayed/EOD stock prices are intentionally not labelled live.
        self.T(plot_l, y1-12*self.k,
               fit(label, self.font(10), width-26*self.k), 10, 'dim', 'w', tag)

    def _mkt(self):
        b = self.rect["mkt"]
        self.mkt_hdr = self.panel(b, "THE TICKER", "AUD")[1]
        self.mkt_box = b
        self.mk_rows = {}

    def refresh_markets(self):
        c = self.c
        snap = self.markets.snapshot()
        sim = self.markets.any_sim() if snap else True
        # 1022 R2: _dyn calls this every 1.5 s and the feed moves about every 3 s.  Same numbers, same picture: nothing is deleted or redrawn.
        # build() deletes the "content" tag (every "mk" item has it) and clears the key, so a resize, VIEW or layout always redraws.
        key = (sim, tuple((s, d["price"], d["pct"], d["sim"], tuple(d["series"])) if d else (s,) for s, d in ((s, snap.get(s)) for s in ("BTC", "USD", "XAU", "XAG"))))
        if key == getattr(self, "_mk_key", None):
            return
        self._mk_key = key
        c.delete("mk")
        x0, y0, x1, y1 = self.mkt_box
        hh = self.hdr_h()
        c.itemconfigure(self.mkt_hdr, text="AUD" if self.clean() else ("AUD  SIM" if sim else "AUD  LIVE"), fill=self.col("orange" if sim else "lime"))
        if not self.clean():                                        # 1046: the SIM/LIVE chip repeated the star already on each row
            self.skin_chip(self.mkt_hdr, self.col("orange" if sim else "lime"), "mktchip")
        if not snap:
            self.T((x0 + x1) / 2, (y0 + y1) / 2, "MARKET DATA OFFLINE", 13, "dim", "center", ("content", "mk"))
            return
        rh = (y1 - y0 - hh - 8) / 4.0
        for i, s in enumerate(("BTC", "USD", "XAU", "XAG")):
            d = snap.get(s)
            if not d:
                continue
            ry = y0 + hh + 6 + i * rh
            if self.skin_on():                                   # 1031: each instrument on its own tile
                try:
                    self.skin_tile((x0 + 7, ry + 1, x1 - 7, ry + rh - 3), ("content", "mk"))
                except Exception:
                    self.skin_ok = False
            up = d["pct"] >= 0
            colr = "lime" if up else "red"
            sym = self.T(x0 + 12 + (4 if self.skin_on() else 0), ry + 4, s + ("*" if d["sim"] else ""), 15, "cyan", "nw", ("content", "mk"), True)
            if self.skin_on():                                   # 1032: the move on a tinted chip beside the symbol, the price under it
                bb = c.bbox(sym)
                mv = self.T(bb[2] + int(14 * self.k), (bb[1] + bb[3]) / 2, self.markets.fmt_pct(d["pct"]), 11, colr, "w", ("content", "mk"), True)
                self.skin_chip(mv, self.col(colr), "mkchip%d" % i, ("mk",))
                self.T(x0 + 16, ry + rh * 0.52, self.markets.fmt_price(s, d["price"]), 13, "txt", "nw", ("content", "mk"))
            else:
                self.T(x0 + 12, ry + rh * 0.52, "%s %s" % (self.markets.fmt_price(s, d["price"]), self.markets.fmt_pct(d["pct"])),
                       13, colr, "nw", ("content", "mk"))
            sx0, sx1 = x0 + (x1 - x0) * 0.56, x1 - 14
            ser = d["series"]
            lo, hi = min(ser), max(ser)
            span = (hi - lo) or 1.0
            pts = []
            for j, v in enumerate(ser):
                pts += [sx0 + (sx1 - sx0) * j / float(len(ser) - 1), ry + rh * 0.82 - (v - lo) / span * rh * 0.62]
            if self.skin_on():                                   # 1031: a soft area under the line
                base = ry + rh * 0.86
                c.create_polygon(*(pts + [sx1, base, sx0, base]), fill=hexmix(hexmix(self.skin_fill(), "#ffffff", 0.06), self.col(colr), 0.16), outline="", tags=("content", "mk"))
            c.create_line(*pts, fill=self.col(colr), width=2, tags=("content", "mk"))
            if not self.skin_on():
                c.create_line(x0 + 10, ry + rh - 2, x1 - 10, ry + rh - 2, fill=self.col("edge2"), tags=("content", "mk"))

    def _cards(self):
        self.cards_hdr = self.panel(self.rect["cards"], "THREE CUTS", "TODAY")[1]
        if not self.clean():
            self.skin_chip(self.cards_hdr, self.col("dim"), "cardschip")
        self.draw_cards()

    def card_ah(self, cw=None):
        """Height of the card art row.  1032: the skin takes a little more (0.565 of the panel, not 0.53) only when that reaches the next whole
        subsample step of the 320x533 art; otherwise the reading box keeps the room, so its last line is never clipped."""
        x0, y0, x1, y1 = self.rect["cards"]
        hh = self.hdr_h()
        if cw is None:
            cw = (x1 - x0 - int(10 * self.sx) * 4) // 3
        ah = int((y1 - y0 - hh) * 0.53)
        if self.skin_on():
            big = int((y1 - y0 - hh) * 0.565)
            step = lambda h: math.ceil(max(320.0 / max(1, cw - 6), 533.0 / max(1, h - 6)))
            if step(big) < step(ah):
                ah = big
        return ah

    def draw_cards(self):
        if self.divination_mode == "runes":
            self.draw_runes()
            return
        self._hide_rune_art_widgets()
        c = self.c
        c.delete("cards")
        c.delete("reading")
        self.hot = [h for h in self.hot if not str(h[4]).startswith("card")]
        self.card_imgs = []
        x0, y0, x1, y1 = self.rect["cards"]
        hh = self.hdr_h()
        gap = int(10 * self.sx)
        cw = (x1 - x0 - gap * 4) // 3
        ah = self.card_ah(cw)
        self.card_sel = getattr(self, "card_sel", 0) % 3
        for n, (idx, rev) in enumerate(self.cards):
            name, up, rv, suit = tarot_card(idx)
            cx0 = x0 + gap + n * (cw + gap)
            cy0 = y0 + hh + 8
            art = (cx0, cy0, cx0 + cw, cy0 + ah)
            img = self.tarot.get(self.c, idx, cw - 6, ah - 6, rev)
            sel = n == self.card_sel
            framed = False
            if self.skin_on() and img is not None:               # 1031: each card casts a shadow; 1032: the frame hugs the card, rounded, the chosen one glows
                try:
                    from oracle_skin import card as skin_card
                    p = max(3, int(4 * self.k))
                    mx, my = (art[0] + art[2]) // 2, (art[1] + art[3]) // 2
                    fb = (mx - img.width() // 2 - p, my - img.height() // 2 - p, mx - img.width() // 2 + img.width() + p, my - img.height() // 2 + img.height() + p)
                    sc = skin_card(self.k, self.skin_fill(), self.skin_border(), 0.8, 5, 10, 4, None, 0.0, self.skin_fill())
                    self.put_nine(sc["body"], fb, ("content", "cards"), fill=sc["fill"], out=sc["S"])
                    self.skin_well(fb, ("content", "cards"), 8, self.col("gold" if sel else ("red" if rev else "cyan")), 0.45 if sel else 0.12)
                    framed = True
                except Exception:
                    self.skin_ok = False
            if framed:
                self.card_imgs.append(img)
                c.create_image((art[0] + art[2]) // 2, (art[1] + art[3]) // 2, image=img, tags=("content", "cards"))
            elif img is not None:
                self.card_imgs.append(img)
                c.create_rectangle(*art, fill=self.col("panel"), outline=self.col("gold" if sel else ("red" if rev else "cyan")),
                                   width=3 if sel else 2, tags=("content", "cards"))
                c.create_image((art[0] + art[2]) // 2, (art[1] + art[3]) // 2, image=img, tags=("content", "cards"))
            else:
                self.vector_card(art, idx, name, suit, rev)
                if sel:
                    c.create_rectangle(*art, outline=self.col("gold"), width=3, tags=("content", "cards"))
            self.hot.append((art[0], art[1], art[2], art[3] + int(34 * self.k), "card%d" % n))
            ty = cy0 + ah + 4
            mono = not self.clean()                                 # 1034: the clean look names the cards in the UI face, a size down when needed
            npx = 11
            room = cw + gap - 4                                     # 1055: a name may use the gap beside its card, and steps down in --retro too
            while npx > (9 if not mono else 8) and self.font(npx, True, mono).measure(name) > room:
                npx -= 1
            self.T(cx0 + cw / 2, ty, fit(name, self.font(npx, True, mono), room), npx, "gold" if sel else "txt", "n", ("content", "cards"), True, mono)
            self.T(cx0 + cw / 2, ty + int(16 * self.k), ("REVERSED \u00b7 " if rev else "") + POSITIONS[n], 10,
                   "red" if rev else "dim", "n", ("content", "cards"), False, mono)
        self._draw_divination_toggle()
        self.draw_reading()

    def _draw_divination_toggle(self):
        """Compact, shared header toggle; Tarot and Runes use the same panel."""
        x0, y0, x1, y1 = self.rect["cards"]
        hh = self.hdr_h()
        # Place tabs just under the header, never over the retained title.
        w = max(45, int(65 * self.k))
        bh = max(17, int(22 * self.k))
        cy = y0 + hh + bh / 2 + 2
        cx = x1 - w * 2 - 8
        self.hot = [h for h in self.hot if h[4] not in ("mode_tarot", "mode_runes")]
        for n, (title, mode) in enumerate((("TAROT", "tarot"), ("RUNES", "runes"))):
            xa = cx + n * w
            ya, yb = cy - bh / 2, cy + bh / 2
            active = mode == self.divination_mode
            self.c.create_rectangle(xa, ya, xa + w - 2, yb,
                fill="#FB8E22" if active and self.clean() else self.col("edge2") if active else self.col("panel"),
                outline="#FB8E22" if active and self.clean() else self.col("gold") if active else self.col("edge"),
                tags=("content", "cards"))
            self.T(xa + w / 2 - 1, cy, title, 9,
                   "#2B1405" if active and self.clean() else "gold" if active else "dim",
                   "center", ("content", "cards"), True)
            self.hot.append((xa, ya, xa + w - 2, yb, "mode_" + mode))

    def _hide_rune_art_widgets(self):
        """Hide external stone widgets when returning to Tarot; do not touch layout."""
        for widget in self.rune_widgets:
            try:
                widget.place_forget()
            except Exception:
                pass

    def _show_rune_art_widget(self, index, image, cx, y, space, bounds):
        """Place complete PNG inside its assigned panel cell, with border clearance.

        A loaded PhotoImage can be larger than the requested stone size. Tk
        Labels crop such images when their place() rectangle is smaller. Use
        the *actual* image dimensions and constrain the entire rectangle to
        the safe region, not just the centre point.
        """
        import tkinter as tk
        while len(self.rune_widgets) <= index:
            label = tk.Label(self.c, bg=self.col("panel"), bd=0,
                             highlightthickness=0, padx=0, pady=0,
                             cursor="hand2")
            n = len(self.rune_widgets)
            label.bind("<Button-1>", lambda event, i=n: self.act("rune_select" + str(i)))
            self.rune_widgets.append(label)
        image_width, image_height = image.width(), image.height()
        left, top, right, bottom = bounds
        assert image_width <= int(space) and image_height <= int(space), (
            "Rune image larger than stone space", image_width, image_height, space)
        assert image_width <= right - left and image_height <= bottom - top, (
            "Rune image larger than panel safe area", bounds, image_width, image_height)
        px = max(left, min(int(round(cx - image_width / 2)), right - image_width))
        py = max(top, min(int(round(y)), bottom - image_height))
        label = self.rune_widgets[index]
        label.configure(image=image, bg=self.col("panel"))
        label.image = image
        label.place(x=px, y=py, width=image_width, height=image_height)
        label.rune_bounds = (px, py, px + image_width, py + image_height)
        label.rune_safe_box = bounds
        label.lift()

    def _rune_image(self, filename, maxsize):
        """Cache a Tk image by canvas lifetime; never alter the supplied PNG on disk."""
        return self.rune_deck.image_for(self.c, filename, maxsize)

    def draw_runes(self):
        """Original card panel positions retained; blank stone backs until reveal."""
        c = self.c
        if hasattr(self, "cards_hdr"):
            c.itemconfigure(self.cards_hdr, text="RUNES")
        c.delete("cards")
        c.delete("reading")
        self.hot = [h for h in self.hot if not str(h[4]).startswith(("card", "rune_", "mode_"))]
        self.rune_imgs = []
        self.rune_art_error = None
        x0, y0, x1, y1 = self.rect["cards"]
        hh = self.hdr_h()
        self._draw_divination_toggle()
        gap = max(4, int(7 * self.k))
        cw = (x1 - x0 - gap * 4) / 3
        # Retain the original three-stone arrangement. Reserve clearance
        # around the panel outline, the mode buttons, and the reading box.
        # Do not position stones immediately beneath the DRAW button. Keep
        # a real empty band even at moderate window scaling, in addition to
        # transparent PNG margins. Small layouts reduce STONE size first.
        py = y0 + hh + max(40, int(48 * self.k))
        bottom_space = max(75, int((y1 - y0) * .30))
        reading_top = y1 - bottom_space + 4
        # Only a narrow gutter is needed: the sprite files already have
        # transparent clearance, and their full bounds are constrained below.
        # The previous nine-pixel inset on each side shrank the rock needlessly.
        art_padding = max(2, int(round(3 * self.k)))
        # The text row keeps the original labels/keywords just below each
        # stone. In a small window, scale the stone, never crop its pixels.
        # Reserve two *actual* Tk text lines even when k is small: font()
        # floors at 10px, so simply multiplying 45 by k overlapped the
        # caption with the interpretation on narrow windows.
        caption_line = max(11, self.font(9, True).metrics("linespace"))
        title_line = max(11, self.font(11, True).metrics("linespace"))
        keywords_enabled = cw >= max(110, int(112 * self.k))
        text_space = max(caption_line + title_line + 5,
                         int(round((53 if keywords_enabled else 40) * self.k)))
        art_bottom = reading_top - text_space
        available_height = max(1, int(art_bottom - py - max(4, int(5*self.k))))
        available_width = max(1, int(cw - art_padding * 2))
        # Use the maximum safe width/height of each column.  The old 96px cap
        # and inset+round-down left stones at ~50px on normal screens.  The
        # new high-resolution sprites include their own transparent margins.
        stone_size = max(1, min(available_width, available_height))
        names = ("PAST", "PRESENT", "POSSIBLE FUTURE")
        for n in range(3):
            cx = x0 + gap * (n + 1) + cw * (n + .5)
            cell_left = int(x0 + gap * (n + 1) + cw * n + art_padding)
            cell_right = int(x0 + gap * (n + 1) + cw * (n + 1) - art_padding)
            # On extremely small screens, allow less label room rather than
            # clipping the stone against the panel's reading border.
            bottom_pad = max(2, int(round(5 * self.k)))
            safe_bottom = max(py + 2, art_bottom - bottom_pad)
            # Reserve real vertical padding; size the image to this safe box
            # *before* fetching the frame, not after Tk has created the label.
            cell_height = max(1, int(safe_bottom - py))
            top_pad = min(max(2, int(round(5 * self.k))), max(0, cell_height // 8))
            stone_budget = max(1, min(stone_size, cell_right - cell_left,
                                      int(safe_bottom - (py + top_pad))))
            # Centre an enlarged stone within the available height instead of
            # leaving the whole unused band underneath it.  Keep a full-image
            # bounding box so nothing can clip at the top.
            breathing_room = max(0, cell_height - top_pad - stone_budget)
            image_y = int(py + top_pad + breathing_room // 2)
            safe_box = (cell_left, image_y, cell_right, int(safe_bottom))
            shown = n < self.rune_revealed and n < len(self.rune_drawn)
            animating = n == self.rune_anim_index and n < len(self.rune_drawn)
            # Use the SAME 12-frame stone artwork throughout the reading. The
            # Previous versions switched between the original tiny static PNG
            # backs and the new flip-strip faces, making the flip appear to
            # pop rather than turn and confusing the displayed rune artwork.
            entry = self.rune_drawn[n] if n < len(self.rune_drawn) else None
            path = f"{entry['file']:02}.png" if shown and entry else f"{n+1:02}-blank.png"
            try:
                img = None
                if entry is not None:
                    step = (self.rune_anim_frame if animating else
                            self.rune_deck.flip_frames - 1 if shown else 0)
                    img = self.rune_deck.flip_frame(self.c, entry['name'], step, stone_budget)
                if img is None:
                    # Idle stones MUST be from the same master as the flip.
                    img = self.rune_deck.blank_frame(self.c, stone_budget)
                self.rune_imgs.append(img)
                # Place and size by the loaded PhotoImage dimensions, not the
                # requested (potentially fractional) slot dimensions.
                self._show_rune_art_widget(n, img, cx, image_y, stone_budget, safe_box)
                ix0, iy0, ix1, iy1 = self.rune_widgets[n].rune_bounds
                c.create_image((ix0 + ix1) / 2, (iy0 + iy1) / 2,
                               image=img, tags=("content", "cards", "rune-art"))
            except Exception as exc:
                self.rune_art_error = str(exc)
                if n < len(self.rune_widgets):
                    self.rune_widgets[n].place_forget()
                c.create_oval(cx-stone_size/2, py, cx+stone_size/2, py+stone_size,
                              fill=self.col("panel"), outline=self.col("gold"), tags=("content", "cards", "rune-art"))
            rendered_height = img.height() if img is not None else max(1, stone_size)
            label_y = image_y + rendered_height + max(3, int(4 * self.k))
            position_label = names[n]
            if self.font(9, True).measure(position_label) > cw - 2 * art_padding:
                position_label = "FUTURE" if n == 2 else fit(position_label, self.font(9, True), cw - 2 * art_padding)
            self.T(cx, label_y, position_label, 9,
                   "gold" if n == self.rune_sel else "dim",
                   "n", ("content", "cards"), True)
            if shown:
                name_y = label_y + caption_line
                rune_title = fit(entry["name"].upper(), self.font(11, True), max(25, cw - 7))
                self.T(cx, name_y, rune_title, 11,
                       "gold" if n == self.rune_sel else "txt", "n", ("content", "cards"), True)
                small_y = name_y + title_line
                # On narrow layouts omit the keywords instead of drawing
                # three tiny, overlapping columns. The complete keywords
                # remain available inside the interpretation panel.
                if keywords_enabled and small_y + caption_line <= reading_top - 3:
                    small = ", ".join(entry["keywords"])
                    self.T(cx, small_y, fit(small, self.font(9), cw - 8), 9,
                           "dim", "n", ("content", "cards"))
            # The whole stone + caption is selectable, but the hitbox must
            # never trespass into the interpretation pane beneath it.
            select_right = min(x1 - 4, cx + cw / 2)
            select_left = max(x0 + 4, cx - cw / 2)
            select_bottom = min(reading_top - 3, label_y + caption_line + title_line +
                                (caption_line if keywords_enabled and shown else 0))
            if select_bottom >= py:
                self.hot.append((select_left, py, select_right, select_bottom,
                                 "rune_select" + str(n)))
        top = y1 - bottom_space + 4
        c.create_rectangle(x0+7, top, x1-7, y1-7, fill=self.col("panel"),
                           outline=self.col("edge"), tags=("content", "reading"))
        if self.rune_state == "idle":
            details = "Three stones. Past / Present / Possible Future. Draw to begin."
        elif self.rune_state != "complete":
            details = "Revealing stones ... Select any stone to focus its position."
        else:
            selected = self.rune_drawn[self.rune_sel]
            details = self.rune_deck.interpret(selected, self.rune_sel)
            details += "  •  " + self.rune_deck.synthesis(self.rune_drawn)
        if self.rune_art_error:
            details = "RUNE IMAGE ERROR: " + self.rune_art_error
        self._rune_wrapped_text(details, (x0+15, top+7, x1-15, y1-max(34, int(40*self.k))))
        # Use a short action under the first stone; retains original panel footprint.
        bw = min(max(90, int(140*self.k)), cw * 1.5)
        by = py - max(31, int(36 * self.k))
        bx = x0 + gap + cw/2
        c.create_rectangle(bx-bw/2, by, bx+bw/2, by+max(17,int(21*self.k)),
                           fill=self.col("edge2"), outline=self.col("gold"), tags=("content", "cards"))
        action = ("DRAW THREE" if self.rune_state == "idle" else
                  "RESTART DRAW" if self.rune_state != "complete" else "NEW READING")
        self.T(bx, by+max(17,int(21*self.k))/2, action, 9, "gold", "center", ("content", "cards"), True)
        # It must not become a dead button for ~4 seconds mid-animation.
        self.hot.append((bx-bw/2, by, bx+bw/2, by+max(17,int(21*self.k)), "rune_draw"))
        # Without this, runtime-created image items can sit under the already
        # painted full-screen sepia/CRT layers until a later redraw.
        self._restack(force=True)

    def _rune_wrapped_text(self, content, box):
        x0, y0, x1, y1 = box
        for pts in (11,10,9,8):
            f=self.font(pts)
            lines=wrap_px(content, f, max(30,x1-x0))
            h=max(11, int(f.metrics("linespace") * 1.12))
            if len(lines)*h <= y1-y0: break
        for i, line in enumerate(lines[:max(1, int((y1-y0)//h))]):
            self.c.create_text(x0, y0+i*h, text=line, font=f, fill=self.col("txt"),
                               anchor="nw", tags=("content", "reading"))

    def _start_rune_draw(self):
        # A click during an animation cancels the old timed callbacks by run ID
        # and immediately begins a new draw; never leave a dead-looking button.
        self.rune_run_id += 1
        run = self.rune_run_id
        self.rune_drawn = self.rune_deck.draw()
        self.rune_revealed = 0
        self.rune_sel = 0
        self.rune_state = "drawing"
        self.rune_anim_index = -1
        self.rune_anim_frame = 0
        self.draw_cards()
        duration = max(50, self.rune_deck.flip_duration_ms)
        frame_count = max(2, self.rune_deck.flip_frames)
        def next_frame(stone, frame):
            if self.rune_run_id != run or self.divination_mode != "runes":
                return
            self.rune_state = "revealing"
            self.rune_anim_index = stone
            self.rune_anim_frame = frame
            self.draw_cards()
            if frame + 1 < frame_count:
                self.root.after(duration, lambda: next_frame(stone, frame + 1))
            else:
                self.rune_revealed = stone + 1
                self.rune_anim_index = -1
                if stone == 2:
                    self.rune_state = "complete"
                    self.draw_cards()
                else:
                    self.root.after(220, lambda: next_frame(stone + 1, 0))
        self.root.after(220, lambda: next_frame(0, 0))

    def draw_reading(self):
        """Full explanation of the selected card, in a box under the three cards (click a card or wait: it cycles)."""
        c = self.c
        c.delete("reading")
        x0, y0, x1, y1 = self.rect["cards"]
        hh = self.hdr_h()
        ah = self.card_ah()
        top = y0 + hh + 8 + ah + int(4 + 16 * self.k + 14 * self.k) + 6
        box = (x0 + 8, top, x1 - 8, y1 - max(34, int(40*self.k)))
        idx, rev = self.cards[self.card_sel]
        if self.skin_on():
            try:
                self.skin_well(box, ("content", "reading"), 10, self.col("red" if rev else "cyan"), 0.18)   # 1031
            except Exception:
                self.skin_ok = False
        if not self.skin_on():
            c.create_rectangle(*box, fill="#0d1020", outline=self.col("red" if rev else "cyan"), tags=("content", "reading"))
        txt = card_reading(idx, rev, self.card_sel)
        for px in (13, 12, 11, 10):
            f = self.font(px, False, not self.skin_on())
            words, h = flow([(txt, "txt")], f, box[2] - box[0] - 16, int(f.metrics("linespace") * 1.1), box[0] + 8, box[1] + 6)
            if h + 12 <= box[3] - box[1]:
                break
        head = txt.split(":", 1)[0]
        ls = f.metrics("linespace")
        keep = [w for w in words if w[3] + ls <= box[3] - 3]
        if len(keep) < len(words) and keep:                   # 1032: a small window cuts the reading at a whole line, marked, never mid-glyph
            wd, colr, x, y = keep[-1]
            keep[-1] = (wd.rstrip(".,;:") + "\u2026", colr, x, y)
        words = keep
        for wd, colr, x, y in words:
            c.create_text(x, y, text=wd, font=f, fill=self.col("txt"), anchor="nw", tags=("content", "reading"))

    def vector_card(self, a, idx, name, suit, rev):
        c = self.c
        x0, y0, x1, y1 = a
        edge = self.col("red" if rev else "cyan")
        tg = ("content", "cards")
        c.create_rectangle(*a, fill=self.col("panel"), outline=edge, width=2, tags=tg)
        c.create_rectangle(x0 + 5, y0 + 5, x1 - 5, y1 - 5, fill="", outline=self.col("edge"), tags=tg)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        m = -1 if rev else 1
        Y = lambda v: cy + m * v                         # reversed = art mirrored top-to-bottom
        w = (x1 - x0) * 0.30
        h = (y1 - y0) * 0.30
        if suit < 0:                                    # major arcana: concentric ovals + rays (never a hexagram)
            for j, r in enumerate((1.0, 0.72, 0.44)):
                c.create_oval(cx - w * r, cy - h * r, cx + w * r, cy + h * r, outline=self.col("gold" if j % 2 == 0 else "mag"), width=2, tags=tg)
            c.create_polygon(cx, Y(-h * 1.15), cx + w * 0.25, cy, cx, Y(h * 1.15), cx - w * 0.25, cy, fill=self.col("cyan"), outline="", tags=tg)
            self.T(cx, Y(h * 1.15) if not rev else Y(h * 1.15), "%d" % idx, 12, "dim", "s" if not rev else "n", tg)
        else:
            colr = self.col(SUIT_COL[suit])
            if suit == 0:
                c.create_line(cx, Y(-h), cx, Y(h), fill=colr, width=4, tags=tg)
                for j in range(3):
                    c.create_line(cx, Y(-h + j * h * 0.55), cx + w * 0.6, Y(-h + j * h * 0.55 - h * 0.3), fill=colr, width=2, tags=tg)
            elif suit == 1:
                c.create_arc(cx - w, Y(-h * 0.6) - h, cx + w, Y(-h * 0.6) + h, start=180 if not rev else 0, extent=180, style="chord",
                             fill=colr, outline="", tags=tg)
                c.create_line(cx, Y(h * 0.4), cx, Y(h), fill=colr, width=3, tags=tg)
                c.create_line(cx - w * 0.6, Y(h), cx + w * 0.6, Y(h), fill=colr, width=3, tags=tg)
            elif suit == 2:
                c.create_line(cx, Y(-h * 1.1), cx, Y(h * 0.9), fill=colr, width=4, tags=tg)
                c.create_line(cx - w * 0.7, Y(h * 0.3), cx + w * 0.7, Y(h * 0.3), fill=colr, width=4, tags=tg)
            else:
                c.create_oval(cx - w, cy - w, cx + w, cy + w, outline=colr, width=3, tags=tg)
                c.create_oval(cx - w * 0.5, cy - w * 0.5, cx + w * 0.5, cy + w * 0.5, outline=colr, width=2, tags=tg)
            self.T(cx, y1 - 10, "%d" % ((idx - 22) % 14 + 1), 12, "dim", "s", tg)


    def _restack(self, force=False):
        """Re-apply LAYERS.  Raising a tag makes Tk repaint every item under it -- the full-screen CRT sheets included,
        which is most of a frame's cost -- so it only runs when the stacking actually changed since the last time
        (items were created, raised or lowered); the result is the same order either way."""
        c = self.c
        order = c.find_all()
        if not force and order == getattr(self, "_stack_seen", None):
            return
        for t in self.LAYERS:
            c.tag_raise(t)
        self._stack_seen = c.find_all()

    # ------------------------------------------------------------------ frame
    def size_ok(self):
        return self.c.winfo_width() == self.TW and self.c.winfo_height() == self.TH

    def tick(self):
        now = time.time()
        dt = min(0.25, now - getattr(self, "_last", now))
        self._last = now
        self.frame_no += 1
        self._tab_art_tick(now)
        if self.dk:
            try:
                self.dk.draw()
            except Exception as e:
                self._overlay_crashed("PASSPHRASE", e)
        elif self.ogg:
            pass  # The independent Oggcultist window owns its own update loop.
        elif self.touch:
            pass  # Touch Type is a native Tk frame with its own lightweight timer.
        elif self.aug:
            pass  # AUGURSPEX owns its Tk charts and async market-data polling.
        else:
            self._dyn(now, dt)
        self._fx(now, dt)
        self._bezel_tick(now)
        if getattr(self, "_grade_at", 0) and now >= self._grade_at:
            self._grade_at = 0
            self.act("view")
        self._glass_tick(now)                        # 1068: ambient sweep and rare reflected shadow
        self._crt_tick(now, dt)
        if self.host is not None and getattr(self.host, "pixel_crt", None) is not None:
            self.host.pixel_crt.tick()
        self._restack()                       # ALWAYS last: rain/stars/popups were created above


    def _dyn(self, now, dt):
        c, k = self.c, self.k
        if now - getattr(self, "q_at", self.t0) > 40:
            self.act("next")
        self._arch_tick(now)
        # maglev
        if self.wire is not None or self.train3d is not None:
            self._train_tick(now)
        elif self.cars:
            s0, s1 = self.train_span
            L = (self.car_w + 4) * len(self.cars)
            head = s0 + ((now * 70 * self.sx) % (s1 - s0 + L))
            for j, (r, wd) in enumerate(self.cars):
                xa = head - (j + 1) * (self.car_w + 4) + 4
                xb = xa + self.car_w
                xa, xb = max(s0, xa), min(s1, xb)
                if xb - xa < 3:
                    c.coords(r, 0, 0, 0, 0)
                    c.coords(wd, 0, 0, 0, 0)
                else:
                    y = self.rail_y
                    c.coords(r, xa, y - 14 * self.sy, xb, y)
                    c.coords(wd, xa + 4, y - 11 * self.sy, xb - 4, y - 7 * self.sy)
        # Fetch on a daemon worker, rotate after 12 seconds, and redraw only
        # when the selected symbol or its history actually changes.
        if self.augurspex_chart.tick():
            self.draw_augurspex_chart()
        # daily roll
        if now - self.mk_last > 1.5:
            self.mk_last = now
            if self.draw.rolled() and self.c.itemcget(self.cards_hdr, "text") == "TODAY":
                self.cards = self.draw.daily()
                self.draw_cards()
        if self.divination_mode == "tarot" and now - getattr(self, "card_at", now) > 9:
            self.card_at = now
            self.card_sel = (self.card_sel + 1) % 3
            self.draw_cards()
        self._status(now, dt)

    def _status(self, now, dt):
        """Static, unobtrusive footer: no news ticker, market or network activity."""
        c = self.c
        if getattr(self, "_tk_s", None) != "":
            self._tk_s = ""
            c.itemconfigure(self.tick_id, text="")
        if getattr(self, "_hd", None) != "":
            self._hd = ""
            c.itemconfigure(self.hold_id, text="")
        st = self.msg if now < self.msg_until else ""
        if st != getattr(self, "_st_s", None):
            self._st_s = st
            c.itemconfigure(self.stat_id, text=fit(st, self.font(12, False, False), self.W * 0.86))

    # ------------------------------------------------------------------ fx: sigil rain, stars
    def _fx(self, now, dt):
        c = self.c
        if len(self.drops) < 14 and self.rng.random() < 0.15 and not self.clean():      # 1034: the clean look has no falling sigils or shooting stars
            x = self.rng.randint(4, max(5, self.W - 4))
            it = c.create_text(x, -10, text=self.rng.choice("01+*:.=/"), font=self.font(12), fill=mix(self.col("bg"), self.col("cyan"), 0.35),
                               tags="fx")
            self.drops.append([it, x, -10.0, self.rng.uniform(40, 110)])
        alive = []
        hide = self._fx_cover()
        for d in self.drops:
            d[2] += d[3] * dt
            if d[2] > self.H:
                c.delete(d[0])
            else:
                if hide and hide[0] <= d[1] <= hide[2] and hide[1] <= d[2] <= hide[3] and len(d) > 4 and d[4]:
                    pass                           # under the deck's frame both before and after: moving it only repaints
                else:
                    c.coords(d[0], d[1], d[2])
                inside = bool(hide) and hide[0] <= d[1] <= hide[2] and hide[1] <= d[2] <= hide[3]
                d[4:] = [inside]
                alive.append(d)
        self.drops = alive
        if self.star is None and self.rng.random() < 0.003 and not self.clean():
            self.star = [self.rng.randint(0, self.W // 2), self.rng.randint(0, self.H // 3), 0,
                         c.create_line(0, 0, 0, 0, fill=self.col("txt"), width=2, tags="fx")]
        if self.star:
            x, y, n, it = self.star
            n += 1
            hx, hy = x + n * 26 * self.sx, y + n * 12 * self.sy
            c.coords(it, hx - 40, hy - 18, hx, hy)
            self.star[2] = n
            if n > 24:
                c.delete(it)
                self.star = None

    def _fx_cover(self):
        """While a Tk-frame tab is open (ARCHIVE DECK) its frame hides the rain behind it: the box
        (shrunk by a glyph's size) in which a falling sigil is invisible, else None.  Drops there keep falling but are not
        moved on the canvas until they come out (or the tab closes: _fx_sync), since Tk repaints a moved item even where
        nothing shows.  DICEKEY is drawn on this canvas, so it is not a cover."""
        name = self._which_overlay()
        if name in (None, "dk"):
            return None
        sess = getattr(self, name, None)
        if sess is None or getattr(sess, "covered", False):
            return None
        x0, y0, x1, y1 = self.overlay_box()
        m = 16 * self.k
        return (x0 + m, y0 + m, x1 - m, y1 - m)

    def _fx_sync(self):
        """Put every rain sigil where it really is (after an overlay that hid some of them closes)."""
        for d in self.drops:
            try:
                self.c.coords(d[0], d[1], d[2])
            except Exception:
                pass
            d[4:] = [False]





    def sfx_play(self, path):
        return Sfx.play(path)




    # 1x1 PNG, black at half alpha.  After every change to a photo Tk scans ALL its pixels for partial alpha, stopping


    # ------------------------------------------------------------------ overlay glue
    def overlay_box(self):
        panels = [self.rect[n] for n in ("arch", "lex", "trans", "mkt", "cards") if n in self.rect]
        return (min(r[0] for r in panels), min(self.rect["menu"][3] + 6, min(r[1] for r in panels)),          # 1055: never shorter than the panels,
                max(r[2] for r in panels), max(self.rect["status"][1] - 6, max(r[3] for r in panels)))        # so no sliver of them shows above it

    # 1058: one overlay is left, PASSPHRASE (--retro and --flat); the dashboard is visible exactly when it is None
    OVERLAY_NAMES = {"dk": "PASSPHRASE", "ogg": "OGGCULTIST", "touch": "TOUCH TYPE", "eido": "EIDOLITH", "aug": "AUGURSPEX"}

    def _which_overlay(self):
        if getattr(self, "dk", None):
            return "dk"
        if getattr(self, "ogg", None):
            return "ogg"
        if getattr(self, "touch", None):
            return "touch"
        if getattr(self, "eido", None):
            return "eido"
        return "aug" if getattr(self, "aug", None) else None

    def close_overlays(self, msg="", keep=None):
        """Close every overlay but `keep`: null the field first, then clear() (its own tag only), then the tab art, then
        say.  Never build(): the dashboard underneath was only covered."""
        closed = None
        for name, attr, tag, after in (("dk", "dk", "dkwin", self._after_close_dk),
                                       ("ogg", "ogg", "oggwin", self._after_close_ogg),
                                       ("touch", "touch", "touchwin", self._after_close_touch),
                                       ("eido", "eido", "eidowin", self._after_close_eido),
                                       ("aug", "aug", "augwin", self._after_close_aug)):
            if name == keep:
                continue
            sess = getattr(self, attr, None)
            if sess is None:
                continue
            if name == 'ogg':
                self._ogg_cached = sess
                self.ogg_process = None
            elif name == 'touch':
                self._touch_cached = sess
            elif name == 'eido':
                self._eido_cached = sess
            elif name == 'aug':
                self._aug_cached = sess
            setattr(self, attr, None)
            try:
                sess.clear()
            except Exception:
                try:
                    self.c.delete(tag)
                except Exception:
                    pass
            try:
                after()
            except Exception:
                pass
            closed = name
        if closed == 'dk' and getattr(self, '_v2_selected_button', None) == 'bz10':
            self._v2_selected_button = None
        self._update_primary_tab_state()
        if msg:
            self.say(msg, 6)
        return closed

    def _after_close_dk(self):
        self._dk_state(False)
        if self.divination_mode == "runes":
            self.draw_cards()

    def _after_close_ogg(self):
        if self.divination_mode == "runes":
            self.draw_cards()

    def _after_close_touch(self):
        if self.divination_mode == "runes":
            self.draw_cards()

    def _after_close_eido(self):
        if self.divination_mode == "runes":
            self.draw_cards()

    def _after_close_aug(self):
        if self.divination_mode == "runes":
            self.draw_cards()

    def go_home(self):
        self.close_overlays()
        self._update_primary_tab_state()

    def toggle_overlay(self, name):
        """Open `name` (closing whatever else is open) or, if it is the open one, close it.  A missing module only says
        so and closes nothing.  The Session is built only after close_overlays() returns."""
        if self._which_overlay() == name:
            self.close_overlays()
            return
        missing = {"dk": (getattr(self, "dk_mod", None), "NO PASSPHRASE TOOL INSTALLED"),
                   "ogg": (True, "OGGCULTIST IS NOT AVAILABLE"),
                   "touch": (True, "TOUCH TYPE IS NOT AVAILABLE"),
                   "eido": (True, "EIDOLITH IS NOT AVAILABLE"),
                   "aug": (True, "AUGURSPEX IS NOT AVAILABLE")}[name]
        if not missing[0]:
            return self.say(missing[1])
        self.close_overlays()
        try:
            box = self.overlay_box()
            font14 = self.font(14)
            if name == "dk":
                kw = {}
                if self.clean():                         # 1035: KEY CUT without its 98 frame and bevelled buttons
                    gr, pf = self.ground(), self.col("panel")   # 1038: PASSPHRASE: one card on the (see-through) ground
                    edge = hexmix(pf, "#ffffff", 0.12)
                    kw = dict(modern=True, ui_family=self.ui_family, minimal=True, ground=gr,
                              button=lambda box, acc, tags: self.skin_outline(box, tags, acc, fill=pf, under=pf),
                              panel=lambda box, tags: self.skin_outline(box, tags, edge, radius=14, fill=pf, under=gr))
                from marble_passphrase_tab import PassphrasePanel
                s = EmbeddedPassphrase(
                    self.c, self.dk_eng,
                    lambda master, engine: PassphrasePanel(
                        master, engine, on_home=self.close_overlays))
                s.layout(box, font14)
                self.dk = s
                self._hide_rune_art_widgets()
                self._dk_state(True)
            elif name == "ogg":
                from oracle_ogg_tab import EmbeddedOggcultist
                if self._ogg_cached is not None and self._ogg_cached.frame.winfo_exists():
                    self.ogg = self._ogg_cached
                else:
                    self.ogg = EmbeddedOggcultist(self.c, on_home=self.go_home)
                    self._ogg_cached = self.ogg
                self.ogg.layout(box)
                self._hide_rune_art_widgets()
                self._update_primary_tab_state()
            elif name == "touch":
                from oracle_touch_type import EmbeddedTouchType
                if self._touch_cached is not None and self._touch_cached.frame.winfo_exists():
                    self.touch = self._touch_cached
                else:
                    self.touch = EmbeddedTouchType(self.c, on_home=self.go_home)
                    self._touch_cached = self.touch
                self.touch.layout(box)
                self._hide_rune_art_widgets()
                self._update_primary_tab_state()
            elif name == "eido":
                from oracle_eidolith import EmbeddedEidolith
                if self._eido_cached is not None and self._eido_cached.frame.winfo_exists():
                    self.eido = self._eido_cached
                else:
                    self.eido = EmbeddedEidolith(self.c, on_home=self.go_home)
                    self._eido_cached = self.eido
                self.eido.layout(box)
                self._hide_rune_art_widgets()
                self._update_primary_tab_state()
            elif name == "aug":
                from oracle_augurspex_tab import EmbeddedAugurspex
                if self._aug_cached is not None and self._aug_cached.frame.winfo_exists():
                    self.aug = self._aug_cached
                else:
                    self.aug = EmbeddedAugurspex(
                        self.c, on_home=self.go_home, theme=self.th,
                        offline=bool(self.o.get('no_network') or self.o.get('no_markets')))
                    self._aug_cached = self.aug
                self.aug.frame.retheme(self.th)
                self.aug.layout(box)
                self._hide_rune_art_widgets()
                self._update_primary_tab_state()
        except Exception as e:
            try:                                          # a Session that died half-built leaves nothing behind
                self.c.delete("dkwin")
                self.c.delete("oggwin")
                self.c.delete("touchwin")
                self.c.delete("eidowin")
                self.c.delete("augwin")
            except Exception:
                pass
            self.close_overlays("%s FAILED: %s" % (self.OVERLAY_NAMES[name], e))

    def toggle_dicekey(self):
        self.toggle_overlay("dk")

    def _overlay_crashed(self, what, e):
        self.close_overlays("%s CRASHED: %s" % (what, e))

    # ------------------------------------------------------------------ input
    def hot_active(self, h):
        # CRT V2 hardware is OUTSIDE the live screen and must stay clickable
        # even while the PSWRD Canvas overlay covers the dashboard. This is
        # essential for toggling PSWRD off or going straight to another key.
        if self.o.get('crt_v2') and isinstance(h[4], str) and (
                h[4].startswith('bz') or h[4].startswith('dial:')):
            return True
        if self._which_overlay() is None:
            return True
        return h[3] <= self.rect["menu"][3] or h[1] >= self.rect["status"][1]

    def _v2_route_section(self, action):
        """Return True when clicking an already-selected key means HOME.

        Only V2's five labeled physical keys participate; legacy callbacks
        are unchanged. A different key closes PSWRD first and then performs
        its own existing application action in one click.
        """
        if not self.o.get('crt_v2'):
            return False
        if getattr(self, '_v2_selected_button', None) == action:
            self._v2_selected_button = None
            self._grade_at = 0  # cancel a not-yet-completed GRID change
            self.close_overlays()
            return True
        self.close_overlays()
        self._v2_selected_button = action
        return False

    def hit(self, x, y):
        # Mode buttons and the Rune draw action take precedence over the
        # broad dashboard/panel hitboxes.  These controls are repainted often
        # during the flip animation, but must always respond to one click.
        if getattr(self, 'divination_mode', 'tarot') == 'runes':
            # Mode/draw controls win first, then each Rune tile. Stale broad
            # dashboard hotspots must never absorb an intended stone click.
            priority = ('mode_tarot', 'mode_runes', 'rune_draw',
                        'rune_select0', 'rune_select1', 'rune_select2')
        else:
            priority = ('mode_tarot', 'mode_runes')
        for action in priority:
            for h in self.hot:
                if h[4] == action and h[0] <= x <= h[2] and h[1] <= y <= h[3] and self.hot_active(h):
                    return h
        for h in getattr(self, "dial_hot", ()) or ():
            if h[0] <= x <= h[2] and h[1] <= y <= h[3] and self.hot_active(h):
                return h
        for h in self.hot:
            if h[0] <= x <= h[2] and h[1] <= y <= h[3] and self.hot_active(h):
                return h
        return None

    def act(self, name, x=None):
        if name == "tab_home":
            return self.go_home()
        if name in ('aug_next', 'aug_previous'):
            self.augurspex_chart.advance(1 if name == 'aug_next' else -1)
            self.draw_augurspex_chart()
            return
        if name == "tab_passphrase":
            if self._which_overlay() != "dk":
                self.toggle_overlay("dk")
            self._update_primary_tab_state()
            return
        if name == "tab_oggcultist":
            if self._which_overlay() != "ogg":
                self.toggle_overlay("ogg")
            self._update_primary_tab_state()
            return
        if name == "tab_touch_type":
            if self._which_overlay() != "touch":
                self.toggle_overlay("touch")
            self._update_primary_tab_state()
            return
        if name == "tab_augurspex":
            # AUGURSPEX is an embedded, palette-matched Tk workspace, like EIDOLITH.
            # Never open a browser or start the former localhost companion server.
            if self._which_overlay() != "aug":
                self.toggle_overlay("aug")
            self._update_primary_tab_state()
            return
        if name == "tab_eidolith":
            if self._which_overlay() != "eido":
                self.toggle_overlay("eido")
            self._update_primary_tab_state()
            return
        if name in ("mode_tarot", "mode_runes"):
            target = name[5:]
            if self.divination_mode != target:
                self.divination_mode = target
                # Cancel pending reveals when leaving; resume stable result on return.
                if target == "tarot" and self.rune_state in ("drawing", "revealing"):
                    self.rune_run_id += 1
                    self.rune_anim_index = -1
                    self.rune_state = "complete" if self.rune_revealed == 3 else "idle"
                self.card_at = time.time()
                self.c.itemconfigure(self.cards_hdr, text="RUNES" if target == "runes" else "TODAY")
                self.draw_cards()
                # The first visit should demonstrate the flip instead of
                # silently displaying 3 blanks. Keep DRAW THREE/NEW READING
                # available; a manual click before the timer safely wins.
                if target == "runes" and self.rune_state == "idle":
                    self.root.after(280, lambda: self._start_rune_draw()
                                    if self.divination_mode == "runes" and self.rune_state == "idle" else None)
            return
        elif name == "rune_draw":
            self._start_rune_draw()
            return
        elif name.startswith("rune_select"):
            self.rune_sel = int(name[-1]) % 3
            self.draw_cards()
            return
        if name == "next":
            self.qi += 1
            self.q_at = time.time()
            self.layout_quote()
            self.set_quote_meta()
        elif name == "word":
            self.set_word(self.wi + 1)
        elif name.startswith("card") and name[4:].isdigit():
            self.card_sel = int(name[4:]) % 3
            self.card_at = time.time()
            self.draw_cards()
        elif name == "deal":
            if self.divination_mode == "runes":
                self._start_rune_draw()
                return
            self.card_sel = 0
            self.card_at = time.time()
            self.cards = self.draw.deal()
            self.c.itemconfigure(self.cards_hdr, text="DEALT")
            if not self.clean():
                self.skin_chip(self.cards_hdr, self.col("dim"), "cardschip")
            self.draw_cards()
        elif name.startswith("bz") and name[2:].isdigit():
            i = int(name[2:])
            self.bz_press(name, 0.22)
            if i in (1, 3, 5, 6, 10) and self._v2_route_section(name):
                return  # same key pressed again: dismiss and show home
            if i == 1:                                     # GRADE rebuilds the screen, so the sink has to finish first
                self._grade_at = time.time() + 0.28
            elif i == 3:
                self.act("next")
            elif i in (5, 6, 7, 8, 9, 10):
                if i == 9 and self.o.get("crt_v2") and self.host is not None:
                    # Let the newly generated rocker press complete before closing.
                    self.root.after(220, self.host.quit)
                else:
                    self.act({5: "word", 6: "deal", 7: "min", 8: "full", 9: "quit", 10: "dk"}[i])
            elif 11 <= i <= 16:
                if not self.o.get("crt_v2"):
                    self.say("SPARE")  # V2 blank auxiliaries intentionally perform no action.
        elif name == "view":
            # 0940: the next preset (a colour scheme and a panel layout), remembered for the next launch
            presets = view_presets(self.o)
            cur = self.o.get("view")
            i = 0 if cur is None else (cur + 1) % len(presets)
            self.o["view"] = i
            self.o["theme"], self.o["layout"] = presets[i]
            self.th = dict(THEMES[self.o["theme"]])
            self.look_colours()
            if not self.o.get("selftest"):
                saved = load_json("view.json", {})
                saved = dict(saved) if isinstance(saved, dict) else {}
                saved["preset" if is_retro(self.o) else "clean"] = i          # 1034: each look remembers its own GRADE
                save_json("view.json", saved)
            self.build(self.W, self.H)
            if self.aug is not None:
                try:
                    self.aug.frame.retheme(self.th)
                    self.aug.layout(self.overlay_box())
                except Exception as ex:
                    self._overlay_crashed('AUGURSPEX', ex)
            if self.host is not None and hasattr(self.host, "apply_look"):
                self.host.apply_look()                     # 1036: a new scheme, a new see-through colour
            self.say("GRADE %d/%d  %s" % (i + 1, len(presets), view_label(self.o["theme"], self.o["layout"]) if is_retro(self.o) else self.o["layout"]))   # 1059: the clean GRADE is a layout only
        elif name == "speak":
            self.speak_word(self.vmode)
        elif name in ("say_c", "say_e"):
            self.speak_word(name[-1])
        elif name == "ecc":
            self.vmode = {"both": "c", "c": "e", "e": "both"}[self.vmode]
            self.set_word(self.wi)
        elif name == "lexvoice":                                  # 1046: volume and the speak-mode line, only when asked
            self.lex_voice_open = not getattr(self, "lex_voice_open", False)
            self.c.itemconfigure("lexvoice", state="normal" if self.lex_voice_open else "hidden")
            if getattr(self, "voice_btn", None):
                self.c.itemconfigure(self.voice_btn, state="hidden" if self.lex_voice_open else "normal")
        elif name == "slider" and x is not None:
            tx0, tx1, _ = self.slider
            self.voice.vol = max(0.0, min(1.0, (x - tx0) / float(tx1 - tx0)))
            self._vol_draw()
        elif name == "dk":
            self.toggle_dicekey()
        elif name == "quit" and self.host:
            self.host.quit()
        elif name == "full" and self.host:
            self.host.toggle_full()
        elif name == "min" and self.host:
            mini = getattr(self.host, "minimize", None)
            if mini:
                mini()
            else:
                self.host.root.iconify()

    def cycle_bezel(self):
        """M switches the photographic housing. Patina is the same frame, lightly rusted."""
        nxt = "patina" if getattr(self, "bezel_theme", "stock") != "patina" else "stock"
        self.bezel_theme = nxt
        save_json("bezel.json", {"theme": nxt})
        if self.W and self.H:
            self.build(self.W, self.H)
        self.say("HOUSING " + ("WEAR" if nxt == "patina" else "CLEAN"))

    def on_key(self, e):
        ks = e.keysym
        ov = self._which_overlay()
        if ov:                                        # the open overlay owns the keyboard
            sess = getattr(self, ov)
            try:
                if sess.key(ks, e.char) == "close":
                    self.close_overlays()
            except Exception as ex:
                self._overlay_crashed(self.OVERLAY_NAMES[ov], ex)
            return
        k = ks.lower()                                # 1058: D, B, O, R and L belonged to removed tools: they do nothing
        if k == "k" and self.dk_mod:
            return self.toggle_dicekey()
        if k == "space": self.act("next")
        elif k in ("return", "kp_enter"): self.act("speak")
        elif k == "n": self.act("word")
        elif k == "t": self.act("deal")
        elif k == "f": self.act("full")
        elif k == "c":
            self.crt_off = not getattr(self, "crt_off", False)
            self.c.delete("crt")
            self._crt()
            self.say("CRT " + ("OFF" if self.crt_off else "ON"))
        elif k == "m": self.cycle_bezel()
        elif k == "e": self.act("ecc")
        elif k == "v": self.act("view")
        elif k == "escape": self.act("quit")

    def _xy(self, e):
        """Window pixel -> inner scene coordinate (real Tk events only; the bezel offsets the canvas)."""
        if hasattr(e, "widget"):
            try:
                ex, ey = self.c.canvasx(e.x), self.c.canvasy(e.y)
            except Exception:
                ex, ey = e.x, e.y
        else:
            ex, ey = e.x, e.y
        compositor = getattr(self.host, 'pixel_crt', None) if self.host is not None else None
        if compositor is not None and compositor.item is not None:
            return compositor.hit_source(ex, ey)
        return ex, ey

    def on_click(self, e):
        ex, ey = self._xy(e)
        h = self.hit(ex, ey)
        if not h and self.host is not None and getattr(self.host, "borderless", False) and not getattr(self.host, "full", False):
            # no OS frame: the bezel and the title bar are the handles
            l, t, r, b = self.mg
            rx, ry = getattr(e, "x_root", e.x), getattr(e, "y_root", e.y)
            if ex >= self.W + r - 40 and ey >= self.H + b - 40:
                return self.host.begin_move(rx, ry, "size")
            if ex < 0 or ex > self.W or ey < 0 or ey > self.H or ey <= self.rect["title"][3]:
                return self.host.begin_move(rx, ry, "move")
        if h:
            if isinstance(h[4], str) and h[4].startswith("dial:"):
                self.dragging = h[4]
                self._dial_down(h[4], ex, ey)
                return
            self.dragging = "slider" if h[4] == "slider" else False
            self.act(h[4], ex)
        elif self._which_overlay():
            ov = self._which_overlay()
            sess = getattr(self, ov)
            try:
                x0, y0, x1, y1 = self.overlay_box()
                if x0 <= ex <= x1 and y0 <= ey <= y1 and hasattr(sess, "click"):
                    if sess.click(ex, ey) == "close":
                        self.close_overlays()
            except Exception as err:
                self._overlay_crashed(self.OVERLAY_NAMES[ov], err)

    def on_motion(self, e):
        try:
            x, y = self._xy(e)
            cur = "hand2" if self.hit(x, y) else ""
            if not cur and getattr(self.host, "borderless", False) and not getattr(self.host, "full", False):
                l, t, r, b = self.mg
                if x >= self.W + r - 40 and y >= self.H + b - 40:
                    cur = "bottom_right_corner"
            self.c.configure(cursor=cur)
        except Exception:
            pass

    def on_drag(self, e):
        if self.host is not None and getattr(self.host, "_mv", None):
            return self.host.do_move(getattr(e, "x_root", e.x), getattr(e, "y_root", e.y))
        if self.dragging == "slider":
            self.act("slider", self._xy(e)[0])
        elif isinstance(self.dragging, str) and self.dragging.startswith("dial:"):
            x, y = self._xy(e)
            self._dial_drag(self.dragging, x, y)

    def on_release(self, e):
        name = self.dragging
        if name == "slider" and not self.o.get("selftest"):
            save_json("voice.json", {"vol": round(self.voice.vol, 3)})      # 1060: the volume is kept for the next launch
        if isinstance(name, str) and name.startswith("dial:"):
            self._dial_up(name)
            if name == "dial:vol" and not self.o.get("selftest"):
                save_json("voice.json", {"vol": round(self.voice.vol, 3)})
        self.dragging = False
        if self.host is not None and getattr(self.host, "_mv", None):
            self.host.end_move()

    def resized(self, TW, TH):
        """TW, TH = whole canvas.  The bezel takes its margin; the scene builds in what is left, and the
        canvas scrollregion is offset so inner (0,0) is the screen's corner and all layout code is unchanged."""
        self.TW, self.TH = TW, TH
        l, t, r, b = self.mg = self.margins(TW, TH)
        if self.o.get("crt_v2"):
            # V2 uses a measured aperture: never inflate the live screen past the
            # actual glass opening at small native bezel scales.
            W, H = max(1, TW-l-r), max(1, TH-t-b)
        else:
            W, H = max(560, TW-l-r), max(340, TH-t-b)  # original legacy safety limit
        try:
            self.c.configure(scrollregion=(-l, -t, -l + TW, -t + TH))
            self.c.xview_moveto(0)
            self.c.yview_moveto(0)
        except Exception:
            pass
        self.build(W, H)
        if self.dk:
            try:
                self.dk.layout(self.overlay_box(), self.font(14))
            except Exception as e:
                self._overlay_crashed("PASSPHRASE", e)
        if self.ogg:
            try:
                self.ogg.layout(self.overlay_box())
            except Exception as e:
                self._overlay_crashed("OGGCULTIST", e)
        if self.touch:
            try:
                self.touch.layout(self.overlay_box())
            except Exception as e:
                self._overlay_crashed("TOUCH TYPE", e)
        if self.eido:
            try:
                self.eido.layout(self.overlay_box())
            except Exception as e:
                self._overlay_crashed("EIDOLITH", e)
        if self.aug:
            try:
                self.aug.layout(self.overlay_box())
            except Exception as e:
                self._overlay_crashed("AUGURSPEX", e)


# --------------------------------------------------------------------------- window icon
APP_ID = "Marble_Oracle"


def set_app_identity():
    """Windows: give the process its own taskbar identity, so the button and Alt-Tab show Marble_Oracle's icon and not pythonw's.
    Must run before the first window exists.  Silent where it cannot work."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        return True
    except Exception:
        return False


WINDOW_ICONS = ("marble_oracle_window.ico", "marble_oracle.ico")     # BMP frames of the eye first (Tk refuses the PNG frames), then the full icon


def apply_window_icon(root):
    """Put the eye on the window. The first file is the same picture as classic BMP frames, which Tk can read. The second is the full icon."""
    for name in WINDOW_ICONS:
        path = oracle_assets.asset(name)
        if not path:
            continue
        try:
            root.iconbitmap(default=path)
            return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------- apps
class WindowApp:
    """Ordinary resizable window (default).  Fullscreen / Wallpaper subclass it."""
    def __init__(self, opts):
        import tkinter as tk
        self.tk = tk
        self.o = opts
        set_app_identity()
        self.root = root = tk.Tk()
        root.title("%s %s" % (TITLE, VERSION_NAME))
        apply_window_icon(root)
        self.fps = max(5, min(60, int(opts.get("fps", 30))))
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        if opts.get("bezel", True):
            try:
                from oracle_photo_bezel import photo_zip, photo_fit_size, SOURCE_W, SOURCE_H
            except Exception:
                photo_zip = None
            if photo_zip is not None and photo_zip() is not None:
                avail_w, avail_h = max(640, sw - 40), max(460, sh - 80)
                w, h = photo_fit_size(avail_w, avail_h)
            else:
                bw, bh = (210, 208)
                w, h = min(REF_W + bw, sw - 40), min(REF_H + bh, sh - 80)
        else:
            w, h = min(REF_W, sw - 40), min(REF_H, sh - 80)
        self.req = (w, h)                   # 1037: the size asked for, used until Tk reports the real one
        self.setup_window(w, h, sw, sh)
        resolve_view(opts)
        # In --fullscreen the root fills the monitor, but the CONTENT canvas
        # is a single native-size CRT frame centred against a black matte.
        self._photo_fullscreen = bool(isinstance(self, Fullscreen) and opts.get('bezel', True)
                                      and self._has_photo())
        # On Windows the photographic CRT should not show the baked black
        # backdrop around the metal silhouette.  Use a chroma-key canvas fill
        # for the *outside* of the frame so transparent photo pixels cut away.
        self._photo_mask_bg = '#ff00ff' if (os.name == 'nt' and opts.get('bezel', True) and self._has_photo()) else None
        # In windowed photographic-bezel mode, make the toplevel itself use
        # the chroma-key colour so transparent edge pixels around the monitor
        # do not reveal a hard black rectangle from the source artwork.
        root_bg = '#000000' if self._photo_fullscreen else (self._photo_mask_bg or THEMES[opts['theme']]['bg'])
        canvas_bg = self._photo_mask_bg or THEMES[opts['theme']]['bg']
        root.configure(bg=root_bg)
        self.canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0, bd=0, bg=canvas_bg)
        if self._photo_fullscreen:
            self.canvas.place(relx=.5, rely=.5, anchor='center', width=w, height=h)
        else:
            self.canvas.pack(fill="both", expand=True)
        root.update_idletasks()
        self.scene = Scene(root, self.canvas, opts, host=self)
        self.pixel_crt = None
        if (not opts.get("crt_v2") and opts.get("bezel", True) and not opts.get("no_pixel_barrel")
                and not opts.get("selftest")):
            try:
                from oracle_pixel_crt import PixelCRT
                self.pixel_crt = PixelCRT(self)
            except Exception:
                self.pixel_crt = None
        self.system_audio = None
        if opts.get('bezel', True) and not opts.get('no_audio_scope', False) and not opts.get('selftest'):
            try:
                from oracle_audio_scope import SystemAudioScope
                self.system_audio = SystemAudioScope()
                self.system_audio.start()
            except Exception:
                self.system_audio = None
        self.apply_look()
        self.after_id = None
        self._pending = None
        root.bind("<Key>", self.scene.on_key)
        self.canvas.bind("<Button-1>", self.scene.on_click)
        self.canvas.bind("<Motion>", self.scene.on_motion)
        self.canvas.bind("<B1-Motion>", self.scene.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.scene.on_release)
        self.canvas.bind("<Configure>", self._cfg)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.focus_force()
        self.errors = 0   # consecutive rendering failures, not lifetime total
        self._callback_errors = 0
        root.report_callback_exception = self._report_callback_error
        self.full = False
        self._shape_after = None
        # A Tk PhotoImage with transparent corners does not punch holes in a
        # Win32 window. Clip the entire actual window to the metal outline.
        if os.name == 'nt' and self.borderless and self._has_photo():
            self._schedule_metal_shape()

    def _warn_missing_pixel_warp(self):
        if self.pixel_crt is not None:
            return
        try:
            from tkinter import messagebox
            messagebox.showwarning('Marble_Oracle',
                'True CRT screen bending is NOT ACTIVE because Pillow is missing.\n\n'
                'Run Marble_Oracle.bat (the normal Windows launcher) to install it, '
                'then restart.\n\nThe flat optical fallback is currently displayed.')
        except Exception:
            pass

    def _schedule_metal_shape(self):
        if os.name != 'nt' or not self.borderless or not self._has_photo():
            return
        if getattr(self, '_shape_after', None) is not None:
            try:
                self.root.after_cancel(self._shape_after)
            except Exception:
                pass
        self._shape_after = self.root.after(180, self._apply_metal_shape)

    def _apply_metal_shape(self):
        self._shape_after = None
        try:
            from oracle_window_shape import apply_region
            self._metal_region_active = apply_region(self.root, self.canvas)
        except Exception as exc:
            self._metal_region_active = False
            try:
                import traceback
                with open(os.path.join(state_dir(), 'crt_shape_error.log'), 'a', encoding='utf-8') as f:
                    f.write(repr(exc) + '\n' + traceback.format_exc())
            except Exception:
                pass

    def _has_photo(self):
        if not self.o.get('bezel', True):
            return False
        from oracle_photo_bezel import photo_zip
        return photo_zip() is not None

    def _set_photo_view(self, fullscreen):
        """Letterbox a WHOLE baked CRT on the monitor; never stretch canvas."""
        from oracle_photo_bezel import photo_fit_size, SOURCE_W, SOURCE_H
        r = self.root
        if fullscreen:
            sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
            w, h = photo_fit_size(sw - 24, sh - 24)
            self.canvas.pack_forget()
            self.canvas.configure(width=w, height=h, bg=(self._photo_mask_bg or THEMES[self.o["theme"]]["bg"]))
            self.canvas.place(relx=.5, rely=.5, anchor='center', width=w, height=h)
            self.req = (w, h)
            r.configure(bg='#000000')
            # A monitor may be 16:9 while the artwork is 4:3; WM aspect
            # restrictions only belong on the normal decorated application.
            try:
                r.tk.call('wm', 'aspect', str(r), '')
            except Exception:
                pass
            r.overrideredirect(True)
            r.geometry('%dx%d+0+0' % (sw, sh))
            self._photo_fullscreen = True
            self._schedule_metal_shape()
        else:
            w, h = photo_fit_size(max(640, r.winfo_screenwidth()-40),
                                  max(460, r.winfo_screenheight()-80))
            self.canvas.place_forget()
            self.canvas.configure(width=w, height=h, bg=(self._photo_mask_bg or THEMES[self.o["theme"]]["bg"]))
            self.canvas.pack(fill='both', expand=True)
            self.req = (w, h)
            self._photo_fullscreen = False
            self._schedule_metal_shape()
            r.configure(bg=(self._photo_mask_bg or THEMES[self.o["theme"]]["bg"]))
            r.geometry(getattr(self, '_restore', None) or
                       '%dx%d+%d+%d' % (w, h,
                         max(0, (r.winfo_screenwidth()-w)//2),
                         max(0, (r.winfo_screenheight()-h)//2)))
            try:
                r.wm_aspect(SOURCE_W, SOURCE_H, SOURCE_W, SOURCE_H)
            except Exception:
                pass

    def setup_window(self, w, h, sw, sh):
        self.root.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))
        try:
            if self.o.get('bezel', True):
                from oracle_photo_bezel import SOURCE_W, SOURCE_H
                self.root.wm_aspect(SOURCE_W, SOURCE_H, SOURCE_W, SOURCE_H)
        except Exception:
            pass
        if self.o.get('bezel', True):
            from oracle_photo_bezel import photo_zip, photo_geometry, PHOTO_STEPS
            if photo_zip() is not None:
                minimum = photo_geometry(PHOTO_STEPS[0])
                self.root.minsize(minimum['outer_w'], minimum['outer_h'])
            else:
                self.root.minsize(640, 460)
        else:
            self.root.minsize(640, 460)
        self.borderless = not self.o.get("osframe")
        if self.borderless:                 # the monitor bezel is the outermost frame: no OS title bar / border
            self.root.overrideredirect(True)
            if os.name == "nt":
                self.root.after(60, self._appwindow)

    _mv = None
    borderless = False
    see_through = ""                     # 1036: what the system made of the look's see-through parts ("cut", "alpha" or "")

    def apply_look(self):
        """1036: FLOAT makes the ground between the panels see-through (Windows' -transparentcolor: those pixels are cut out of the window, and
        clicks there reach what is behind it); GLASS makes the whole window a little see-through (-alpha: Windows, macOS, and Linux with a
        compositor).  Where the system has neither, the ground simply shows, in the same colour.  Never on a framed window."""
        sc, r = self.scene, self.root
        look = sc.look() if self.borderless else None
        want = getattr(self, '_photo_mask_bg', '') if (self.borderless and getattr(self, '_photo_mask_bg', None)) else (sc.ground() if look in SEE_THROUGH else "")
        self.see_through = ""
        try:
            r.attributes("-transparentcolor", want)
            self.see_through = "cut" if want else ""
        except Exception:
            pass                                          # X11 / macOS: no colour key
        try:
            r.attributes("-alpha", LOOK_ALPHA.get(look, 1.0))
            if look in LOOK_ALPHA:
                self.see_through = "alpha"
        except Exception:
            pass

    def _appwindow(self):
        """Borderless windows get no taskbar button on Windows unless flagged as an app window."""
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            st = u.GetWindowLongW(hwnd, -20)
            u.SetWindowLongW(hwnd, -20, (st & ~0x80) | 0x40000)
            self.root.withdraw()
            self.root.after(30, self.root.deiconify)
        except Exception:
            pass

    _min_bind = None
    _min_geo = None

    def minimize(self):
        """The bezel's minimise button.  Windows will not iconify a window that has no frame (the default look is override-redirect: Tk
        refuses, or nothing happens), so the frame is switched on just for the minimise and off again when the window comes back."""
        r = self.root
        if not self.borderless or isinstance(self, Fullscreen):
            try:
                r.iconify()
            except Exception:
                pass
            return
        try:
            self._min_geo = r.geometry()
            r.overrideredirect(False)
            r.iconify()
            if self._min_bind is None:
                self._min_bind = r.bind("<Map>", self._restore_frame, add="+")
        except Exception:
            try:
                r.overrideredirect(True)                 # whatever failed, never leave the window framed
            except Exception:
                pass

    def _restore_frame(self, e=None):
        """The window was mapped again (restored from the taskbar): take the frame off and put the window back where it was."""
        r = self.root
        if e is not None and getattr(e, "widget", r) is not r:
            return                                       # a child widget's Map
        try:
            if r.state() != "normal":
                return                                   # the unmap/map of the frame switch itself, still minimised
            if self._min_bind is not None:
                r.unbind("<Map>", self._min_bind)
                self._min_bind = None
            r.overrideredirect(True)
            if self._min_geo:
                r.geometry(self._min_geo)
            if os.name == "nt":
                r.after(60, self._appwindow)
        except Exception:
            pass

    def begin_move(self, ex, ey, mode="move"):
        r = self.root
        self._mv = (mode, ex, ey, r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height())

    def do_move(self, ex, ey):
        if not self._mv:
            return
        mode, x0, y0, wx, wy, ww, wh = self._mv
        if mode == "move":
            self.root.geometry("+%d+%d" % (wx + ex - x0, wy + ey - y0))
        else:
            from oracle_photo_bezel import photo_zip, photo_fit_size, PHOTO_STEPS, photo_geometry
            if self.o.get('bezel', True) and photo_zip() is not None:
                # Resize by selecting a complete image size. No partial photo
                # tiles and no non-uniform scaling, even on frameless Windows.
                delta = max((ex-x0)/1448.0, (ey-y0)/1086.0)
                intended = ww/1448.0 + delta
                allowed = [k for k in PHOTO_STEPS if (
                    photo_geometry(k)['outer_w'] <= self.root.winfo_screenwidth() and
                    photo_geometry(k)['outer_h'] <= self.root.winfo_screenheight())]
                if allowed:
                    k = min(allowed, key=lambda scale: abs(scale-intended))
                    g = photo_geometry(k)
                    self.root.geometry('%dx%d' % (g['outer_w'],g['outer_h']))
            else:
                self.root.geometry("%dx%d" % (max(640, ww + ex - x0), max(460, wh + ey - y0)))

    def end_move(self):
        self._mv = None

    def canvas_size(self):
        """1037: the canvas's size, or the size the window asked for while Tk still reports 1 x 1 (Windows, before the window is shown).  The
        first build used to run at 200 x 200, where the skin's pieces fail; that switched the skin off and left the Windows 98 frame on screen."""
        W, H = self.canvas.winfo_width(), self.canvas.winfo_height()
        rw, rh = getattr(self, "req", (REF_W, REF_H))
        return (W if W >= 400 else rw, H if H >= 300 else rh)

    def _cfg(self, e):
        if self._pending:
            self.root.after_cancel(self._pending)
        self._pending = self.root.after(120, self._rebuild)
        if os.name == 'nt' and self.borderless and self._has_photo():
            self._schedule_metal_shape()

    def _rebuild(self):
        self._pending = None
        W, H = self.canvas.winfo_width(), self.canvas.winfo_height()
        if (self.o.get('bezel', True) and not self.full and
                not isinstance(self, Fullscreen)):
            from oracle_photo_bezel import photo_zip, photo_fit_size
            if photo_zip() is not None:
                target = photo_fit_size(W,H)
                if target != (W,H):
                    # Only exact photo dimensions are accepted; request the
                    # matching native window size and handle its Configure.
                    self.root.geometry('%dx%d' % target)
                    return
        if W > 50 and H > 50 and (W, H) != (self.scene.TW, self.scene.TH):
            self.scene.resized(W, H)

    def toggle_full(self, on=None):
        want = (not self.full) if on is None else bool(on)
        if want == self.full:
            return
        if self._has_photo():
            if want:
                self._restore = self.root.geometry()
            self._set_photo_view(want)
            self.full = want
            return
        # Legacy fullscreen for no-bezel / flat modes.
        if self.borderless:
            r = self.root
            if want:
                self._restore = r.geometry()
                r.geometry('%dx%d+0+0' % (r.winfo_screenwidth(), r.winfo_screenheight()))
            elif getattr(self, '_restore', None):
                r.geometry(self._restore)
        else:
            try:
                self.root.attributes('-fullscreen', want)
            except Exception:
                pass
        self.full = want

    def _report_callback_error(self, exc_type, exc_value, exc_tb):
        # Tk silently prints callback exceptions to stderr, which is absent for
        # console-free Windows pythonw.exe builds. Log them instead.
        try:
            import traceback
            self._callback_errors += 1
            with open(os.path.join(state_dir(), 'callback_error.log'), 'a', encoding='utf-8', errors='replace') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') +
                        ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)) + '\n')
        except Exception:
            pass

    def loop(self):
        t_loop = time.perf_counter()
        try:
            if self.scene.W == 0 or self.scene.need_build:
                self._pending = None
                self.scene.resized(*self.canvas_size())
            self.scene.tick()
            # A single transient Tk/rendering error must never accumulate
            # toward an unexpected crash minutes or hours later.
            self.errors = 0
        except Exception:
            self.errors += 1
            try:
                import traceback
                log = os.path.join(state_dir(), "error.log")
                if os.path.exists(log) and os.path.getsize(log) > 256 * 1024:
                    os.replace(log, log + ".1")          # capped: the newest ~256 KB, plus one older file
                with open(log, "a", encoding="utf-8", errors="replace") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
            except Exception:
                pass
            if self.errors > 50:
                try:
                    from tkinter import messagebox
                    messagebox.showerror('Marble Oracle — rendering error',
                        'The display failed repeatedly. Marble Oracle must close.\n\n'
                        'Diagnostics have been saved to:\n' + os.path.join(state_dir(), 'error.log'),
                        parent=self.root)
                except Exception:
                    pass
                return self.quit(intentional=False)
        # The delay is corrected for the time the frame took.
        fps = self.fps
        wait = int(1000 / fps - (time.perf_counter() - t_loop) * 1000)
        self.after_id = self.root.after(max(1, wait), self.loop)

    def _announce_suite_ready(self):
        """Tell the first-run launcher that this real Tk window is running."""
        marker = os.environ.get('MARBLE_ORACLE_READY_FILE')
        if not marker:
            return
        try:
            self.root.update_idletasks()
            with open(marker, 'w', encoding='ascii') as f:
                f.write(str(os.getpid()))
        except OSError:
            pass

    def run(self):
        self.loop()
        self.root.after_idle(self._announce_suite_ready)
        self.root.mainloop()

    def quit(self, *, intentional=True):
        try:
            if self.system_audio is not None:
                self.system_audio.stop()
        except Exception:
            pass
        try:
            cached_ogg = getattr(self.scene, '_ogg_cached', None)
            if cached_ogg is not None and not cached_ogg.shutdown():
                return   # protect an ongoing conversion from accidental interruption
            cached_touch = getattr(self.scene, '_touch_cached', None)
            if cached_touch is not None:
                cached_touch.shutdown()
            cached_aug = getattr(self.scene, '_aug_cached', None)
            if cached_aug is not None:
                cached_aug.shutdown()
            cached_eido = getattr(self.scene, '_eido_cached', None)
            if cached_eido is not None and not cached_eido.shutdown():
                return   # protect an ongoing video conversion from accidental interruption
            self.scene.markets.stop()
            self.scene.augurspex_chart.close()
            self.scene.close_overlays()
            # Release the reused Rune animation ZIP descriptor on exit.
            try:
                self.scene.rune_deck.close()
            except Exception:
                pass
            # Inform the hidden suite monitor that the user deliberately
            # closed Oracle, not that Tk crashed with a status code of zero.
            if intentional:
                marker = os.environ.get('MARBLE_ORACLE_EXIT_FILE')
                if marker:
                    try:
                        with open(marker, 'w', encoding='ascii') as output:
                            output.write(str(os.getpid()))
                    except OSError:
                        pass
            self.root.destroy()
        except Exception:
            pass


class Fullscreen(WindowApp):
    def setup_window(self, w, h, sw, sh):
        # The root is truly full-monitor, but the photographic canvas is
        # kept at exact baked size and centred by WindowApp.__init__.
        self.root.geometry('%dx%d+0+0' % (sw, sh))
        self.root.overrideredirect(True)
        self.borderless = True

    def __init__(self, opts):
        WindowApp.__init__(self, opts)
        self.full = True


class Wallpaper(Fullscreen):
    """Windows: parent the window under the desktop icons (WorkerW).  Elsewhere it is simply
    borderless fullscreen.  The WorkerW path could not be exercised in the build sandbox."""
    def setup_window(self, w, h, sw, sh):
        self.root.overrideredirect(True)
        self.root.geometry("%dx%d+0+0" % (sw, sh))

    def run(self):
        if os.name == "nt":
            self.root.after(400, self._attach)
        self.loop()
        self.root.after_idle(self._announce_suite_ready)
        self.root.mainloop()

    def _attach(self):
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            prog = u.FindWindowW("Progman", None)
            u.SendMessageTimeoutW(prog, 0x052C, 0, 0, 0, 1000, None)
            found = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def cb(h, _):
                if u.FindWindowExW(h, None, "SHELLDLL_DefView", None):
                    found.append(u.FindWindowExW(None, h, "WorkerW", None))
                return True
            u.EnumWindows(EnumProc(cb), 0)
            if found and found[0]:
                u.SetParent(hwnd, found[0])
        except Exception:
            pass


def startup_cmd(extra=()):
    """The command Windows runs at sign-in: the program in its normal window (pythonw, so no console), plus any extra flags (--wallpaper...)."""
    exe = sys.executable
    if os.name == "nt" and exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return '"%s" "%s"%s' % (exe, os.path.abspath(__file__), "".join(" " + x for x in extra))


STARTUP_FLAGS = (("wallpaper", "--wallpaper"), ("fullscreen", "--fullscreen"), ("no_network", "--no-network"),
                 ("no_crt", "--no-crt"), ("calm", "--calm"), ("legacy_bezel", "--legacy-bezel"))


def startup_flags(a):
    """The launch flags given together with --install-startup that are kept in the startup command (e.g. --wallpaper, --no-network)."""
    return [flag for attr, flag in STARTUP_FLAGS if getattr(a, attr, False)]


def notify(msg, title="Marble_Oracle"):
    """Say it on the console, and in a message box when there is no console (pythonw, a double-clicked .bat): otherwise the user sees nothing."""
    try:
        print(msg)
    except Exception:
        pass
    try:
        if os.name == "nt" and (sys.stdout is None or not sys.stdout.isatty()):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40)
    except Exception:
        pass


class _WinRun:
    """The current user's Run list in the registry (HKCU, no administrator rights needed)."""
    PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _key(self, access):
        import winreg
        return winreg, winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.PATH, 0, access)

    def set(self, name, value):
        w, k = self._key(__import__("winreg").KEY_SET_VALUE)
        w.SetValueEx(k, name, 0, w.REG_SZ, value)

    def delete(self, name):
        w, k = self._key(__import__("winreg").KEY_SET_VALUE)
        try:
            w.DeleteValue(k, name)
            return True
        except FileNotFoundError:
            return False


def startup(install, extra=(), reg=None, windows=None, say=None):
    """--install-startup / --remove-startup: have Windows open the program when the user signs in.  Returns the exit code."""
    say = say or notify
    if not (os.name == "nt" if windows is None else windows):
        say("Starting with Windows is Windows-only (it adds Marble_Oracle to the current user's startup list).")
        return 1
    reg = reg or _WinRun()
    try:
        if install:
            cmd = startup_cmd(extra)
            try:
                reg.delete("MarbleOracle")
            except Exception:
                pass
            reg.set("Marble_Oracle", cmd)
            say("Marble_Oracle will now open when you sign in to Windows.\n\n" + cmd +
                "\n\nTo stop it: run Marble_Oracle-StopStartingWithWindows.bat (or the program with --remove-startup).")
        else:
            gone = False
            for name in ("Marble_Oracle", "MarbleOracle"):
                try:
                    gone = reg.delete(name) or gone
                except Exception:
                    pass
            say("Marble_Oracle will no longer open when you sign in to Windows." if gone
                else "Marble_Oracle was not set to open when you sign in to Windows.")
        return 0
    except Exception as e:
        say("Could not change the Windows startup list: %s: %s" % (type(e).__name__, e))
        return 1


def check(cond, msg="selftest failed"):
    """A --selftest condition. assert is removed by python -O, so a broken window would still print SELFTEST OK."""
    if not cond:
        sys.stderr.write("SELFTEST FAIL: %s\n" % msg)
        raise SystemExit(1)


class Driver(WindowApp):
    """--selftest: drives the real window headlessly: keys, clicks, the deck and the navigator."""
    def run(self):
        s, r = self.scene, self.root
        ev = type("E", (), {})

        def key(ks, ch=""):
            e = ev(); e.keysym, e.char = ks, ch
            s.on_key(e)

        def frames(n):
            for _ in range(n):
                r.update()
                s.tick()
        r.update()
        s.resized(self.canvas.winfo_width(), self.canvas.winfo_height())
        frames(30)
        # The statue must remain readable above CRT/sepia/glass effects,
        # while secondary windows and chrome retain their normal priority.
        stack = list(self.canvas.find_all())
        statue_ids = self.canvas.find_withtag("statue")
        check(bool(statue_ids), "ASCII statue was not rendered")
        highest_statue = max(stack.index(i) for i in statue_ids)
        for effect_tag in ("crt", "pixel-crt", "glare"):
            effects = self.canvas.find_withtag(effect_tag)
            if effects:
                check(highest_statue > max(stack.index(i) for i in effects),
                      "ASCII statue is obscured by %s effect" % effect_tag)
        for k in ("space", "n", "t", "e", "Return", "g", "v", "v"):
            key(k)
            frames(4)
        if s.dk_mod:
            s.act("dk")
            check(s.dk, "Passphrase Studio tab did not open")
            frames(3)
            check(s.dk_eng.check(s.dk.phrase), "Passphrase Studio phrase is invalid")
            first = s.dk.phrase
            key("r")
            check(s.dk.phrase != first and s.dk_eng.check(s.dk.phrase), "new phrase did not roll")
            s.dk.frame.swap()
            check(s.dk_eng.check(s.dk.phrase), "swap broke passphrase")
            s.dk.frame.reroll("w3")
            check(s.dk_eng.check(s.dk.phrase), "reroll broke passphrase")
            check(len(s.dk.frame.part_labels) == 5, "original five-card layout missing")
            check(s.dk.frame.home_button.winfo_exists(), "return-home button missing")
            s.dk.frame.home_button.invoke()
            check(s.dk is None and s._which_overlay() is None, "back-to-Oracle did not return home")
            s.act("dk")
            check(s.dk is not None, "Passphrase cannot be reopened after return home")
            key("Escape")
            check(s.dk is None and s._which_overlay() is None, "escape did not return home")
        s.act("tab_eidolith")
        check(s.eido is not None and s._which_overlay() == "eido", "EIDOLITH tab did not open")
        key("Escape")
        check(s.eido is None and s._which_overlay() is None, "EIDOLITH escape did not return home")
        # Rune integration regression: original Tarot survives switching modes.
        old_tarot = [list(card) for card in s.cards]
        s.act("mode_runes")
        frames(3)
        check(s.divination_mode == "runes", "rune mode did not open")
        check(len(s.c.find_withtag("rune-art")) >= 3,
              "rune images were not drawn to canvas")
        check(not s.rune_art_error, "rune image loading failed: " + str(s.rune_art_error))
        check(len(s.rune_widgets) == 3 and all(w.winfo_ismapped() for w in s.rune_widgets),
              "native rune art widgets missing or invisible")
        check(all(s.c.type(item) == "image" for item in s.c.find_withtag("rune-art")),
              "rune artwork was replaced by fallback ovals")
        order = list(s.c.find_all())
        for tag in ("crt", "pixel-crt", "glare"):
            fx = s.c.find_withtag(tag)
            if fx:
                check(min(order.index(item) for item in s.c.find_withtag("rune-art")) > max(order.index(item) for item in fx),
                      "rune image still obscured by " + tag)
        s.act("rune_draw")
        check(len(s.rune_drawn) == 3, "rune draw did not select three")
        check(len(set(entry["name"] for entry in s.rune_drawn)) == 3, "duplicate runes in reading")
        check(s.rune_state == "drawing", "rune reading did not start")
        first_run = s.rune_run_id
        s.act("rune_draw")
        check(s.rune_run_id == first_run + 1 and s.rune_state == "drawing",
              "RESTART DRAW button did not respond during reveal")
        # Exercise actual timed eight-frame animation across all three stones.
        deadline = time.monotonic() + 15.0
        while s.rune_state != "complete" and time.monotonic() < deadline:
            r.update()
            time.sleep(0.012)
        check(not s.rune_art_error, "rune animation image failed: " + str(s.rune_art_error))
        check(s.rune_state == "complete" and s.rune_revealed == 3,
              "three sequential rune flips did not complete")
        check(s.rune_anim_index == -1, "last animated frame not released")
        s.draw_cards()
        s.act("rune_select2")
        check(s.rune_sel == 2, "rune selection failed")
        s.act("mode_tarot")
        check(s.divination_mode == "tarot" and s.cards == old_tarot, "Tarot state was altered")
        check(all(not w.winfo_ismapped() for w in s.rune_widgets), "rune art still covers Tarot")
        s.resized(900, 620)
        frames(10)
        print("SELFTEST OK  v%s build %s  fps-frames=%d" % (VERSION, BUILD, s.frame_no))
        self.quit()


def parse(argv):
    import argparse
    p = argparse.ArgumentParser(prog="Marble_Oracle", description="Marble_Oracle")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--wallpaper", action="store_true")
    p.add_argument("--fullscreen", action="store_true")
    p.add_argument("--frameless", action="store_true", help=argparse.SUPPRESS)   # no-op alias: borderless is already the default; old startup entries still parse
    p.add_argument("--theme", default=None, choices=sorted(THEMES), help="colour scheme (default: the last GRADE preset)")
    p.add_argument("--layout", default=None, choices=sorted(LAYOUTS), help="panel layout, with --theme")
    p.add_argument("--no-dicekey", action="store_true", help="leave the PASSPHRASE tab out")
    for gone in ("--no-calendar", "--no-flux", "--no-comfy", "--no-chat", "--no-promptforge"):     # 1027: BIN WEEK and X-PLATE are gone; 1031: the MIND PIT too; the flags are hidden no-ops so old startup entries still parse
        p.add_argument(gone, action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--comfy", default=None, help=argparse.SUPPRESS)
    p.add_argument("--calm", action="store_true", help="no motion in the 90s tab art")
    p.add_argument("--no-markets", action="store_true")
    p.add_argument("--no-network", action="store_true")
    for gone in ("--no-deck", "--no-liarsdice", "--no-local", "--no-web", "--check-webui", "--check-ollama"):   # 1058: MEDIA, LIAR'S DICE and THE LIEN are gone; hidden no-ops so old startup entries still parse
        p.add_argument(gone, action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--local-model", default=None, help=argparse.SUPPRESS)
    p.add_argument("--no-crt", action="store_true")
    p.add_argument("--crt-v2", action="store_true", help="use the new CRT V2 hardware renderer (default)")
    p.add_argument("--legacy-bezel", action="store_true", help="select the old Flush bezel instead of CRT V2")
    p.add_argument("--no-pixel-barrel", action="store_true", help="leave the inner screen flat; the metal bezel is unchanged")
    p.add_argument("--no-audio-scope", action="store_true", help="disable Windows system-output audio capture")
    p.add_argument("--no-bezel", action="store_true")
    p.add_argument("--retro", action="store_true", help="the 1033 look: neon colours, the CRT monitor case and scanlines")
    p.add_argument("--look", default=None, type=str.upper, choices=LOOKS + RETIRED_LOOKS, help=argparse.SUPPRESS)   # 1059: OLED is the one look; old names still parse
    p.add_argument("--flat", action="store_true", help="the flat 1030 look (no modern panels, shadows or glass bars)")
    p.add_argument("--os-frame", action="store_true", help="keep the normal OS title bar / border")
    p.add_argument("--horizon", default=None, help=argparse.SUPPRESS)
    p.add_argument("--wire", default=None, help="optional RSS URL for ticker headlines")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("--install-startup", action="store_true")
    p.add_argument("--remove-startup", action="store_true")
    return p.parse_args(argv)


def hide_console():
    """Windows: python.exe opens a console window behind the app.  Hide it if it belongs to us alone
    (never hide a terminal the user launched us from).  Launching with pythonw / Marble_Oracle.pyw
    avoids it appearing at all."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        hwnd = k32.GetConsoleWindow()
        if not hwnd:
            return
        pids = (ctypes.c_uint * 8)()
        n = k32.GetConsoleProcessList(pids, 8)
        if n <= 1:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main(argv=None):
    if sys.stdout is None:                 # pythonw: no console streams
        sys.stdout = sys.stderr = open(os.devnull, "w")
    hide_console()
    args = list(argv if argv is not None else sys.argv[1:])
    if not any(x in args for x in ("--crt-v2", "--legacy-bezel", "--retro", "--no-bezel", "--wallpaper", "--fullscreen")):
        args.insert(0, "--no-bezel")
    a = parse(args)
    # New rusted hardware frame is the default for ALL launchers.
    # --legacy-bezel is the explicit compatibility path.
    use_v2 = (a.crt_v2 or not a.legacy_bezel) and not a.no_bezel and not a.wallpaper
    if use_v2:
        os.environ["MARBLE_ORACLE_CRT_V2"] = "1"
    else:
        os.environ.pop("MARBLE_ORACLE_CRT_V2", None)
    if a.calm:
        os.environ["MARBLE_ORACLE_CALM"] = "1"                 # read by oracle_vhs when each tab builds its art
    if a.version:
        print("%s %s" % (TITLE, VERSION_NAME))
        return 0
    if a.install_startup or a.remove_startup:
        return startup(a.install_startup, startup_flags(a))
    if a.check_webui or a.check_ollama:                # 1058: THE LIEN is gone; the old checks print that and exit, as they always exited
        print("THE LIEN was removed in build 1058: there is no model to check.")
        return 0
    opts = dict(theme=a.theme, layout=a.layout or "CLASSIC", fps=a.fps, frameless=a.frameless, crt_v2=use_v2,
                no_dicekey=a.no_dicekey, no_markets=a.no_markets,
                no_network=a.no_network or a.selftest, crt=not a.no_crt, wire=a.wire, bezel=not a.no_bezel, osframe=a.os_frame or a.no_bezel, flat=a.flat,
                retro=a.retro, look=a.look, no_pixel_barrel=a.no_pixel_barrel, no_audio_scope=a.no_audio_scope)
    if not is_retro(opts):
        # A photographic CRT monitor MUST have restrained scanlines by default,
        # even with the clean OLED dashboard.  --no-crt / C still disables them.
        opts["crt"] = bool(opts.get('bezel') and not a.no_crt)

    if a.wallpaper:
        opts["bezel"] = False
    if a.selftest:
        opts["no_markets"] = False
        opts["selftest"] = True                  # presses V twice: it must not move the owner's saved VIEW
        cls = Driver
    elif a.wallpaper:
        cls = Wallpaper
    elif a.fullscreen:
        cls = Fullscreen
    else:
        cls = WindowApp
    cls(opts).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
