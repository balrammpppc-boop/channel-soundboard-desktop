# Channel Soundboard (Windows desktop)

A free, offline soundboard mixer. **Every channel has its own output device**, so different songs can play at the same time on the laptop speakers, a Bluetooth headset, USB audio, HDMI, etc. Each channel streams straight to its device through Windows WASAPI - no browser involved.

## Get the installer (no programming needed)
1. Create a new **Public** repository on GitHub and upload every file in this folder (keep the `.github` folder).
2. Open the **Actions** tab -> **Build Windows installer** -> **Run workflow**. Wait about 5-10 minutes.
3. Open the finished run -> **Artifacts** -> download **ChannelSoundboard-Setup**, unzip it, double-click `ChannelSoundboard-Setup.exe`.
   *(Pushing a tag such as `v1.1` also puts the installer on the repository's **Releases** page.)*

To update later: upload the new files over the old ones, run the workflow again and install the new `ChannelSoundboard-Setup.exe` over the old program. Your song list and settings are kept.

Windows may show "Windows protected your PC" because the installer is not code-signed. Click **More info -> Run anyway**.

## Use
- **+ Add song** (or drag audio files onto the window). MP3, WAV, FLAC, OGG, OPUS. Songs are referenced by their file location, not copied.
- **Each channel:** device button, Mute (only that channel), play/pause, fader, name menu (move, start/stop time, remove) and duration.
- **Left panel:** previous / rewind / play-pause **all** / forward / next, Multiplay, Shuffle, Stop-Repeat-Continue, Timer (stop everything at a clock time), EQ / Bass boost, played / total time (click to reset), Clear, Master volume. Space = play/pause all. Click rewind/forward = 10 s, hold = fast scrub.
- **Continue** plays down the list and stops after the last song. With **Shuffle** every song plays once, then it stops.
- **Start / stop time** (song name menu): a one-shot time that clears itself after it has run. At a stop time with **Continue**, the next song starts. While a timer is waiting the program keeps the PC from going to sleep (the screen may still turn off).
- Waveform on top: click or drag to seek; shows elapsed and remaining time.
- Library and settings are saved in `%APPDATA%\ChannelSoundboard`.

## DJ pre-listen (cue)
Set two outputs in the left panel: **Main** (dance floor: laptop speaker, HDMI, sound box ...) and **Headset** (wired or Bluetooth). Every channel then has:
- **🎧** - hear that song only in the headset (the Main output is not affected). Click the waveform or use rewind/forward to find the part you want; the top bar follows the pre-listen while it plays. The **🎧 Level** slider sets the headset volume (it ignores Master volume and Mute).
- **⇒ Main** - fade the song in on the Main output **from the same point**, while the other Main song fades out (with Multiplay on, the others keep playing).
Choosing a device plays a short beep on it, so you can hear which physical output it is. If a Bluetooth/USB device is not in the list, open the menu and use **Refresh device list**.

## Choosing devices (important)
- A channel's own device button overrides Main for that channel; "Main" means it follows the Main output.
- On many laptops the speaker and the 3.5 mm headphone jack are **one** Windows device ("Speakers / Headphones"). With a wired headset plugged in, Windows sends that device to the headset and mutes the speaker, so Main and Headset cannot both use it. Use different outputs: for example Main = HDMI / Bluetooth speaker / USB sound card and Headset = the jack, or Main = laptop speaker and Headset = Bluetooth.
- Bluetooth headsets add about 0.2-0.5 s of delay, so a wired headset is better for beat matching. Choose the "Headphones (... Stereo)" entry, not "Hands-Free".
- The app warns when Main and Headset are the same output.

## Notes
- Equalizer and bass boost apply to all channels. Very loud boosts are limited to avoid distortion.
- Media keys / lock-screen style controls are not included.
