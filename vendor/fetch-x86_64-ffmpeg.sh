#!/usr/bin/env bash
# Fetch the x86_64 ffmpeg slice used by the macOS universal2 build of Vortex.
#
# imageio-ffmpeg ships per-arch wheels on PyPI rather than as GitHub release
# assets, so we grab the macOS x86_64 wheel and pull the ffmpeg binary out of
# it. The arm64 slice already comes with the imageio-ffmpeg installed in your
# Python environment; this script only covers the Intel half.
#
# Re-run is safe: if the binary is already in place, the script exits cleanly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/ffmpeg-macos-x86_64-v7.1"

WHEEL_URL="https://files.pythonhosted.org/packages/da/58/87ef68ac83f4c7690961bce288fd8e382bc5f1513860fc7f90a9c1c1c6bf/imageio_ffmpeg-0.6.0-py3-none-macosx_10_9_intel.macosx_10_9_x86_64.whl"
WHEEL_INNER_PATH="imageio_ffmpeg/binaries/ffmpeg-macos-x86_64-v7.1"

if [[ -x "$TARGET" ]]; then
    echo "Already present: $TARGET"
    exit 0
fi

TMP_WHEEL="$(mktemp -t iio_ffmpeg_x86.XXXXXX).whl"
trap 'rm -f "$TMP_WHEEL"' EXIT

echo "Downloading imageio-ffmpeg 0.6.0 x86_64 wheel..."
curl -sL -o "$TMP_WHEEL" "$WHEEL_URL"

echo "Extracting $WHEEL_INNER_PATH..."
unzip -p "$TMP_WHEEL" "$WHEEL_INNER_PATH" > "$TARGET"
chmod +x "$TARGET"

echo "Done: $TARGET"
file "$TARGET"
