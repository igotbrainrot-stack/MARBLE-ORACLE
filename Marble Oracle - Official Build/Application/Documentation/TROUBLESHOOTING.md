# Troubleshooting

## It does not start

| Symptom | Cause and fix |
|---|---|
| Windows: nothing happens, or "Windows Script Host is disabled" | VBScript is blocked. Use `START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat`. |
| Windows: "Python was not found" | Install Python 3 from python.org (tick "tcl/tk and IDLE") and start again. |
| Linux: a message that Tk is missing | `sudo apt install python3-tk`, then start again. |
| Linux: the launcher opens in a text editor | `chmod +x "START MARBLE ORACLE - LINUX.sh"`, or install the menu entry with `bash Application/Runtime/install_linux_desktop.sh`. |
| The requirements window reports a failed install | It shows the path of its log. Python libraries go into a private environment under `MarbleOracleSuite` in your user-data folder; deleting only that `venv` folder makes the next start rebuild it. |

To see errors directly: `python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --no-network` from the extracted folder. Unhandled errors are also written to `error.log`, `callback_error.log` or `startup_error.log` in the state folder (`~/.local/state/Marble_Oracle` or `%LOCALAPPDATA%\Marble_Oracle`).

## HOME

| Symptom | Cause and fix |
|---|---|
| Statues, tarot or runes are blank | The artwork archives under `Application/Runtime/Marble_Oracle_App/data/` are missing. They are in the release ZIP but not in the Git repository; extract the whole ZIP. |
| The AUGURSPEX panel says NETWORK DISABLED | The suite was started with `--no-network`. |

## EIDOLITH

| Symptom | Cause and fix |
|---|---|
| "FFmpeg not found" | Install FFmpeg (Linux: `sudo apt install ffmpeg`; Windows: any build with `ffmpeg.exe`, `ffprobe.exe` and `ffplay.exe` on `PATH`) and restart. |
| A job says FAILED | Select it and press **OPEN LOG** for FFmpeg's own output. The queue has already moved on to the next job; **RETRY SELECTED** runs it again. |
| A job is refused before it starts | The reason is on the job line: HDR source, a track that cannot go in the chosen container, or under 200 MB free in the output folder. The original is untouched. |
| Conversion is slow | Use **Fast AV1** or **Turbo AV1**, lower **RESOLUTION**, or **USE FAST PROFILE** to try a hardware encoder. |
| No sound in the viewer | The viewer needs FFplay for audio. It is a 12 fps preview; use your normal player to judge a finished file. |
| Asking for help | **COPY DIAGNOSTICS** copies a report with your folder names removed. |

## AUGURSPEX

Press **SOURCE DETAILS**: it lists each source tried for the selected chart, what it answered and when the app will ask again. The status words are explained in `MARKET_DATA.md`.

| Symptom | Cause and fix |
|---|---|
| A stock shows DATA SOURCE LIMITED | The free sources throttled the request. It is retried after the cool-down shown. For dependable stock history add a key (MANAGE LIST → CONNECT API KEY) or import a CSV. |
| An Australian, Japanese or Korean listing shows DATA SOURCE SETUP NEEDED | There is no free source for those exchanges; they need a key with the right entitlement. |
| CHARTS 9 shows a market I did not pick, marked AUTO-FILLED | The saved market for that slot has no data right now, so the slot shows another watchlist market that has. Your saved choice returns when its data does. |

## PASSPHRASE and TOUCH TYPE

| Symptom | Cause and fix |
|---|---|
| The copied passphrase vanished from the clipboard | It is cleared after 60 seconds on purpose. Clipboard-history tools may still hold it; clear their history if that matters. |
| Typing does nothing in TOUCH TYPE | Click the typing field (or press **START GAME**) so it has keyboard focus. |

## Starting clean without losing data

Rename (do not delete) the state folder listed in the README and start again; the suite creates a fresh one. Move the old folder back to restore everything.
