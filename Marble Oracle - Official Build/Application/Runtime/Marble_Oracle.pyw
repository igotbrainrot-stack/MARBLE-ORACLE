"""Double-click entry point for the organized MARBLE_ORACLE distribution.

Keep Marble_Oracle_App beside this file. This wrapper invokes the same in-app
bootstrap as the original GUI launcher, without duplicating dependency logic.
"""
from pathlib import Path
import os
import sys

APP_DIR = Path(__file__).resolve().parent / "Marble_Oracle_App"
if not (APP_DIR / "oracle_bootstrap.py").is_file():
    try:
        from tkinter import messagebox
        messagebox.showerror("MARBLE_ORACLE", "Application folder is missing.\nExtract the entire ZIP before launching.")
    except Exception:
        sys.stderr.write("MARBLE_ORACLE: missing Marble_Oracle_App\n")
    raise SystemExit(2)

# Ensure old code that uses relative files behaves just as with the inner launcher.
os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))
from oracle_bootstrap import launch
try:
    raise SystemExit(launch(['--no-bezel', '--os-frame', *sys.argv[1:]], gui=True))
except Exception as exc:
    from oracle_bootstrap import report_gui_error
    report_gui_error(exc)
    raise SystemExit(1)
