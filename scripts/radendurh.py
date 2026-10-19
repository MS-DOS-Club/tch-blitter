"""Builds radendurh, the clone of Radical Enduro whose maincpu ROM has the prototype's faults fixed.

Its table has two layers, the five faults and the blitter interrupt handlers opened to the sound's
interrupt as Power Ball's are, and an optional third, scenery drawn further round the view
(not the board's behaviour), which the set does not carry and `--with scenery` adds.

The board's dump has five faults, four that stop the game and one that draws a scrolled row's props
in the wrong row (`hardware/radendurh.yaml` says which and why). MAME's driver emulates that dump
as it is, and the clone loads a corrected maincpu ROM instead. That ROM is somebody else's work
with our changes on it, so what travels is this recipe and its table, never the bytes: anybody
holding the verified dump builds the same ROM.

What it refuses, as INVALID (exit 3), because a radendurh built from the wrong thing would boot and
look plausible: an input that is not the dump the parent's `ROM_LOAD` declares; a table that does
not match that dump, or that does not say what it means (an unknown or missing key, two entries on
one byte, a routine past the hook area); and anything it could not read.

The SHA1s and load offsets are read from the driver (`src/mame/tch/wheelfir.cpp` in the MAME
checkout, patched): the parent's are the input check and the clone's are the output check, so each
is written once.

USE:
    uv run scripts/radendurh.py                          # build run/mame_roms/<clone>.zip
    uv run scripts/radendurh.py --check                  # 0 up to date, 1 stale or missing
    uv run scripts/radendurh.py --stage fixes --out F    # stop after a layer, write elsewhere
    uv run scripts/radendurh.py --with scenery --out F   # add an optional layer, write elsewhere
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "hardware" / "radendurh.yaml"
# the driver as the checkout holds it, patched (MAME_SRC, else upstream/); export-patch.sh --check
# and verify-patches.sh say it is what patches/ carries
MAME_SRC = Path(os.environ.get("MAME_SRC") or ROOT / "upstream")
DRIVER = MAME_SRC / "src" / "mame" / "tch" / "wheelfir.cpp"
ROMS = ROOT / "run" / "mame_roms"
JSR_ABS_L = 0x4EB9
NOP = 0x4E71
# The hook area is part of an all-zero run of the dump (registers.yaml records it).
HOOK_FILL = 0x00
# Where ROM_LOAD16_BYTE puts each half of the 68000's word.
OFFSET = {"even": 0x00000, "odd": 0x00001}
# A fixed timestamp and host field keep the zip byte-identical from one build to the next.
ZIP_DATE = (1997, 1, 1, 0, 0, 0)
ZIP_UNIX = 3

KEYS = {
    "table": ({"target", "clone", "hook_base", "hook_limit", "layers"}, set()),
    "romset": ({"set", "roms"}, set()),
    "layer": ({"name"}, {"doc", "optional", "words", "hooks", "sites"}),
    "word": ({"addr", "old", "new", "why"}, set()),
    "hook": ({"label", "words", "source"}, {"doc", "falls_into"}),
    "site": ({"hook", "at", "old"}, {"sets_flags"}),
}


class InvalidError(Exception):
    """The build cannot be proved; nothing is written."""


class UsageError(Exception):
    """The command line asks for something that has no meaning."""


def keys(d: Any, kind: str, where: str) -> None:
    """Refuse a mapping with a key the table's format does not have, or without one it needs."""
    required, optional = KEYS[kind]
    if not isinstance(d, dict):
        raise InvalidError(f"{where}: a {kind} must be a mapping")
    missing, unknown = required - d.keys(), d.keys() - required - optional
    if missing or unknown:
        raise InvalidError(f"{where}: missing {sorted(missing)}, unknown {sorted(unknown)}")


def load_table(path: Path) -> dict[str, Any]:
    table: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    keys(table, "table", path.name)
    for k in ("target", "clone"):
        keys(table[k], "romset", k)
    if not table["layers"]:
        raise InvalidError("the table has no layer")
    seen_optional = False
    for layer in table["layers"]:
        keys(layer, "layer", "layer")
        # an optional layer goes last, so the set's hooks keep their addresses with or without it
        if not isinstance(layer.get("optional", False), bool):
            raise InvalidError(f"layer {layer['name']}: optional is true or false")
        if layer.get("optional"):
            seen_optional = True
        elif seen_optional:
            raise InvalidError(f"layer {layer['name']} comes after an optional layer")
        if not any(layer.get(k) for k in ("words", "hooks", "sites")):
            raise InvalidError(f"layer {layer['name']} changes nothing")
        for w in layer.get("words", []):
            keys(w, "word", f"{layer['name']} word")
        for h in layer.get("hooks", []):
            keys(h, "hook", f"{layer['name']} hook")
        for s in layer.get("sites", []):
            keys(s, "site", f"{layer['name']} site")
    return table


