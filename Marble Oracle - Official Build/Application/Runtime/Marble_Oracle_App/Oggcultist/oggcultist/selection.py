"""Compatibility alias: ``oggcultist.selection`` is ``oggcultist.gui.selection``.

Kept so existing imports, scripts and tests continue to work after the v1.7
package reorganisation. The alias *is* the same module object, so attribute
changes (including test monkeypatching) affect the real implementation.
"""
import sys as _sys
from .gui import selection as _impl

_sys.modules[__name__] = _impl
