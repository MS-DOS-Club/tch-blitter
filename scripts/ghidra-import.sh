#!/usr/bin/env bash
# ghidra-import.sh [image] -- imports disasm/img/'s 68000 images into a Ghidra project
# (disasm/ghidra/) as Motorola 68000 big-endian, with the pre-script ghidra/SetupTCH.java seeding
# the auto-analysis. With no argument it processes all the images; with a .bin path, only that one.
#
# An image is analysed again only when what its analysis came from changed: the image, the labels
# (disasm/symbols.txt), the addresses MAME executed in it (disasm/executed/), SetupTCH.java and the
# MemoryMapTCH.java it reads, the processor or the Ghidra release. The sha256 of those is
# kept beside the project (disasm/ghidra/<image>.seed), compared rather than file dates, which a
# checkout rewrites. FORCE=1 imports regardless.
#
# Requires: tools/ghidra (make ghidra-setup) and a JDK (brew install openjdk).
# Sequential on purpose: each analysis holds its own JVM heap, and side by side they exhaust a
# small machine's memory.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# One image named, or none for all of them; an image named that does not exist is a usage error,
# not a skip, or a typo imports nothing and exits green.
[ "$#" -le 1 ] || { echo "Use: $0 [disasm/img/<image>.bin]" >&2; exit 2; }
[ "$#" -eq 0 ] || [ -f "$1" ] || { echo "no such image: $1" >&2; exit 2; }

GHIDRA="${GHIDRA_HOME:-$PROJECT_DIR/tools/ghidra}"
HEADLESS="$GHIDRA/support/analyzeHeadless"
PROJDIR="$PROJECT_DIR/disasm/ghidra"
SYMBOLS="$PROJECT_DIR/disasm/symbols.txt"
SETUP="$SCRIPT_DIR/ghidra/SetupTCH.java"
MEMORY_MAP="$SCRIPT_DIR/ghidra/MemoryMapTCH.java"
PROCESSOR="68000:BE:32:default"

[ -x "$HEADLESS" ] || { echo "ERROR: Ghidra not found in $GHIDRA (analyzeHeadless). make ghidra-setup"; exit 1; }
[ -f "$SYMBOLS" ] || { echo "ERROR: $SYMBOLS is missing. make hw-docs" >&2; exit 1; }

. "$SCRIPT_DIR/lib/jdk.sh"
require_jdk || exit 1
echo "==> JAVA_HOME=$JAVA_HOME"

mkdir -p "$PROJDIR" "$PROJECT_DIR/tmp"

# executed_of <name>: the addresses MAME executed in that image (scripts/trace-seeds.py), if any.
executed_of() {
    local f="$PROJECT_DIR/disasm/executed/$1.txt"
    [ -f "$f" ] && printf '%s\n' "$f"
    return 0
}

# seed_of <image> <name>: the sha256 of everything one image's analysis is a function of.
seed_of() {
    local executed
    executed=$(executed_of "$2")
    {
        # shellcheck disable=SC2086 # executed is one path or empty, never a list
        shasum -a 256 "$1" "$SYMBOLS" "$SETUP" "$MEMORY_MAP" "$GHIDRA/Ghidra/application.properties" $executed \
            | cut -d' ' -f1
        echo "$PROCESSOR"
    } | shasum -a 256 | cut -d' ' -f1
}

images=()
if [ -n "${1:-}" ]; then
    images=("$1")
else
    # every image disasm.sh extracted, so a new set needs no edit here
    for img in disasm/img/*.bin; do [ -f "$img" ] && images+=("$img"); done
fi
[ "${#images[@]}" -gt 0 ] || { echo "INVALID: no image in disasm/img; run make disasm" >&2; exit 3; }

for img in "${images[@]}"; do
    name=$(basename "$img" .bin)
    seed=$(seed_of "$img" "$name")
    executed=$(executed_of "$name")
    if [ "${FORCE:-0}" != 1 ] && [ -f "$PROJDIR/$name.seed" ] && [ "$(cat "$PROJDIR/$name.seed")" = "$seed" ]; then
        echo "==> $name: up to date"
        continue
    fi
    echo "==> Ghidra import + analyze: $name"
    rm -f "$PROJDIR/$name.seed"
    # Logged and read afterwards rather than piped: a pipe's exit code is its last stage's.
    log="$PROJECT_DIR/tmp/ghidra-import-$name.log"
    if ! "$HEADLESS" "$PROJDIR" tch \
        -import "$img" \
        -processor "$PROCESSOR" \
        -scriptPath "$SCRIPT_DIR/ghidra" \
        -preScript SetupTCH.java "$SYMBOLS" ${executed:+"$executed"} \
        -overwrite >"$log" 2>&1
    then
        echo "ERROR: Ghidra failed importing $name (see $log)" >&2
        exit 1
    fi
    # analyzeHeadless answers 0 even when a script fails to compile or throws, so the pre-script's
    # own report is the proof that the seeding ran: the entry and the labels, each.
    for said in "entry (reset) =" "labels applied from symbols.txt"; do
        command grep -qF "$said" "$log" \
            || { echo "ERROR: SetupTCH.java did not report '$said' for $name (see $log)" >&2; exit 1; }
    done
    command grep -E "vector targets|executed addresses|RAM-run code|labels applied|labels of other" "$log" || true
    printf '%s\n' "$seed" > "$PROJDIR/$name.seed"
done

echo "==> Ghidra project in $PROJDIR/tch.gpr"
echo "    Open the GUI:  JAVA_HOME=$JAVA_HOME $GHIDRA/ghidraRun"