def rom_manifest(setname: str) -> dict[str, tuple[int, str, str]]:
    """{rom: (load offset, crc32, sha1)} of ROM_START(setname) in the driver."""
    if not DRIVER.is_file():
        raise InvalidError(f"no driver at {DRIVER}: make setup")
    source = DRIVER.read_text(encoding="utf-8")
    m = re.search(rf"ROM_START\(\s*{re.escape(setname)}\s*\)(.*?)ROM_END", source, re.S)
    if not m:
        raise InvalidError(f"ROM_START({setname}) is not in {DRIVER}")
    out = {}
    # One ROM_LOAD line at a time, so a NO_DUMP entry can never borrow the next entry's hash.
    for line in m.group(1).splitlines():
        call = re.search(r'ROM_LOAD\w*\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)', line)
        sums = re.search(r"CRC\(([0-9a-f]{8})\)\s*SHA1\(([0-9a-f]{40})\)", line)
        if call and sums:
            out[call.group(1)] = (int(call.group(2), 16), sums.group(1), sums.group(2))
    return out


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sums(data: bytes) -> str:
    """CRC32 and SHA1, the pair a ROM_LOAD declares and MAME checks."""
    return f"{zlib.crc32(data):08x} {sha1(data)}"


def declared(romset: dict[str, Any]) -> dict[str, str]:
    """{rom: "crc32 sha1"} the driver declares for a romset's two program ROMs, offsets checked."""
    manifest = rom_manifest(romset["set"])
    out = {}
    for side, rom in romset["roms"].items():
        if rom not in manifest:
            raise InvalidError(f"{rom} is not a hashed ROM_LOAD of ROM_START({romset['set']})")
        offset, crc, digest = manifest[rom]
        if offset != OFFSET[side]:
            raise InvalidError(f"{rom} loads at {offset:#x}, the table makes it the {side} half")
        out[rom] = f"{crc} {digest}"
    return out


def load_image(table: dict[str, Any]) -> bytearray:
    """The parent's program ROMs, checked against its ROM_LOAD and interleaved for the 68000."""
    t = table["target"]
    want = declared(t)
    zpath = ROMS / f"{t['set']}.zip"
    if not zpath.exists():
        raise InvalidError(f"{zpath.relative_to(ROOT)} is missing")
    halves = {}
    with zipfile.ZipFile(zpath) as z:
        names = {n.lower(): n for n in z.namelist()}
        for side, rom in t["roms"].items():
            if rom not in names:
                raise InvalidError(f"{rom} is not in {zpath.name}")
            data = z.read(names[rom])
            if sums(data) != want[rom]:
                raise InvalidError(f"{rom} sha1 {sha1(data)} is not the dump the driver declares")
            halves[side] = data
    image = bytearray(len(halves["even"]) * 2)
    image[0::2] = halves["even"]
    image[1::2] = halves["odd"]
    return image


def words(ws: list[int]) -> bytes:
    if any(not 0 <= w <= 0xFFFF for w in ws):
        raise InvalidError(f"not a 16-bit word in {[hex(w) for w in ws]}")
    return b"".join(w.to_bytes(2, "big") for w in ws)


def layout(layer: dict[str, Any], base: int) -> tuple[dict[str, int], bytes]:
    """Each hook's address when the layer's block starts at `base`, and the block itself."""
    labels: dict[str, int] = {}
    block = b""
    for h in layer.get("hooks", []):
        if h["label"] in labels:
            raise InvalidError(f"hook {h['label']} is declared twice")
        labels[h["label"]] = base + len(block)
        block += words(h["words"])
    return labels, block


