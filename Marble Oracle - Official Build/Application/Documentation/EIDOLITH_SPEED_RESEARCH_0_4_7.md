# EIDOLITH 0.4.7 — conversion speed: research, measurements and changes

**Date:** 11 November 2026

## 1. How leading tools get their speed

| Technique | Who uses it | What it does | Status in EIDOLITH |
|---|---|---|---|
| Hardware encoders (NVIDIA NVENC, Intel Quick Sync, AMD VCE/AMF, Apple VideoToolbox) | HandBrake, Tdarr, Jellyfin | The graphics chip encodes. Much faster than software, with somewhat larger files or lower quality at the same size. | NVENC existed. Quick Sync and AMF HEVC profiles added in 0.4.7; they are offered only after a test encode succeeds. **Not verified on real hardware.** |
| Confirm the hardware really works | Jellyfin, Tdarr guides | An encoder listed by FFmpeg may still fail without the GPU or driver. | **Added:** a one-second test encode per hardware profile. |
| Encoder preset | Every tool | The largest lever on a CPU: faster presets trade file size for time. | **Added:** Turbo AV1 (preset 12). |
| Skip or copy files that already meet the target | Tdarr and similar library tools | Files already in HEVC/AV1 below a bitrate cut-off are left alone. | **Added:** “Don't re-encode video that is already compact AV1/HEVC” (stream copy). |
| Chunked parallel encoding | Av1an | Splits the video at scene changes and runs several encoder processes at once, because AV1 encoders do not use many cores well. | **Not added.** Measured here (2 cores): no gain. Worth revisiting on 8+ core machines. |
| Several jobs at once | Tdarr workers | Runs more than one file at a time. | **Not added**, for the same reason. |
| Full GPU pipeline (decode and resize on the GPU) | FFmpeg/NVIDIA guidance | Avoids copying frames between CPU and GPU. | **Not added**; cannot be tested without a GPU. |
| Newer encoder library | SVT-AV1 releases | SVT-AV1 2.3 reports roughly 20–40% speed-ups at similar quality for presets 7 down to 0 compared with 2.0; 3.0 and 3.1 report further gains. | **Added:** the app detects the SVT-AV1 version inside FFmpeg and logs a hint when it is older than 2.3 (Ubuntu 24.04 ships 1.7.0). |

Sources:
- HandBrake performance documentation: https://handbrake.fr/docs/en/1.8.0/technical/performance.html
- HandBrake NVENC documentation: https://handbrake.fr/docs/en/latest/technical/video-nvenc.html
- Av1an project description: https://pypi.org/project/Av1an/1.10.5/
- AOMedia, SVT-AV1 v2.3: https://aomedia.org/blog%20posts/Software-Implementation-Working-Group-Releases-SVT-AV1-v2_3
- AOMedia, SVT-AV1 v3.0: https://aomedia.org/blog%20posts/SVT-AV1-V3_0-is-Now-Available
- SVT-AV1 v3.1.0 release notes: https://newreleases.io/project/gitlab/AOMediaCodec/SVT-AV1/release/v3.1.0
- Tdarr workers: https://docs.tdarr.io/docs/nodes/workers
- Tdarr QSV plugin (skip rules): https://docs.tdarr.io/docs/plugins/classic-plugins/index/Tdarr_Plugin_bsh1_Boosh_FFMPEG_QSV_HEVC
- NVIDIA, FFmpeg with GPU acceleration: https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/ffmpeg-with-nvidia-gpu/index.html
- Jellyfin hardware acceleration: https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/

## 2. Measurements on this test machine

Environment: 2-core Xeon 2.1 GHz, FFmpeg 6.1.1, SVT-AV1 1.7.0, no GPU.
Source: 10-second synthetic 1080p clip at 6 Mb/s H.264, converted to 720p.
Speed is a multiple of real time. Quality is SSIM against the resized source (1.0 = identical).
Synthetic content is indicative only; no VMAF build or real footage was available.

| Setting | Speed | Size | SSIM |
|---|---:|---:|---:|
| Balanced archive (preset 5) | 0.24× | 2592 KB | not measured |
| Fast AV1 (preset 8), the default | 1.02× | 2296 KB | 0.9908 |
| Faster CPU AV1 (preset 10) | 1.68× | 2472 KB | 0.9902 |
| **Turbo AV1 (preset 12)** | 2.55× | 2632 KB | 0.9883 |
| Preset 12 in 8-bit | 2.98× | 2676 KB | 0.9890 |
| Fast CPU H.264 (x264 veryfast) | 3.79× | 2052 KB | 0.9892 |

Other findings:
- Decoding and resizing cost about 1.3 s of each 10-second clip, so they are not the bottleneck on a CPU.
- The resize method (lanczos vs bilinear) made no measurable difference to speed.
- Two encoder processes in parallel on 2 cores: 15.1 s vs 15.9 s for SVT-AV1 (no real gain) and 7.3 s vs 5.4 s for x264 (slower).
- 8-bit instead of 10-bit AV1 is 10–25% faster. 10-bit was kept, since it is the usual recommendation for AV1.
- An earlier benchmark in this project used a 177 Mb/s source, which made decoding dominate and understated all speeds.
- Smart copy: a 20-second 720p HEVC file at 1.6 Mb/s took under a second (about 97× real time). Re-encoding it to AV1 took 21 s and produced a file 33% larger.

## 3. What changed in 0.4.7

- **Turbo AV1 (preset 12)** profile: about 2.5× the speed of Fast AV1 for roughly 15% larger files.
- **Don't re-encode video that is already compact AV1/HEVC** (on by default). The video is copied when all of these hold: the source is AV1 or HEVC, the profile targets AV1 or HEVC, no resize or deinterlace is needed, and the overall bitrate is under 0.10 bits per pixel per frame (about 5 Mb/s at 1080p24). Audio and slim settings still apply, and the job log says the video was copied.
- **Hardware test encode**: USE FAST PROFILE tries NVIDIA AV1, NVIDIA HEVC, Intel Quick Sync HEVC and AMD AMF HEVC with a real one-second encode and picks the first that works, otherwise the fastest CPU profile. Queuing a hardware profile that fails the test is refused with FFmpeg's reason.
- **Intel Quick Sync HEVC** and **AMD AMF HEVC** profiles. Their settings come from documentation and have not been run on that hardware.
- Finished jobs show their **average speed**.
- The app logs a hint when FFmpeg contains an SVT-AV1 older than 2.3.

## 4. Not verified

- No hardware encoder (NVENC, Quick Sync, AMF) has been run on real hardware by this project. Only their failure path was exercised.
- Speeds on your computer will differ; the ratios between profiles are the useful part.
- Quality was measured with SSIM on synthetic content only.
