"""Tests for scripts/port_names.py.

The listings put these names beside register accesses, so a name on the wrong address, or on a
board that does not have that register, is a wrong fact printed in every listing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "port_names_mod", Path(__file__).resolve().parents[1] / "scripts" / "port_names.py"
)
assert _spec and _spec.loader
pn = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pn
_spec.loader.exec_module(pn)

REGISTERS = {
    "blitter": {
        "base": 0x700000,
        "common_to": ["radendur", "wheelfir"],
        "registers": [{"word": 15, "name": "trigger"}],
    },
    "ports": [{"address": 0x7C0000, "name": "control_and_link", "common_to": ["wheelfir"]}],
}


def test_a_blitter_word_is_named_at_both_bytes_on_the_games_the_block_is_common_to() -> None:
    rows = pn.names(REGISTERS)
    for game in ("radendur", "wheelfir"):
        assert (f"{game}_maincpu", 0x70001E, "trigger") in rows
        assert (f"{game}_maincpu", 0x70001F, "trigger") in rows
    assert not [r for r in rows if r[2] == "trigger" and r[0] == "pwball_maincpu"]


def test_a_port_is_named_only_on_the_games_it_is_common_to() -> None:
    rows = pn.names(REGISTERS)
    assert ("wheelfir_maincpu", 0x7C0001, "control_and_link") in rows
    assert not [r for r in rows if r[2] == "control_and_link" and r[0] != "wheelfir_maincpu"]


def test_reality_tennis_and_the_sound_cpus_get_no_name() -> None:
    rows = pn.names(REGISTERS)
    assert not [r for r in rows if r[0].startswith("rltennis") or "subcpu" in r[0]]