def jsr_to(target: int, length: int) -> bytes:
    """A jsr to `target` filling an instruction of `length` bytes, padded with nops."""
    code = words([JSR_ABS_L, target >> 16, target & 0xFFFF])
    if length < len(code) or length % 2:
        raise InvalidError(f"a {length}-byte instruction cannot take a jsr")
    return code + words([NOP] * ((length - len(code)) // 2))


def put(
    image: bytearray, claimed: dict[int, str], addr: int, old: bytes, new: bytes, what: str
) -> None:
    """Write `new` over `old` at addr, refusing a byte another entry wrote or a mismatch."""
    if len(old) != len(new):
        raise InvalidError(f"{what} at {addr:06x}: {len(old)} bytes expected, {len(new)} written")
    for a in range(addr, addr + len(new)):
        if a in claimed:
            raise InvalidError(f"{what} at {addr:06x} overlaps {claimed[a]}")
    if image[addr : addr + len(old)] != old:
        raise InvalidError(
            f"{what} at {addr:06x}: reads {image[addr : addr + len(old)].hex()},"
            f" expected {old.hex()}"
        )
    for a in range(addr, addr + len(new)):
        claimed[a] = what
    image[addr : addr + len(new)] = new


def apply_layer(
    image: bytearray, claimed: dict[int, str], layer: dict[str, Any], base: int, limit: int
) -> int:
    """Apply one layer; return where its hooks end, which is where the next layer's begin."""
    for w in layer.get("words", []):
        put(image, claimed, w["addr"], words(w["old"]), words(w["new"]), w["why"])
    labels, block = layout(layer, base)
    if base + len(block) > limit:
        raise InvalidError(
            f"{layer['name']} hooks end at {base + len(block):06x}, past {limit:06x}"
        )
    if block:
        put(image, claimed, base, bytes([HOOK_FILL]) * len(block), block, f"{layer['name']} hooks")
    for s in layer.get("sites", []):
        if s["hook"] not in labels:
            raise InvalidError(f"site hook {s['hook']} is not a hook of layer {layer['name']}")
        old = words(s["old"])
        for at in s["at"]:
            put(image, claimed, at, old, jsr_to(labels[s["hook"]], len(old)), f"jsr {s['hook']}")
    return base + len(block)


def selected(table: dict[str, Any], extra: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """The layers a build applies, in table order: every one not optional, and the optional ones
    named in `extra`."""
    return [
        layer for layer in table["layers"] if not layer.get("optional") or layer["name"] in extra
    ]


def build(
    table: dict[str, Any], stage: str | None, extra: tuple[str, ...] = ()
) -> tuple[dict[str, bytes], list[str]]:
    """The clone's two ROMs built up to `stage` (every selected layer when None), and the layers
    applied."""
    image = load_image(table)
    claimed: dict[int, str] = {}
    base = table["hook_base"]
    done = []
    for layer in selected(table, extra):
        base = apply_layer(image, claimed, layer, base, table["hook_limit"])
        done.append(layer["name"])
        if layer["name"] == stage:
            break
    roms = table["clone"]["roms"]
    return {roms["even"]: bytes(image[0::2]), roms["odd"]: bytes(image[1::2])}, done


def zipped(roms: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(roms):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = ZIP_UNIX
            z.writestr(info, roms[name])
    return buf.getvalue()


def write_atomically(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def check(table: dict[str, Any], roms: dict[str, bytes], out: Path) -> int:
    """0 when the recipe and the zip on disk are what the clone's ROM_LOAD declares, 1 when not."""
    want = declared(table["clone"])
    stale = [n for n, d in roms.items() if want[n] != sums(d)]
    if stale:
        print(f"{', '.join(stale)}: the table builds other bytes than ROM_START declares")
        return 1
    if not out.exists():
        print(f"{out} is missing: make radendurh")
        return 1
    with zipfile.ZipFile(out) as z:
        on_disk = {n: sums(z.read(n)) for n in z.namelist()}
    if on_disk != want:
        print(f"{out} is not what ROM_START declares: make radendurh")
        return 1
    print(f"{table['clone']['set']}: up to date with the driver")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--stage", help="stop after this layer; needs --out")
    ap.add_argument("--out", type=Path, help="zip to write (default: run/mame_roms/<clone>.zip)")
    ap.add_argument("--check", action="store_true", help="compare with the clone's ROM_LOAD")
    ap.add_argument(
        "--with",
        dest="extra",
        action="append",
        default=[],
        help="add an optional layer; needs --out",
    )
    a = ap.parse_args(argv)
    try:
        table = load_table(TABLE)
        extra = tuple(a.extra)
        optional = [layer["name"] for layer in table["layers"] if layer.get("optional")]
        for name in extra:
            if name not in optional:
                raise UsageError(f"--with {name!r}: the optional layers are {optional}")
        names = [layer["name"] for layer in selected(table, extra)]
        if a.stage is not None and a.stage not in names:
            raise UsageError(f"--stage {a.stage!r}: the layers are {names}")
        if a.stage is not None and extra and names.index(a.stage) < names.index(extra[-1]):
            raise UsageError(f"--stage {a.stage!r} stops before --with {extra[-1]!r}")
        if (a.stage is not None or extra) and (a.check or a.out is None):
            raise UsageError("--stage and --with build another ROM: give them --out, never --check")
        out = a.out or ROMS / f"{table['clone']['set']}.zip"
        roms, done = build(table, a.stage, extra)
        if a.check:
            return check(table, roms, out)
        write_atomically(out, zipped(roms))
        for n, d in sorted(roms.items()):
            print(f"{n} crc32 sha1 {sums(d)}")
        print(f"wrote {out} ({', '.join(done)})")
        return 0
    except UsageError as e:
        print(f"usage: {e}", file=sys.stderr)
        return 2
    except (InvalidError, OSError, KeyError, TypeError, zipfile.BadZipFile, yaml.YAMLError) as e:
        print(f"INVALID: {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
