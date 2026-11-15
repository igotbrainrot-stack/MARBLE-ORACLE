# Actual Oggcultist texture integration

This release **removes the earlier custom `warm_grain` noise-and-wave approximation**.
Marble Oracle now uses PNGs exported **directly from the bundled Oggcultist 2.0.6**
`oggcultist/gui/textures.py` `grain()` function. The source uses half-strength film
noise and a low-frequency mottling mask in dark colours.

## Source and files

- Authoritative algorithm: `Application/Runtime/Marble_Oracle_App/Oggcultist/oggcultist/gui/textures.py`
- Exported PNGs: `Application/Runtime/Marble_Oracle_App/data/oggcultist_texture/*.png`
- Exact palette: `Application/Runtime/Marble_Oracle_App/oggcultist_design_system.py`
- Source/PNG checksums: `data/oggcultist_texture/SOURCE_MANIFEST.json`
- Regenerator: `Application/Tools/export_actual_oggcultist_textures.py`
- Runtime image bridge: `Application/Runtime/Marble_Oracle_App/oracle_ogg_texture.py`

The production app uses these **unchanged 256×256** tiles; it does not regenerate
or recreate a noise algorithm, and **Pillow is not needed to draw Oracle's
texture backgrounds**. Ttk image elements use the same tiling mechanism as
Oggcultist. Canvas panels tile via Tk PhotoImage `copy` (not image stretching).

## Where the textures are used

- **HOME**: underlying page, PLATE VAULT, DEAD TONGUE, THE WIRE, THE TICKER,
  THREE CUTS, and inset card/well surfaces.
- **PASSPHRASE**: page, raised workspace, all five word/number/symbol cards,
  frame and label backgrounds.
- **TOUCH TYPE**: sidebar, practice workspace, stats, prompt surrounds,
  frame and label backgrounds.
- **OGGCULTIST**: its original embedded theme code remains authoritative and
  unchanged.

Input fields use their dark inset background; exactly as in Oggcultist, the
text-entry surfaces are not overwritten by a grain image and remain legible.
All artwork and text appear **above**, not beneath, these textures.

## Important theme-switch repair

Opening Oggcultist applies the `clam` theme to the shared Tcl interpreter.
On returning to the other tabs, the same Oggcultist PNG image elements are
registered in the active theme. Cached Touch Type sessions retain their state.

## Verification

Run from the `Application` directory:

`xvfb-run -a python3 Tests/test_source_ogg_texture.py`

It compares exported PNG pixels against fresh results from the original
Oggcultist source, checks no stretching at tile boundaries and checks that
image-based styles survive tab switches.
