"""GUI launcher using the shared bootstrap and optional audio setup."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oracle_bootstrap import launch
sys.exit(launch(gui=True))
