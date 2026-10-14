#!/usr/bin/env bash
# disasm.sh -- the 68000 program images of the sets, disasm/img/<set>_<region>.bin: the even and odd
# ROMs each driver's ROM_START names, interleaved into the image the cpu sees from 0x0 (even is the
# high byte). Code regions only; a sub cpu's image mixes code and samples. Ghidra reads these.
#
#   ./scripts/disasm.sh                                          every image
#   TARGETS="rltennis:maincpu:rltennis.cpp" ./scripts/disasm.sh  one image

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
. "$SCRIPT_DIR/lib/mame_src.sh"
MAME_SRC=$(mame_src_path)
TCH="$MAME_SRC/src/mame/tch"
OUT=disasm; IMG="$OUT/img"

mkdir -p "$IMG"

[ -d "$TCH" ] || { echo "ERROR: tch drivers missing. make setup"; exit 1; }

# set:region:driver. Kong Ball has no sub cpu image: its dump lacks the sound ROMs.
TARGETS="${TARGETS:-radendur:maincpu:radendur.cpp radendur:subcpu:radendur.cpp \
wheelfir:maincpu:wheelfir.cpp wheelfir:subcpu:wheelfir.cpp \
pwball:maincpu:wheelfir.cpp pwball:subcpu:wheelfir.cpp \
kongball:maincpu:wheelfir.cpp \
rltennis:maincpu:rltennis.cpp rltennisa:maincpu:rltennis.cpp}"

for t in $TARGETS; do
    set=$(echo "$t" | cut -d: -f1); region=$(echo "$t" | cut -d: -f2); drv=$(echo "$t" | cut -d: -f3)
    DRIVER="$TCH/$drv" SET="$set" REGION="$region" ZIP="run/mame_roms/$set.zip" BIN="$IMG/${set}_${region}.bin" python3 - <<'PY'
import os, re, sys, zipfile
drv, setname, region, zippath, out = (os.environ[k] for k in ("DRIVER","SET","REGION","ZIP","BIN"))
rs = re.search(r"ROM_START\(\s*%s\s*\).*?ROM_END" % re.escape(setname), open(drv, encoding="utf-8").read(), re.S).group(0)
rm = re.search(r'ROM_REGION\d*\(\s*[^,]+,\s*"%s".*?(?=ROM_REGION|ROM_END)' % re.escape(region), rs, re.S)
if not rm: sys.exit(f"  ROM_REGION {region} not found in {setname}")
loads = re.findall(r'ROM_LOAD16_BYTE\(\s*"([^"]+)",\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)', rm.group(0))
even = odd = None
for name, off, size in loads:
    if int(off,16) & 1 == 0: even = name
    else: odd = name
if not (even and odd): sys.exit(f"  {region}: there is no even/odd pair")
z = zipfile.ZipFile(zippath); e = z.read(even); o = z.read(odd)
if len(e) != len(o): sys.exit("  even/odd sizes differ")
img = bytearray(len(e)*2); img[0::2] = e; img[1::2] = o   # even=high byte (BE), odd=low byte
open(out,"wb").write(img)
print(f"  {setname}/{region}: even={even} odd={odd} -> {out} ({len(img)} B, base 0x0)")
PY
done
