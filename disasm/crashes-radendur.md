# The two Radical Enduro crashes

The prototype has two different grey screens, and both are the same kind of fault: **game code
walking off its own array**. Neither is an emulation failure: the first happens on the real board
too (MAME's original driver notes it: *"crashes when selecting track on PCB"*), and the second
comes from the game's own RAM state.

The grey screen itself is not a MAME screen: it is the **game's own address-error handler** at
`0x25a4`, the target of vector `0x0c`, which paints the RAMDAC grey and loops at `0x25d4`-`0x25da`
for ever. Seeing it already tells you there has been an address error, not a hang; the bus-error
vector goes to the bare `rte` at `0x25a2` instead.

## Crash 1: entering a race. A memcpy overflow

The routine at `0xe2ed6` (`palette_range_copy`) copies a palette range from a ROM table into the
palette buffer in RAM, and computes the destination by multiplying a "step" read from that same
table by three:

```
0xe2ede  lea 0x203208, a3        ; a3 = base of the palette buffer
0xe2ee4  lea 0xd6b12, a2         ; a2 = data table in ROM
0xe2ef2  move.w 0x8(a6), d0      ; d0 = index (parameter)
0xe2f06  add.w d0,d0 ; add.w d0,d0
0xe2f0a  move.b 0x2(a2,d0.w), d1 ; d1 = step (0-255, from the table)
0xe2f14  adda.l d1,a3            ; a3 += step
0xe2f16  adda.l d1,a3            ; x3
0xe2f18  adda.l d1,a3
0xe2f1c  move.b 0x3(a2,d0.w), d1 ; d1 = length of the copy
0xe2f2c  move.b (a2)+, (a3)+     ; the memcpy
0xe2f32  dbra d1, 0xe2f2c
```

For the race-entry state, `a3 = 0x203208 + 3*step` **runs past the palette buffer and lands on the
display-list cursor block at `0x203508`**, 0x300 bytes further along. The memcpy writes raw ROM
bytes over three display-list pointers; the game then loads them at `0xf21f8`, `0xf2204` and
`0xf220a`, and at `0xf2210` does `clr.w (a1)` with the one from `0x203510`. An odd pointer there
raises an address error: grey screen.

It is a classic overflow: the copy runs past the palette buffer into the cursors beside it, fed by
the out-of-table index of the environment loop (below). The writes are byte writes, and the
overflow stays inside the base RAM (`0x203208` to `0x203508`): it does not cross the 64 KB mirror.

## Crash 2: in a race. A runaway object loop

Different from the previous one and with the same ending. The loop that walks the object list
computes its counter as `min - max - 1`; when that computation underflows, `d7` takes an enormous
value and the loop keeps advancing `a0` **below the array**, reading garbage sprite identifiers
until one of them indexes off the end of a table and falls into the `0x25a4` handler. The faulting
PC lies outside any patched region, and the game addresses 64 KB of RAM only: the fault is the
game's own RAM state.

## Where the fix lives

In the code of the `radendurh` ROM, never in the driver, which emulates the dump as it is: two
word patches of 32 words in total (2 + 5x6), for two faults that hang the game without a crash of
their own here (the BT478 uploader returning with A0 moved under the object drawer, and the prop
sweep reading its x window from a register it never sets, in five copies), and three routines that correct the data the game
reads at the instructions that read it. Crash 1 has no fix of its own: its out-of-table index comes
from the environment loop reading one record past its array, and the routine that corrects that
loop removes the overrun at its source. The table that holds them, each with the words it expects
beside its replacement, is `hardware/radendurh.yaml`; `scripts/radendurh.py` builds the ROM from
the verified dump and refuses any word that is not what it expects.
