#!/usr/bin/env bash
# remake-media.sh -- the documentation's GIFs and before/after "after" images of the Wheels & Fire
# board family, remade from the current binary: the recipe of each one, so a driver change that moves
# the picture remakes them instead of leaving a picture the driver no longer draws.
#
#   ./scripts/remake-media.sh
#
# The stills have their own manifest (family-captures.py). The "before" images are the original
# driver's and never change. Frames are screen:frame_number()'s, as frame-series.sh names them.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

GIFS=docs/img/gifs
# gif <set> <first frame> <frames> <scale> <file> [lua]: a stretch at real time; the lua drives it
gif() {
    if [ -n "${6:-}" ]; then SERIES_LUA="$6" SCALE="$4" ./scripts/gif.sh "$1" "$2" "$3" "$GIFS/$5"
    else SCALE="$4" ./scripts/gif.sh "$1" "$2" "$3" "$GIFS/$5"; fi
}
gif wheelfir 296  300 2 wheelfir-car.gif
gif wheelfir 1062 402 2 wheelfir-race.gif
gif wheelfir 2727 300 2 wheelfir-records.gif
gif wheelfir 2400 252 1 wheelfir-play.gif scripts/drive.lua
gif pwball   296  300 2 pwball-tv.gif
gif pwball   1395 261 2 pwball-logo.gif
gif pwball   2396 360 2 pwball-demo.gif
gif pwball   1400 252 1 pwball-play.gif scripts/drive.lua
gif kongball 197  300 2 kongball-title.gif
gif kongball 897  300 2 kongball-match.gif
gif kongball 999  252 1 kongball-play.gif scripts/drive.lua

# after <set> <frame> <id>: one frame of the attract, at the screen's native size
WORK=tmp/remake-media
after() {
    ./scripts/frame-series.sh "$1" "$2" "$2" "$WORK" > /dev/null
    cp "$(printf '%s/%s/f%05d.png' "$WORK" "$1" "$2")" "docs/img/before-after/$3-after.png"
}
after wheelfir 474  wheelfir-cars
after wheelfir 1767 wheelfir-sky
after wheelfir 2266 wheelfir-repeated-road
after kongball 196  kongball-title
rm -rf "$WORK"
echo "==> remade; then: uv run scripts/gen-gif-manifest.py, and the before/after manifest's figures"
