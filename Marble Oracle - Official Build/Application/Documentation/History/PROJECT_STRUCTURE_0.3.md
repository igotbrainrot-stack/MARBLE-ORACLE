# MARBLE ORACLE — Project structure and dependency map

**Maintenance release:** 10 November 2026, based on complete EIDOLITH 0.3 distribution. This is a source/build guide, not a proposal to rewrite modules.

## Archive layout

```text
Marble Oracle - Official Build/
├── START MARBLE ORACLE - WINDOWS.vbs    # graphical WScript entry, no CMD
├── START MARBLE ORACLE - LINUX.sh     # Tk precheck, then graphical requirements manager
└── Application/
    ├── README.md                     # current single starting point
    ├── .gitignore                    # generated caches / environment exclusions
    ├── Runtime/
    │   ├── launch_suite.pyw          # first-run requirements, FFmpeg and GUI process checks
    │   ├── Marble_Oracle.pyw         # legacy/direct wrapper; preserved
    │   ├── install_linux_desktop.sh  # menu shortcut: Terminal=false
    │   ├── [other historical launchers, retained]
    │   └── Marble_Oracle_App/
    │       ├── marble_oracle.py      # Scene, five-tab coordination, window/input/render loop
    │       ├── oracle_chrome.py      # primary tab rendering and CRT navigation
    │       ├── oracle_eidolith.py    # video player, probe, CPU/NVENC profiles, queue, naming
    │       ├── oracle_ogg_tab.py     # Oggcultist embedded adapter
    │       ├── oracle_touch_type.py  # four teaching games and key/finger guide
    │       ├── marble_passphrase_tab.py / oracle_dicekey.py
    │       ├── oracle_runes.py, oracle_media.py, oracle_ascii_bitmap.py
    │       ├── oracle_skin.py, oracle_ogg_texture.py, oggcultist_design_system.py
    │       ├── oracle_assets.py     # resources and OS user-state paths
    │       ├── marble_uberata.py    # custom font registration
    │       ├── Oggcultist/          # original 2.0.6 app, standalone assets and tests
    │       ├── fonts/               # Uberata Clear + source notices
    │       └── data/                # protected animation/media archives and textures
    ├── Tests/                        # automated functional checks and reference screenshots
    ├── Tools/                        # asset regeneration, texture export, release verification
    └── Documentation/
        ├── DOCUMENTATION_INDEX.md   # current vs historical docs
        ├── BUILD_MANIFEST.json      # regenerated release metadata
        ├── FILE_INVENTORY.json      # source SHA-256 inventory
        ├── AUDIT_REPORT.md
        ├── VERIFICATION_REPORT.md
        ├── PROJECT_STRUCTURE.md
        ├── [current subsystem notes]
        ├── Reference/              # unchanged EIDOLITH design brief
        └── History/                # all previous handovers, changelogs and old manifests
```

## Startup and state

- **Recommended Windows route:** `START MARBLE ORACLE - WINDOWS.vbs` → `Application/Runtime/launch_suite.pyw` (via `pyw`/`pythonw`) → environment checks/optional setup → main program.
- **Recommended Linux Mint route:** `START MARBLE ORACLE - LINUX.sh` (or menu shortcut installed by `Application/Runtime/install_linux_desktop.sh`) → `launch_suite.pyw` → main program.
- Both official paths request consent for missing dependencies; the source's alternate legacy launchers are retained because older workflows and standalone launches may still depend on them. Direct wrappers should **not** be mistaken for the official requirements-checking entry points.
- `oracle_assets.py::state_dir()` writes preferences outside the installation folder: Linux `~/.local/state/Marble_Oracle`, Windows `%LOCALAPPDATA%/Marble_Oracle`, unless overridden with `MARBLE_ORACLE_STATE`. The requirements manager uses per-install private state under `MarbleOracleSuite` in OS user-data location. Do not delete these paths during upgrades.

## Modules and runtime relationships

| Part | Entry / implementation | Dependencies and boundaries |
|---|---|---|
| Suite home and navigation | `marble_oracle.py` + `oracle_chrome.py` | Native Tk/Canvas; switches overlay windows without rebuilding base HOME |
| Visual identity | `oracle_skin.py`, `oracle_ogg_texture.py`, `oggcultist_design_system.py` | Fixed source-generated Oggcultist grain PNGs; keep resource paths stable |
| Oggcultist | `oracle_ogg_tab.py` and `Oggcultist/oggcultist` | Original 2.0.6 app embedded; independent standalone resources; Pillow/Mutagen and optional FFmpeg |
| EIDOLITH | `oracle_eidolith.py` | FFmpeg/FFprobe for conversion and probing, optional video/audio playback helpers; queue status and TV/movie naming |
| Passphrase | `marble_passphrase_tab.py`, `oracle_dicekey.py` | Local word lists and five-card widget |
| Touch Type | `oracle_touch_type.py` | Tk, standard library, score state file |
| Tarot, Rune and ASCII | `oracle_media.py`, `oracle_runes.py`, `oracle_ascii_bitmap.py` | Large ZIP archives with exact expected names under `data/`; all retained |
| CRT, photos, audio | `oracle_chrome.py`, `oracle_photo_bezel.py`, `oracle_audio.py` and related files | Artwork/audio archives, fonts, optional media integrations |

## Protected asset archives and why they are retained

- `rune_consistent_flips.zip` is the active enlarged Rune frame source. `rune_native_frames.zip`, `rune_flip_strips.zip` and `runes.zip` support old/or alternative animation/reader paths and tests; no one-to-one removal proof is established.
- `tarot_cards.zip`, `marble_archive.zip`, `latin_voices.zip`, `photo_bezel_locked.zip`, `bezel.zip` are referenced by source modules, fallback logic or asset recovery checks. **None were repacked, resized or removed.**
- `Uberata-Clear.ttf` is duplicated intentionally under Marble Oracle's and Oggcultist's resource roots; keep both until standalone and integrated font loading can be proven after a shared-font migration.
- Oggcultist's branding directories contain byte-identical logos for approved and original identity histories. They are preserved rather than deduplicated because asset paths and provenance matter.

## Testing and maintenance

From the extracted release root, run `python3 Application/Tools/verify_release.py` (stdlib-only integrity check). For GUI checks use `Application/Tests/README.md` and commands recorded in `VERIFICATION_REPORT.md`. `Application/.gitignore` excludes generated caches and virtual environments; do not commit user state or media.

Platform notes: media and launcher capabilities vary by installed tools and drivers. This cleanup performed no platform migration, runtime restructuring or changes to the visual design.
