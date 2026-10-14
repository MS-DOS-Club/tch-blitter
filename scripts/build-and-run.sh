#!/usr/bin/env bash
# build-and-run.sh -- builds one board sibling under its own SUBTARGET, if it is not built, and opens
# it in a window to play (MAME's red NOT_WORKING warning, where a set has it, waits for a key).
#
#   ./scripts/build-and-run.sh <set> [extra MAME arguments]     e.g. pwball, rltennisa, radendurh
#
# One SUBTARGET per driver gives one binary per driver, side by side in upstream/: passing a second
# source to one SUBTARGET does not work, because the filtered driver list then links against a
# driver it never compiled.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"

SET="${1:?usage: build-and-run.sh <set> [MAME args]. Sets: wheelfir pwball kongball radendur radendurh rltennis rltennisa}"
shift
DRIVER="$(mame_driver_for_set "$SET")"
BIN="$(mame_src_path)/$DRIVER"
if [ ! -x "$BIN" ]; then
    jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
    echo "==> building $DRIVER ($jobs jobs)"
    # REGENIE=1: a SUBTARGET's filtered driver list is cached, and a stale one builds a binary
    # without the machine and without a warning.
    ( cd "$(mame_src_path)" && make SUBTARGET="$DRIVER" SOURCES="src/mame/tch/$DRIVER.cpp" REGENIE=1 -j"$jobs" )
fi
mame_run "$SET" --binary "$BIN" --mode session -- "$@"
