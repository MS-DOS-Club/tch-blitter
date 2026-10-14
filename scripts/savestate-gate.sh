#!/usr/bin/env bash
# savestate-gate.sh -- a save state puts the machine back exactly where it was, which is what a
# driver's MACHINE_SUPPORTS_SAVE promises.
#
#   A) emulate, save at frame FROM, and capture frames FROM..FROM+N;
#   B) a fresh process loads that state and captures the N frames after it.
# B's frames must equal A's FROM+1..FROM+N byte for byte. A fresh process, because a member the
# driver forgot to register keeps its live value across a load inside the same one. The pairing is
# by frame number, which the state carries; B prints the first frame it sees after the load, so a
# save that slipped a frame is refused rather than read as a difference.
#
# It sees what reaches the picture: state the game rewrites before the first visible line, and the
# devices outside the picture (sub cpu, DACs, EEPROM), are beyond it.
#
#   ./scripts/savestate-gate.sh [first_frame] [how_many] [set]     defaults: 900 20 wheelfir
# Exit: 0 green, 1 a frame differs, 2 usage, 3 it could not compare.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"

FROM="${1:-900}"; N="${2:-20}"; SET="${3:-wheelfir}"
case "$FROM$N" in *[!0-9]*|'') echo "usage: $0 [first_frame] [how_many] [set]" >&2; exit 2 ;; esac
[ "$N" -ge 1 ] && [ "$FROM" -ge 1 ] || { echo "usage: $0: both numbers start at 1" >&2; exit 2; }

REFRESH="$(mame_refresh_for_set "$SET")" || exit $?
bound_for() { awk -v f="$1" -v r="$REFRESH" -v s="$2" 'BEGIN { printf "%d", int(f / r) + s }'; }
T="tmp/gate-save"
rm -rf "$T"; mkdir -p "$T/a" "$T/b" "$T/states"

# both passes share the state directory (one saves, the other loads); each starts from a clean
# cfg and NVRAM of its own
launch() {
    mkdir -p "$T/$1/cfg" "$T/$1/nvram"
    mame_run "$SET" --seconds "$3" --lua "$2" --snapshots "$T/$1" -- -state_directory "$T/states" \
        -cfg_directory "$T/$1/cfg" -nvram_directory "$T/$1/nvram" > "$T/$1/mame.log" 2>&1 \
        || echo "  pass $1 exited $? ($T/$1/mame.log)"
}

cat > "$T/a.lua" <<LUA
local p = manager.machine.screens[":screen"]
local saved = false
_G._g = emu.add_machine_frame_notifier(function()
  local f = p:frame_number()
  if not saved and f >= $FROM then saved = true; manager.machine:save("gate") end
  if f >= $FROM and f <= $FROM + $N then manager.machine.video:snapshot() end
end)
LUA
launch a "$T/a.lua" "$(bound_for $((FROM + N)) 3)"
[ -s "$T/states/$SET/gate.sta" ] || { echo "==> INVALID: pass A saved no state ($T/a/mame.log)" >&2; exit 3; }

# The load is asked from the script, not with -state: on a board with no pending timer the -state
# load would land first and restore the autoboot timer as already fired, and the script never runs.
cat > "$T/b.lua" <<LUA
local p = manager.machine.screens[":screen"]
local first = nil
_G._g = emu.add_machine_frame_notifier(function()
  local f = p:frame_number()
  if f < $FROM then return end
  if first == nil then first = f; print(string.format("GATE_FIRST_FRAME_AFTER_LOAD %d", f)) end
  if f <= $FROM + $N then manager.machine.video:snapshot() end
end)
manager.machine:load("gate")
LUA
launch b "$T/b.lua" "$(bound_for $((FROM + N)) 4)"

first="$(sed -n 's/^GATE_FIRST_FRAME_AFTER_LOAD \([0-9]*\)$/\1/p' "$T/b/mame.log" | head -1)"
if [ "$first" != "$((FROM + 1))" ]; then
    echo "==> INVALID: after the load pass B saw frame ${first:-none}, not $((FROM + 1)) ($T/b/mame.log)" >&2
    exit 3
fi

different=0
for i in $(seq 0 $((N - 1))); do
    fa=$(printf "%s/a/%s/%04d.png" "$T" "$SET" "$((i + 1))")
    fb=$(printf "%s/b/%s/%04d.png" "$T" "$SET" "$i")
    [ -f "$fa" ] && [ -f "$fb" ] || { echo "==> INVALID: frame $((FROM + i + 1)) was not captured by both passes" >&2; exit 3; }
    if ! cmp -s "$fa" "$fb"; then
        different=$((different + 1))
        if [ "$different" -le 3 ]; then echo "  frame $((FROM + i + 1)) differs"; fi
    fi
done
echo "$SET: $N frames after a state saved at frame $FROM and loaded in a fresh process; different: $different"
[ "$different" -eq 0 ]
