#!/usr/bin/env bash
# radendur-session.sh -- Radical Enduro in a window, one instance at a time.
#
#   ./scripts/radendur-session.sh play              to play, at real speed (make play)
#   ./scripts/radendur-session.sh fast              unthrottled
#   ./scripts/radendur-session.sh debug [--throttle]   with the gdbstub on GDB_PORT (default 23946)
#   ./scripts/radendur-session.sh stop              ends the instance this script started
#
# MACHINE=radendur runs the board's dump, which stops on the prototype's own faults; the default,
# radendurv2, plays. The instances this script starts are told apart from any other MAME by the
# snapshot directory it gives them, so `stop` never touches a run it did not start.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"

MACHINE="${MACHINE:-radendurv2}"
GDB_PORT="${GDB_PORT:-23946}"
MARK="-snapshot_directory $PROJECT_DIR/tmp/snap"

# ps and not pgrep -f, which on macOS fails outright when any process holds a non-UTF-8 argument
own_pids() { ps -Ao pid=,args= | awk -v m="$MARK " 'index($0, m) && $2 != "awk" {print $1}'; }

stop() {
    local pids
    pids=$(own_pids)
    [ -z "$pids" ] && return 0
    # shellcheck disable=SC2086  # one pid per word
    kill -9 $pids 2>/dev/null || true
    sleep 1
    [ -z "$(own_pids)" ] || { echo "ERROR: still running: $(own_pids | tr '\n' ' ')" >&2; return 1; }
}

# a window at 3/4 of the main display on macOS, 1280x960 elsewhere
play_resolution() {
    local w h
    read -r w h < <(system_profiler SPDisplaysDataType 2>/dev/null | awk '/Resolution:/ {print $2, $4; exit}') || true
    case "${w:-}${h:-}" in ''|*[!0-9]*) echo 1280x960 ;; *) echo "$((w * 3 / 4))x$((h * 3 / 4))" ;; esac
}

# launch <log> <resolution> [MAME flags...]
launch() {
    local log="tmp/$1" res="$2" cmd=() line
    shift 2
    stop
    mkdir -p tmp/snap
    while IFS= read -r line; do cmd+=("$line"); done < <(mame_cmd "$MACHINE" \
        --mode session --resolution "$res" --snapshots tmp/snap -- -prescale 3 "$@")
    [ "${#cmd[@]}" -gt 0 ] || exit 1
    echo "==> $MACHINE ($log)"
    nohup "${cmd[@]}" > "$log" 2>&1 &
    disown
    for _ in 1 2 3 4 5 6 7 8 9 10; do [ -n "$(own_pids)" ] && break; sleep 1; done
    [ -n "$(own_pids)" ] || { echo "ERROR: MAME did not start; $log says:"; tail -20 "$log"; exit 1; }
    echo "    running (pid $(own_pids | head -1)). Stop it with: $0 stop"
}

case "$#:${1:-}:${2:-}" in
    1:stop:)  stop; echo "OK -- nothing of ours running" ;;
    1:play:)  launch mame-play.log "$(play_resolution)" -keepaspect ;;
    1:fast:)  launch mame-fast.log 640x480 -nothrottle ;;
    1:debug:) launch mame-debug.log 640x480 -debug -debugger gdbstub -debugger_port "$GDB_PORT" -nothrottle ;;
    2:debug:--throttle) launch mame-debug.log 640x480 -debug -debugger gdbstub -debugger_port "$GDB_PORT" ;;
    *) echo "Use: $0 stop | play | fast | debug [--throttle]" >&2; exit 2 ;;
esac
