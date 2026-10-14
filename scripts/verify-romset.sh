#!/usr/bin/env bash
# verify-romset.sh [set] -- audits run/mame_roms/<set>.zip against the driver's ROM_START(<set>)
# manifest (searching every tch/*.cpp). A reproducible audit that FAILS if a ROM is missing or a
# CRC does not match. Default set: radendur. Once built, `<binary> -verifyroms <set>` is the
# canonical check.
#
#   ./scripts/verify-romset.sh            # radendur (the target)
#   ./scripts/verify-romset.sh rltennis   # the blitter reference (it works)
#   ./scripts/verify-romset.sh wheelfir   # sibling on the same driver

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

. "$SCRIPT_DIR/lib/mame_src.sh"
MAME_SRC=$(mame_src_path)
[ "$#" -le 1 ] || { echo "Use: $0 [set]" >&2; exit 2; }
SET="${1:-radendur}"
ZIP="run/mame_roms/$SET.zip"

[ -d "$MAME_SRC/src/mame/tch" ] || { echo "INVALID: tch drivers missing ($MAME_SRC); could not check. make setup"; exit 3; }
[ -f "$ZIP" ] || { echo "INVALID: romset missing ($ZIP); could not check"; exit 3; }

MAME_SRC="$MAME_SRC" SET="$SET" ZIP="$ZIP" python3 - <<'PY'
import glob, os, re, subprocess, sys
setname = os.environ["SET"]
block = None
for path in glob.glob(os.path.join(os.environ["MAME_SRC"], "src/mame/tch/*.cpp")):
    m = re.search(r"ROM_START\(\s*%s\s*\).*?ROM_END" % re.escape(setname), open(path, encoding="utf-8").read(), re.S)
    if m:
        block = m.group(0); driver = os.path.basename(path); break
if not block:
    print(f"ERROR: ROM_START({setname}) not found in any tch/*.cpp"); sys.exit(3)
expected = {n: c.lower() for n, c in
            re.findall(r'ROM_LOAD(?:16_BYTE|16_WORD|32_BYTE)?\(\s*"([^"]+)",[^)]*?CRC\(([0-9a-fA-F]+)\)', block)}
def contents(zippath):
    """{name: crc} of a zip, or {} if it does not exist."""
    if not os.path.exists(zippath):
        return {}
    out = subprocess.check_output(["unzip", "-v", zippath], encoding="utf-8")
    d = {}
    for line in out.splitlines():
        m = re.match(r"\s*\d+\s+\S+\s+\d+\s+\S+\s+[\d-]+\s+[\d:]+\s+([0-9a-fA-F]{8})\s+(\S+)", line)
        if m: d[m.group(2)] = m.group(1).lower()
    return d

actual = contents(os.environ["ZIP"])

# a clone (the GAME line's third field names its parent) takes the files it lacks from the parent
parent = None
gm = re.search(r"^GAME\w*\(\s*[^,]+,\s*%s\s*,\s*([a-z0-9_]+)\s*," % re.escape(setname),
               open(os.path.join(os.environ["MAME_SRC"], "src/mame/tch", driver), encoding="utf-8").read(), re.M)
if gm and gm.group(1) != "0":
    parent = gm.group(1)
from_parent = contents(f"run/mame_roms/{parent}.zip") if parent else {}

ok = miss = bad = inherited = 0
# an empty manifest is a ROM_START that could not be read, not a perfect romset
if not expected:
    print("  INVALID: not one ROM_START entry was read; nothing has been verified"); sys.exit(3)

for n, c in expected.items():
    if n in actual:
        if actual[n] == c: ok += 1
        else: print(f"  BAD CRC  {n}: driver {c} != zip {actual[n]}"); bad += 1
    elif n in from_parent and from_parent[n] == c:
        inherited += 1
    else:
        print(f"  MISSING  {n} (expected {c})"); miss += 1
extra = f"   INHERITED from {parent} {inherited}" if inherited else ""
print(f"{setname} ({driver}):  OK {ok}   MISSING {miss}   BAD CRC {bad}{extra}")
sys.exit(0 if miss == 0 and bad == 0 else 1)
PY
echo "==> romset $SET OK"
