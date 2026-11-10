# Integrating Oggcultist v2.0.6 into a larger desktop suite

**Supported now:** launch Oggcultist from the suite as a separate, complete window.
The full UI, player, converter, user settings and approved branding remain intact.
The integration adapter is `oggcultist.suite_bridge` and this folder's manifest
contains relative icon paths and metadata for a suite home screen.

**Example:** given the whole `Oggcultist-2.0.6` folder extracted and dependencies
installed by the usual launcher, add its inner `Oggcultist` folder to `sys.path`:

```python
import sys
from pathlib import Path
source_root = Path('/absolute/path/Oggcultist-2.0.6/Oggcultist')
sys.path.insert(0, str(source_root))
from oggcultist.suite_bridge import launch
process = launch(root=source_root)  # returns subprocess.Popen; does not block the suite UI
```

Call from a suite button callback, not a Tk worker thread. The full source tree
must stay together; keep its `.venv` installed by the provided Windows/Linux
launcher or provide an explicit `python_executable` / `OGGCULTIST_PYTHON`.
Never pass the suite's frozen `.exe` as a Python interpreter.

**First-run setup:** launch `WINDOWS LAUNCHER.bat` or `LINUX LAUNCHER.sh` once
before hosting. Python 3.10+, Tk and required Python packages, plus FFmpeg/FFplay,
are expected to be available. In a suite, don't silently download dependencies.

**Brand on suite home:** use the supplied PNG/SVG asset files from the manifest,
not a fallback emoji, retyped wordmark, or legacy brand. All regular interface
text uses the included Uberata Clear. The approved wordmark is raster/vector art.

**Not provided:** a true in-window embedded tab. `gui.app.OggcultistApp` is
currently a `tk.Tk` root, sets Tk-wide styles and owns window lifecycle, global
media controls and playback state. Refactoring to `ttk.Frame` for an existing Tk
host, or to a Qt/web view, needs a separate explicit design and integration
review. Do NOT simply call `mainloop()` from inside the suite or pack the `Tk`
root into a frame.

**Isolation:** `oggcultist/paths.py` defines all user settings, playlists, logs,
tools and portable-data behavior. Never point it to the host suite's storage
without a migration plan; never overwrite source audio. When launching more
than one instance, prevent accidental concurrent writes to the same playlists.

See `CLAUDE_SUITE_HANDOVER_v2.0.6.md` in the complete handover ZIP for tests,
file inventory and the next AI's acceptance checklist.
