"""gen-before-after.py -- the README's before/after section, generated from the measured manifest
docs/img/before-after/manifest.yaml, so the section is the manifest and the two cannot disagree.

USE:
    uv run scripts/gen-before-after.py            writes the block into the README
    uv run scripts/gen-before-after.py --check    fails if it is out of sync
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import doc_blocks
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "img" / "before-after" / "manifest.yaml"
README = ROOT / "README.md"
BASE = "docs/img/before-after"


HEADER = (
    "The same frames with MAME 0.288's driver on the left and this repository's on the right.\n"
    "Each side runs with freshly created NVRAM. **The percentage is measured**, not estimated:\n"
    "`uv run scripts/before-after.py` computes it and `uv run scripts/verify-images.py` checks it\n"
    "still matches the caption.\n"
)
BEFORE = "MAME 0.288"
AFTER = "here"


def block(pairs: list[dict]) -> str:
    parts = [HEADER]
    for p in pairs:
        caption = p["caption"].strip()
        # THE ALT TEXT IS WRITTEN, not composed from the pair's `id`: an identifier does not
        # describe the image to somebody who cannot see it, which is the only thing an `alt` is
        # for.
        alt = p["alt"].strip()
        cell = '<td width="50%"><img src="{}/{}" alt="{}, {}"></td>'
        img_a = cell.format(BASE, p["before"], alt, BEFORE)
        img_b = cell.format(BASE, p["after"], alt, AFTER)
        parts.append(
            f"\n<table><tr>\n"
            f"{img_a}\n"
            f"{img_b}\n"
            f"</tr><tr>\n"
            f'<td align="center"><i>{BEFORE}</i></td>\n'
            f'<td align="center"><b>{AFTER}</b></td>\n'
            f"</tr></table>\n\n"
            f"{caption} (`{p['game']}`, frame {p['frame']})\n"
        )
    return "".join(parts)


def insert_block(path: Path, content: str) -> tuple[str, bool]:
    text = path.read_text()
    new = doc_blocks.replace(
        text, doc_blocks.opener("gen-before-after.py"), content + "\n", path.name
    )
    return new, new != text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print(f"INVALID: {MANIFEST} is missing")
        sys.exit(3)
    pairs = (yaml.safe_load(MANIFEST.read_text()) or {}).get("pairs") or []
    if not pairs:
        print("INVALID: the manifest declares not one pair")
        sys.exit(3)
    if not README.exists():
        print("INVALID: the README does not exist; nothing has been checked")
        sys.exit(3)

    new, changed = insert_block(README, block(pairs))
    if changed:
        if args.check:
            print(f"out of sync: {README.name}  (run: uv run {Path(__file__).name})")
            return 1
        README.write_text(new)
        print(f"  wrote the block into {README.name}")
        return 0
    print(f"==> the block of {len(pairs)} pairs is up to date in {README.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
