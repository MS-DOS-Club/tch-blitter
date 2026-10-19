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
#
# A scene behind a control (the service mode's screens) holds it with "press <frame> <frames> <value>
# <port> <field>" lines, on the same frame count as the scenes: the field is held at that value from
# that frame for that many and then given back, so a key is pressed once and a wheel or pedal returns
# to rest; a field the set lacks fails the run. An analog value is the one the port reads
# (lib/analog.lua).
#
# A set whose sound CPU writes its DACs also declares "sound <cpu> <frames> <dac>..." there: the run
# that captures the scenes takes a CRC-32 of those writes over its first <frames> (lib/sound_crc.lua),
# and a second boot on the EEPROM the first one left takes it again, because a board that has run
# before boots that way, and Power Ball's sound once died only there. Both lines are compared with
# goldens/<set>/sound.crc.
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
    FRAMES=$(scenes_of "$CONF" | awk '{print $1}' | tr '\n' ' ')
    LAST=$(scenes_of "$CONF" | awk 'END {print $1}')
    REFRESH="$(mame_refresh_for_set "$SET")"
    SECONDS_TO_RUN=$(awk -v f="$LAST" -v r="$REFRESH" 'BEGIN { printf "%d", int(f / r) + 3 }')
    SOUND=$(awk '$1 == "sound" { $1 = ""; print; exit }' "$CONF")
    : > "$WORK/capture.lua"
    if [ -n "$SOUND" ]; then
        read -r SOUND_CPU SOUND_FRAMES SOUND_DACS <<< "$SOUND"
        if [ "$SOUND_FRAMES" -gt "$LAST" ]; then
            echo "  $SET: the sound window ($SOUND_FRAMES frames) outlasts the last scene ($LAST)"
            fail=$((fail + 1)); continue
        fi
        # paths relative to the repository, where MAME runs: a Windows MAME reads no MSYS2 path
        sound_lua() { # sound_lua <out file>
            printf 'dofile("scripts/lib/sound_crc.lua")\nsound_crc("%s", { %s }, %s, "%s")\n' \
                "$SOUND_CPU" "$(echo "$SOUND_DACS" | tr ' ' ',')" "$SOUND_FRAMES" "$1"
        }
        sound_lua "$WORK/sound-cold.txt" > "$WORK/capture.lua"
    fi
    # a press is refused here when a number is not one or it would end after the run does
    BAD_PRESS=$(awk -v last="$LAST" '$1 == "press" && ($2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ ||
        $4 !~ /^[0-9]+$/ || NF < 6 || $2 + $3 > last) { print; exit }' "$CONF")
    if [ -n "$BAD_PRESS" ]; then
        echo "  $SET: a press line is malformed or outlasts the last scene ($LAST): $BAD_PRESS"
        fail=$((fail + 1)); continue
    fi
    PRESSES=$(awk '$1 == "press" { f = $6; for (i = 7; i <= NF; i++) f = f " " $i
        printf "{ %d, %d, %d, \"%s\", \"%s\" },\n", $2, $3, $4, $5, f }' "$CONF")
    cat >> "$WORK/capture.lua" <<LUA
local target = {}
for f in string.gmatch("$FRAMES", "%d+") do target[tonumber(f)] = true end
local presses = { $PRESSES }
-- the presses grouped by field, keyed by name: each lookup of a field returns a new Lua object, so
-- keyed by the object two presses of one field would each release the other
local held = {}
for _, p in ipairs(presses) do
  local port = manager.machine.ioport.ports[p[4]]
  local field = port and port.fields[p[5]]
  local why = not field and "no such field"
      or (field.is_analog and (p[3] < field.minvalue or p[3] > field.maxvalue) and "value out of range")
  if why then
    emu.print_error("__GOLDEN INVALID: " .. why .. ": " .. p[4] .. " " .. p[5] .. " " .. p[3])
    manager.machine:exit()
    return
  end
  local key = p[4] .. " " .. p[5]
  held[key] = held[key] or { field = field }
  table.insert(held[key], p)
end
dofile("scripts/lib/analog.lua")
local function hold(field, value)
  if field.is_analog then analog_hold(field, value) else field:set_value(value) end
