# Channel Soundboard (Windows desktop) v11

A free, offline soundboard mixer by Balram Sevak. **Every channel has its own output device**, so different songs can play at the same time on the laptop speakers, a Bluetooth headset, USB audio, HDMI, an amplifier, etc. Each channel streams straight to its device through Windows WASAPI.

## Get the installer
1. Create a **Public** repository on GitHub and upload `app.py`, `engine.py`, `icon.ico`, `icon.png`, `installer.iss`, `README.md`, `requirements.txt`.
2. Create the file `.github/workflows/build.yml` (Add file -> Create new file) and paste the text of `build.yml` from this zip into it. (A folder starting with a dot cannot be dragged in.)
3. Actions tab -> **Build Windows installer** -> Run workflow (5-15 minutes).
4. Open the finished run -> Artifacts -> **ChannelSoundboard-Setup**, unzip it and run `ChannelSoundboard-Setup.exe`.
   To update later: upload the new files over the old ones, run the workflow again and install the new Setup over the old program. Your list and settings stay.

Windows may say "Windows protected your PC" (the installer is not signed): More info -> Run anyway.

## What it does
- **Pages** (Page 1, Page 2 ...): each page has its own song list. Click the open page to rename it, give it a **start/stop time**, **Duplicate** it or delete it. Page play: Stop / Continue / Multiple page play. Timers of all pages stay active.
- **Channels:** device, Mute, pre-listen 🎧 and "Send to Main", play, fader, number (#1, #2 ...), own time / running total, Clips, name menu, drag handle (hold and drag to move a song).
- **Continue** goes on from the song you start, skips songs that have their own start time, crossfades (or is gapless) into the next song and stops after the last one.
- **Clips:** dialogue sounds that play at set times of a song, even when the song is muted. They pause with the song and stop when the song ends. Set the times, then press **Apply**.
- **DJ pre-listen:** choose a Main output and a Headset output, listen with 🎧, then send the song to Main.
- Master and Level faders, Equalizer + Bass boost, per-song start/stop time (one shot), Clear (only the open page), Settings (fade, crossfade, clip ducking, themes, About).
- Space = play/pause all. Click rewind/forward = 10 s, hold = fast scrub.
- Formats: MP3, WAV, FLAC, OGG, OPUS. Library and settings: `%APPDATA%\ChannelSoundboard`.

## Notes
- If the Headset is plugged into the 3.5 mm jack, Windows may mute the laptop speaker: use HDMI, USB or Bluetooth for Main.
- While a timer is waiting, the program keeps the PC from sleeping (the screen may still turn off).
