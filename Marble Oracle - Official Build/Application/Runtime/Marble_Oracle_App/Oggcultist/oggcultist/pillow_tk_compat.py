"""Tk PhotoImage adapter for distributions with Pillow but without PIL.ImageTk.

Some Linux distributions split ``python3-pil`` and ``python3-pil.imagetk``.
Oggcultist uses Pillow for processing but should not require the second
package merely to display artwork and theme textures. Tk 8.6 loads PNGs
natively; this module bridges in-memory PIL images to standard Tk PhotoImage.

When the full ImageTk + compiled backend are available, we leave them alone.
The adapter is installed only if ImageTk or its extension is unavailable.
"""
from __future__ import annotations

import base64
import importlib
import io
import os
import sys
import tkinter as tk
import types


def _png_data(image) -> bytes:
    if not hasattr(image, 'save'):
        raise TypeError('Expected a Pillow image, got ' + type(image).__name__)
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return base64.b64encode(stream.getvalue())


class PortablePhotoImage(tk.PhotoImage):
    """ImageTk.PhotoImage-compatible Tk image backed by PNG, not _imagingtk.

    Supports PhotoImage(image, master=...) and .paste(image). Retaining the
    image object keeps its Tcl image alive, just like PIL.ImageTk.PhotoImage.
    """

    def __init__(self, image=None, size=None, master=None, **kw):
        if image is None:
            dimensions = size or kw.pop('size', None)
            if dimensions is not None:
                kw.setdefault('width', dimensions[0])
                kw.setdefault('height', dimensions[1])
            super().__init__(master=master, **kw)
        else:
            super().__init__(master=master, data=_png_data(image), format='png', **kw)

    def paste(self, image, box=None):
        if box is not None:
            raise NotImplementedError('Partial image paste is not needed by Oggcultist')
        # Image data is decoded by Tk 8.6, so no Pillow/Tk native extension is needed.
        self.tk.call(str(self), 'configure', '-data', _png_data(image), '-format', 'png')


def ensure_image_tk() -> bool:
    """Return True if the PNG adapter was activated, False for native ImageTk.

    Import Pillow normally when possible, but do not depend on _imagingtk on
    Linux Mint where the system package may omit it. The optional environment
    variable exists only to exercise the fallback in regression tests.
    """
    from PIL import Image  # Pillow image manipulation is still required.
    force = os.environ.get('MARBLE_TEST_NO_IMAGETK') == '1'
    if not force:
        try:
            importlib.import_module('PIL.ImageTk')
            importlib.import_module('PIL._imagingtk')
            return False
        except ImportError:
            pass
    shim = types.ModuleType('PIL.ImageTk')
    shim.__doc__ = 'Marble Oracle portable PIL.ImageTk adapter using Tk PNG support.'
    shim.PhotoImage = PortablePhotoImage
    # image-code imports use ``from PIL import ImageTk``. Set both, even on
    # Python distributions whose PIL module previously cached a failed import.
    sys.modules['PIL.ImageTk'] = shim
    import PIL
    PIL.ImageTk = shim
    return True
