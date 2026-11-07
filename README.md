# Vortex

A simple desktop app for downloading video and music from YouTube and other
sites, built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and
[FFmpeg](https://ffmpeg.org).

I made it for my mom and my brother. They used to download songs from shady
converter websites full of ads and malware, and the command line tools were too
technical for them. Vortex wraps those same tools in a window with a URL field
and a Download button, and ships FFmpeg inside the app so there's nothing else
to install.

Runs on Windows and macOS.

## What it does

- **Download** video + audio, video only, or audio only (MP3, M4A, FLAC, WAV,
  Opus, AAC), with a quality limit from 360p up to 4K
- **Queue** several downloads, see progress, cancel a running one, open the
  finished file or show it in its folder
- **Retry with browser cookies** when YouTube asks to "confirm you're not a
  bot"
- **Convert** local files between common formats, change codecs and trim
- Optional subtitles, embedded thumbnails, playlists and SponsorBlock, plus a
  field for extra yt-dlp flags if you know what you're doing

## Running from source

You need Python 3.10 or newer.

```bash
git clone https://github.com/FarAbove420/vortex.git
cd vortex
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### YouTube needs Deno

Since yt-dlp 2025.11.12, YouTube downloads need a JavaScript runtime. Without
one, fewer formats are available and some downloads fail
([yt-dlp announcement](https://github.com/yt-dlp/yt-dlp/issues/15012)).
Install [Deno](https://deno.com); yt-dlp finds it automatically.

### Keep yt-dlp up to date

YouTube changes often and older yt-dlp versions stop working. If downloads
start failing, update first:

```bash
pip install -U "yt-dlp[default]"
```

## Building the app

- **Windows**: see [WINDOWS_BUILD.md](WINDOWS_BUILD.md). It produces
  `Vortex.exe` and a `Vortex-Setup.exe` installer.
- **macOS**: needs a universal2 Python from python.org. Fetch the Intel FFmpeg
  binary once, then build:

  ```bash
  pip install -r requirements-build.txt
  ./vendor/fetch-x86_64-ffmpeg.sh
  pyinstaller Vortex.spec --noconfirm
  ```

  The result is `dist/Vortex.app`.

The app icon is drawn by `assets/make_icon.py`, which writes `icon.png`,
`Vortex.icns` and `Vortex.ico`. Only run it again if you change the design
(it needs `pip install pillow`, and macOS for the `.icns`).

The builds are not code-signed, so Windows SmartScreen and macOS Gatekeeper
will warn the first time the app is opened.

### Releasing a new version

The version number lives in three places. Update all of them:

- `__version__` in `main.py` (the macOS build reads it from there)
- `MyAppVersion` in `Vortex.iss`
- `version_info.txt` (Windows file properties)

## Where Vortex keeps its files

Settings and a log file are stored in `~/.vortex/` (on Windows
`%USERPROFILE%\.vortex\`). If something goes wrong, `vortex.log` usually says
why.

## Known issues

- **Browser cookies on Windows**: since Chrome 127, other programs can't read
  Chrome or Edge cookies on Windows, so "Retry with browser cookies" only works
  reliably with Firefox there.
- **Cancel** works while data is downloading. Once the download is done and
  the file is being converted (for example to MP3), it can't be cancelled
  anymore.

## Please download responsibly

Only download content you have the right to download. Downloading from some
sites, YouTube included, may go against their terms of service. Vortex is a
front end for yt-dlp and FFmpeg and is not affiliated with any of the sites it
can download from.

## License

Vortex is released under the [MIT License](LICENSE). The packaged app includes
third-party software under other licenses, including FFmpeg under the GPL. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
