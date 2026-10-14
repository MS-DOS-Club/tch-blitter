#!/usr/bin/env bash
# setup-mame.sh -- builds this repository's MAME: clones MAME at the pinned commit into upstream/,
# applies patches/, builds one binary per driver (radendu for radendur.cpp, wheelfir for wheelfir,
# pwball and kongball, rltennis for rltennis and rltennisa), builds radendurv2's ROM from the
# radendur dump, and checks every binary lists its sets. Run again, it skips what is done.
#
#   ./scripts/setup-mame.sh            make setup
#   ./scripts/setup-mame.sh --doctor   make doctor: what this machine is missing; changes nothing
#   ./scripts/setup-mame.sh --force    rebuilds the binaries even when they look built
#   ./scripts/setup-mame.sh --yes      clones without asking
#
# The romsets are not distributed: they go in run/mame_roms/ first (README, Getting started).
set -euo pipefail

MAME_REPO="https://github.com/mamedev/mame"
# <subtarget>:<source>:<sets its binary lists>; radendur is the driver whose two names differ
MAME_TARGETS="radendu:src/mame/tch/radendur.cpp:radendur,radendurv2
wheelfir:src/mame/tch/wheelfir.cpp:wheelfir,pwball,kongball
rltennis:src/mame/tch/rltennis.cpp:rltennis,rltennisa"
# the one set built here rather than dumped
BUILT_SET="radendurv2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
. "$SCRIPT_DIR/lib/jdk.sh"

die()  { printf "ERROR: %s\n" "$*" >&2; exit 1; }
info() { printf "==> %s\n" "$*"; }
ok()   { printf "  OK   %s\n" "$*"; }
miss() { printf "  MISSING %s\n" "$*"; missing=$((missing + 1)); }
note() { printf "  --   %s\n" "$*"; }

target_bin() { printf "%s\n" "$MAME_SRC/$1"; }

