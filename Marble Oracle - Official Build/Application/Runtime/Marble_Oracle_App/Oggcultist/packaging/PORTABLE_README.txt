Oggcultist — portable edition
=============================

Run Oggcultist.exe. Nothing is installed and no administrator rights are needed.

First start
  If FFmpeg is not included in this download, Oggcultist asks before downloading
  the official, checksum-verified FFmpeg build into your user profile
  (%LOCALAPPDATA%\Oggcultist\ffmpeg\bin). Nothing is downloaded without your OK.

Where your data goes
  Settings and playlists: %APPDATA%\Oggcultist
  Logs:                   %LOCALAPPDATA%\Oggcultist\logs
  Conversion records:     inside your destination music folder (.oggcultist)

Fully portable (USB stick) mode
  Create a folder named  OggcultistData  next to Oggcultist.exe. Settings,
  playlists, logs and the private FFmpeg copy are then kept there instead.
  Your existing settings and playlists are copied (not moved) the first time.

Using your own FFmpeg
  Put ffmpeg.exe, ffprobe.exe and ffplay.exe in a folder named  tools  next to
  Oggcultist.exe, or anywhere on your PATH.

Your original music files are never modified, moved or deleted.
