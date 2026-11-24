"""OVERCAST — local, pessimism-first news forecasting for Marble Oracle.

"Mostly cloudy, with a chance of being right." Formerly SIGNAL / News Oracle; `import news_oracle`
still works through a compatibility alias.

Public integration API: create_panel(), NewsOracleEngine (alias OvercastEngine),
EVENT_SCHEMA_VERSION. No Marble Oracle internals are imported by this package.
"""
APP_NAME = 'OVERCAST'
TAGLINE = "Mostly cloudy, with a chance of being right."
__version__ = '1.1.2'
EVENT_SCHEMA_VERSION = 1


def create_panel(parent, *, state_dir=None, on_event=None, appearance=None, accent=None):
    """Mount the application in an existing tkinter parent widget.

    Returns a NewsOraclePanel (tk.Frame). The host owns its layout.
    Optional on_event(dict) receives versioned activity events.
    Optional appearance ('dark'/'light') and accent (1.1.2): the host's look, used instead of OVERCAST's own
    saved setting (which is left untouched); Settings › Appearance then says the host decides.
    """
    from .ui import NewsOraclePanel
    return NewsOraclePanel(parent, state_dir=state_dir, on_event=on_event, appearance=appearance, accent=accent)


def __getattr__(name):
    if name in ('NewsOracleEngine', 'OvercastEngine'):
        from .engine import NewsOracleEngine
        return NewsOracleEngine
    if name == 'OperationCancelled':
        from .engine import OperationCancelled
        return OperationCancelled
    raise AttributeError(name)
