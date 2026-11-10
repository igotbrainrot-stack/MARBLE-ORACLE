# MARBLE ORACLE — Senior engineering audit and conservative cleanup

**Audit date:** 10 November 2026  
**Authoritative source:** `Marble-Oracle-OFFICIAL-EIDOLITH-0.3-Faster-Conversion-Standard-Naming-FULL-Windows-Linux.zip`  
**Original SHA-256:** `df9f71512120d913f94b2e9736b5824cabc8e6f6ea07ac31928e40b355f9620a`  
**Scope:** all application modules, five tabs, runtime files, launchers, assets, dependencies, tests, documentation and release packaging.  
**Method:** inventory → baseline tests → static references + hash comparison → conservative changes → post-cleanup tests → regenerated manifests/ZIP.

## 1. Baseline and recovery checkpoint

- The original immutable ZIP is kept separately in the working environment; no cleanup was done in that copy. It can be used to recover original relative paths and release metadata.
- **Original extracted source:** **355 files**, **114,645,316 bytes** (sum of extracted regular files). Original ZIP size: **111,686,840 bytes**.
- A full per-file SHA-256 and size record was captured *before* modifications. The old manifest and inventory are also preserved exactly as `History/PRE_CLEANUP_BUILD_MANIFEST.json` and `History/PRE_CLEANUP_FILE_INVENTORY.json`.
- Baseline checks: **9/9 passed**. See `VERIFICATION_REPORT.md`.
- The source contained **22 groups of identical-file hashes** (including Oggcultist artwork, standalone resources, Uberata Clear license/font copies and two preview duplicates). Hash equality alone was *not* treated as proof that runtime paths were dispensable.

## 2. Confirmed findings and actions

| Finding | Classification | Evidence and action |
|---|---|---|
| `BUILD_MANIFEST.json` still claimed 4-tab Touch Type release | **SAFE TO CONSOLIDATE** | Clear release mismatch with five-tab EIDOLITH 0.3. Preserved prior manifest under `History/`; created correct final manifest. |
| Prior `FILE_INVENTORY.json` was generated for an earlier build | **SAFE TO CONSOLIDATE** | Replaced with final relative-path SHA-256 inventory; previous file preserved in History. Self-referential hashes explicitly excluded. |
| 40 historical guides and changelogs mixed with current documentation | **SAFE TO CONSOLIDATE** | Relocated unchanged into `Documentation/History/`. Added `Application/README.md`, `DOCUMENTATION_INDEX.md`, and History index to mark authoritative vs older instructions. No runtime source imports them. |
| Original EIDOLITH v0.1 design brief mixed with implementation notes | **SAFE TO CONSOLIDATE** | Relocated unchanged into `Documentation/Reference/`; preserved design intent separately from current v0.3 status. |
| Two duplicated Rune preview images in Documentation and Tools | **SAFE TO REMOVE** | Verified *identical bytes* with SHA-256, searched source/test/docs references. Removed Documentation duplicates only. Identical originals remain at `Tools/Rune-24-New-Stones.png` and `Tools/Rune-Flip-Preview.gif`. **No actual Rune assets or approvals were removed.** |
| Application-menu description omitted EIDOLITH, Touch Type, Passphrase | **SAFE TO CONSOLIDATE** | Updated only `Comment=` in `install_linux_desktop.sh`, leaving interpreter path, executable mode, `Terminal=false`, and all actions untouched. |
| Automatic Python cache files | **SAFE TO REMOVE** | Generated under tests; excluded from final packaging and future Git tracking. Original release had no compiler caches. |
| Duplicate Oggcultist branding / original-identity artwork | **PRESERVE** | Approved art and provenance; distinct resource roots may be used by standalone/UI code. No deletion. |
| Identical Uberata Clear fonts in Marble and Oggcultist | **PRESERVE** | Both standalone and integrated use expected relative paths. No license/font edits. |
| Duplicate `oggcultist_design_system.py` and internal theme source | **REQUIRES TESTING** | Separate import roots and standalone operation; aliasing or moving code could alter behaviour, so both remain. |
| Multiple Windows/Linux legacy entry scripts | **REQUIRES TESTING** | Official startup routes are known but older launchers may remain in use. Keep all to avoid breaking install or debug flows. |
| 64 MB Rune archive and other large ZIP assets | **PRESERVE** | Source paths and recovery logic reference them. No asset recompression/rebuild. |
| EIDOLITH queue state not persisted and preview engine limitations | **REQUIRES TESTING / FUTURE FEATURE** | Known v0.3 limitations, not introduced or altered by cleanup. Do not redesign during maintenance. |

## 3. Measured change and performance

- **Final extracted file count:** **363 files** (vs 355 original). New reporting, README, verification script, indices and preserved history may increase this count slightly; file count reduction was **not** a goal at the expense of traceability.
- **Final extracted bytes:** **114,457,749 bytes** (vs 114,645,316 original). The documentation-only duplicate previews remove **294,886 bytes** without changing the live artwork.
- **Final compressed ZIP size:** **approximately 106 MiB** (rounded; exact packaged ZIP size is in its file properties) (vs 111,686,840 bytes original). Size reduction may be small because video/Rune archives are already compressed.
- **Startup/runtime performance:** **no measured material improvement claimed.** The cleanup intentionally changes no core rendering, media, caching or scheduling algorithm. Small wall-clock differences between test runs are noise, not an optimisation result.
- **Runtime change set:** one nonfunctional Linux `.desktop` comment string. No Python application modules, Oggcultist app files, media assets, fonts or launch commands changed byte-for-byte.

## 4. Risk and recovery

- **Low risk:** documentation moves and standalone read-only verification script; verified by unchanged runtime SHA-256 and post-cleanup tests.
- **Managed risk:** moving historical relative documentation paths affects old bookmarks. The index and immutable original ZIP provide lookup/recovery; unchanged texts remain in `History/`.
- **Preserved unresolved work:** Windows-native launch, real Linux Mint package installation, libmpv/HDR, exact A/V synchronisation, GPU encoding, unusual attachment/subtitle streams and interrupted-batch persistence. These require separate platform feature work, not speculative cleanup.
- **Restoration:** extract the original EIDOLITH 0.3 source ZIP into a new folder. Never overwrite user state folders, saved media or conversion outputs. To restore individual old documentation paths, copy from `Documentation/History/` or the original ZIP.

## 5. Definition-of-done review

All five tabs, embedded Oggcultist, EIDOLITH separate player/converter/queue pages, standard naming and queue operation, Touch Type, Passphrase, Tarot/Rune, ASCII and original film-grain textures passed regression checks in the test environment. The root retains only the two official launchers and `Application/`. Historical assets and working source are preserved. **Native Windows, physical Linux Mint and NVIDIA NVENC validation remain NOT TESTED**, not silently reported as successes.

Consult `VERIFICATION_REPORT.md` for the exact tests and `PROJECT_STRUCTURE.md` for module dependencies.
