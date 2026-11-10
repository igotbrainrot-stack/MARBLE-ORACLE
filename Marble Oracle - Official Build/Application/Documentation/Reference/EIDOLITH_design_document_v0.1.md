# EIDOLITH
## Video Player & Archival Converter — Design Document

**Version:** 0.1 — Initial specification  
**Date:** 10 November 2026  
**Status:** Concept / pre-implementation  
**Name:** *Eidolith* — an invented name drawn from *eidolon* (image) and *lithos* (stone), suggesting moving images preserved in durable form.

## 1. Project concept

EIDOLITH is a **local-first desktop video player and converter** focused on making video collections smaller **without sacrificing more visible quality than necessary**. It combines reliable playback, source inspection, single-file conversion, and batch archival workflows in one application.

The default archival strategy is **AV1 video in MKV, encoded with SVT-AV1 at 10-bit**. The application must also offer H.265/HEVC and H.264/AVC output when compatibility matters more than compression efficiency. It must not imply that a particular container, codec, or quality number guarantees a specific file-size reduction.

**Primary priorities, in order:**
1. Preserve perceptual quality at substantially reduced storage cost when feasible.
2. Protect originals and avoid silent changes to audio, subtitle, colour, or chapter data.
3. Play original and converted media reliably, including modern AV1 files.
4. Make batch conversion understandable, recoverable, and unattended once started.
5. Remain offline-capable, private, and portable.

## 2. Intended users and supported environments

- People maintaining sizable personal film, television, recorded-video, or home-video collections.
- Users who want a dependable video player as well as a converter rather than separate applications.
- Users who wish to compare source and output before converting an entire collection.
- **Initial desktop validation target:** Linux Mint, x86-64. Design the core to be portable to Windows; macOS can be considered later.
- All processing is performed locally; no cloud account or upload is required.

## 3. Scope and boundaries

### In scope for initial development
- Open and play local video files, with common audio and subtitle formats.
- Inspect media properties using `ffprobe`.
- Convert one video or a batch using `ffmpeg`.
- Default to SVT-AV1 in MKV with configurable constant-quality settings.
- Offer audio passthrough or optional audio conversion.
- Preserve chapters, tracks, and metadata wherever technically supported.
- Show progress, cancel jobs, retain job history, and recover cleanly from failure.
- Compare source and converted files, including resulting size and basic quality checks.

### Out of scope for first release
- Streaming subscriptions, DRM circumvention, or a streaming server.
- Video editing timeline, compositing, and effects.
- AI upscaling or interpolation.
- Cloud processing and account synchronization.
- Automatic deletion or replacement of source files.
- A full media-server library/indexing feature, though this could be added later.

## 4. Playback requirements

**P1 — Core player**
- Open files directly and via a playlist; support drag-and-drop as an input action.
- Seek, pause, resume, change playback speed, and navigate chapters.
- Switch between embedded audio tracks and subtitles; load external subtitle files.
- Resume from last watched position (opt-in per-file local history).
- Support common source formats, including H.264, HEVC, VP9, AV1, and common audio codecs, subject to installed decoding support.
- Use hardware-accelerated decoding when available, with software fallback.
- Preserve correct display aspect ratio and avoid unrequested frame-rate conversion.

**P2 — Player extensions**
- Frame stepping, screenshots, A–B repeat, and subtitle timing adjustment.
- Side-by-side or rapid-toggle source/output comparison with synchronized timestamps, if technically practical.
- Local playlists and optional folder-based browsing.
- HDR playback where the platform and display pipeline support it; clearly warn when tone mapping or HDR output is unavailable.

**Proposed playback engine:** `libmpv` embedded in a desktop application. Confirm binding stability, packaging and HDR behaviour during the proof of concept.

## 5. Conversion engine and codec policy

### Default archival output

| Parameter | Initial default |
|---|---|
| Container | MKV |
| Video codec | AV1 |
| Encoder | SVT-AV1 (`libsvtav1`) |
| Pixel format | 10-bit 4:2:0 (`yuv420p10le`) where suitable |
| Quality control | Constant quality, CRF 28 |
| Encoder preset | 5 |
| Resolution | Preserve original |
| Frame rate | Preserve original |
| Audio | Stream copy by default |
| Subtitles and chapters | Preserve where supported |
| Source file | Always keep; no overwrite |

**Built-in starting profiles** (user-editable, not quality guarantees):

