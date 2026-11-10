Home Background Darker
======================

This build darkens the HOME canvas background to match the darker embedded
sections more closely.

Change
- Replaced the HOME full-canvas Oggcultist texture tile from the lighter
  `page` surface to the darker `side` surface.

Result
- The background between HOME panels now appears as dark as the other tabs.
- Existing panel textures, Rune features, Passphrase, Oggcultist, and Touch
  Type remain unchanged.

Verification
- marble_oracle.py --selftest passed under xvfb.
