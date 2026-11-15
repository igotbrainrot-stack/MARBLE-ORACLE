"""Suite-wide design tokens shared by every Marble Oracle workspace.

The colour roles, type scale and spacing live in oggcultist_design_system
(the "Ember" tokens Oggcultist introduced and the other workspaces adopted).
This module re-exports them and adds the few tokens that belong to the suite
as a whole, so a workspace never has to spell a colour or a label inline:

* MARKET_COLORS  one colour per market category, used wherever AUGURSPEX
                 marks a row or legend entry (colour is always paired with
                 a text label or symbol; it never carries meaning alone);
* HOME_LABEL     the single wording for "leave this workspace".

Nothing here imports Tk.
"""
from __future__ import annotations

from oggcultist_design_system import COLOR, SPACE, TYPE  # noqa: F401  (re-exported)

# Warm amber for equities, muted teal for currencies, restrained lavender for
# crypto. Contrast on the 'sidebar' surface: 10.9:1, 11.6:1 and 9.7:1.
MARKET_COLORS = {'stocks': '#FFB667', 'fx': '#77DCC2', 'crypto': '#CCAAFF'}
MARKET_LABELS = {'stocks': 'STOCKS', 'fx': 'FX', 'crypto': 'CRYPTO'}

# Every workspace offers one way back to the HOME dashboard, worded the same.
HOME_LABEL = 'HOME'


def market_color(category: str) -> str:
    return MARKET_COLORS.get(category, COLOR['text'])


def flow_layout(sizes, width, gap_x=8, gap_y=4):
    """Positions for items laid left to right that wrap to a new row at `width`.

    `sizes` is a sequence of (item width, item height). Returns ([(x, y), ...],
    total height). An item wider than the whole row still gets a row of its
    own rather than being dropped. Pure arithmetic, so the rule every wrapping
    toolbar in the suite follows can be tested without a display.
    """
    width = max(1, int(width))
    positions = []
    x = y = row_height = 0
    for item_width, item_height in sizes:
        if x and x + item_width > width:
            x, y, row_height = 0, y + row_height + gap_y, 0
        positions.append((x, y))
        x += item_width + gap_x
        row_height = max(row_height, item_height)
    return positions, (y + row_height if positions else 0)
