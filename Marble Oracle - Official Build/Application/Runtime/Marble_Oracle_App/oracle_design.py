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
