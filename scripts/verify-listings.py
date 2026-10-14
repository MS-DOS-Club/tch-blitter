#!/usr/bin/env python3
"""verify-listings.py DIR -- each annotated listing against its image, by instruments Ghidra is not.

A listing is Ghidra's reading of an image, and nothing in Ghidra can say that reading went wrong,
so `ghidra-export.sh` runs this over the freshly written listings before it moves them into place:

- **bytes**: every line shows exactly the image's bytes at its address;
- **coverage**: the lines and the never-reached ranges tile the ROM, no hole, no overlap;
- **boundaries**: at every instruction, capstone, a disassembler with nothing in common with
  Ghidra and limited to the 68000, decodes an instruction of the same length, or the line carries
  ListTCH's mark saying the analysis decoded something no 68000 runs; a mark capstone disagrees
  with is a contradiction too. `--suspects OUT` writes the unmarked ones for ListTCH to mark;
- **symbols**: every ROM symbol `hardware/symbols.yaml` gives the image is at its address, as a
  label line or as one inside the next line;
- **executed**: every address MAME executed in the image (`disasm/executed/<image>.txt`, which
  the import seeds) still starts an instruction, so no heuristic of the analysis overrode one;
- **register names**: every name beside an instruction is the name `port_names.py` gives an
  address that instruction references in the facts FactsTCH.java dumped of the same project.

`--trace SET` adds the machine as the oracle: a MAME trace's executed addresses (one JSON object
per line with "addr", the tracer's `.set.jsonl`), every one in ROM has to start an instruction
in the listing of `--image`.

Exit codes: 0 every listing holds | 1 a listing contradicts its image | 2 usage | 3 INVALID (no
listing, no image or facts for one, or a listing that parses to nothing)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import capstone  # type: ignore[import-untyped]
import yaml
from image_keys import reaches
from listing_format import GAP, UNIT, executed_addresses
from memory_map import ROM_END

ROOT = Path(__file__).resolve().parents[1]
IMGDIR = ROOT / "disasm" / "img"
SYMBOLS = ROOT / "hardware" / "symbols.yaml"
FACTS = ROOT / "tmp" / "ghidra-facts"
EXECUTED = ROOT / "disasm" / "executed"
# ListTCH.java's SUSPECT, the mark on a line no 68000 runs.
SUSPECT = "  ; not 68000 code: the analysis decoded data or an operand here"

_LABEL = re.compile(r"^(\S+):$")
_INNER = re.compile(r"^; (\S+) is (\d+) bytes into the next line$")
_ARRAY = re.compile(r"^dc\.b ((?:0x[0-9a-f]{2},?)+)")
_NOTE = re.compile(r"  ; ([a-z_0-9, ]+)$")


@dataclass
class Unit:
    addr: int
    shown: bytes
    text: str
    size: int = 0


@dataclass
class Listing:
    units: list[Unit] = field(default_factory=list)
    gaps: list[tuple[int, int]] = field(default_factory=list)
    labels: dict[int, set[str]] = field(default_factory=dict)


def parse(text: str) -> Listing:
    out = Listing()
    pending: set[str] = set()
    inner: list[tuple[str, int]] = []
    for line in text.splitlines():
        if m := GAP.match(line):
            out.gaps.append((int(m.group(2), 16), int(m.group(3), 16)))
            for name in pending:
                out.labels.setdefault(int(m.group(2), 16), set()).add(name)
            pending, inner = set(), []
        elif m := UNIT.match(line):
            addr, rest = int(m.group(1), 16), m.group(3)
            unit = Unit(addr, bytes.fromhex(m.group(2)), rest)
            if a := _ARRAY.match(rest):
                unit.shown = bytes(int(v, 16) for v in a.group(1).rstrip(",").split(","))
            out.units.append(unit)
            for name in pending:
                out.labels.setdefault(addr, set()).add(name)
            for name, off in inner:
                out.labels.setdefault(addr + off, set()).add(name)
            pending, inner = set(), []
        elif m := _INNER.match(line):
            inner.append((m.group(1), int(m.group(2))))
        elif m := _LABEL.match(line):
            pending.add(m.group(1))
    return out


def rom_symbols(image: str) -> dict[int, set[str]]:
    want: dict[int, set[str]] = {}
    for key, rows in yaml.safe_load(SYMBOLS.read_text())["images"].items():
        if reaches(key, image):
            for r in rows or []:
                if r["addr"] < ROM_END:
                    want.setdefault(r["addr"], set()).add(r["name"])
    return want


def port_names(path: Path, image: str) -> dict[int, str]:
    names: dict[int, str] = {}
    for line in path.read_text().splitlines():
        img, addr, name = line.split("\t")
        if img == image:
            names[int(addr, 16)] = name
    return names


def referenced(facts: dict, ports: dict[int, str]) -> dict[int, set[str]]:
    """instruction address -> the register names its hardware references reach."""
    out: dict[int, set[str]] = {}
    for r in facts["hw_refs"]:
        if r["to"] in ports:
            out.setdefault(r["from"], set()).add(ports[r["to"]])
    return out


def check(
    image: str, listing: Listing, data: bytes, names: dict[int, set[str]], suspects: list[int]
) -> list[str]:
    bad: list[str] = []
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    spans = [(u.addr, u) for u in listing.units] + [(g[0], g) for g in listing.gaps]
    spans.sort(key=lambda s: s[0])
    pos = 0
    for i, (addr, item) in enumerate(spans):
        if addr != pos:
            bad.append(f"{image}: coverage breaks at {pos:#08x} (next line at {addr:#08x})")
        end = spans[i + 1][0] if i + 1 < len(spans) else ROM_END
        if isinstance(item, tuple):
            if item[1] + 1 != end:
                bad.append(
                    f"{image}: the range {item[0]:#08x}..{item[1]:#08x} does not reach {end:#08x}"
                )
        else:
            item.size = end - addr
        pos = end
    if pos != ROM_END:
        bad.append(f"{image}: the listing stops at {pos:#08x}")

    for u in listing.units:
        if data[u.addr : u.addr + len(u.shown)] != u.shown:
            bad.append(
                f"{image}: {u.addr:#08x} shows {u.shown.hex()}, the image holds "
                f"{data[u.addr : u.addr + len(u.shown)].hex()}"
            )
        if u.text.startswith("dc."):
            continue
        marked = u.text.endswith(SUSPECT)
        text = u.text.removesuffix(SUSPECT)
        ins = next(md.disasm(data[u.addr : u.addr + 16], u.addr), None)
        agrees = ins is not None and ins.size == u.size
        if not agrees and not marked:
            suspects.append(u.addr)
            bad.append(
                f"{image}: {u.addr:#08x} is a {u.size}-byte instruction to Ghidra, "
                f"{'undecodable' if ins is None else f'{ins.size} bytes'} to capstone, unmarked"
            )
        if agrees and marked:
            bad.append(f"{image}: {u.addr:#08x} is marked, and capstone decodes it the same")
        note = _NOTE.search(text)
        if note:
            for name in (n.strip() for n in note.group(1).split(",")):
                if name not in names.get(u.addr, set()):
                    bad.append(
                        f"{image}: {u.addr:#08x} is annotated '{name}', no reference says so"
                    )

    for addr, declared in rom_symbols(image).items():
        missing = declared - listing.labels.get(addr, set())
        if missing:
            bad.append(f"{image}: {', '.join(sorted(missing))} at {addr:#08x} not in the listing")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dir", type=Path, help="the listings")
    ap.add_argument("--ports", type=Path, help="port_names.py's TSV (made afresh when omitted)")
    ap.add_argument("--trace", type=Path, help="a MAME trace's .set.jsonl, judged on --image")
    ap.add_argument("--image", help="the image the trace was taken on")
    ap.add_argument("--facts", type=Path, default=FACTS, help="FactsTCH.java's JSON of the project")
    ap.add_argument("--suspects", type=Path, help="write the unmarked non-68000 lines here (TSV)")
    args = ap.parse_args()
    if bool(args.trace) != bool(args.image):
        ap.error("--trace and --image go together")

    ports_tsv = args.ports
    if ports_tsv is None:
        ports_tsv = Path(tempfile.mkdtemp(prefix="ports-")) / "ports.tsv"
        subprocess.run(["uv", "run", "scripts/port_names.py", str(ports_tsv)], cwd=ROOT, check=True)
    listings = sorted(args.dir.glob("*.lst"))
    if not listings:
        print(f"==> INVALID: no listing in {args.dir}")
        return 3
    bad: list[str] = []
    suspects: list[tuple[str, int]] = []
    units = 0
    for path in listings:
        image = path.stem
        img = IMGDIR / f"{image}.bin"
        if not img.exists():
            print(f"==> INVALID: no image for {path.name}")
            return 3
        listing = parse(path.read_text())
        if not listing.units:
            print(f"==> INVALID: {path.name} parses to nothing")
            return 3
        units += len(listing.units)
        try:
            facts = json.loads((args.facts / f"{image}.json").read_text())
        except (OSError, json.JSONDecodeError):
            print(f"==> INVALID: no readable facts for {image} in {args.facts}")
            return 3
        found: list[int] = []
        names = referenced(facts, port_names(ports_tsv, image))
        bad += check(image, listing, img.read_bytes(), names, found)
        suspects += [(image, a) for a in found]
        seeds = EXECUTED / f"{image}.txt"
        if seeds.exists():
            starts = {u.addr for u in listing.units if not u.text.startswith("dc.")}
            try:
                ran = executed_addresses(seeds)
            except ValueError as e:
                print(f"==> INVALID: {e}")
                return 3
            bad += [
                f"{image}: MAME executed {a:#08x}, which starts no instruction"
                for a in ran
                if a not in starts
            ]
        if args.image == image:
            starts = {u.addr for u in listing.units if not u.text.startswith("dc.")}
            traced = [
                int(json.loads(ln)["addr"], 16)
                for ln in args.trace.read_text().splitlines()
                if ln.strip()
            ]
            rom = [a for a in traced if a < ROM_END]
            if not rom:
                print(f"==> INVALID: the trace holds no ROM address of {image}")
                return 3
            off = [a for a in rom if a not in starts]
            bad += [f"{image}: MAME executed {a:#08x}, which starts no instruction" for a in off]
            print(
                f"trace: {len(rom)} executed ROM addresses of {image}, "
                f"{len(off)} not instruction starts"
            )
    if args.suspects:
        args.suspects.write_text("".join(f"{i}\t{a:#08x}\n" for i, a in suspects))
    for b in bad:
        print(f"  {b}")
    if bad:
        print(f"==> {len(bad)} contradictions over {len(listings)} listings")
        return 1
    print(f"==> {len(listings)} listings, {units} lines, hold against their images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
