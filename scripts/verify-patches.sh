#!/usr/bin/env bash
# verify-patches.sh -- the patches rebuild upstream/'s changes from a clean tree at the pin, byte for
# byte. export-patch.sh --check compares the patches with upstream/ as it is now; this proves they
# also apply on a fresh clone, which is where they have to work. It compiles nothing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
. "$SCRIPT_DIR/lib/mame_src.sh"
# shellcheck source=lib/patch_table.sh
. "$SCRIPT_DIR/lib/patch_table.sh"
MAME_SRC="$(mame_src_path)"
[ -d "$MAME_SRC/.git" ] || { echo "INVALID: no MAME checkout in $MAME_SRC (make setup)"; exit 3; }

WORK=$(mktemp -d)
trap 'git -C "$MAME_SRC" worktree remove --force "$WORK/mame" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
git -C "$MAME_SRC" worktree add --detach "$WORK/mame" "$MAME_PINNED_COMMIT" >/dev/null 2>&1 \
    || { echo "INVALID: no worktree at the pin $MAME_PINNED_COMMIT"; exit 3; }

failures=0
while IFS= read -r name; do
    if git -C "$WORK/mame" apply "$PROJECT_DIR/patches/$name" 2>/dev/null; then
        echo "  applies $name"
    else
        echo "  FAILS   $name"; failures=$((failures + 1))
    fi
done < <(patch_table_names)

while IFS= read -r f; do
    cmp -s "$WORK/mame/$f" "$MAME_SRC/$f" || { echo "  DIFFERS $f"; failures=$((failures + 1)); }
done < <(git -C "$WORK/mame" status --porcelain | awk '{print $2}')

if [ "$failures" -ne 0 ]; then echo "==> $failures failures"; exit 1; fi
echo "==> the patches rebuild upstream/ from the pin"
