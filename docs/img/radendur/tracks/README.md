# Full track maps (docs/img/radendur/tracks/)

Each section rendered whole from the ROM with `scripts/radendur_tracks_all.py`, emulating the
blitter and the isometric model. The full-resolution version goes to `full/` and the one rescaled
to 1400 px is what illustrates the game page.

The five rescaled images in this folder are versioned; `full/` is not, and regenerates from the ROM
with `uv run scripts/radendur_tracks_all.py` (the other renders: [../sections/README.md](../sections/README.md)).
