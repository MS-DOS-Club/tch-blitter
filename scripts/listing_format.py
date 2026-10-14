"""The line formats of the disassembly's tracked files, read the same way by every script.

An annotated listing (`disasm/listings/<image>.lst`, written by `ghidra/ListTCH.java`) holds one
line per unit, `ADDR  BYTES  text`, and one per range the analysis never reached; the executed
addresses (`disasm/executed/<image>.txt`, written by `trace-seeds.py`) hold one `0x` address per
line under a `#` header. Two readers with a copy of each pattern each is how one of them misparses
in silence after the writer changes.
"""

from __future__ import annotations

import re
from pathlib import Path

UNIT = re.compile(r"^([0-9a-f]{8})  ([0-9a-f]*)\s+(\S.*)$")
GAP = re.compile(r"^([0-9a-f]{8})  ; ([0-9a-f]{8})\.\.([0-9a-f]{8})  \d+ bytes")


def executed_addresses(path: Path) -> list[int]:
    """The addresses of an executed-seeds file; a file that holds none is an error, never an
    empty run."""
    ran = [
        int(word, 16) for word in path.read_text(encoding="utf-8").split() if word.startswith("0x")
    ]
    if not ran:
        raise ValueError(f"{path.name} holds no address")
    return ran
