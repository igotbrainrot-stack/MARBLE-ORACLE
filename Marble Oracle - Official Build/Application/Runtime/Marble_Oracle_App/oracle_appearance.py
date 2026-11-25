"""The suite's appearance (0.5.1): Dark, Light or Classic, with an accent colour.

Dark and Light are OVERCAST's quiet, rounded, Apple-like design (its palette and accents come from
``overcast.theme``, so the whole suite and OVERCAST share one set of colours): flat surfaces, a sans-serif
interface font, a left sidebar. Classic is the suite as it was up to 0.5.0: Oggcultist's Ember palette, film
grain, Uberata Clear and the tab strip.

How it works: every workspace takes its colours from shared token dictionaries
(``oggcultist_design_system.COLOR``, the embedded Oggcultist's own ``design_system.COLOR``, and HOME's
``THEMES``) and its font from ``marble_uberata.FAMILY``. ``apply(root)`` runs once, after the window exists
and before anything is drawn, and points those tokens at the chosen palette and font. Changing the appearance
therefore takes effect when the suite next starts (Settings offers to restart).

The choice is stored in ``<state>/appearance.json``. ``MARBLE_ORACLE_APPEARANCE`` (dark / light / classic)
and ``MARBLE_ORACLE_ACCENT`` override it for one run (screenshots, tests).
"""
from __future__ import annotations

import json
import os
import sys

APPEARANCES = ('dark', 'light', 'classic')
LABELS = {'dark': 'Dark', 'light': 'Light', 'classic': 'Classic'}
DESCRIPTIONS = {
    'dark': 'Quiet dark surfaces, rounded cards, a sidebar.',
    'light': 'The same design on light surfaces.',
    'classic': "The original look: Oggcultist's Ember colours, film grain, the serif face and the tab strip.",
}
DEFAULT_APPEARANCE = 'dark'
PREFS_FILE = 'appearance.json'

_state = {'appearance': None, 'accent': None, 'palette': None, 'family': None, 'applied': False}


# ---- preference ---------------------------------------------------------------------------------
def _prefs_path():
    from oracle_assets import state_dir
    return os.path.join(state_dir(), PREFS_FILE)


def accents():
    from overcast.theme import ACCENTS
    return tuple(ACCENTS)


