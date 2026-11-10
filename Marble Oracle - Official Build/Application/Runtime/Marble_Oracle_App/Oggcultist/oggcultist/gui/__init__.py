"""Tkinter desktop UI; supports Linux Pillow installations without ImageTk."""

from ..pillow_tk_compat import ensure_image_tk

ensure_image_tk()
