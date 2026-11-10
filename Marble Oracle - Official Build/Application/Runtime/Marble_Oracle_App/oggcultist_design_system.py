"""Oggcultist 2.0 "Ember" design tokens: the one source of truth for the look.

``theme.py`` turns these into ttk styles; views should take sizes, spacing and colours
from here (or from the named fonts the theme creates) rather than writing numbers inline.

Units: spacing and sizes are logical Tk pixels on a 4 px grid. Type sizes are points
(Tk scales them with the system DPI). Contrast ratios were measured against ``canvas``.
"""
from __future__ import annotations

# ---- colour roles ---------------------------------------------------------------------------
COLOR = {
    # surfaces
    'canvas': '#1D1714',          # page background (film grain)
    'raised': '#261F1B',          # cards, player bar
    'sunken': '#16110F',          # tables and fields
    'sunken_alt': '#1A1512',      # alternate table rows
    'sidebar': '#130F0D',
    'nav_hover': '#1E1714',
    'nav_current': '#2A1F19',
    'hover': '#372A23',
    'line': '#3A2E27',            # borders, separators
    'line_strong': '#493B32',
    'control': '#2F2620',
    'control_line': '#59473B',
    # text (contrast on canvas): text 14.7:1, text_2 7.8:1, text_3 4.7:1
    'text': '#F2E8DE',
    'text_2': '#B9A99B',
    'text_3': '#928174',          # disabled and tertiary text (was #6F5E52 at 2.6:1)
    'text_on_accent': '#2B1405',
    'text_bright': '#FFF4E6',
    'sidebar_text': '#D9C9BB',
    'sidebar_icon': '#AFA092',
    # accent: used only for the primary action, the playing state, progress and focus
    'accent': '#FB8E22',
    'accent_deep': '#E0601A',
    'accent_soft': '#4A2C18',     # selected rows, current filter
    'focus': '#FB8E22',
    # status
    'ready': '#F2E8DE',
    'done': '#93CC7F',
    'review': '#FFC24A',
    'skipped': '#A49B93',
    'failed': '#FF6A55',
    'danger_text': '#FF9A85',
}
ACCENT_GRADIENT = ('#FED154', '#FDA629', '#EC4406')
ACCENT_GRADIENT_HOVER = ('#FFDB6E', '#FFB441', '#F45616')
ACCENT_GRADIENT_PRESSED = ('#F0BC45', '#EE931F', '#D63B05')
ACCENT_GRADIENT_DISABLED = ('#5E4A39', '#56402F', '#4C3426')

# ---- type scale (Uberata Clear v3.0 throughout) ----------------------------------------------------
# role: (family, size in points relative to the body size, weight, use)
# Both display and text roles use the single Uberata Clear family, with sizes defining hierarchy.
BODY_POINTS = 12                  # Uberata Clear v3.0 retains legibility at typical UI sizes
TYPE = {
    'display_xl': ('display', +14, 'normal', 'page titles'),
    'display_l': ('display', +6, 'normal', 'now-playing title, empty-state titles'),
    'brand': ('display', +6, 'normal', 'wordmark fallback text'),
    'title': ('text', +2, 'bold', 'card and section titles'),
    'body': ('text', 0, 'normal', 'default text, lists, fields'),
    'body_bold': ('text', 0, 'bold', 'emphasis'),
    'small': ('text', -1, 'normal', 'secondary lines, status'),
    'small_bold': ('text', -1, 'bold', 'chips, compact controls'),
    'label': ('text', -2, 'bold', 'group labels and column headings (capitals)'),
    'nav': ('text', +1, 'normal', 'sidebar items'),
}
MIN_POINTS = 10

# ---- spacing (4 px grid) -------------------------------------------------------------------------
SPACE = {'xxs': 2, 'xs': 4, 's': 8, 'm': 12, 'l': 16, 'xl': 24, 'xxl': 32}
SPACING = {"hairline": 2, "micro": 4, "tight": 8, "related": 12,
           "control": 16, "section": 24, "major": 32}        # 1.9 names, same values

# ---- layout -------------------------------------------------------------------------------------
SIDEBAR_WIDTH = 208
SIDEBAR_COMPACT_WIDTH = 64        # icon rail
COMPACT_BREAKPOINT = 1100         # window width below which the sidebar becomes the icon rail
MIN_WINDOW = (960, 600)
DEFAULT_WINDOW = (1280, 800)
PLAYER_HEIGHT = 88
COVER_SMALL = 64
ROW_HEIGHT = 36
SIDEBAR_INSET = 12
NAV_VERTICAL_PAD = 8
NAV_ICON = 18
BUTTON_HORIZONTAL = 16
BUTTON_VERTICAL = 8
TABLE_ROW_GAP = ROW_HEIGHT        # kept for 1.9 callers: rows are a fixed 36 px now
TOPBAR_MARGIN = 32
CONTENT_MARGIN = 32
PAGE_PADDING = (CONTENT_MARGIN, 4, CONTENT_MARGIN, 16)   # left, top, right, bottom
MIN_CONTENT_WIDTH = MIN_WINDOW[0] - SIDEBAR_COMPACT_WIDTH - 2 * CONTENT_MARGIN

# ---- shape and depth ----------------------------------------------------------------------------
RADIUS = {'s': 4, 'm': 6, 'round': 999}
BEVEL = {'raised': 0.20, 'soft': 0.12, 'sunken': -0.22}

# ---- motion (milliseconds) ----------------------------------------------------------------------
MOTION = {'hover': 120, 'press': 60, 'drift_cycle': 8000}


def points(role: str, body: int = BODY_POINTS) -> int:
    """Point size for a type role given the body size."""
    return max(MIN_POINTS, body + TYPE[role][1])


def sidebar_font_points(base_size: int) -> int:
    """Sidebar item size: one step above body, capped so labels never crowd the 208 px rail."""
    return max(MIN_POINTS, min(15, base_size + TYPE['nav'][1]))


def contrast(foreground: str, background: str) -> float:
    """WCAG 2 contrast ratio between two #RRGGBB colours."""
    def luminance(colour: str) -> float:
        channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    a, b = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)
