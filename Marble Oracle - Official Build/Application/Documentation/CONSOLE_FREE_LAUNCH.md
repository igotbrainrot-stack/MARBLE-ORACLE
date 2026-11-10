# Console-free launch — Marble Oracle Official Build

**Windows 11:** Double-click `START MARBLE ORACLE - WINDOWS.vbs` in the main folder.
This starts the graphical requirements manager using `pyw.exe` (or `pythonw.exe`)
with Windows Script Host, hidden subprocess startup flags, and logging to the
user-profile MarbleOracleSuite directory. The GUI is visible; Command Prompt
and PowerShell are not used for normal startup. If Python is not installed,
the launcher displays a message box.

**Linux Mint:** Run `Application/Runtime/install_linux_desktop.sh` once to install
`Marble Oracle` in the Mint application menu; then launch from that menu.
The shortcut is generated with `Terminal=false` and runs the *official* top-level
Linux launcher (which checks requirements before opening the application).
You can also run `START MARBLE ORACLE - LINUX.sh` from a file manager, but some
file managers choose to open an interactive terminal for arbitrary `.sh` files;
the Mint application-menu shortcut avoids that.

**Important:** Never launch one of the old `.bat` diagnostics or Python files
inside `Application/Runtime` for normal use. They are kept for development and
may open a console. Always use the official launchers.

**Testing:** Linux GUI startup and launch-script checks can run in this environment.
Actual Windows 11 window visibility must be verified on Windows; static and
process-configuration tests alone cannot guarantee it on all systems.