end
local n = 0
_G._g = emu.add_machine_frame_notifier(function()
  n = n + 1
  for _, group in pairs(held) do
    local value
    for _, p in ipairs(group) do if n >= p[1] and n < p[1] + p[2] then value = p[3] end end
    if value then hold(group.field, value) else group.field:clear_value() end
  end
  if target[n] then manager.machine.video:snapshot() end
end)
LUA
    rc=0
    mame_run "$SET" --seconds "$SECONDS_TO_RUN" --lua "$WORK/capture.lua" --snapshots "$WORK" \
        --isolate "$WORK" > "$WORK/mame.log" 2>&1 || rc=$?
    if [ "$rc" != 0 ]; then echo "  $SET: the run exited $rc:"; cat "$WORK/mame.log"; fi

    i=0; blessed=0; missing=0
    while read -r frame name _; do
        png=$(printf "%s/%s/%04d.png" "$WORK" "$SET" "$i"); i=$((i + 1))
        if [ ! -f "$png" ]; then
            echo "  $SET: no capture of frame $frame"; fail=$((fail + 1)); missing=1
        elif [ "$MODE" = bless ]; then
            cp "$png" "goldens/$SET/$name.png"; blessed=$((blessed + 1)); ok=$((ok + 1))
        elif cmp -s "$png" "goldens/$SET/$name.png"; then
            ok=$((ok + 1))
        else
            echo "  $SET/$name: DIFFERS (goldens/$SET/$name.actual.png)"
            cp "$png" "goldens/$SET/$name.actual.png"; fail=$((fail + 1))
        fi
    done < <(scenes_of "$CONF")
    # the harness says why it stopped the run, and the log goes with the work directory
    [ "$missing" = 0 ] || grep -E 'INVALID|LUA ERROR' "$WORK/mame.log" | sed 's/^/    /' || true
    if [ -n "$SOUND" ]; then
        sound_lua "$WORK/sound-warm.txt" > "$WORK/warm.lua"
        WARM_SECONDS=$(awk -v f="$SOUND_FRAMES" -v r="$REFRESH" 'BEGIN { printf "%d", int(f / r) + 3 }')
        rc=0
        mame_run "$SET" --seconds "$WARM_SECONDS" --lua "$WORK/warm.lua" --isolate "$WORK" \
            > "$WORK/warm.log" 2>&1 || rc=$?
        if [ "$rc" != 0 ]; then echo "  $SET: the warm boot exited $rc:"; cat "$WORK/warm.log"; fi
        actual=""; missing=0
        for boot in cold warm; do
            line=$(cat "$WORK/sound-$boot.txt" 2>/dev/null || echo "no result")
            case "$line" in crc=*" writes="[1-9]*) ;; *) echo "  $SET: $boot boot's sound NOT examined ($line)"; fail=$((fail + 1)); missing=1; continue ;; esac
            actual+="$boot $line"$'\n'
        done
        # a boot not examined is already counted, and neither compared nor blessed half
        if [ "$missing" = 1 ]; then
            :
        elif [ "$MODE" = bless ]; then
            printf '%s' "$actual" > "goldens/$SET/sound.crc"
        elif [ ! -f "goldens/$SET/sound.crc" ]; then
            echo "  $SET/sound: no goldens/$SET/sound.crc to compare with (bless first)"; fail=$((fail + 1))
        elif [ "$actual" = "$(cat "goldens/$SET/sound.crc")"$'\n' ]; then
            ok=$((ok + 1))
        else
            echo "  $SET/sound: DIFFERS from goldens/$SET/sound.crc; this run:"; printf '%s' "$actual" | sed 's/^/    /'
            fail=$((fail + 1))
        fi
    fi
    if [ "$MODE" = bless ]; then
        rm -f "goldens/$SET"/*.actual.png
        ( cd "goldens/$SET" && shasum -a 256 ./*.png > checksums.sha256 )
        echo "  $SET: blessed $blessed scenes"
    fi
done

if [ $((ok + fail)) -eq 0 ]; then echo "==> INVALID: no scene was examined" >&2; exit 3; fi
if [ "$MODE" = verify ]; then echo "==> $ok PASS, $fail FAIL"; else echo "==> $ok blessed, $fail NOT blessed"; fi
[ "$fail" -eq 0 ]
