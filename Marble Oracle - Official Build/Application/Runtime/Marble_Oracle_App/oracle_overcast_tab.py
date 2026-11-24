"""OVERCAST as a Marble Oracle workspace (0.5.0).

OVERCAST is the suite's local, pessimism-first news forecasting desk ("Mostly cloudy, with a chance of being
right."). The package in ./overcast is self-contained: it never imports suite modules, so it also runs on its own
(`python -m overcast`). This module only mounts its panel on the suite canvas, like the other Tk workspaces:

* one panel per session, built on first open and kept while other tabs are shown, so a running forecast or a
  feed refresh carries on in the background (its worker threads never touch Tk; the panel polls a queue);
* the forecast ledger lives in the suite's state folder, in `news_oracle/` (the same folder a standalone
  OVERCAST install uses, so both see the same forecasts);
* the panel never binds the suite's keys; Escape returns HOME as in every workspace.
"""
from __future__ import annotations

from pathlib import Path

from oracle_assets import state_dir

# Short status-line messages for OVERCAST's versioned activity events (EVENT_SCHEMA_VERSION 1).
EVENT_MESSAGES = {
    'news_refreshed': 'OVERCAST · HEADLINES REFRESHED',
    'model_connected': 'OVERCAST · MODEL CONNECTED',
    'forecast_created': 'OVERCAST · FORECAST SAVED TO THE LEDGER',
    'forecast_resolved': 'OVERCAST · FORECAST RESOLVED',
    'briefing_created': 'OVERCAST · BRIEFING SAVED',
    'outlook_created': 'OVERCAST · BROAD OUTLOOK SAVED',
    'outlook_resolved': 'OVERCAST · OUTLOOK RESOLVED',
    'claims_extracted': 'OVERCAST · CLAIMS EXTRACTED',
}


def overcast_state_dir():
    return Path(state_dir()) / 'news_oracle'


class EmbeddedOvercast:
    """layout(box) / clear() / shutdown() / key(), like the suite's other Tk workspaces."""

    TAG = 'ovcwin'

    def __init__(self, canvas, on_home=None, on_status=None):
        from overcast import create_panel
        import oracle_appearance
        self.canvas = canvas
        self.on_home = on_home
        self.on_status = on_status
        # 0.5.1: in Dark and Light OVERCAST follows the suite's appearance and accent (its own saved choice is
        # kept for when it runs on its own). In Classic it keeps its own.
        look = oracle_appearance.appearance() if oracle_appearance.modern() else None
        self.frame = create_panel(canvas, state_dir=str(overcast_state_dir()), on_event=self._event,
                                  appearance=look, accent=oracle_appearance.accent() if look else None,
                                  font=oracle_appearance.family() if look else None)
        self.frame._marble_no_round = True     # OVERCAST draws its own rounded artwork (oracle_round)
        self.window = canvas.create_window(0, 0, anchor='nw', window=self.frame, tags=(self.TAG,))
        self._box = None

    def _event(self, event):
        message = EVENT_MESSAGES.get(event.get('event')) if isinstance(event, dict) else None
        if message and self.on_status is not None:
            try:
                self.on_status(message)
            except Exception:
                pass

    def layout(self, box):
        self._box = box
        x0, y0, x1, y1 = box
        if not self.canvas.type(self.window):
            self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.frame, tags=(self.TAG,))
        self.canvas.coords(self.window, x0, y0)
        self.canvas.itemconfigure(self.window, width=max(100, int(x1 - x0)), height=max(100, int(y1 - y0)),
                                  state='normal')
        self.canvas.tag_raise(self.window)

    def clear(self):
        # Hidden, not destroyed: a forecast in progress keeps running and lands in the ledger.
        if self.canvas.type(self.window):
            self.canvas.itemconfigure(self.window, state='hidden')

    @property
    def busy(self):
        return bool(getattr(self.frame, '_running', False))

    def shutdown(self):
        """Stop cleanly at exit: cancel a model call between steps (nothing incomplete is saved), close the ledger."""
        try:
            if self.busy:
                self.frame.cancel_job()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass
        return True

    def key(self, keysym, char=''):
        if keysym.lower() in ('escape', 'esc'):
            return 'close'
        return None


def available():
    """True when the bundled package imports (it needs only the standard library and Tk)."""
    try:
        import overcast  # noqa: F401
        return True
    except Exception:
        return False
