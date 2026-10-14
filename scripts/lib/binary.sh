# shellcheck shell=bash
# binary.sh -- which binary a run executes, and a warning when its driver source is newer: a failed
# build leaves the previous binary in place, and the next run would test old code without saying so.
# Needs lib/mame_src.sh sourced first.

binary_identity() {
    local bin="$1" source="${2:-}"
    [ -x "$bin" ] || { echo "  binary: MISSING $bin"; return; }
    echo "  binary: $bin ($(date -r "$bin" '+%Y-%m-%d %H:%M' 2>/dev/null || echo '?'))"
    if [ -n "$source" ] && [ -f "$source" ] && [ "$source" -nt "$bin" ]; then
        echo "  WARNING: $source is newer than the binary: rebuild before trusting this run"
    fi
}

source_of_binary() {
    case "$1" in
        *wheelfir) echo "$(mame_src_path)/src/mame/tch/wheelfir.cpp" ;;
        *rltennis) echo "$(mame_src_path)/src/mame/tch/rltennis.cpp" ;;
    esac
}
