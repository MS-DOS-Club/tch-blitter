#!/usr/bin/env bash
# ghidra-setup.sh -- downloads Ghidra and leaves it ready in tools/ghidra (gitignored).
#
# ghidra-import.sh and ghidra-export.sh run its analyzeHeadless. The version is pinned, because the
# published analysis (disasm/analysis.txt, disasm/listings/) comes from it.
#
# Idempotent: if the pinned version is already there, it does nothing.
# Requires: a JDK (brew install openjdk) and curl.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

. "$SCRIPT_DIR/lib/jdk.sh"

GHIDRA_VERSION="12.1.2"
GHIDRA_BUILD="20260605"
GHIDRA_SHA256="b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d"
ZIP="ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_BUILD}.zip"
URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/$ZIP"

DEST="$PROJECT_DIR/tools/ghidra"
HEADLESS="$DEST/support/analyzeHeadless"

installed_version() {
    [ -f "$DEST/Ghidra/application.properties" ] || return 1
    sed -n 's/^application\.version=//p' "$DEST/Ghidra/application.properties"
}

if [ "$(installed_version 2>/dev/null)" = "$GHIDRA_VERSION" ] && [ -x "$HEADLESS" ]; then
    echo "==> Ghidra $GHIDRA_VERSION already installed in $DEST"
else
    require_jdk || exit 1

    mkdir -p "$PROJECT_DIR/tools"
    TMPZIP="$PROJECT_DIR/tools/$ZIP"

    if [ ! -f "$TMPZIP" ]; then
        echo "==> Downloading Ghidra $GHIDRA_VERSION (~546 MB)"
        curl -fL --progress-bar -o "$TMPZIP.part" "$URL"
        mv "$TMPZIP.part" "$TMPZIP"
    fi

    echo "==> Verifying SHA256"
    got=$(shasum -a 256 "$TMPZIP" | awk '{print $1}')
    if [ "$got" != "$GHIDRA_SHA256" ]; then
        echo "ERROR: SHA256 does not match."
        echo "  expected: $GHIDRA_SHA256"
        echo "  got:      $got"
        echo "  Delete $TMPZIP and try again."
        exit 1
    fi

    echo "==> Unzipping into tools/"
    rm -rf "$DEST" "$PROJECT_DIR/tools/ghidra_${GHIDRA_VERSION}_PUBLIC"
    unzip -q "$TMPZIP" -d "$PROJECT_DIR/tools"
    mv "$PROJECT_DIR/tools/ghidra_${GHIDRA_VERSION}_PUBLIC" "$DEST"
    rm -f "$TMPZIP"
fi

# Gate: the install is only worth anything if analyzeHeadless STARTS on this machine (a missing or
# incompatible JDK shows up here, not three commands later).
require_jdk || exit 1
[ -x "$HEADLESS" ] || { echo "ERROR: $HEADLESS is missing after the install"; exit 1; }
if ! "$HEADLESS" 2>&1 | grep -q "Headless Analyzer Usage"; then
    echo "ERROR: analyzeHeadless does not start (JAVA_HOME=$JAVA_HOME)."
    exit 1
fi

echo "==> OK. Ghidra $(installed_version) in $DEST"
echo "    JAVA_HOME=$JAVA_HOME"
echo "    Next:  make ghidra    # imports and analyses the 68000 images"
