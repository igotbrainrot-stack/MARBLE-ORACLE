"""Compatibility alias: ``oggcultist.core`` is ``oggcultist.converter.core``.

Kept so existing imports, scripts and tests continue to work after the v1.7
package reorganisation. The alias *is* the same module object, so attribute
changes (including test monkeypatching) affect the real implementation.
"""
import sys as _sys
from .converter import core as _impl

_sys.modules[__name__] = _impl