| Profile | Codec / encoder | CRF | Preset | Intended trade-off |
|---|---|---:|---:|---|
| High fidelity | AV1 / SVT-AV1 | 24 | 4 | More detail, larger output, slower conversion |
| Balanced archive (default) | AV1 / SVT-AV1 | 28 | 5 | Storage reduction with good perceptual quality |
| Space saver | AV1 / SVT-AV1 | 34 | 6 | Smaller output, visibly greater loss risk |
| Broad device compatibility | HEVC / x265 | Configurable | Configurable | Better compatibility than AV1 on some devices |
| Legacy compatibility | AVC / x264 | Configurable | Configurable | Widest playback support, typically larger files |
| Lossless remux | Copy streams | N/A | N/A | Change container where compatible, no video re-encode |

Advanced settings: codec, CRF, preset, pixel format, resolution, cropping, optional deinterlacing, colour handling, selected streams, and audio bitrate/channel configuration. Controls must indicate when a change can reduce quality.

### Audio treatment
- **Default:** copy audio without transcoding to avoid unnecessary quality loss.
- Optional Opus conversion for audio-heavy sources, including adjustable bitrates and channel layouts.
- Other compatible audio codecs may be offered depending on chosen container and target device.
- Do not silently downmix multichannel sound or drop alternate-language tracks.

### Stream and colour fidelity
- Probe and display all video, audio, subtitle, chapter, attachment, and metadata streams.
- Preserve tracks and chapter markers when supported by the output container; warn before omitting an unsupported stream.
- Respect rotation metadata, sample aspect ratio, colour primaries, transfer functions, matrix coefficients, and HDR status.
- Avoid silently converting HDR to SDR or stripping essential HDR information. For HDR content, output must be verified, or conversion must be blocked/warned if preservation cannot be assured.
- Treat animation, screen recordings, interlaced footage, high-motion scenes, dark scenes, and film grain as distinct compression challenges.
- Advanced film-grain synthesis may be added after validation; it is not a lossless preservation method.

## 6. Source analysis and conversion workflow

1. **Import:** select one or more files or folders; optional recursive discovery.
2. **Inspect:** run `ffprobe` to collect dimensions, frame rate, duration, bitrate, codec, bit depth, audio streams, subtitles, chapters, HDR flags, and source size.
3. **Assess:** flag likely poor re-encode candidates (e.g. existing low-bitrate AV1, already-small files, problematic HDR or unsupported streams).
4. **Choose:** apply a built-in profile or custom settings; show what will change and what will be preserved.
5. **Optional test encode:** convert a user-selected excerpt or several short representative excerpts before committing to the full encode.
6. **Queue:** validate output path, permissions, expected free disk space, and source availability.
7. **Convert:** run FFmpeg as a managed subprocess with machine-readable progress, pause/resume strategy if feasible, and cancellation.
8. **Validate:** probe output, compare expected tracks and metadata, inspect duration, check for decoder errors, and report resulting size. Full decode verification is an optional slower check.
9. **Review:** provide original/output sizes, percentage saved, time spent, selected settings, validation warnings, and playback/visual comparison.
10. **Keep source:** never delete or overwrite automatically; any future cleanup operation must require explicit confirmation.

**File-size estimation:** label estimates as approximate. Constant-quality encodes have unpredictable final sizes; short sample estimates must not be presented as guarantees.

**Quality assessment:** offer visual A/B inspection first. Optional objective measures such as VMAF/SSIM may be integrated when available, with warnings that a numerical score is not equivalent to preserving the original and can be misleading on grain, animation, or altered output.

## 7. Conversion queue and failure handling

- Queue multiple files with individual status: queued, analyzing, converting, validating, completed, cancelled, failed, skipped.
- Show per-job progress, processing speed, elapsed time, approximate remaining time, and encoding configuration.
- Support cancel, retry, reorder, skip, and pause-before-next-job; resume an interrupted batch by restarting incomplete jobs rather than assuming FFmpeg can resume an encoded file midstream.
- Write to a temporary output path and finalize only after validation; avoid presenting partial output as complete.
- Keep a readable error log and exact FFmpeg command for troubleshooting.
- Avoid collisions by using deterministic, user-editable output naming with safe suffixes.
- Default to one concurrent software encode; allow advanced users to adjust concurrency and CPU use.
- Check disk capacity before conversion and detect out-of-space failures during a job.

## 8. Technical architecture

**Suggested implementation:** Python desktop application with PySide6/Qt (functional shell only; visual treatment will come from the external suite). Use `libmpv` for playback and installed or bundled FFmpeg binaries for probing and conversion.

