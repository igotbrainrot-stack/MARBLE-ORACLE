"""Oggcultist approved triple-G emblem and matching original wordmark artwork.

Both images are exact assets from the user's approved branding screenshot.
Application UI text continues using the bundled Uberata Clear font.
"""
from __future__ import annotations

import tkinter as tk

from .. import paths

SYMBOL = 'brand_symbol.png'
WORDMARK = 'brand_wordmark.png'
ICON_SIZES = (16, 32, 48)


def _scale(root: tk.Misc) -> float:
    try:
        return max(1.0, root.winfo_fpixels('1i') / 96.0)
    except tk.TclError:
        return 1.0


def compose_lockup(symbol_height: int, wordmark_height: int, gap: int):
    """Compose the user-approved image assets, maintaining their original proportions."""
    from PIL import Image
    symbol = Image.open(paths.resource_path(SYMBOL)).convert('RGBA')
    wordmark = Image.open(paths.resource_path(WORDMARK)).convert('RGBA')
    symbol_width = max(1, round(symbol.width * symbol_height / symbol.height))
    word_width = max(1, round(wordmark.width * wordmark_height / wordmark.height))
    symbol = symbol.resize((symbol_width, symbol_height), Image.Resampling.LANCZOS)
    wordmark = wordmark.resize((word_width, wordmark_height), Image.Resampling.LANCZOS)
    h = max(symbol.height, wordmark.height)
    out = Image.new('RGBA', (symbol.width + gap + wordmark.width, h), (0, 0, 0, 0))
    out.alpha_composite(symbol, (0, (h - symbol.height) // 2))
    out.alpha_composite(wordmark, (symbol.width + gap, (h - wordmark.height) // 2))
    return out


def sidebar_lockup(root: tk.Misc, max_width: int):
    """Keep the complete logo visible inside the navigation sidebar."""
    try:
        from PIL import Image, ImageTk
        scale = _scale(root)
        image = compose_lockup(round(36 * scale), round(21 * scale), round(8 * scale))
        if image.width > max_width:
            factor = max_width / image.width
            image = image.resize((max_width, max(1, round(image.height * factor))), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image, master=root)
    except Exception:  # branding failure should not prevent use of the player
        return None


def window_icons(root: tk.Misc) -> list:
    """Return the multi-size window icon images, including the new triple-G emblem."""
    icons = []
    for name in ('icon.png', *(f'icon-{n}.png' for n in ICON_SIZES)):
        path = paths.resource_path(name)
        if path.is_file():
            try:
                icons.append(tk.PhotoImage(file=str(path), master=root))
            except tk.TclError:
                pass
    return icons


def sidebar_symbol(root: tk.Misc, height: int):
    """Approved emblem by itself for the compact navigation rail."""
    try:
        from PIL import Image, ImageTk
        height = round(height * _scale(root))
        symbol = Image.open(paths.resource_path(SYMBOL)).convert('RGBA')
        width = max(1, round(symbol.width * height / symbol.height))
        return ImageTk.PhotoImage(symbol.resize((width, height), Image.Resampling.LANCZOS), master=root)
    except Exception:
        return None
