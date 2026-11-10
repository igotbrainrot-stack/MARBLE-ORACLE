"""Audio tag reading and the Track model used by the converter.

Implementation lives in :mod:`oggcultist.metadata.tags`; the public names are
re-exported here so ``from oggcultist.metadata import Track`` keeps working.
"""
from .tags import *  # noqa: F401,F403
from .tags import Track, year_of, EXTENSIONS  # noqa: F401  (explicit for readers and linters)
