# EIDOLITH 0.3 — Speed profiles, progress and standard file naming

This is the full Marble Oracle integration, preserving HOME, OGGCULTIST, EIDOLITH, PASSPHRASE and TOUCH TYPE.

## Encoding speed

The original *Balanced archive (default)* is **10-bit SVT-AV1, CRF 28, preset 5**. It is CPU-based and can take substantially longer than the video's playtime. Not finishing a 30-minute episode within 10 minutes does **not** necessarily mean conversion is stuck.

For faster conversions, in **EIDOLITH → CONVERT**, select **USE FAST PROFILE**. If a functioning NVIDIA GPU/driver and a matching FFmpeg encoder are found, it chooses `NVIDIA AV1 (fast)` (or NVIDIA HEVC when AV1 is not available); otherwise it chooses a fast CPU option. You can also choose the profile manually. Neither a specific speed nor smaller files are guaranteed: speed, perceptual quality, compatibility and output size all depend on the source and hardware.

Available profiles now include the original archival presets plus:

- **Faster CPU AV1:** SVT-AV1 10-bit, preset 10, CRF 30. Faster than preset 5 but may produce larger files or lower detail.
- **NVIDIA AV1 (fast):** hardware encoder `av1_nvenc`, preset p4. Requires GPU, driver and compatible FFmpeg build.
- **NVIDIA HEVC (fast):** `hevc_nvenc`, preset p4.
- **NVIDIA H.264 (fastest compatibility):** `h264_nvenc`, preset p4.
- **Fast CPU H.264:** `libx264`, preset veryfast, CRF 23.

FFmpeg encoder *listing* alone is not proof that NVIDIA encoding can run on a given machine. If a hardware encode fails, EIDOLITH reports the FFmpeg error and preserves the original.

## Visible progress

The QUEUE page now receives machine-readable FFmpeg progress updates. Each active job shows **percentage, elapsed media time, source duration, encode speed in x realtime, and estimated time remaining** whenever duration and speed are available. These are estimates, not promises. Progress is based on media timestamps, not filesystem size.

Conversion writes to a unique temporary output, verifies its streams and duration with FFprobe, then finalizes using an overwrite-safe operation. Failed or cancelled jobs delete only their own temporary output, never the source. The job log reports actual size change.

## Standard organisational filenames

The **ORGANISE OUTPUT FILENAME** section provides Auto (TV / movie), TV episode, Movie and Keep source name modes. Auto recognises common `S01E02`, `1x02`, `Season 1 Episode 2`, and movie-year patterns. It does **not** invent missing season or episode numbers.

- `The.Show.S02E05.Episode.Title.1080p.mkv` → `The Show - S02E05 - Episode Title [AV1].mkv`
- `Example.Movie.2024.2160p.mkv` → `Example Movie (2024) [HEVC].mkv`
- Ambiguous names remain recognisable, with a codec suffix.

A **Title override** can rename a whole selected batch to the correct show/movie title. Season and episode override fields apply only when exactly one file is selected; batch jobs otherwise derive each episode number from its source filename. An on-screen preview shows the planned name. Invalid path characters are removed, and collisions receive `(2)`, `(3)`, etc. All originals remain unchanged. No automatic folder moving or deletion occurs.

## Protective checks and limitations

- The application does not silently overwrite output files.
- It maps the primary video, audio tracks, subtitles, chapters and metadata, and preserves Matroska attachments where supported.
- It blocks re-encoding of detected HDR/Dolby Vision until a verified HDR workflow exists; remuxing remains an option.
- It blocks unsupported data streams or multi-video layouts to avoid silent loss.
- Encoder support and exact container/track compatibility depend on local FFmpeg.
- The player remains a basic embedded preview, not full libmpv HDR playback.
- Queued jobs are not yet persisted across application restarts.

## Testing

EIDOLITH parser, progress and encoder policy unit tests passed. Real FFmpeg tests passed for fast CPU H.264 plus 10-bit Faster CPU AV1; the H.264 job was validated with FFprobe and the source compared byte-for-byte. Marble Oracle's GUI self-test, five-tab navigation, Touch Type, Rune interaction and original Oggcultist texture checks passed in a Linux virtual display. Native Windows and NVIDIA GPU tests are still outstanding.
