# OGGCULTIST — Approved O/G/G Logo (9 November 2026)

This set replaces the previous Stone Knot brand in Oggcultist v2.0.5.
It was traced from the **user-approved uploaded screenshot** `ORIGINAL-USER-APPROVED-REFERENCE.png`.

## Approved composition
- Left: triple-G interwoven emblem inside an angular O-shaped border, with no spikes.
- Right: the approved geometric OGGCULTIST wordmark (image/vector outlines, not retyped).
- Do not add sound, speaker, waveform, radio, CD, or record symbolism.
- Preserve the even white/transparent margins and octagonal geometry.
- UI labels, controls, tables and all ordinary application text still use **Uberata Clear v3.0 exclusively**. The approved wordmark is artwork, not a second application font.

## Assets
- `symbol.svg` — scalable isolated mark, black
- `wordmark-outlined.svg` — scalable standalone approved wordmark, black
- `horizontal-lockup.svg` — mark + wordmark together, black
- `*-black-transparent.png` — black foreground, transparent background
- `*-cream-transparent.png` — light foreground for the app's dark theme
- `Oggcultist.ico` — Windows multiresolution icon (16, 24, 32, 48, 64, 128, 256)
- `icon-{16,24,32,48,64,128,256,512,1024}.png` — native desktop icons (dark background)
- `favicon-{16,32,64}.png` — transparent web/sample icons

## Drop-in program paths
For a v2.0.5 source installation, copy the complete `oggcultist/resources` contents from the patched program; see the accompanying updated program ZIP. The important files are:
`oggcultist/resources/brand_symbol.png`, `brand_wordmark.png`, `icon.png`, `icon-16.png`, `icon-32.png`, `icon-48.png`, and `icon.ico`.
The revised `oggcultist/gui/brand.py` must also be used because earlier releases redrew the wordmark using Uberata instead of showing this approved original art.
Linux Mint's menu launcher uses `oggcultist/resources/icon.png`; PyInstaller builds use `icon.ico`.
The source SVGs live under `branding/original-identity/`. Never rerun an older brand generator that recreates the former logo.

The SVGs are contour-traced from the approved raster, not supplied original design vectors. Check small rasterizations before producing the final standalone executable; Windows .exe compilation itself is not included.
