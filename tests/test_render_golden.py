"""The Python render of Radical Enduro's tracks does not move: a hash of the index canvas before the
palette and a hash of the palette, per playable section, so a failure says which of the two moved.
A change made on purpose rewrites tests/data/render-refs.json from `fingerprints`, and the commit
says why.
"""

import hashlib
import json
import os

import numpy as np
import pytest

REFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "render-refs.json")

# A small fixed window of each playable section: enough to catch a change of geometry or order, and
# it renders in milliseconds instead of seconds.
CROPS = {
    0: (170, 985, 190, 1005),
    1: (430, 990, 450, 1010),
    2: (170, 985, 190, 1005),
    4: (230, 985, 250, 1005),
    8: (100, 985, 120, 1005),
}


def _hash(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def fingerprints(rd, sec):
    """(geometry, palette) of a section: uncoloured indices and the 256 colours."""
    res = rd.render(sec, crop=CROPS[sec])
    assert res is not None, f"section {sec} does not render"
    img = res[0]
    # section_palette returns 768 integers (256 colours x RGB). The render already comes out
    # coloured, so to separate GEOMETRY from COLOUR it is re-indexed against that same palette: if
    # only the colour changes, one hash fails and not the other, and the message says which of the
    # two moved.
    pal = rd.section_palette(sec)
    table = {}
    for i in range(256):
        table.setdefault((pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]), i)
    a = np.asarray(img.convert("RGB"))
    idx = np.array([[table.get(tuple(px), 255) for px in row] for row in a], dtype=np.uint8)
    return _hash(idx), _hash(np.asarray(pal, dtype=np.uint8))


@pytest.fixture(scope="module")
def refs():
    with open(REFS) as f:
        return json.load(f)


@pytest.mark.parametrize("sec", sorted(CROPS))
def test_the_render_does_not_move(rd, refs, sec):
    geo, pal = fingerprints(rd, sec)
    expected = refs[str(sec)]
    assert geo == expected["geo"], (
        f"section {sec}: the render's GEOMETRY changed ({expected['geo']} -> {geo}). "
        f"Suspects: the order of the three passes, the intra-cell order (descending index), "
        f"or parse()'s coordinate filter."
    )
    assert pal == expected["pal"], (
        f"section {sec}: the PALETTE changed ({expected['pal']} -> {pal}). Suspect: the "
        f"environment loop, which is where the bug of reading a prop past the array lived."
    )
