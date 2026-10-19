#!/usr/bin/env bash
# radendur-goldens.sh -- Radical Enduro's goldens: the boot, the race start and, on radendurh, two
# frames of the desert race, against goldens/<set>/checksums.sha256.
#
#   ./scripts/radendur-goldens.sh verify [set]   exit 1 if any capture differs
#   ./scripts/radendur-goldens.sh bless [set]    rewrites the baseline
#
# The set is radendurh (the default, the one that plays) or radendur (the dump, whose baseline is
# where it stops). A FAIL means the boot state changed: a regression, or the boot getting further
# (re-bless with make goldens); goldens/README.md says how to tell.
set -euo pipefail

usage() { echo "Use: $0 verify|bless [radendurh|radendur]" >&2; exit 2; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
case "$1" in verify|bless) GMODE="$1" ;; *) usage ;; esac
MACHINE="${2-radendurh}"
case "$MACHINE" in radendurh|radendur) ;; *) usage ;; esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"
# shellcheck source=lib/binary.sh
. "$SCRIPT_DIR/lib/binary.sh"

GOLDENS="goldens/$MACHINE"
REFRESH="$(mame_refresh_for_set "$MACHINE")"
binary_identity "$(mame_binary_for_set "$MACHINE")" "$(source_of_binary "$(mame_binary_for_set "$MACHINE")")"
WORK="tmp/goldens-$GMODE-$MACHINE"
LABELED="$WORK/labeled"
# the passes share cfg and nvram: the race and scenery scenes are reached by navigating after boot
CFG="$WORK/cfg"; NVRAM="$WORK/nvram"
rm -rf "$WORK"; mkdir -p "$LABELED" "$CFG" "$NVRAM"

# pass <tag> <seconds> <lua> <expected images>, with the harness's environment before the call
pass() {
    local rc=0
    mkdir -p "$WORK/$1"
    mame_run "$MACHINE" --seconds "$2" --lua "$3" --snapshots "$WORK/$1" --expect "$4" \
        -- -snapname '%i' -cfg_directory "$CFG" -nvram_directory "$NVRAM" > "$WORK/$1.log" 2>&1 || rc=$?
    if [ "$rc" != 0 ]; then
        echo "FAIL: the $1 pass exited $rc; nothing is blessed or compared ($WORK/$1.log):"
        cat "$WORK/$1.log"; exit 1
    fi
}

# The boot: the end of the SATOR logo's fade, then 5, 10 and 15 seconds.
ORACLE_FRAMES="${ORACLE_FRAMES:-180,300,600,900}"; export ORACLE_FRAMES
LABELS=(00_sator_3s 01_boot_5s 02_boot_10s 03_boot_15s)
pass boot 250 scripts/radendur/oracle.lua "${#LABELS[@]}"
for i in "${!LABELS[@]}"; do cp "$(printf "%s/boot/%04d.png" "$WORK" "$i")" "$LABELED/${LABELS[$i]}.png"; done

# shot <tag> <seconds> <lua> <proof> <label>: one scene, kept only if the harness logged the line
# that proves where it was ($OUT, set by the caller).
shot() {
    pass "$1" "$2" "$3" 1
    grep -q "$4" "$OUT" || { echo "FAIL: the $1 harness did not log \`$4\` ($OUT)"; exit 1; }
    cp "$WORK/$1/0000.png" "$LABELED/$5.png"; LABELS+=("$5")
}

# The race: the desert's starting line, bike stopped; nav-phase.lua checks the section in RAM.
OUT="$PROJECT_DIR/$WORK/race.harness.log" shot race 60 scripts/radendur/nav-phase.lua "^START ok" 04_race_start

# Mid-race, radendurh only (the dump stops on its faults): a frame of the desert race, accepted
# only where the game's view origin says it is; drive.lua's inputs are pinned because they decide
# where the bike is at that frame.
scenery() {
    SHOT_FRAME="$2" COIN_FRAME=200 START_FRAME=320 STEER=1 OUT="$PROJECT_DIR/$WORK/$1.harness.log" \
        shot "$1" "$(awk -v f="$2" -v r="$REFRESH" 'BEGIN { printf "%d", int(f / r) + 5 }')" \
            scripts/radendur/scenery-shot.lua "^SHOT f=$2 view $3\$" "$4"
}
if [ "$MACHINE" = radendurh ]; then
    scenery scenery 2025 "x=27 y=860" 05_desert_scenery
    scenery descent 1800 "x=5 y=869" 06_desert_descent
fi

if [ "$GMODE" = bless ]; then
    mkdir -p "$GOLDENS"; : > "$GOLDENS/checksums.sha256"
    for label in "${LABELS[@]}"; do
        cp "$LABELED/$label.png" "$GOLDENS/$label.png"
        ( cd "$GOLDENS" && shasum -a 256 "$label.png" ) >> "$GOLDENS/checksums.sha256"
    done
    echo "==> ${#LABELS[@]} goldens blessed in $GOLDENS/"
    exit 0
fi

pass_n=0; fail_n=0
for label in "${LABELS[@]}"; do
    expected=$(awk -v f="$label.png" '$2 == f {print $1}' "$GOLDENS/checksums.sha256")
    actual=$(shasum -a 256 "$LABELED/$label.png" | awk '{print $1}')
    if [ -n "$expected" ] && [ "$actual" = "$expected" ]; then
        pass_n=$((pass_n + 1)); echo "  PASS $label"
    else
        fail_n=$((fail_n + 1)); echo "  FAIL $label (expected ${expected:-nothing in the baseline}, got $actual)"
    fi
done
echo "==> $pass_n/${#LABELS[@]} PASS"
[ "$fail_n" -eq 0 ]
