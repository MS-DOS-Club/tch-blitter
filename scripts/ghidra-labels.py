#!/usr/bin/env python3
"""ghidra-labels.py -- the Ghidra project carries exactly the labels hardware/symbols.yaml declares.

ghidra-export.sh runs it before writing the analysis and the listings, over what
scripts/ghidra/FactsTCH.java dumped of the project into tmp/ghidra-facts/: a label missing from the
project, or one the table does not declare, means the listings would name addresses the table does
not, so nothing is exported.

Use:
    uv run scripts/ghidra-labels.py [--facts DIR]

Exit: 0 the labels match | 2 usage | 3 they do not, or there is nothing to compare
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from image_keys import reaches

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ROOT / "hardware" / "symbols.yaml"
IMGDIR = ROOT / "disasm" / "img"
FACTS = ROOT / "tmp" / "ghidra-facts"
# SetupTCH.java names the function at the reset vector itself; it is the script's, not the table's.
SETUP_OWN = {"reset"}


def load_facts(directory: Path, images: list[str]) -> dict[str, dict] | None:
    """Each image's facts, or None if one is missing or truncated."""
    facts = {}
    for image in images:
        try:
            data = json.loads((directory / f"{image}.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if "symbols" not in data:
            return None
        facts[image] = data
    return facts


def conflicts(image: str, symbols: dict, facts: dict) -> list[str]:
    """The labels of one image that are in the table and not the project, or the other way."""
    want = {
        (e["addr"], e["name"])
        for key, entries in symbols.items()
        if reaches(key, image)
        for e in entries or []
    }
    have = {(s["addr"], s["name"]) for s in facts["symbols"] if s["source"] == "USER_DEFINED"}
    out = [
        f"{image}: {n} at {a:#x} is in symbols.yaml, not in the project"
        for a, n in sorted(want - have)
    ]
    out += [
        f"{image}: the project labels {a:#x} {n}, which symbols.yaml does not declare"
        for a, n in sorted(have - want)
        if n not in SETUP_OWN
    ]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--facts", type=Path, default=FACTS, help="FactsTCH.java's JSON directory")
    args = ap.parse_args()
    images = sorted(p.stem for p in IMGDIR.glob("*.bin"))
    facts = load_facts(args.facts, images) if images else None
    if facts is None:
        print(f"==> INVALID: no images in disasm/img, or no readable facts in {args.facts}")
        return 3
    symbols = yaml.safe_load(SYMBOLS.read_text())["images"]
    found = [c for image in images for c in conflicts(image, symbols, facts[image])]
    for c in found:
        print(f"  {c}")
    if found:
        print(f"==> INVALID: the project is not the table's ({len(found)} labels differ)")
        return 3
    print(f"==> the project holds exactly the table's labels on {len(images)} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
