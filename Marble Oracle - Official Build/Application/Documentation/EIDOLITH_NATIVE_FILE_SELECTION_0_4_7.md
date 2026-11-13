# EIDOLITH 0.4.7 — local file selection audit and repair

Reviewed 11 November 2026 against the previous dashboard-simplified 0.4.7 build.

- EIDOLITH OPEN FILES now uses the local OS file-selection UI. Linux: Zenity/YAD GTK, then KDialog (where installed), otherwise Tk fallback. Windows: Tk OS-common Explorer-style open-file dialog.
- EIDOLITH ADD FOLDER / CHOOSE OUTPUT FOLDER now use the same shared Oggcultist native directory selector. Linux: GTK chooser (Zenity/YAD), then KDialog, then Tk fallback. Windows: Explorer-style IFileOpenDialog, with Tk fallback.
- Opening the logs folder and other filesystem paths already used `os.startfile` on Windows and `xdg-open` on Linux (system default handler). Preserved.
- These are **native dialogs**, not the full Thunar application. Thunar is used for opening folders only when configured as the Linux default file manager. The application does not override the user's desktop choice.
- No web browser, cloud upload, or external file browser is involved.
- Test results: five unit tests passed for Linux GTK, cancel, Windows routing, fallback and EIDOLITH entry points. Actual Windows and Mint desktop tests are not available here.
- News and markets removal from the previous 0.4.7 update remains intact.
