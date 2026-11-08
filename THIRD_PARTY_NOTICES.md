# Third-party software

Vortex's own code is MIT licensed (see `LICENSE`). The packaged app (the
Windows installer and the macOS app) also contains the software below, each
under its own license.

| Component | What it does in Vortex | License | Source |
|---|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloads the media | Unlicense | https://github.com/yt-dlp/yt-dlp |
| [yt-dlp-ejs](https://github.com/yt-dlp/ejs) | Helps yt-dlp with YouTube's JavaScript challenges | Unlicense AND MIT AND ISC | https://github.com/yt-dlp/ejs |
| [FFmpeg](https://ffmpeg.org) | Merges, converts and trims media | GPL (see below) | https://ffmpeg.org/download.html |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | The Python package the FFmpeg programs come in | BSD-2-Clause | https://github.com/imageio/imageio-ffmpeg |
| [Deno](https://deno.com) | JavaScript runtime yt-dlp uses for YouTube. Not bundled: downloaded on first start | MIT | https://github.com/denoland/deno |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | User interface | MIT | https://github.com/TomSchimansky/CustomTkinter |
| [certifi](https://github.com/certifi/python-certifi) | HTTPS certificate list | MPL-2.0 | https://github.com/certifi/python-certifi |
| [Python](https://www.python.org) | Runtime, bundled by PyInstaller, with the libraries it ships with: Tcl/Tk, OpenSSL, SQLite, zlib, libffi and the Microsoft Visual C++ runtime on Windows | PSF License, and each library's own license as listed in Python's license file | https://www.python.org/downloads/source/ |
| [PyInstaller](https://pyinstaller.org) | Starts the packaged app (its bootloader) | GPL-2.0-or-later with an exception that allows bundling any program under any license | https://github.com/pyinstaller/pyinstaller |

Libraries that yt-dlp and CustomTkinter use, bundled with them:

| Component | What it does in Vortex | License | Source |
|---|---|---|---|
| [mutagen](https://github.com/quodlibet/mutagen) | Adds cover art and tags to some audio formats | GPL-2.0-or-later (see below) | https://github.com/quodlibet/mutagen |
| [pycryptodomex](https://github.com/Legrandin/pycryptodome) | Decrypts browser cookies and encrypted streams | BSD-2-Clause and public domain | https://github.com/Legrandin/pycryptodome |
| [requests](https://github.com/psf/requests) | HTTP connections | Apache-2.0 | https://github.com/psf/requests |
| [urllib3](https://github.com/urllib3/urllib3) | HTTP connections | MIT | https://github.com/urllib3/urllib3 |
| [idna](https://github.com/kjd/idna) | International domain names | BSD-3-Clause | https://github.com/kjd/idna |
| [charset-normalizer](https://github.com/jawah/charset_normalizer) | Detects text encodings | MIT | https://github.com/jawah/charset_normalizer |
| [websockets](https://github.com/python-websockets/websockets) | WebSocket connections some sites need | BSD-3-Clause | https://github.com/python-websockets/websockets |
| [Brotli](https://github.com/google/brotli) | Decompresses web responses | MIT | https://github.com/google/brotli |
| [darkdetect](https://github.com/albertosottile/darkdetect) | Detects dark mode for CustomTkinter | BSD-3-Clause | https://github.com/albertosottile/darkdetect |
| [packaging](https://github.com/pypa/packaging) | Version checks in CustomTkinter | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |

## FFmpeg

The FFmpeg 7.1 programs come from the imageio-ffmpeg 0.6.0 wheels on PyPI.
imageio-ffmpeg is only the package they come in: a small Python library that
ships an FFmpeg program and tells Vortex where to find it. That's why FFmpeg
and imageio-ffmpeg are listed separately, each with its own license. The
Windows app contains one FFmpeg program. The macOS app contains two, one for
Apple Silicon and one for Intel Macs (see `vendor/fetch-x86_64-ffmpeg.sh`).

The programs are built with `--enable-gpl` (and include libx264 and libx265),
so FFmpeg in Vortex is licensed under the GNU General Public License. The
Windows program is the 7.1 "essentials" build from
[gyan.dev](https://www.gyan.dev/ffmpeg/builds/), also built with
`--enable-version3`, which makes it GPL version 3. Vortex runs FFmpeg as a
separate program and does not link to it.

To see the exact build configuration of a bundled program, run it with
`-version`. The FFmpeg 7.1 source code is at
https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz and the license terms at
https://ffmpeg.org/legal.html.

## mutagen

mutagen is GPL-2.0-or-later and, unlike FFmpeg, runs inside the app as part
of yt-dlp. The packaged app is therefore distributed under the terms of the
GPL as a whole, while Vortex's own code stays MIT licensed, which the GPL
allows. The source code of everything in the app is public: Vortex at
https://github.com/FarAbove420/vortex and each component at the link above.
