"""A set's GAME line is found by its short name, GAMEL included, not by the name anywhere."""

from __future__ import annotations

from script_loader import load_script

vg = load_script("verify_games", "verify-games.py")

WHEELFIR = (
    "GAMEL( 199?, wheelfir,   0, wheelfir,    wheelfir, wheelfir_state, empty_init,    ROT0,  "
    '"TCH", "Wheels & Fire", MACHINE_IMPERFECT_GRAPHICS | MACHINE_SUPPORTS_SAVE, layout_wheelfir )'
)
PWBALL = (
    "GAME( 199?, pwball,      0, wheelfir,    pwball,   wheelfir_state, empty_init,    ROT0,  "
    '"TCH", "Power Ball (prototype)",    MACHINE_SUPPORTS_SAVE )'
)
DRIVER = f"{WHEELFIR}\n{PWBALL}\n"


def test_a_gamel_line_is_its_sets_own() -> None:
    assert vg.macro_in(DRIVER, "wheelfir") == WHEELFIR


def test_a_name_in_another_sets_line_is_not_a_match() -> None:
    assert vg.macro_in(DRIVER, "pwball") == PWBALL
    assert vg.macro_in(DRIVER, "wheelfir_state") is None


def test_without_its_own_line_a_set_finds_none() -> None:
    assert vg.macro_in(f"{PWBALL}\n", "wheelfir") is None


def test_a_clone_line_is_the_clones_not_its_parents() -> None:
    clone = (
        "GAME( 2026, radendurh,   radendur, radendur, pwball,   radendur_state, empty_init, ROT0, "
        '"hack", "Radical Enduro (early prototype, bugfix hack)", MACHINE_SUPPORTS_SAVE )'
    )
    assert vg.macro_in(clone, "radendurh") == clone
    assert vg.macro_in(clone, "radendur") is None


def test_a_gamel_line_with_a_year_states_it() -> None:
    line = WHEELFIR.replace("199?", "1997")
    assert vg.year_in(line, "1997") == (True, True)
