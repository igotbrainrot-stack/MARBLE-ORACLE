"""``python -m overcast`` opens the desktop app (``python -m overcast cli --help`` for headless tools)."""
from .app import main

raise SystemExit(main())
