# Marble Oracle — Official Ember Styling + Startup Repair

## Visual / styling changes
- Refined HOME dashboard to match embedded Oggcultist 2.0.6, using the same warm charcoal, sunken reading fields, black navigation bar, copper controls and orange active states.
- Added subtle deterministic film-grain texture to panels **under text and images**; unlike the CRT overlay, it never fades the artwork or typography.
- Changed nonsemantic bright quote colours to Oggcultist ivory/tan/amber while retaining the live-market green/red indicators and original scene artwork.
- Matched the Passphrase five-card screen's inset surfaces and secondary actions to Oggcultist.
- Restyled first-run requirements installer in the same palette and retained the bundled Uberata Clear typeface.
- HOME, PASSPHRASE and OGGCULTIST tab navigation, position, panel geometry, and all functions remain in their original places.

## Setup and stability
- FFmpeg, FFprobe and FFplay are optional for **core Oracle** startup; installation requires user approval and failure is reported, not an application exit.
- First-run setup stays open after an attempted installation, shows the refreshed requirements status, and offers an explicit START MARBLE ORACLE action.
- Media-tool path-discovery failures no longer crash the graphical requirements manager.
- Missing essential Python dependencies still block startup with a visible explanation.
- A startup handshake verifies Oracle initialized rather than assuming spawning a process is success.
- Fixed a small-window Rune sizing edge case; Rune symbols and animation positions are preserved.

## Tests run in this build
- `marble_oracle.py --selftest`: passed on Linux Xvfb
- `test_tab_layout.py`: passed normal, retro, flat
- `test_refinement.py`: passed
- `test_ogg206_embedded.py`: passed all seven Oggcultist pages
- `test_media_setup.py`: passed simulated installation modes
- `test_launch_gate.py`: passed missing-media / missing-Python / cancelled installer / GUI handshake
- `test_rune_native_assets.py`: passed
- `test_rune_border_fit.py`: 456 placements passed
- Fresh ZIP extraction, asset listing and integrity verification: passed

## Outstanding platform checks
- Live Linux Mint pkexec authentication and FFmpeg download/installation were **not** exercised; the tests simulate permission and package-manager outcomes.
- Physical Linux Mint desktop and native Windows 11 startup/media playback require real-device testing.
- This is a Python/Tkinter distribution, not a compiled standalone Windows executable.
