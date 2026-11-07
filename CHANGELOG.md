# Changelog

## 0.3.2

Windows fixes:

- Convert shows progress for files with accented names or tags (most
  songs); the bar used to jump straight from 0 to 100%
- Paths in the Advanced tab's extra args keep their backslashes, so
  `C:\Music\archive.txt` works
- The History icon in the sidebar no longer turns into a box when selected
- Running from source shows the Vortex icon in the taskbar instead of
  Python's

## 0.3.1

- Convert is back in the sidebar; only the Advanced download tab is hidden
  by default, with a tip on Home pointing to the setting
- Fixed: a row in the queue that was downloading or waiting was much too tall
- Search results line up on the left; Settings dropdowns line up across
  sections
- Screenshots in the README

## 0.3.0

- New Home tab: paste a link or search by song name, see a preview with the
  thumbnail, then press Song or Video
- A link copied anywhere is filled in when you switch to Vortex
- Songs get cover art and tags; videos are MP4 by default so they play on any
  device
- A song with the same name as an existing file is saved as "Title (2)"
  instead of overwriting it
- History tab that survives a restart
- "Song 3 of 37" progress for playlists, "Finishing up" while converting
- Warning before quitting with unfinished downloads; only one Vortex at a time
- Notification when a download finishes in the background (banner on macOS,
  taskbar flash on Windows)
- Text size setting; the Download and Convert tabs are now "advanced" and
  hidden unless switched on in Settings
- SponsorBlock now removes sponsor segments (before, it only fetched them)
- "Retry with browser cookies" uses Firefox on Windows when it's installed
- Updates: versions are read without the GitHub API (no hourly limit), the
  previous yt-dlp is kept, a yt-dlp that fails with a missing module is
  dropped automatically, and Settings has "Undo the last yt-dlp update" and
  "Always use the built-in yt-dlp"
- The sidebar shows when a new Vortex release is out
- Code split into a `vortex/` package, with tests and GitHub Actions for tests
  and release builds

## 0.2.0

- yt-dlp and Deno update themselves at startup, checked against their
  published checksums
- Version shown in the sidebar
- New app icon
- Fixes: extra args no longer reset the other options, Convert to MP3/WAV/FLAC
  works, Video Only has no audio, cancel a running download, no more parallel
  downloads from a race in the queue, errors logged to `~/.vortex/vortex.log`

## 0.1.1

- First version shared with family
