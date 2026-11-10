# Marble Oracle — GRADE Footer Button Position

- Moved the GRADE button from the lower-left to the lower-right side of the global status/footer section.
- Its existing layout-cycling action (`view`) and hitbox behavior are unchanged.
- WIRE, TONGUE and CUT remain in the lower-left of their respective sections.
- HOME, PASSPHRASE and OGGCULTIST remain in the top-left tab area.
- All other source and bundled assets are retained from the preceding Rune Clip and Pre-Reveal Fix build.

## Verification
- `python3 -m py_compile marble_oracle.py oracle_runes.py` — passed.
- `xvfb-run -a python3 marble_oracle.py --selftest` — passed.
- `xvfb-run -a python3 test_tab_layout.py` — passed in normal, retro and flat modes, including an assertion that GRADE is on the right side of the footer and its hitbox resolves correctly.

Windows 11 and physical Linux Mint GUI testing have not been performed for this build.
