#!/usr/bin/env bash
# frame-series.sh -- captures a run of consecutive frames of one set, which is what shows a flicker
# the goldens' isolated instants cannot.
#
#   ./scripts/frame-series.sh <set> <first_frame> <last_frame> <out_dir>
#
# Frames are named f<NNNNN>.png after screen:frame_number(), so they line up with any other log the
# emulator writes. The frame notifier counts one ahead of that number: scene "1100" of a scenes.conf
# is frame 1099 here.
#   SERIES_LUA=<file>        another harness run first (a coin and START, to reach a race)
#   SERIES_RESOLUTION=<WxH>  the window's size; the capture is the screen at its native size anyway
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"
# shellcheck source=lib/binary.sh
. "$SCRIPT_DIR/lib/binary.sh"

usage() { echo "Use: $0 <set> <first_frame> <last_frame> <out_dir>" >&2; exit 2; }
[ "$#" -eq 4 ] || usage
SET="$1"; FROM="$2"; TO="$3"; DEST="$4"
case "$FROM:$TO" in *[!0-9:]*|:*|*:) usage ;; esac
[ "$TO" -ge "$FROM" ] || usage
BIN="$(mame_binary_for_set "$SET")" || usage
case "$DEST" in /*) WORK="$DEST" ;; *) WORK="$PROJECT_DIR/$DEST" ;; esac
rm -rf "$WORK"; mkdir -p "$WORK/cfg" "$WORK/nvram"

echo "  series $SET $FROM..$TO -> $DEST"
binary_identity "$BIN" "$(source_of_binary "$BIN")"

if [ -n "${SERIES_LUA:-}" ]; then cat "$SERIES_LUA" > "$WORK/capture.lua"; else : > "$WORK/capture.lua"; fi
cat >> "$WORK/capture.lua" <<LUA
local from, to = $FROM, $TO
local screen = manager.machine.screens[":screen"]
_G._series = emu.add_machine_frame_notifier(function()
  local f = screen:frame_number()
  if f >= from and f <= to then manager.machine.video:snapshot() end
end)
LUA

REFRESH="$(mame_refresh_for_set "$SET")"
SECONDS_TO_RUN=$(awk -v f="$TO" -v r="$REFRESH" 'BEGIN { printf "%d", int(f / r) + 3 }')
expected=$((TO - FROM + 1))
rc=0
mame_run "$SET" --seconds "$SECONDS_TO_RUN" --lua "$WORK/capture.lua" --snapshots "$WORK" \
    --expect "$expected" --resolution "${SERIES_RESOLUTION:-320x240}" \
    -- -cfg_directory "$WORK/cfg" -nvram_directory "$WORK/nvram" > "$WORK/mame.log" 2>&1 || rc=$?
[ "$rc" = 0 ] || { echo "FAIL: the run exited $rc ($WORK/mame.log)" >&2; exit "$rc"; }

# MAME adds one snapshot of its own when -seconds_to_run ends; the requested frames are the first ones
n=0
for f in "$WORK/$SET"/*.png; do
    if [ "$n" -lt "$expected" ]; then mv "$f" "$(printf '%s/%s/f%05d.png' "$WORK" "$SET" $((FROM + n)))"
    else rm -f "$f"; fi
    n=$((n + 1))
done
echo "==> $expected frames in $DEST/$SET/ (frames $FROM..$TO)"
