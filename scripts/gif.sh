#!/usr/bin/env bash
# gif.sh -- a stretch of a game's frames as an animated GIF for the documentation, at real time.
#
# frame-series.sh captures the exact frames; this converts them with a palette computed over the
# whole stretch (the board already works in 256 colours, so a generic quantisation ruins its
# gradients), keeps one frame every whole number of emulated frames near FPS, and plays them at the
# binary's declared refresh over that step, so the GIF runs at real time. The size is printed, and
# MAX_MB makes it a limit.
#
#   ./scripts/gif.sh <set> <first_frame> <n_frames> <out.gif>
#   Env: FPS (20, the target), SCALE (2), MAX_MB (4).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
# shellcheck source=lib/mame_src.sh
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"

usage() { echo "Use: $0 <set> <first_frame> <n_frames> <out.gif>" >&2; exit 2; }
[ "$#" -eq 4 ] || usage
SET="$1"; FROM="$2"; N="$3"; DEST="$4"
case "$FROM:$N" in *[!0-9:]*|:*|*:) usage ;; esac

FPS="${FPS:-20}"
SCALE="${SCALE:-2}"
MAX_MB="${MAX_MB:-4}"

command -v ffmpeg >/dev/null || { echo "ffmpeg is missing (brew install ffmpeg)" >&2; exit 1; }
[ "$N" -ge 2 ] || { echo "a GIF of fewer than two frames is not a GIF" >&2; exit 1; }
case "$FPS" in ''|*[!0-9]*|0) echo "FPS=$FPS is not a positive whole number" >&2; exit 2 ;; esac

# From the board's rate to the GIF's pace: one of every `step` is taken, and played at hz/step.
# Asked before the capture, so a binary that declares no rate costs nothing.
HZ="$(mame_refresh_for_set "$SET")" || exit 3
step=$(awk -v h="$HZ" -v f="$FPS" 'BEGIN{ s = int(h / f + 0.5); print (s < 1 ? 1 : s) }')
OUT_FPS=$(awk -v h="$HZ" -v s="$step" 'BEGIN{ printf "%.6f", h / s }')

WORK="tmp/gif-$SET-$FROM"
TO=$(( FROM + N - 1 ))

echo "==> $SET, frames $FROM..$TO -> $DEST"
"$SCRIPT_DIR/frame-series.sh" "$SET" "$FROM" "$TO" "$WORK" >/dev/null

CAPTURES="$WORK/$SET"
n_png=$(find "$CAPTURES" -name '*.png' | wc -l | tr -d ' ')
# The capture script already fails if frames are missing, but this is what separates "it converted
# few" from "it converted the ones there were": without counting here, a half stretch comes out as
# a short and correct-looking GIF.
[ "$n_png" -eq "$N" ] || { echo "INVALID: $n_png captures of the $N asked for" >&2; exit 1; }

mkdir -p "$(dirname "$DEST")"
PALETTE="$WORK/palette.png"

filter="select=not(mod(n\,$step)),scale=iw*$SCALE:ih*$SCALE:flags=neighbor"
ffmpeg -y -loglevel error -framerate "$HZ" -pattern_type glob -i "$CAPTURES/*.png" \
    -vf "$filter,palettegen=max_colors=256:stats_mode=diff" "$PALETTE"
ffmpeg -y -loglevel error -framerate "$HZ" -pattern_type glob -i "$CAPTURES/*.png" -i "$PALETTE" \
    -lavfi "$filter [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3" \
    -loop 0 -r "$OUT_FPS" "$DEST"

bytes=$(wc -c < "$DEST" | tr -d ' ')
mb=$(echo "scale=1; $bytes/1048576" | bc)
echo "    $DEST: ${mb} MB, $(( (N + step - 1) / step )) frames at ${OUT_FPS} fps (${HZ} Hz / ${step}), x${SCALE}"
rm -rf "$WORK"

# The limit is HARD on purpose: if a GIF goes over, the decision (trim the stretch, lower the fps
# or the scale) is taken by whoever is making it, not by the repository a year from now.
if [ "$(echo "$mb > $MAX_MB" | bc)" -eq 1 ]; then
    echo "==> TOO BIG: ${mb} MB is over MAX_MB=${MAX_MB}. Trim the stretch or lower FPS/SCALE." >&2
    exit 1
fi
