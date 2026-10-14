# Assembling graphics from the ROM

The intro text ("SATOR VIDEOGAMES", the RADICAL ENDURO logo) can be rebuilt directly from the
graphics ROM by replicating what the blitter does: the art is complete and correctly stored. The
same approach, generalized, is what `scripts/radendur_track_render.py` uses to rebuild the tracks.

## The palette has to be the exact frame's

Each screen has its own palette, and a fade changes it every frame: the SATOR credits are drawn
mid-fade, with every component in a low, contiguous range. Rendering them with another screen's
palette gives noise, so a reconstruction takes the palette of the exact frame it rebuilds. A
palette confined to a low, contiguous range is the signature of a mid-fade capture, not of data
loss, nor of a 6-bit RAMDAC truncation, which would populate values above that range.

## How the two boards' blits differ

Reality Tennis gives explicit source AND destination end coordinates, so copying its rectangle
needs no scale decoding at all: bounded integer steps reproduce it exactly. Wheels & Fire gives a
start coordinate plus a scale field, so a copy is only as good as the decoding of that field: every
scale has its own 16-byte descriptor in the program ROM, applied by `wf_scale_coord` (`0xe47fe`),
and the percentage is only the index used to find the descriptor (see
[Wheels & Fire](../docs/games/wheels-and-fire.md), "The zoom is not a percentage").

A bounded, integer-step destination walk with no edge adjustment is what composes legible text.
Edge adjustments (`dst_y0 += 1; dst_y1 -= 1`), a do-while destination walk that can wrap past its
exit test, and a floating-point source step all garble text that a bounded, integer-step copy of
the same source rectangle renders correctly.

Two things that look like blit-model defects are not: blits carrying the disable bit
(`d7 & 0x08`) draw nothing, and blits that read regions of index 0 draw nothing visible.

## Tools

`scripts/radendur_track_render.py` implements this model; it is described in `scripts/README.md`.
