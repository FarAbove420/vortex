# Vortex

A simple desktop app for downloading music and video from YouTube and other
sites, built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and
[FFmpeg](https://ffmpeg.org).

I made it for my mom and my brother. They used to download songs from shady
converter websites full of ads and malware, and the command line tools were too
technical for them. Vortex wraps those same tools in a window with one search
box and two buttons, and ships FFmpeg inside the app so there's nothing else to
install.

Runs on Windows and macOS.

![Vortex Home: a Big Buck Bunny preview with the Song and Video buttons, and a finished download](docs/screenshots/home.png)

## Download

Get the latest version from the
[Releases page](https://github.com/FarAbove420/vortex/releases):

- **Windows**: `Vortex-Setup.exe`
- **macOS**: `Vortex-macOS.zip`, unzip it and drag Vortex to Applications

The builds are not code-signed, so Windows SmartScreen and macOS Gatekeeper
warn the first time you open Vortex.

To run Vortex from source or build it yourself, see
[DEVELOPMENT.md](DEVELOPMENT.md).

## What it does

**Home** is the simple way in:

- Paste a link, or type a song name and pick from the search results
- Copy a link anywhere and switch to Vortex: it's filled in and looked up
- A preview shows the thumbnail, title, channel and length
- Two big buttons: **Song** (MP3 with cover art and tags) and **Video** (MP4
  that plays on any device)

The rest:

- **Queue**: several downloads in a row, progress ("song 3 of 37" for
  playlists), cancel, open the file or show it in its folder, and "Retry with
  browser cookies" when YouTube asks to confirm you're not a bot
- **History**: everything downloaded before, also after a restart
- **Settings**: download folder, song format, text size, notifications and
  updates
- **Convert**: change a local file to another format, make it smaller, or cut
  out a part. Quality is explained as quality versus file size, and the
  progress says what it's doing, how fast, and how long is left
- **Advanced** (switch it on in Settings, a tip on Home points there): every
  quality and format option, subtitles, SponsorBlock and extra yt-dlp flags

| Search by song name | The queue |
|---|---|
| ![Search results for "blender open movie"](docs/screenshots/search.png) | ![Queue with two finished downloads, one downloading and one waiting](docs/screenshots/queue.png) |
| **History** | **Settings** |
| ![History of finished downloads](docs/screenshots/history.png) | ![Settings: download folder, song format, text size, notifications](docs/screenshots/settings.png) |

Vortex never overwrites a file: a second song with the same name is saved as
"Title (2)". It warns before quitting with unfinished downloads, and only one
Vortex runs at a time.

## Automatic updates

YouTube changes often, and older yt-dlp versions stop working. YouTube
downloads also need a JavaScript runtime called Deno
([yt-dlp announcement](https://github.com/yt-dlp/yt-dlp/issues/15012)).
Vortex takes care of both, so nobody has to reinstall the app when YouTube
breaks something:

- **yt-dlp**: at most every 6 hours, Vortex looks for a newer
  [yt-dlp release](https://github.com/yt-dlp/yt-dlp/releases), checks it
  against its published checksum and uses it from the next start.
- **Deno**: downloaded the first time Vortex starts, and refreshed once a week.
- **Vortex itself**: once a day it checks for a new release and shows a
  clickable note in the sidebar.
- **If an update is bad**: a downloaded yt-dlp that doesn't work is dropped
  automatically and Vortex goes back to the previous one or the built-in copy.
  Settings also has "Undo the last yt-dlp update" and "Always use the yt-dlp
  built into the app".

This means Vortex contacts `github.com` when it starts. You can turn it off in
Settings with "Keep yt-dlp and Deno up to date".

## Where Vortex keeps its files

Settings, history, a log file, the downloaded yt-dlp and Deno are stored in
`~/.vortex/` (on Windows `%USERPROFILE%\.vortex\`). If something goes wrong,
`vortex.log` usually says why.

## Known issues

- **Browser cookies on Windows**: since Chrome 127, other programs can't read
  Chrome or Edge cookies on Windows. "Retry with browser cookies" uses Firefox
  there when it's installed.
- **Cancel** works while data is downloading. Once the file is being converted
  (for example to MP3), it can't be cancelled anymore.
- **Playlists** can still overwrite a file with the same name; the "Title (2)"
  check only covers single videos.
- **Notifications** on Windows flash the taskbar button instead of showing a
  banner.
- **Drag and drop** isn't supported. Copying a link works instead.

## Please download responsibly

Only download content you have the right to download. Downloading from some
sites, YouTube included, may go against their terms of service. Vortex is a
front end for yt-dlp and FFmpeg and is not affiliated with any of the sites it
can download from.

## License

Vortex is released under the [MIT License](LICENSE). The packaged app includes
third-party software under other licenses, including FFmpeg under the GPL. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