dumped_sets() {
    local _a _b sets set
    while IFS=: read -r _a _b sets; do
        for set in ${sets//,/ }; do [ "$set" = "$BUILT_SET" ] || printf "%s\n" "$set"; done
    done <<< "$MAME_TARGETS"
}

# doctor: everything a build needs, reported whole; it returns how many things are missing
doctor() {
    missing=0
    info "Tools"
    if echo '#include <type_traits>' | clang++ -x c++ -c -o /dev/null - >/dev/null 2>&1; then ok "a C++ compiler (clang++)"
    else miss "a C++ compiler: clang++ cannot build (macOS: xcode-select --install; Linux: g++)"; fi
    if python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then ok "Python >= 3.11"
    else miss "Python >= 3.11"; fi
    local cmd
    for cmd in uv git make unzip shasum shellcheck; do
        if command -v "$cmd" >/dev/null 2>&1; then ok "$cmd"; else miss "$cmd"; fi
    done

    info "MAME at $MAME_SRC"
    if [ ! -d "$MAME_SRC/.git" ]; then
        miss "the checkout (make setup clones it)"
    else
        local head target bin
        if head=$(pinned_commit_state "$MAME_SRC"); then ok "at the pinned commit ${MAME_PINNED_COMMIT:0:12}"
        else miss "the pinned commit: it is at ${head:-nothing}, not ${MAME_PINNED_COMMIT:0:12}"; fi
        while IFS=: read -r target _ _; do
            bin=$(target_bin "$target")
            if [ -x "$bin" ]; then ok "$(basename "$bin") built"; else miss "$(basename "$bin") (make setup)"; fi
        done <<< "$MAME_TARGETS"
    fi

    info "Romsets in run/mame_roms/ (not distributed: README, Getting started)"
    local set
    for set in $(dumped_sets); do
        if [ -f "run/mame_roms/$set.zip" ]; then ok "$set"; else miss "$set.zip"; fi
    done
    if [ -f run/mame_roms/radendur.zip ]; then
        if uv run --no-sync scripts/radendur-v2.py --check >/dev/null 2>&1; then ok "radendurv2.zip matches the patch table"
        else miss "radendurv2.zip up to date (make v2)"; fi
    fi

    info "Optional: the GIFs and the disassembly chain"
    if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then ok "ffmpeg"
    else note "no ffmpeg (gif.sh and the GIF manifest need it)"; fi
    if java_home_path >/dev/null 2>&1; then ok "a JDK"; else note "no JDK (brew install openjdk)"; fi
    if [ -x tools/ghidra/support/analyzeHeadless ]; then ok "Ghidra"; else note "no Ghidra (make ghidra-setup)"; fi
    if ls disasm/img/*.bin >/dev/null 2>&1; then ok "the 68000 images"; else note "no 68000 images (make disasm)"; fi
    return "$missing"
}

clone() {
    if [ "$ASSUME_YES" != 1 ]; then
        [ -t 0 ] || die "no MAME at $MAME_SRC and no terminal to ask: ./scripts/setup-mame.sh --yes"
        printf "MAME is not at %s. Clone %s at %s there (shallow)? [y/N] " \
            "$MAME_SRC" "$MAME_REPO" "${MAME_PINNED_COMMIT:0:12}"
        read -r answer
        case "$answer" in y|Y) ;; *) die "cancelled; MAME_SRC=<path> points at a checkout elsewhere" ;; esac
    fi
    info "Cloning MAME at $MAME_PINNED_COMMIT into $MAME_SRC"
    clone_pinned "$MAME_REPO" "$MAME_SRC" || die "the clone failed"
}

apply_patches() {
    local p
    for p in "$PROJECT_DIR"/patches/*.patch; do
        if git -C "$MAME_SRC" apply --check "$p" 2>/dev/null; then
            info "applying $(basename "$p")"; git -C "$MAME_SRC" apply "$p"
        elif git -C "$MAME_SRC" apply --reverse --check "$p" 2>/dev/null; then
            info "$(basename "$p") already applied"
        else
            die "$(basename "$p") does not apply; git -C $MAME_SRC checkout . and run again"
        fi
    done
}

build() {
    local jobs target source bin
    jobs="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
    while IFS=: read -r target source _; do
        bin=$(target_bin "$target")
        if [ -x "$bin" ] && [ "$FORCE" != 1 ]; then info "$(basename "$bin") already built (--force rebuilds)"; continue; fi
        info "building $(basename "$bin") with $jobs jobs (a long build the first time)"
        # REGENIE=1: a SUBTARGET's filtered driver list is cached, and a stale one builds a binary
        # without the machine and without a warning
        ( cd "$MAME_SRC" && make SUBTARGET="$target" SOURCES="$source" REGENIE=1 -j"$jobs" )
    done <<< "$MAME_TARGETS"
}

validate() {
    local target sets bin set
    while IFS=: read -r target _ sets; do
        bin=$(target_bin "$target")
        for set in ${sets//,/ }; do
            "$bin" -listxml "$set" >/dev/null 2>&1 || die "$(basename "$bin") does not list $set: an incomplete build"
        done
        info "$(basename "$bin"): ${sets//,/, }"
    done <<< "$MAME_TARGETS"
    info "ready: make play runs radendurv2, make check runs the checks"
}

FORCE=0; DOCTOR=0; ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --doctor) DOCTOR=1 ;;
        --force)  FORCE=1 ;;
        --yes)    ASSUME_YES=1 ;;
        --help)   sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Use: $0 [--doctor|--force|--yes]" >&2; exit 2 ;;
    esac
done
MAME_SRC=$(mame_src_path)

if [ "$DOCTOR" = 1 ]; then
    rc=0; doctor || rc=$?
    if [ "$rc" -eq 0 ]; then info "nothing missing"; else info "$rc missing"; exit 1; fi
    exit 0
fi
[ -f run/mame_roms/radendur.zip ] || die "run/mame_roms/radendur.zip is missing: the romsets go there first (README, Getting started)"
[ -d "$MAME_SRC/.git" ] || clone
apply_patches
build
info "building run/mame_roms/radendurv2.zip from the dump"
uv run scripts/radendur-v2.py || die "the radendurv2 ROM could not be built"
validate
