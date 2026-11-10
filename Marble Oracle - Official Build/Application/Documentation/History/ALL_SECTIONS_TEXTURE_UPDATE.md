All Sections Texture Update
===========================

This build extends the Oggcultist-style dark film grain and faint mottled stain
texture across Marble Oracle's section backgrounds.

Changes
- Updated the shared warm_grain() texture to include a subtle mottled stain field.
- Applied the texture to all panel sections, not just selected clean-mode surfaces.
- Applied the same texture treatment to inset tiles such as ticker rows.

Result
- HOME, PASSPHRASE, TOUCH TYPE, and other Oracle sections now better match the
  dark Oggcultist panel background character.
- Text and artwork remain above the texture and are not washed out.

Verification
- marble_oracle.py --selftest passed under xvfb.