def read_prefs():
    try:
        with open(_prefs_path(), encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_prefs(appearance, accent):
    if appearance not in APPEARANCES:
        raise ValueError(appearance)
    if accent not in accents():
        raise ValueError(accent)
    path = _prefs_path()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump({'appearance': appearance, 'accent': accent}, handle)
    os.replace(tmp, path)


def chosen():
    """(appearance, accent) for this run: the environment overrides, then the saved choice, then Dark/Amber."""
    saved = read_prefs()
    appearance = (os.environ.get('MARBLE_ORACLE_APPEARANCE') or saved.get('appearance') or DEFAULT_APPEARANCE).lower()
    if appearance not in APPEARANCES:
        appearance = DEFAULT_APPEARANCE
    accent = (os.environ.get('MARBLE_ORACLE_ACCENT') or saved.get('accent') or 'Amber').title()
    if accent not in accents():
        accent = 'Amber'
    return appearance, accent


def appearance():
    return _state['appearance'] or chosen()[0]


def accent():
    return _state['accent'] or chosen()[1]


def modern():
    """True for Dark and Light; False for Classic."""
    return appearance() != 'classic'


def palette():
    """OVERCAST's resolved palette for this run (None in Classic)."""
    return _state['palette']


def family():
    """The interface font family in use (Uberata Clear in Classic)."""
    if _state['family']:
        return _state['family']
    from marble_uberata import FAMILY
    return FAMILY


# ---- the token mapping --------------------------------------------------------------------------
def ember_roles(p):
    """Oggcultist's Ember colour roles, re-expressed in OVERCAST's palette `p`."""
    from overcast.theme import mix
    dark = p['appearance'] == 'dark'
    sunken = p['side'] if dark else '#FFFFFF'
    return {
        'canvas': p['bg'], 'raised': p['card'], 'sunken': sunken,
        'sunken_alt': mix(p['card'], sunken, 0.5) if dark else '#F7F7FA',
        'sidebar': p['side'], 'nav_hover': mix(p['field'], p['side'], 0.45), 'nav_current': p['select_side'],
        'hover': p['field_hover'], 'line': p['line'], 'line_strong': mix(p['faint'], p['line'], 0.5),
        'control': p['field'], 'control_line': p['faint'],
        'text': p['ink'], 'text_2': p['dim'], 'text_3': p['dim'], 'text_on_accent': p['on_accent'],
        'text_bright': p['ink'], 'sidebar_text': p['ink'], 'sidebar_icon': p['dim'],
        'accent': p['accent'], 'accent_deep': p['accent_hover'], 'accent_soft': p['select'],
        'focus': p['accent'],
        'ready': p['ink'], 'done': p['green'], 'review': p['accent_text'], 'skipped': p['dim'],
        'failed': p['red'], 'danger_text': p['red'], 'danger_line': p['red'],
        'rise': p['green'], 'fall': p['red'],
    }


def home_theme(p):
    """HOME's canvas tokens (the names the dashboard has always used) in OVERCAST's palette."""
    from overcast.theme import mix
    return dict(bg=p['bg'], panel=p['card'], edge=p['line'], edge2=p['field'], cyan=p['accent_text'],
                mag=p['dim'], gold=p['accent_text'], lime=p['green'], txt=p['ink'], dim=p['dim'], red=p['red'],
                orange=p['accent'], marble=p['ink'], sun1=p['accent'], sun2=p['accent_hover'],
                ramp=(mix(p['faint'], p['card'], 0.5), p['ink']))


def _flat_gradient(colour):
    return (colour, colour, colour)


def retint_design_system(ds, p):
    """Point a design_system module (the suite's or the embedded Oggcultist's) at the palette, in place."""
    ds.COLOR.update(ember_roles(p))
    from overcast.theme import mix
    for name, colour in (('ACCENT_GRADIENT', p['accent']), ('ACCENT_GRADIENT_HOVER', p['accent_hover']),
                         ('ACCENT_GRADIENT_PRESSED', mix(p['accent'], p['bg'], 0.8)),
                         ('ACCENT_GRADIENT_DISABLED', mix(p['accent'], p['bg'], 0.35))):
        if hasattr(ds, name):
            setattr(ds, name, _flat_gradient(colour))


def choose_family(root):
    """Inter, bundled with the suite (0.5.3), so every machine reads the same; the system's best sans-serif
    (OVERCAST's order) if it could not be loaded. MARBLE_ORACLE_FONT forces another (tests use it to try the
    wider faces other machines fall back to)."""
    from overcast.theme import choose_font, FONT_PREFERENCE
    import marble_uberata
    marble_uberata.register_inter()
    order = (marble_uberata.INTER_FAMILY,) + tuple(f for f in FONT_PREFERENCE if f != marble_uberata.INTER_FAMILY)
    forced = os.environ.get('MARBLE_ORACLE_FONT')
    return choose_font(root, (forced,) + order if forced else order)


def apply(root):
    """Apply the chosen appearance for this run. Call once, after the Tk root exists and before the scene is
    built or any workspace is opened. Classic changes nothing."""
    if _state['applied']:
        return appearance()
    look, tint = chosen()
    _state.update(appearance=look, accent=tint, applied=True)
    if look == 'classic':
        return look
    from overcast.theme import palette as overcast_palette
    p = overcast_palette(look, tint)
    _state['palette'] = p
    # 1. Colours: the shared Ember tokens, HOME's scheme and its surfaces.
    import oggcultist_design_system as ds
    retint_design_system(ds, p)
    import oracle_chrome
    import marble_oracle
    scheme = home_theme(p)
    oracle_chrome.THEMES['EMBER'].clear()
    oracle_chrome.THEMES['EMBER'].update(scheme)
    marble_oracle.EMBER_SURFACES.clear()
    marble_oracle.EMBER_SURFACES.update(bg=p['bg'], panel=p['card'], edge=p['line'], edge2=p['field'])
    import oracle_home_focus
    oracle_home_focus.FOCUS_COLOUR = p['accent']
    oracle_home_focus.HOVER_COLOUR = p['faint']
    install_text_case()
    # Market colours (AUGURSPEX's rows, chips and legends): the same hues, readable on this palette's surfaces.
    # The Ember pastels were 1.5:1 on Light's white cards (0.5.4).
    from overcast.theme import readable
    import oracle_design
    surfaces = (p['bg'], p['card'], p['side'], p['field'])
    oracle_design.MARKET_COLORS.update({k: readable(v, surfaces) for k, v in oracle_design.MARKET_COLORS.items()})
    try:
        import oracle_augurspex_insights
        oracle_augurspex_insights.COLORS.update(oracle_design.MARKET_COLORS)
    except Exception:
        pass
    # 2. A faint pumice instead of Classic's film grain (0.5.2), on the new surface colours.
    import oracle_ogg_texture
    roles = ember_roles(p)
    oracle_ogg_texture.use_pumice({'page': p['bg'], 'card': p['card'], 'side': p['side'], 'sunken': roles['sunken'],
                                   'sunken_alt': roles['sunken_alt'], 'control': p['field'],
                                   'accent_soft': p['select']})
    # 3. The interface font. HOME's statue keeps Uberata Clear (it is ASCII art and needs its metrics).
    import marble_uberata
    marble_uberata.ART_FAMILY = marble_uberata.FAMILY
    face = choose_family(root)
    _state['family'] = face
    marble_uberata.FAMILY = face
    # OVERCAST's type sizes: the shell's sizes were set for the narrower serif face.
    import oracle_shell
    oracle_shell.TYPE.update(nav=(12, 'normal'), button=(10, 'bold'), group=(9, 'bold'))
    oracle_shell.BUTTON_PAD = (12, 6)
    for module in list(sys.modules.values()):
        if getattr(module, 'FAMILY', None) == marble_uberata.ART_FAMILY and getattr(module, '__name__', '') in (
                'oracle_shell', 'oracle_augurspex_tab', 'oracle_touch_type', 'oracle_augurspex_insights', 'oracle_ogg_tab',
                'oracle_eidolith', 'marble_passphrase_tab'):
            module.FAMILY = face
    return look


def retint_oggcultist():
    """The embedded Oggcultist keeps its own copy of the tokens and fonts; point them at the palette before its
    window is built (called by oracle_ogg_tab)."""
    p = palette()
    if p is None:
        return
    try:
        from oggcultist.gui import design_system as ogg_ds
        retint_design_system(ogg_ds, p)
        ogg_ds.BODY_POINTS = 11          # the sans face reads larger than Uberata Clear at the same size
        # 0.5.3: rounder corners (its theme draws buttons, fields and cards at RADIUS['s'] - 2; its nine-slice
        # borders are 7-10 px, so up to 7 px stays undistorted).
        ogg_ds.RADIUS = dict(ogg_ds.RADIUS, s=9, m=10)
    except Exception:
        pass
    try:
        _flatten_oggcultist_artwork(p)
    except Exception:
        pass
    try:
        from oggcultist import fonts as ogg_fonts
        face = family()
        for name in ('HEADING_FAMILY', 'BODY_FAMILY', 'FAMILY', 'CLEAR_FAMILY'):
            if hasattr(ogg_fonts, name):
                setattr(ogg_fonts, name, face)
    except Exception:
        pass


# ---- text case ----------------------------------------------------------------------------------
# Classic labels are set in capitals; Dark and Light use sentence case, as OVERCAST does. Acronyms and
# product names keep their form.
KEEP_UPPER = {'AV1', 'HEVC', 'H.264', 'H.265', 'CSV', 'FX', 'BTC', 'ETH', 'ETF',
              'ETFS', 'US', 'UK', 'EU', 'RSS', 'LM', 'ICS', 'CRT', 'GPU', 'CPU', 'HDR', 'OK', 'EFF', 'URL', 'API',
              'ID', 'IDS', 'PDF', 'I', 'TV', 'AAC', 'MP3', 'OGG', 'OPUS', 'FLAC', 'MKV', 'MP4', 'WEBM', 'SVT', 'CRF',
              'NVENC', 'QSV', 'AMF', 'VAAPI', 'UTC', 'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'IPA', 'WPM',
              'II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'D', 'W', 'M', 'Y', 'OHLC', 'SMA', 'EMA', 'RSI',
              'MACD', 'ATR', 'VWAP', 'DPI', 'UI', 'RAM', 'STK', 'WAV', 'SRT', 'ASS', 'JSON', 'PNG',
              'JPG', 'GIF', 'YAML', 'HTTP', 'HTTPS', 'LLM', 'AI', 'OS', 'NTSC', 'PAL', 'FPS', 'SDR', 'VP9', 'DTS', 'AC3'}
NAMES = {'HOME': 'Home', 'OGGCULTIST': 'Oggcultist', 'EIDOLITH': 'Eidolith', 'AUGURSPEX': 'Augurspex',
         'OVERCAST': 'Overcast', 'MARBLE': 'Marble', 'ORACLE': 'Oracle',
         'LATIN': 'Latin', 'TAROT': 'Tarot', 'EFF': 'EFF', 'FFMPEG': 'FFmpeg', 'FFPROBE': 'FFprobe',
         'FFPLAY': 'FFplay', 'LM STUDIO': 'LM Studio'}


_REGISTERED = set()


def register_terms(words):
    """Add words that stay in capitals in Dark/Light (market symbols such as AAPL, from AUGURSPEX's list)."""
    _REGISTERED.update(str(w).upper() for w in words if w)


def _keep_upper(word):
    if word in KEEP_UPPER or word in _REGISTERED or any(ch.isdigit() for ch in word):
        return True
    for joint in ('-', ':', '/'):              # BTC-USD, FX:EURUSD, USD/JPY
        if joint in word and len(word) > 1:
            head = word.split(joint)[0]
            if head in KEEP_UPPER or head in _REGISTERED:
                return True
    return False


def install_text_case():
    """Write widget labels in sentence case in Dark and Light (0.5.4).

    Each workspace was written for Classic, whose serif face is set in capitals; in the sans-serif looks
    those capitals read as shouting and clash with the sentence-case shell. Rather than rewrite hundreds of
    strings (and lose Classic's look), every widget's `text` option passes through display() on its way to
    Tk. Text that already has a lower-case letter is left alone, as are acronyms and market symbols
    (KEEP_UPPER, register_terms). Canvas items are not touched: HOME and the charts set their own case.
    """
    import tkinter as tk
    if getattr(tk.Misc, '_marble_case', False) or not modern():
        return
    original = tk.Misc._options

    def _options(self, cnf, kw=None):
        if not isinstance(self, tk.Canvas):
            # Copies: the caller's dictionaries are left as they were.
            if isinstance(cnf, dict) and isinstance(cnf.get('text'), str):
                cnf = dict(cnf, text=display(cnf['text']))
            if isinstance(kw, dict) and isinstance(kw.get('text'), str):
                kw = dict(kw, text=display(kw['text']))
        return original(self, cnf, kw)
    tk.Misc._options = _options
    tk.Misc._marble_case = True


def display(text):
    """The label as this appearance writes it: unchanged in Classic; capitals become sentence case in Dark/Light."""
    if not isinstance(text, str) or not modern():
        return text
    letters = [ch for ch in text if ch.isalpha()]
    if not letters or any(ch.islower() for ch in letters):
        return text
    out, start = [], True
    for token in text.split(' '):
        core = token.strip('()[]{}"\'.,:;!?…+-–—/·')
        if not core:
            out.append(token)
            if '·' in token or token.endswith(('.', ':', '?', '!')):
                start = True
            continue
        word = core.upper()
        if '+' in core and len(core) > 1:                   # key combinations: Ctrl+C, Shift+Tab
            new = '+'.join(part[:1].upper() + part[1:].lower() if len(part) > 1 else part.upper()
                           for part in core.split('+'))
        elif core == 'A' and not start:                        # the article, not the A key
            new = 'a'
        elif len(core) == 1 or (token.startswith('[') and token.rstrip(',.').endswith(']')):   # keys: R, [S]
            new = core
        elif _keep_upper(word):
            new = core
        elif word in NAMES:
            new = NAMES[word]
        elif start:
            new = core[:1] + core[1:].lower()
        else:
            new = core.lower()
        out.append(token.replace(core, new, 1))
        if any(ch.isalpha() for ch in core):
            start = token.endswith(('.', ':', '?', '!')) or token.endswith('·')
        elif any(ch.isdigit() for ch in core) and not (len(core) == 2 and core.startswith('0')):
            # A count or measure reads as part of the sentence: "2 shown", "~44.3 bits", "−10 sec". A list
            # number (01, 02) and symbols (▣) leave the next word starting the label.
            start = False
    return ' '.join(out)


# ---- the embedded Oggcultist's generated artwork ------------------------------------------------
_EMBER_ORIGINAL = {
    '#1D1714': 'canvas', '#261F1B': 'raised', '#16110F': 'sunken', '#1A1512': 'sunken_alt', '#130F0D': 'sidebar',
    '#1E1714': 'nav_hover', '#2A1F19': 'nav_current', '#372A23': 'hover', '#3A2E27': 'line', '#493B32': 'line_strong',
    '#2F2620': 'control', '#85705F': 'control_line', '#F2E8DE': 'text', '#B9A99B': 'text_2', '#A79686': 'text_3',
    '#2B1405': 'text_on_accent', '#FFF4E6': 'text_bright', '#FB8E22': 'accent', '#E0601A': 'accent_deep',
    '#4A2C18': 'accent_soft',
}


_EMBER_LITERALS = set()      # the hex colours written in Oggcultist's theme and its original gradients (filled lazily)


def _ember_literals():
    if not _EMBER_LITERALS:
        import re
        from pathlib import Path
        _EMBER_LITERALS.update(_EMBER_ORIGINAL)
        _EMBER_LITERALS.update(('#FED154', '#FDA629', '#EC4406', '#FFDB6E', '#FFB441', '#F45616', '#F0BC45', '#EE931F',
                                '#D63B05', '#5E4A39', '#56402F', '#4C3426'))
        gui = Path(__file__).resolve().parent / 'Oggcultist' / 'oggcultist' / 'gui'
        for name in ('theme.py', 'textures.py', 'design_system.py'):
            try:
                _EMBER_LITERALS.update(c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", (gui / name).read_text()))
            except OSError:
                pass
    return _EMBER_LITERALS


def translate_ember(colour, p, strict=False):
    """An Ember-family colour (Oggcultist's warm browns, ambers and creams) as the matching OVERCAST colour.
    strict: only colours Oggcultist itself writes (its tokens, gradients and theme literals) are translated, so
    tints computed from the new palette are left alone."""
    import colorsys
    from overcast.theme import hex_rgb, luminance, mix
    key = str(colour).upper()
    if key in _EMBER_ORIGINAL:
        return ember_roles(p)[_EMBER_ORIGINAL[key]]
    if strict and key not in _ember_literals():
        return colour
    try:
        r, g, b = (v / 255.0 for v in hex_rgb(key))
    except (ValueError, IndexError):
        return colour
    hue, saturation, value = colorsys.rgb_to_hsv(r, g, b)
    if key in ('#000000', '#FFFFFF') or r <= b + 0.015:
        return key           # neutral or cool: not an Ember colour (OVERCAST's greys are neutral or slightly blue)
    if saturation > 0.45 and value > 0.55:                     # amber / gold highlights
        return p['accent_hover'] if value > 0.9 and saturation < 0.6 else p['accent']
    if value > 0.8 and saturation <= 0.45:                     # creams: text
        return p['ink']
    low, high = luminance('#120E0C'), luminance('#6A5646')
    t = max(0.0, min(1.0, (luminance(key) - low) / max(1e-6, high - low)))
    if p['appearance'] == 'dark':
        return mix(p['field_hover'], p['side'], t)
    return mix(p['faint'], p['card'], t) if t > 0.5 else mix(p['field_hover'], p['card'], t * 2)


def _flatten_oggcultist_artwork(p):
    from oggcultist.gui import textures as tx
    if getattr(tx, '_marble_flat', False):
        return
    original_rgb = tx._rgb
    tx._rgb = lambda colour: original_rgb(translate_ember(colour, p, strict=True) if isinstance(colour, str) else colour)
    tx._finish = _pumice_finish                                              # pumice, not film grain (0.5.2)
    tx.bevel = lambda image, radius=0, strength=0, inset=0.0: image          # no bevel shading
    tx._marble_flat = True


_PUMICE_OFFSET = {}


def _pumice_finish(body, seed=0, amount=0.0, mottle=True):
    """Oggcultist's _finish for Dark / Light: the faint pumice relief over a Pillow image, instead of film grain.
    Surfaces with no grain asked for (amount 0) stay flat."""
    if not amount:
        return body
    try:
        import io
        from PIL import Image, ImageChops
        import oracle_pumice
        tile = _PUMICE_OFFSET.get('tile')
        if tile is None:
            tile = _PUMICE_OFFSET['tile'] = Image.open(io.BytesIO(oracle_pumice.offset_png())).convert('RGB')
        w, h = body.size
        offset = Image.new('RGB', (w, h))
        for y in range(0, h, tile.height):
            for x in range(0, w, tile.width):
                offset.paste(tile, (x, y))
        mode = body.mode
        out = ImageChops.add(body.convert('RGB'), offset, 1.0, -128)
        return out.convert(mode) if mode != 'RGB' else out
    except Exception:
        return body
