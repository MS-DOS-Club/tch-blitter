"""Common fixtures. The romsets are not distributed: the tests that read them skip without them."""

import os
import zipfile

import pytest
from radendur_track_render import ROOT, SPRITE_TABLE, Renderer, load_gfx, load_maincpu

ROMSET = os.path.join(ROOT, "run/mame_roms/radendur.zip")


@pytest.fixture(scope="session")
def rd():
    if not os.path.exists(ROMSET):
        pytest.skip("no run/mame_roms/radendur.zip (the romsets are not distributed)")
    with zipfile.ZipFile(ROMSET) as z:
        # load_maincpu/load_gfx return whole bytes, so the Renderer outlives the zip
        return Renderer(load_maincpu(z), load_gfx(z))


@pytest.fixture(scope="session")
def n_sprites(rd):
    """Entries of the sprite table, derived: its first entry points to its end."""
    return (rd.u32(SPRITE_TABLE) - SPRITE_TABLE) // 4
