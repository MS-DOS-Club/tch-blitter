#!/usr/bin/env bash
# goldens-family.sh -- the visual gate of the board siblings (Radical Enduro has radendur-goldens.sh,
# because its scenes are reached by navigating a menu).
#
#   ./scripts/goldens-family.sh verify [set...]   compares against goldens/<set>/
#   ./scripts/goldens-family.sh bless  [set...]   (re)blesses
#
# Each set declares its scenes in goldens/<set>/scenes.conf, one "<frame> <name> <why>" per line: the
# attract is deterministic from a clean NVRAM, so fixed frames reached without touching a control are
# enough. It runs unthrottled; the throttle only paces the wall clock, the frames are the same.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"
# shellcheck source=lib/binary.sh
. "$SCRIPT_DIR/lib/binary.sh"

usage() { echo "Use: $0 verify|bless [set...]" >&2; exit 2; }
[ "$#" -ge 1 ] || usage
MODE="$1"; shift
case "$MODE" in verify|bless) ;; *) usage ;; esac
for s in "$@"; do mame_binary_for_set "$s" >/dev/null || usage; done
SETS="${*:-wheelfir pwball kongball rltennis rltennisa}"

mkdir -p tmp
WORKS=()
trap '[ "${#WORKS[@]}" -eq 0 ] || rm -rf "${WORKS[@]}"' EXIT

# the scenes of a conf, by increasing frame, which is the order MAME numbers its snapshots in
scenes_of() { awk '/^[0-9]+[[:space:]]/' "$1" | sort -n; }

ok=0; fail=0
for SET in $SETS; do
    CONF="goldens/$SET/scenes.conf"
    BIN="$(mame_binary_for_set "$SET")"
    if [ ! -f "$CONF" ] || [ ! -x "$BIN" ]; then
        echo "  $SET: NOT examined (no $CONF, or no $(basename "$BIN"): make setup)"
        fail=$((fail + 1)); continue
    fi
    binary_identity "$BIN" "$(source_of_binary "$BIN")"
    WORK=$(mktemp -d "tmp/goldens-$SET.XXXXXX"); WORKS+=("$WORK")
    mkdir -p "$WORK/cfg" "$WORK/nvram"
    FRAMES=$(scenes_of "$CONF" | awk '{print $1}' | tr '\n' ' ')
    LAST=$(scenes_of "$CONF" | awk 'END {print $1}')
    REFRESH="$(mame_refresh_for_set "$SET")"
    SECONDS_TO_RUN=$(awk -v f="$LAST" -v r="$REFRESH" 'BEGIN { printf "%d", int(f / r) + 3 }')
    cat > "$WORK/capture.lua" <<LUA
local target = {}
for f in string.gmatch("$FRAMES", "%d+") do target[tonumber(f)] = true end
local n = 0
_G._g = emu.add_machine_frame_notifier(function()
  n = n + 1
  if target[n] then manager.machine.video:snapshot() end
end)
LUA
    rc=0
    mame_run "$SET" --seconds "$SECONDS_TO_RUN" --lua "$WORK/capture.lua" --snapshots "$WORK" \
        -- -cfg_directory "$WORK/cfg" -nvram_directory "$WORK/nvram" > "$WORK/mame.log" 2>&1 || rc=$?
    if [ "$rc" != 0 ]; then echo "  $SET: the run exited $rc:"; cat "$WORK/mame.log"; fi

    i=0; blessed=0
    while read -r frame name _; do
        png=$(printf "%s/%s/%04d.png" "$WORK" "$SET" "$i"); i=$((i + 1))
        if [ ! -f "$png" ]; then
            echo "  $SET: no capture of frame $frame"; fail=$((fail + 1))
        elif [ "$MODE" = bless ]; then
            cp "$png" "goldens/$SET/$name.png"; blessed=$((blessed + 1)); ok=$((ok + 1))
        elif cmp -s "$png" "goldens/$SET/$name.png"; then
            ok=$((ok + 1))
        else
            echo "  $SET/$name: DIFFERS (goldens/$SET/$name.actual.png)"
            cp "$png" "goldens/$SET/$name.actual.png"; fail=$((fail + 1))
        fi
    done < <(scenes_of "$CONF")
    if [ "$MODE" = bless ]; then
        rm -f "goldens/$SET"/*.actual.png
        ( cd "goldens/$SET" && shasum -a 256 ./*.png > checksums.sha256 )
        echo "  $SET: blessed $blessed scenes"
    fi
done

if [ $((ok + fail)) -eq 0 ]; then echo "==> INVALID: no scene was examined" >&2; exit 3; fi
if [ "$MODE" = verify ]; then echo "==> $ok PASS, $fail FAIL"; else echo "==> $ok blessed, $fail NOT blessed"; fi
[ "$fail" -eq 0 ]
