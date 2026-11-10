# EIDOLITH 0.2 — Embedded Player and Separate Workspaces

This version changes EIDOLITH inside the full Marble Oracle suite. No other tab has been removed.

## Fixed navigation

The EIDOLITH sidebar now switches between genuinely different workspaces:

- **PLAYER:** import and select videos, play inside the Marble Oracle window, inspect ffprobe metadata.
- **CONVERT:** select videos, choose AV1/HEVC/H.264/remux profile, choose audio treatment and output folder, queue selected files.
- **QUEUE:** review queued jobs, run conversion, cancel a job, retry failures and see logs.
- **ABOUT:** technical limitations and local-first policy.

The `SELECT ALL` button appears in both PLAYER and CONVERT; Ctrl+A works in their file lists. Imported files are selectable immediately. Output filenames are checked for on-disk *and queued* collisions.

## Embedded video viewer

- No graphical external FFplay window is launched by the normal PLAY operation.
- **Video:** FFmpeg decodes a reduced-frame-rate stream into raw PPM frames, displayed using Tk's native PhotoImage inside the EIDOLITH PLAYER workspace (no extra Python packages required).
- **Audio:** FFplay, if available, plays **audio only**, with `-nodisp -vn`. Playback does not require audio to operate.
- The viewer includes PLAY/RESUME, PAUSE, STOP, seek slider, skip ±10 seconds, a volume slider, and a separate FULLSCREEN button.
- Changing audio volume restarts the audio-only FFplay subprocess at the current approximate position.
- Playback starts **embedded**. Fullscreen is never automatic, and the fullscreen host is placed at the parent window's display position before enabling fullscreen. Exit fullscreen with Escape or its on-screen button.
- Changing away from PLAYER pauses playback and preserves the position.
- Local keyboard controls: Space toggle play/pause, left/right arrows seek, F fullscreen, Escape return to home (or exit fullscreen).

### Limitations of this first embedded player

This is a **CPU-based preview**, not the planned libmpv playback engine. It renders up to 12 video frames per second and uses a separate audio-only process. Lip-sync and precise seeking are not guaranteed, especially for long or heavy files. HDR tone mapping, hardware-accelerated presentation, subtitle rendering and native track switching are not implemented. No automatic full-screen or second-display player window is created.

For production-grade HDR/AV1 playback, future work should implement the original design document's `libmpv` backend with a stable embedded native window and explicit track controls, or provide a clearly labeled alternative player path.

## Safety and packaging

- Source files are never automatically deleted.
- FFmpeg and FFprobe are checked; Windows subprocesses are launched with `CREATE_NO_WINDOW` to avoid unwanted command consoles.
- No network account or telemetry.
- The existing first-run dependency installer and all other Marble Oracle tabs are preserved.
- Full fidelity validation, temp-output atomics, codec/track compatibility audits, and durable queue history remain future work. Do not treat a successful FFmpeg process as proof of zero stream or metadata loss.

## Tests performed

- Generated an H.264/AAC media file with FFmpeg; confirmed frames display inside Tk; tested pause, seek, opt-in fullscreen and return to embedded playback.
- Selected all imported files in both PLAYER and CONVERT.
- Queued and completed a lossless MKV remux; confirmed FFprobe reads H.264 and AAC from the output, and sources remain intact.
- Tested app GUI self-test, normal/retro/flat tab layouts, Touch Type games, Oggcultist's embedded pages, exact grain texture generator, and Rune panel scaling.
- Verified ZIP integrity and clean extraction. Native Windows and the user's physical Linux Mint machine still require end-to-end testing.
