#!/usr/bin/env bash
# export-patch.sh [--check] -- writes the driver changes in upstream/ into patches/ (make patch).
# upstream/ is not committed, so the patches are the only part of a driver change that travels.

set -euo pipefail

# --check writes nothing: it says whether the patches still reflect upstream/.
CHECK=0
case "$#:${1:-}" in
    0:) ;;
    1:--check) CHECK=1 ;;
    *) echo "Use: $0 [--check]" >&2; exit 2 ;;
esac
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

. "$SCRIPT_DIR/lib/mame_src.sh"

MAME_SRC=$(mame_src_path)

# shellcheck source=lib/patch_table.sh
. "$SCRIPT_DIR/lib/patch_table.sh"

[ -d "$MAME_SRC/.git" ] || { echo "ERROR: there is no MAME checkout in $MAME_SRC. Run make setup"; exit 1; }

mkdir -p "$PROJECT_DIR/tmp"

# every file that diverges from the pin has to belong to a patch, or it would not travel
covered="$(printf '%s\n' "$PATCHES" | cut -d'|' -f2 | tr ' ' '\n' | grep -v '^$' | sort -u)"
diverging="$(git -C "$MAME_SRC" status --porcelain | sed 's/^...//' | sort -u)"
orphans="$(comm -23 <(echo "$diverging") <(echo "$covered"))"
if [ -n "$orphans" ]; then
    echo "ERROR: these upstream/ files diverge and NO patch covers them:"
    while IFS= read -r f; do echo "  $f"; done <<< "$orphans"
    echo "  Add them to the PATCHES table in scripts/lib/patch_table.sh, or they will not travel to other machines."
    exit 1
fi

# A new driver is an untracked file, which `git diff` does not see: `add -N` registers it for the
# diff and the reset undoes it.
echo "$PATCHES" | while IFS='|' read -r name sources; do
    [ -n "$name" ] || continue
    PATCH="$PROJECT_DIR/patches/$name"
    tmp="$PROJECT_DIR/tmp/export-patch.$$"

        read -ra paths <<< "$sources"
    git -C "$MAME_SRC" add -N -- "${paths[@]}" 2>/dev/null || true
    git -C "$MAME_SRC" diff -- "${paths[@]}" > "$tmp"
    git -C "$MAME_SRC" reset -q -- "${paths[@]}" 2>/dev/null || true

    if [ ! -s "$tmp" ]; then
        rm -f "$tmp"
        echo "ERROR: upstream/ has no changes in $sources. Nothing to export to $name."
        exit 1
    fi

    if [ -f "$PATCH" ] && diff -q "$tmp" "$PATCH" >/dev/null 2>&1; then
        rm -f "$tmp"
        echo "  $name: up to date"
        continue
    fi

    if [ "$CHECK" = "1" ]; then
        rm -f "$tmp"
        echo "  $name: STALE against upstream/. Run 'make patch'."
        exit 1
    fi

    mv "$tmp" "$PATCH"
    echo "  $name: exported ($(wc -l < "$PATCH" | tr -d ' ') lines)"
done