| Module | Responsibility |
|---|---|
| Media Player | libmpv lifecycle, playback state, audio/subtitle selection, resume |
| Media Probe | Parse `ffprobe` JSON, normalize streams, detect edge cases |
| Profile Manager | Codec profiles, validated options, user presets |
| Conversion Builder | Create safe argument arrays; choose compatible stream mappings |
| Job Scheduler | Queue persistence, priorities, subprocess lifecycles, cancellation |
| Verification | Output probing, stream checks, duration and decode checks |
| File Operations | Naming, temporary outputs, disk checks, finalization |
| Local Storage | SQLite or equivalent for queue, settings, and watch history |
| Application Adapter | Expose functions to the suite-defined UI without embedding styling |

**Engineering rules:**
- Keep the conversion engine independent of interface implementation so it can be tested headlessly.
- Invoke FFmpeg using subprocess argument arrays, **not** interpolated shell commands.
- Never send local media paths or playback history to a remote service.
- Allow the user to inspect the detected FFmpeg build and whether `libsvtav1`, `libx265`, `libx264`, and `libopus` are actually available.
- Do not assume all FFmpeg distributions contain every encoder; report missing capabilities clearly.
- Review distribution and codec licensing before bundling FFmpeg and libmpv.

### Illustrative FFmpeg baseline

```bash
ffmpeg -hide_banner -i input.mp4 \
  -map 0:V:0 -map 0:a? -map 0:s? \
  -map_metadata 0 -map_chapters 0 \
  -c:v libsvtav1 -crf 28 -preset 5 -pix_fmt yuv420p10le \
  -c:a copy -c:s copy \
  output.mkv
```

This is a **baseline example, not a universal production command**: it includes the primary non-cover-art video and all audio/subtitle streams, but not every attachment or data stream. The actual application must generate source-dependent stream mappings and colour metadata handling, and must preflight container compatibility before encoding. A remux or copied subtitle codec can fail if unsupported by the destination.

## 9. Safety, privacy, and accessibility requirements

- Offline-first operation with no account requirement or telemetry by default.
- Explicit source/destination paths; no automatic original-file deletion.
- Clear, accessible text descriptions of what a profile changes, independent of its eventual appearance.
- Keyboard operation for common player and queue actions.
- Failure messages must identify which file failed, what operation failed, and whether the source is intact.
- Do not claim lossless quality when using lossy codecs.

## 10. Visual style and layout

## 11. Development phases

### Phase 1 — Technical proof of concept
- Demonstrate libmpv playback in a basic desktop host.
- Probe representative media with `ffprobe`.
- Perform a successful 10-bit SVT-AV1 encode at CRF 28/preset 5.
- Verify playback and source/output metadata for H.264, H.265, and AV1 examples, including subtitle and HDR test cases.

### Phase 2 — Minimum viable application
- Player with essential controls, track selection, and playlist.
- Single-file and batch encoding, presets, progress, cancel, queue persistence, and file safety.
- Post-encode statistics and basic validation.
- Linux Mint packaging and simple launch process.

### Phase 3 — Archival quality improvements
- Sample encodes and original/output comparisons.
- Advanced audio and subtitle handling; attachment preservation.
- More reliable HDR handling and expanded test media coverage.
- HEVC/AVC compatibility profiles and device targets.

### Phase 4 — Optional expansion
- Windows packaging, library browsing, duplicate detection, and richer metadata tools.
- Optional quality metrics and advanced grain-aware profiles.
- Integration with a broader application suite when its design system and layout specification arrive.

## 12. Definition of done for first usable release

- Open and play ordinary H.264, HEVC, and AV1 test files successfully on the supported host.
- Convert a supported file to playable AV1/MKV using default settings without modifying the input.
- Batch jobs recover sensibly from cancellation, process termination, and bad files.
- No silent loss of expected audio tracks, subtitles, or chapters on supported test cases.
- HDR and unsupported stream cases produce explicit handling or warnings, not invisible degradation.
- A completed output is verified and accompanied by accurate source size, destination size, and savings percentage.
- UI-independent modules pass automated tests; the application can launch with a basic functional shell pending suite styling.

## 13. Unresolved decisions

1. Whether to bundle FFmpeg/libmpv or locate compatible system installations (including license implications).
2. Which hardware platforms and playback devices must be supported at launch.
3. Whether to allow video conversion if HDR metadata cannot be faithfully preserved.
4. How much audio conversion and stream-editing functionality to expose in v1.
5. Whether optional output size targets should be supported through a multi-pass bitrate mode in addition to CRF.
6. Whether source/output A–B comparison belongs in MVP or the next release.
7. Integration contract for the external program suite's navigation, theme, typography, and layout.

---

*This is a starting design document, not an implementation specification frozen for development. The Visual style and layout section is intentionally empty pending input from the separate program suite.*
