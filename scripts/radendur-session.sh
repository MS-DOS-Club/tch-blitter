#!/usr/bin/env bash
# radendur-session.sh -- Radical Enduro in a window, one instance at a time.
#
#   ./scripts/radendur-session.sh play              to play, at real speed (make play)
#   ./scripts/radendur-session.sh fast              unthrottled
#   ./scripts/radendur-session.sh debug [--throttle]   with the gdbstub on GDB_PORT (default 23946)
#   ./scripts/radendur-session.sh stop              ends the instance this script started
#
# MACHINE=radendur runs the board's dump, which stops on the prototype's own faults; the default,
# radendurh, plays. `stop` never touches a run this script did not start: the instance is told
# apart by the snapshot directory it is given, or on Windows by the pid kept when it was launched.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/mame_run.sh
. "$SCRIPT_DIR/lib/mame_run.sh"

MACHINE="${MACHINE:-radendurh}"
GDB_PORT="${GDB_PORT:-23946}"
SNAPS=tmp/snap

# session_mark -- the snapshot pair of the command line mame_cmd builds for this session, which is
# what tells our instance apart in ps; read from that line, so a change in how it is spelt there
# cannot leave stop and launch looking for an argument the process no longer carries.
session_mark() {
    local line prev=""
    while IFS= read -r line; do
        [ "$prev" != -snapshot_directory ] || { printf '%s %s\n' "$prev" "$line"; return 0; }
        prev="$line"
    done < <(mame_cmd "$MACHINE" --mode session --snapshots "$SNAPS")
    echo "radendur-session: no -snapshot_directory in the command line of $MACHINE" >&2
    return 1
}
MARK="$(session_mark)"

# ps and not pgrep -f, which on macOS fails outright when any process holds a non-UTF-8 argument.
# MSYS2's ps takes no -o and shows no arguments, so on Windows the instance is the pid and the binary
# launch() kept, and only while that pid is still running that binary.
PIDFILE="$PROJECT_DIR/tmp/session.pid"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) PID_KEPT=1 ;; *) PID_KEPT=0 ;; esac

own_pids() {
    if [ "$PID_KEPT" = 0 ]; then
        ps -Ao pid=,args= | awk -v m="$MARK " 'index($0, m) && $2 != "awk" {print $1}'
        return
    fi
    local pid bin
    [ -f "$PIDFILE" ] || return 0
    IFS=$'\t' read -r pid bin < "$PIDFILE" || return 0
    # COMMAND is the last column and may hold spaces; the row's first number is its pid
    ps -p "$pid" 2>/dev/null | awk -v b=" $bin" 'NR > 1 && substr($0, length($0) - length(b) + 1) == b {
        for (i = 1; i <= NF; i++) if ($i ~ /^[0-9]+$/) { print $i; exit } }'
    return 0
}

# record_instance <pid> -- what own_pids reads back where ps cannot show the snapshot directory
record_instance() {
    [ "$PID_KEPT" = 1 ] || return 0
    local bin
    bin=$(mame_binary_for_set "$MACHINE")
    printf '%s\t%s\n' "$1" "$(cd "$(dirname "$bin")" && pwd)/$(basename "$bin")" > "$PIDFILE"
}

stop() {
    local pids
    pids=$(own_pids)
    if [ -n "$pids" ]; then
        # shellcheck disable=SC2086  # one pid per word
        kill -9 $pids 2>/dev/null || true
        sleep 1
        [ -z "$(own_pids)" ] || { echo "ERROR: still running: $(own_pids | tr '\n' ' ')" >&2; return 1; }
    fi
    rm -f "$PIDFILE"
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
    mkdir -p "$SNAPS"
    while IFS= read -r line; do cmd+=("$line"); done < <(mame_cmd "$MACHINE" \
        --mode session --resolution "$res" --snapshots "$SNAPS" -- -prescale 3 "$@")
    [ "${#cmd[@]}" -gt 0 ] || exit 1
    echo "==> $MACHINE ($log)"
    nohup "${cmd[@]}" > "$log" 2>&1 &
    record_instance "$!"
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
