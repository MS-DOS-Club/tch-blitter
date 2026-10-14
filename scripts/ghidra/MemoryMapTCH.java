// MemoryMapTCH.java -- the 68000 memory map every board of the family shares, for the Ghidra
// scripts beside it. Not a script: a helper class Ghidra compiles from the same script directory,
// so the ranges are written once on this side, as scripts/memory_map.py writes them once on the
// Python side.

public final class MemoryMapTCH {
    private MemoryMapTCH() {}

    /** The vector table fills the first 0x400 bytes of the program ROM. */
    public static final long VECTORS_END = 0x400L;
    /** The program ROM fills the first megabyte. */
    public static final long ROM_END = 0x100000L;
    /** The work RAM, 64 KB. */
    public static final long RAM_START = 0x200000L, RAM_SIZE = 0x10000L;
    /** The board's registers, up to the end of the 24-bit space. */
    public static final long HW_START = 0x700000L, HW_SIZE = 0x100000L;
    /** The blitter's sixteen words. */
    public static final long BLITTER_START = 0x700000L, BLITTER_LAST = 0x70001fL;

    /** In the program ROM, past the vectors: where code can be. */
    public static boolean inCode(long addr) {
        return addr >= VECTORS_END && addr < ROM_END;
    }
}
