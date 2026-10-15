# shellcheck shell=bash
# mame_run.sh -- which binary runs each set, and the one MAME command line the scripts launch.
# Sourced, never executed, after lib/mame_src.sh, by scripts that set PROJECT_DIR and run from it.
#
#   mame_run <set> [options] [-- extra MAME arguments]
#     --mode quick     a small unthrottled window for unattended runs (the default); needs --seconds
#     --mode session   a window at real speed for somebody to play, with -log; Wheels & Fire also
#                      loads its game-controller map, ctrlr/gamepad.cfg
#     --seconds <n>    emulated seconds to run (-seconds_to_run)
#     --lua <file>     an autoboot Lua script
#     --snapshots <d>  where snapshots go
#     --expect <n>     fewer than n images under --snapshots is a run that collected nothing: rc 3
#     --resolution <WxH>
#     --binary <path>  another build of the set's binary
#
# A quick run keeps --seconds from 1 to 300 because MAME only skips its red NOT_WORKING warning
# with a run bounded that far (0 means no bound) (src/frontend/mame/ui/ui.cpp, display_startup_screens): above it the
# machine waits for a key that nobody unattended will press. `-video none` is never used: on macOS it
# takes over the whole display instead of opening nothing.

# mame_binary_for_set <set> -- the binary built for that set's driver.
mame_binary_for_set() {
    case "${1:?mame_binary_for_set needs a set}" in
        wheelfir|pwball|kongball|radendur|radendurh) printf '%s\n' "$(mame_src_path)/wheelfir" ;;
        rltennis|rltennisa)       printf '%s\n' "$(mame_src_path)/rltennis" ;;
        *) echo "mame_binary_for_set: unknown set '$1' (radendur radendurh wheelfir pwball kongball rltennis rltennisa)" >&2
           return 2 ;;
    esac
}

# mame_driver_for_set <set> -- the SUBTARGET of a set, which is also its .cpp's basename.
mame_driver_for_set() {
    local bin
    bin="$(mame_binary_for_set "$1")" || return 2
    basename "$bin"
}

# mame_refresh_for_set <set> -- the refresh the binary declares, in Hz, asked of it rather than
# written here, so a capture bound follows the driver's geometry.
mame_refresh_for_set() {
    local bin hz
    bin="$(mame_binary_for_set "$1")" || return 2
    [ -x "$bin" ] || { echo "mame_refresh_for_set: the binary $bin is missing (make setup)" >&2; return 2; }
    hz="$("$bin" -listxml "$1" 2>/dev/null | sed -n 's/.*<display[^>]*refresh="\([0-9][0-9.]*\)".*/\1/p' | head -1)"
    awk -v v="${hz:-0}" 'BEGIN { exit !(v + 0 > 0) }' || { echo "mame_refresh_for_set: $1 declares no refresh" >&2; return 3; }
    printf '%s\n' "$hz"
}

_mame_abs() { case "$1" in /*) printf '%s\n' "$1" ;; *) printf '%s\n' "$PWD/$1" ;; esac; }

# mame_cmd <set> [options] [-- args] -- the command line, one argument per line.
mame_cmd() {
    local set="${1:?mame_cmd needs a set}" mode=quick seconds="" lua="" snaps="" res="" bin=""
    shift
    while [ $# -gt 0 ]; do
        case "$1" in
            --mode)       mode="${2:?}"; shift 2 ;;
            --seconds)    seconds="${2:?}"; shift 2 ;;
            --lua)        lua="$(_mame_abs "${2:?}")"; shift 2 ;;
            --snapshots)  snaps="$(_mame_abs "${2:?}")"; shift 2 ;;
            --resolution) res="${2:?}"; shift 2 ;;
            --binary)     bin="${2:?}"; shift 2 ;;
            --expect)     shift 2 ;;
            --)           shift; break ;;
            *) echo "mame_run: unknown option $1" >&2; return 2 ;;
        esac
    done
    [ -n "$bin" ] || bin="$(mame_binary_for_set "$set")" || return 2
    [ -x "$bin" ] || { echo "mame_run: the binary $bin is missing (make setup)" >&2; return 1; }
    local args=()
    # a quick run's window opens behind the others on macOS instead of taking the focus
    [ "$mode" != quick ] || args=(env SDL_MAC_BACKGROUND_APP=1)
    # -inipath keeps a mame.ini of the user's (~/.mame, the working directory) out of the run
    args+=("$bin" "$set" -skip_gameinfo -rompath "$PROJECT_DIR/run/mame_roms" -inipath "$PROJECT_DIR/run"
        -window -nomaximize)
    case "$mode" in
        quick)
            case "$seconds" in ''|*[!0-9]*) echo "mame_run: --mode quick needs --seconds" >&2; return 2 ;; esac
            [ "$seconds" -ge 1 ] && [ "$seconds" -le 300 ] || { echo "mame_run: --seconds $seconds would leave MAME on its red warning; keep it from 1 to 300" >&2; return 2; }
            args+=(-resolution "${res:-320x240}" -nothrottle -seconds_to_run "$seconds") ;;
        session)
            # the drivers log through logerror, as MAME's C++ guide asks, so a played run keeps its
            # log: error.log in the working directory says, among other things, which scale law ran
            args+=(-resolution "${res:-960x720}" -log)
            # MAME stops on a controller file with no section for the set, so only the set it maps
            # loads it
            [ "$set" != wheelfir ] || args+=(-ctrlrpath "$PROJECT_DIR/ctrlr" -ctrlr gamepad)
            [ -z "$seconds" ] || args+=(-seconds_to_run "$seconds") ;;
        *) echo "mame_run: unknown mode $mode (quick or session)" >&2; return 2 ;;
    esac
    [ -z "$lua" ] || args+=(-autoboot_script "$lua")
    [ -z "$snaps" ] || args+=(-snapshot_directory "$snaps")
    printf '%s\n' "${args[@]}" "$@"
}

# mame_run <set> [options] [-- args] -- runs it; MAME's exit code, or 3 when --expect was not met.
mame_run() {
    local set="${1:?mame_run needs a set}" expect="" snaps="" a line
    local -a cmd=()
    for ((a = 2; a <= $#; a++)); do
        case "${!a}" in
            --) break ;;
            --expect) a=$((a + 1)); expect="${!a}" ;;
            --snapshots) a=$((a + 1)); snaps="${!a}" ;;
        esac
    done
    while IFS= read -r line; do cmd+=("$line"); done < <(mame_cmd "$@")
    [ "${#cmd[@]}" -gt 0 ] || return 2
    [ -z "$snaps" ] || mkdir -p "$snaps"
    local rc=0
    "${cmd[@]}" || rc=$?
    if [ -n "$expect" ]; then
        local got
        got=$(find "$snaps" -name '*.png' | wc -l | tr -d ' ')
        if [ "$got" -lt "$expect" ]; then
            echo "mame_run: $set collected $got of $expect images in $snaps (MAME rc $rc)" >&2
            return 3
        fi
        return 0
    fi
    return "$rc"
}
