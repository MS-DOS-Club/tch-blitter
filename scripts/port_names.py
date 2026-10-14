#!/usr/bin/env python3
"""port_names.py OUT -- the name registers.yaml gives each hardware address, per image, as TSV.

The annotated listings put that name beside every access to a register, and they are written by a
Ghidra script that cannot read YAML; this is where the listings' names are derived.

It covers what registers.yaml describes as the E1333 board's: the blitter's sixteen words and each
port, in the main-cpu image of every game its block's `common_to` names. A word is
named at both of its bytes, since the games reach the blitter with byte writes too. Reality
Tennis's earlier blitter and the sound cpus' DACs are not this board's registers and get no name.

Format: one `<image>\\t<0xaddress>\\t<name>` line per address, sorted. Exit 3 when it named nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTERS = ROOT / "hardware" / "registers.yaml"


def names(registers: dict) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    blitter = registers["blitter"]
    for game in blitter["common_to"]:
        image = f"{game}_maincpu"
        for reg in blitter["registers"]:
            address = blitter["base"] + 2 * reg["word"]
            rows += [(image, address, reg["name"]), (image, address + 1, reg["name"])]
    for port in registers.get("ports") or []:
        for game in port.get("common_to") or []:
            image = f"{game}_maincpu"
            rows += [
                (image, port["address"], port["name"]),
                (image, port["address"] + 1, port["name"]),
            ]
    return sorted(set(rows))


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} OUT", file=sys.stderr)
        return 2
    rows = names(yaml.safe_load(REGISTERS.read_text()))
    if not rows:
        print("INVALID: registers.yaml named no hardware address", file=sys.stderr)
        return 3
    Path(sys.argv[1]).write_text("".join(f"{i}\t{a:#08x}\t{n}\n" for i, a, n in rows))
    print(f"port_names: {len(rows)} addresses named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
