"""Compatibility alias: SIGNAL / News Oracle was renamed OVERCAST in 1.0.

`import news_oracle`, `from news_oracle.engine import NewsOracleEngine`,
`news_oracle.create_panel(...)` and every other submodule import keep working
and return the SAME module objects as `overcast.*` (so patches apply to both).
New code should import `overcast`.
"""
import importlib
import importlib.abc
import importlib.util
import sys

import overcast as _overcast
from overcast import __version__, EVENT_SCHEMA_VERSION, create_panel  # noqa: F401


class _AliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    prefix = __name__ + '.'

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(self.prefix):
            real = importlib.util.find_spec('overcast.' + fullname[len(self.prefix):])
            if real is None:
                return None
            return importlib.util.spec_from_loader(fullname, self, origin=real.origin)
        return None

    def create_module(self, spec):
        module = importlib.import_module('overcast.' + spec.name[len(self.prefix):])
        # The import system will stamp the alias spec onto the module; remember the
        # real identity so exec_module can restore it (keeps relative imports correct).
        self._identity = (module.__spec__, getattr(module, '__loader__', None))
        return module

    # Needed by `python -m news_oracle.cli`: runpy executes the real module's code
    # as __main__ (relative imports then resolve through this alias to overcast).
    def get_code(self, fullname):
        real = importlib.util.find_spec('overcast.' + fullname[len(self.prefix):])
        return real.loader.get_code(real.name)

    def is_package(self, fullname):
        return False

    def exec_module(self, module):
        spec, loader = self._identity
        module.__spec__ = spec
        if loader is not None:
            module.__loader__ = loader


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())


def __getattr__(name):
    return getattr(_overcast, name)
