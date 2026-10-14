"""verify-images.py -- every before/after pair still measures what its caption declares: both files
exist, the share of pixels that change is still the manifest's (within a recompression's tenths),
the change sits in the box the manifest names, and the pair still shows a change. Whether the
caption's words describe the picture is for a person to see; the box makes a wrong one visible.

Use:
    uv run scripts/verify-images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from image_diff import MINIMUM_PCT, box, changed, load

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "img" / "before-after"
MANIFEST = DIR / "manifest.yaml"

# A recompression or a change of tool version moves tenths, not points.
TOLERANCE = 0.5


def percentage(a: Path, b: Path) -> tuple[float, str]:
    mask = changed(load(a), load(b))
    return 100.0 * mask.sum() / mask.size, box(mask)


def main() -> int:
    if not MANIFEST.exists():
        print(f"INVALID: {MANIFEST} is missing")
        sys.exit(3)
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    pairs = data.get("pairs") or []
    if not pairs:
        print("INVALID: the manifest declares not one pair; nothing has been checked")
        sys.exit(3)

    failures: list[str] = []
    for p in pairs:
        a, b = DIR / p["before"], DIR / p["after"]
        if not a.exists() or not b.exists():
            failures.append(f"{p['id']}: {a.name if not a.exists() else b.name} is missing")
            continue
        pct, box = percentage(a, b)
        print(f"  {p['id']:22s} {pct:6.2f}%  (declared {p['changes_pct']:.2f}%)  {box}")
        if abs(pct - float(p["changes_pct"])) > TOLERANCE:
            failures.append(
                f"{p['id']}: it changes {pct:.2f}% and the manifest says {p['changes_pct']:.2f}%. "
                "If the image is new, measure it again and REWRITE the caption."
            )
        # the box is what a caption naming a zone of the screen rests on
        if p.get("box") and p["box"] != box:
            failures.append(
                f"{p['id']}: it changes in `{box}` and the manifest declares `{p['box']}`. "
                "The percentage can stay the same while the caption stops saying where it happens."
            )
        elif not p.get("box"):
            failures.append(f"{p['id']}: no `box` in the manifest; add `box: {box}`")
        if pct < MINIMUM_PCT:
            failures.append(f"{p['id']}: it only changes {pct:.2f}%; this pair illustrates nothing")
        for field in ("caption", "alt"):
            if not p.get(field):
                failures.append(f"{p['id']}: no {field}")

    print(f"\npairs checked: {len(pairs)}")
    if failures:
        print(f"FAILURES: {len(failures)}")
        for f in failures:
            print(f"  {f}")
        return 1
    print("==> every pair still measures what its caption declares")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
