"""The 68000 memory map every board of the family shares, as the scripts read addresses.

The program ROM fills the first megabyte, its first 0x400 bytes the vector table; the work RAM is
64 KB at 0x200000; the board's registers start at 0x700000. One module, because a range written
into each script is a range one of them gets wrong. The Ghidra scripts read the same map from
`scripts/ghidra/MemoryMapTCH.java`.
"""

from __future__ import annotations

VECTORS_END = 0x400
ROM_END = 0x100000
RAM_START, RAM_END = 0x200000, 0x210000
HARDWARE_START = 0x700000
BLITTER_START, BLITTER_LAST = 0x700000, 0x70001F  # its sixteen words


def in_code(addr: int) -> bool:
    """In the program ROM, past the vectors: where code can be."""
    return VECTORS_END <= addr < ROM_END


def in_ram(addr: int) -> bool:
    return RAM_START <= addr < RAM_END
