"""The grammar of an image key in hardware/symbols.yaml, shared by every reader of the table.

A key is a comma-separated list of fragments, and a fragment reaches every image whose name
CONTAINS it, which is how SetupTCH.java seeds Ghidra; `common` reaches every image. It lives in
one module because a reader that paired keys its own way agreed with Ghidra only for the keys the
table happened to hold.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

COMMON = "common"


def fragments(key: str) -> list[str]:
    """The fragments of a key, in order, blanks dropped."""
    return [t.strip() for t in key.split(",") if t.strip()]


def reaches(key: str, image: str) -> bool:
    """Whether the rows filed under `key` belong to `image`."""
    return key == COMMON or any(t in image for t in fragments(key))


def images_of(key: str, images: Iterable[str]) -> list[str]:
    """The images, of those given, that `key` reaches."""
    return [i for i in images if reaches(key, i)]


Table = Mapping[str, Sequence[Mapping[str, Any]] | None]


def rows_for(table: Table, image: str) -> list[tuple[str, Any]]:
    """(key, row) of every row of the table that belongs to `image`, `common` first."""
    keys = [COMMON] + [k for k in table if k != COMMON]
    return [(k, row) for k in keys if k in table and reaches(k, image) for row in table[k] or []]
