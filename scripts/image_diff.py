"""image_diff.py -- what changes between two images, the measure every before/after pair uses."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

# below this share of changing pixels a pair shows nothing
MINIMUM_PCT = 1.0


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def changed(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The pixels that differ, over the area the two images have in common."""
    height, width = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    mask: np.ndarray = np.abs(a[:height, :width] - b[:height, :width]).sum(axis=2) > 0
    return mask


def box(mask: np.ndarray) -> str:
    ys, xs = np.nonzero(mask)
    return f"x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()}" if len(ys) else "no changes"
