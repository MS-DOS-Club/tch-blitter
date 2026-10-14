#!/usr/bin/env bash
# ghidra-export.sh -- writes disasm/analysis.txt (function list, the code that touches the blitter,
# the reset's pseudo-C) and the annotated listings disasm/listings/<image>.lst, from one Ghidra
# project in one run, so the two never describe different analyses.
#
# Before writing anything it brings every image up to date (ghidra-import.sh skips the current
# ones), reads the labels back (FactsTCH.java into tmp/ghidra-facts/) and refuses unless they are
# exactly hardware/symbols.yaml's (ghidra-labels.py).
#
# Both outputs are built in tmp/ and moved into place only after every image produced its part.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

GHIDRA="${GHIDRA_HOME:-$PROJECT_DIR/tools/ghidra}"
HEADLESS="$GHIDRA/support/analyzeHeadless"
PROJDIR="$PROJECT_DIR/disasm/ghidra"
OUTFILE="$PROJECT_DIR/disasm/analysis.txt"
LISTINGS="$PROJECT_DIR/disasm/listings"

[ -x "$HEADLESS" ] || { echo "ERROR: Ghidra not found at $GHIDRA. make ghidra-setup"; exit 1; }

"$SCRIPT_DIR/ghidra-import.sh"

. "$SCRIPT_DIR/lib/jdk.sh"
require_jdk || exit 1

# headless <log> <script> <args...>: one read-only pass of a TCH script over the whole project.
# analyzeHeadless answers 0 even when a script fails to compile, so the caller checks the script's
# own report in <log>.
headless() {
    local log=$1 script=$2
    shift 2
    "$HEADLESS" "$PROJDIR" tch -process -noanalysis -readOnly \
        -scriptPath "$SCRIPT_DIR/ghidra" -postScript "$script" "$@" >"$log" 2>&1 \
        || { echo "ERROR: Ghidra failed running $script (see $log)" >&2; exit 1; }
}

# reported <log> <verb>: every image is named by the script's "<verb> <image>" line.
reported() {
    local img name
    for img in disasm/img/*.bin; do
        name=$(basename "$img" .bin)
        command grep -q "$2 $name" "$1" \
            || { echo "ERROR: no '$2 $name' in $1: the script did not finish that image" >&2; exit 1; }
    done
}

work="$PROJECT_DIR/tmp/ghidra-export"
facts="$PROJECT_DIR/tmp/ghidra-facts"
rm -rf "${work:?}" "${facts:?}"
mkdir -p "$work/listings" "$facts"

echo "==> reading the project's labels back"
headless "$work/facts.log" FactsTCH.java "$facts"
reported "$work/facts.log" facts
rc=0
uv run scripts/ghidra-labels.py --facts "$facts" || rc=$?
[ "$rc" -eq 0 ] || { echo "==> not exported: ghidra-labels.py answered $rc" >&2; exit "$rc"; }

: > "$work/analysis.txt"
for img in disasm/img/*.bin; do
    name=$(basename "$img")
    echo "==> export $name"
    log="$work/export-$name.log"
    "$HEADLESS" "$PROJDIR" tch -process "$name" -noanalysis -readOnly \
        -scriptPath "$SCRIPT_DIR/ghidra" -postScript ExportTCH.java "$work/analysis.txt" >"$log" 2>&1 \
        || { echo "ERROR: Ghidra failed exporting $name (see $log)" >&2; exit 1; }
    command grep -q "exported $name" "$log" \
        || { echo "ERROR: ExportTCH.java did not report $name (see $log)" >&2; exit 1; }
done

echo "==> annotated listings"
uv run scripts/port_names.py "$work/ports.tsv"
headless "$work/listings.log" ListTCH.java "$work/listings" "$work/ports.tsv"
reported "$work/listings.log" listed
# Each listing is checked against its image by instruments Ghidra is not. Ghidra decodes as a
# 68040, so its heuristics can take data or an operand for an instruction no 68000 runs: those
# lines come back as suspects, are marked by a second pass, and the marked listings must then hold
# whole.
rc=0
uv run scripts/verify-listings.py "$work/listings" --ports "$work/ports.tsv" --facts "$facts" \
    --suspects "$work/suspects.tsv" || rc=$?
if [ "$rc" -eq 1 ] && [ -s "$work/suspects.tsv" ]; then
    echo "==> marking the lines no 68000 runs"
    headless "$work/relist.log" ListTCH.java "$work/listings" "$work/ports.tsv" "$work/suspects.tsv"
    reported "$work/relist.log" listed
    rc=0
    uv run scripts/verify-listings.py "$work/listings" --ports "$work/ports.tsv" --facts "$facts" || rc=$?
fi
[ "$rc" -eq 0 ] || { echo "==> not exported: verify-listings.py answered $rc" >&2; exit "$rc"; }

mv "$work/analysis.txt" "$OUTFILE"
rm -rf "${LISTINGS:?}"
mv "$work/listings" "$LISTINGS"
echo "==> the analysis is in $OUTFILE, the listings in $LISTINGS"
