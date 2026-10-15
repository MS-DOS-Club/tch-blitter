"""A game page's fact table is the data file's, with the state read from the GAME macro's flags."""

from __future__ import annotations

from typing import Any

from script_loader import load_script

gg = load_script("gen_games_facts", "gen-games.py")

GAME: dict[str, Any] = {
    "set": "radendur",
    "mame_driver": "tch/wheelfir.cpp",
    "year": {"value": None, "level": "unknown"},
    "mame_status": {"evidence": "MACHINE_NOT_WORKING | MACHINE_IMPERFECT_GRAPHICS"},
    "page": {"board": "the board", "status_note": ": it hangs"},
}


def test_the_state_is_every_flag_of_the_macro() -> None:
    table = gg.facts_table(GAME)
    assert "| status in stock MAME | `NOT_WORKING`, `IMPERFECT_GRAPHICS`: it hangs |" in table
    assert "| year | no known date |" in table
    assert "| driver | `tch/wheelfir.cpp` |" in table


def test_a_working_set_says_so_and_drops_the_save_flag() -> None:
    flags = "MACHINE_IMPERFECT_TIMING | MACHINE_SUPPORTS_SAVE"
    game: dict[str, Any] = dict(GAME, mame_status={"evidence": flags})
    game["variants"] = [{"set": "rltennis"}, {"set": "rltennisa"}]
    table = gg.facts_table(game)
    assert "| status in stock MAME | **working**, `IMPERFECT_TIMING`: it hangs |" in table
    assert "| MAME sets | `rltennis` and `rltennisa` |" in table


def test_the_notes_and_the_driver_here_reach_their_rows() -> None:
    page = dict(GAME["page"], year_note=" (a note)", sets_note=" (the dump)", driver_here="ours")
    game: dict[str, Any] = dict(GAME, page=page, year={"value": "1997", "level": "verified"})
    table = gg.facts_table(game)
    assert "| year | 1997 (a note) |" in table
    assert "| MAME set | `radendur` (the dump) |" in table
    assert "| driver in MAME | `tch/wheelfir.cpp` |" in table
    assert "| driver in this repository | ours |" in table
