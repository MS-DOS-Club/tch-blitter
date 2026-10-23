"""gen-games.py -- the README's game, resource, credits and preservation tables, and each game
page's facts and thanks, from hardware/games.yaml. Each fact keeps its level: `verified` is written
as it stands, `external` is marked, `unknown` is said rather than filled in (MAME's `199?` is a
fact).

USE:
    uv run scripts/gen-games.py            writes the blocks
    uv run scripts/gen-games.py --check    fails if they are out of sync
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import doc_blocks
import yaml

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "hardware" / "games.yaml"
TCH = ROOT / "upstream" / "src" / "mame" / "tch"


PAGE = {
    "rltennis": "reality-tennis",
    "wheelfir": "wheels-and-fire",
    "pwball": "power-ball",
    "kongball": "kong-ball",
    "radendur": "radical-enduro",
}
# two states, because there are two drivers: stock MAME's at the pin, and this repository's
HEAD_GAMES = "| game | set | year | manufacturer | state in stock MAME | state here |"
HEAD_RESOURCES = "| game | main 68000 | sound 68000 | graphics | other ROMs |"
HEAD_CREDITS = "| game | who made it, according to its own ROM |"
HEAD_PRESERVED = "| game | who preserved it |"
# A game with no authors does NOT get an empty row: it gets the negative, which is a fact.
NO_AUTHORS = "_none legible in the ROM_"


def year_of(j: dict) -> str:
    a = j["year"]
    if a["level"] == "unknown":
        return "_unknown_ (`199?`)"
    txt = str(a["value"])
    if a.get("discrepancy"):
        txt += " ⚠"
    if a["level"] == "external":
        txt += " *"
    return txt


def mame_state_of(j: dict) -> str:
    return str(j["mame_status"]["value"])


def driver_state_of(j: dict) -> str:
    return str(j["driver_status"]["value"])


def sets_of(j):
    """A game's MAME sets, which may be more than one.

    Reality Tennis has TWO, and the cover page does not grow because of it: it is one game with two
    revisions, not two games, and that is how a newcomer reads it. The detail of how they differ
    lives on its page, which is where the captures showing it fit.
    """
    sets = [v["set"] for v in j.get("variants", [])] or [j["set"]]
    return ", ".join(f"`{s}`" for s in sets)


PAGE_KEYS = {"board", "driver_here", "year_note", "sets_note", "status_note"}


def flags_of(j: dict) -> list[str]:
    """The GAME macro's flags, as verify-games.py checks them against the driver: the state."""
    flags = re.findall(r"MACHINE_(\w+)", j["mame_status"]["evidence"])
    return [f for f in flags if f != "SUPPORTS_SAVE"]


def check_page(j: dict) -> None:
    """INVALID (3) for page data that would render a lie: a typo'd note vanishing through .get,
    evidence with no MACHINE_ flag at all, a known year with no value."""
    if j["set"] not in PAGE or "board" not in j.get("page", {}):
        print(f"INVALID: {j['set']} has no game page in PAGE, or no `page: board` in games.yaml")
        sys.exit(3)
    unknown = set(j["page"]) - PAGE_KEYS
    no_flags = not re.search(r"MACHINE_\w+", j["mame_status"]["evidence"])
    if unknown or no_flags or (j["year"]["level"] != "unknown" and not j["year"]["value"]):
        print(
            f"INVALID: {j['set']}: unknown page keys {sorted(unknown)}, no MACHINE_ flag, "
            "or a known year with no value"
        )
        sys.exit(3)


def facts_table(j: dict) -> str:
    """A game page's fact table: the year, the sets, the driver and the state in stock MAME are
    the data file's; the board, the driver here and the short notes are the page's own, under
    `page:`."""
    page = j["page"]
    year = j["year"]
    known = "no known date" if year["level"] == "unknown" else str(year["value"])
    sets = [v["set"] for v in j.get("variants", [])] or [j["set"]]
    flags = flags_of(j)
    state = ", ".join(f"`{f}`" for f in flags)
    if "NOT_WORKING" not in flags:
        state = f"**working**, {state}" if state else "**working**"
    rows = [
        "| | |",
        "|---|---|",
        f"| year | {known}{page.get('year_note', '')} |",
        f"| board | {page['board']} |",
        f"| MAME set{'s' if len(sets) > 1 else ''} | "
        f"{' and '.join(f'`{x}`' for x in sets)}{page.get('sets_note', '')} |",
    ]
    driver = f"`{j['mame_driver']}`"
    if "driver_here" in page:
        rows += [
            f"| driver in MAME | {driver} |",
            f"| driver in this repository | {page['driver_here']} |",
        ]
    else:
        rows.append(f"| driver | {driver} |")
    rows.append(f"| status in stock MAME | {state}{page.get('status_note', '')} |")
    return "\n".join(rows) + "\n"


def page_link(page):
    return f"docs/games/{page}.md"


def games_table(data: dict) -> str:
    """The table, with the footnotes that are NEEDED and no others.

    A note explaining a symbol absent from the table is noise and ages badly: it says there is an
    external fact when there no longer is one, and the reader goes looking for it.
    """
    rows = [HEAD_GAMES, "|---|---|---|---|---|---|"]
    marks: set[str] = set()
    for j in data["games"]:
        year = year_of(j)
        marks.update(m for m in ("*", "⚠", "199?") if m in year)
        page = PAGE.get(j["set"], j["set"])
        rows.append(
            f"| [{j['name']}]({page_link(page)}) | {sets_of(j)} | {year} | "
            f"{j['manufacturer']['value']} | {mame_state_of(j)} | {driver_state_of(j)} |"
        )
    notes = {
        "*": "`*` from an external source, not verifiable in the binary.",
        "⚠": "`⚠` sources contradict each other: the game's page says which ones and why this "
        "value is the published one.",
        "199?": "`199?` is MAME's own: the year of those games was lost, and is not filled in.",
    }
    footnote = " ".join(notes[m] for m in ("*", "⚠", "199?") if m in marks)
    return "\n".join(rows) + "\n" + (f"\n{footnote}\n" if footnote else "")


def credits_table(data: dict) -> str:
    """Who made each game, read from its own ROM.

    THE ROM'S OWN LABELS go exactly as they come out of the binary: they are verifiable by opening
    the ROM at the offset the evidence names, and rewording them would turn a fact into an
    interpretation. The `role` is only used where the ROM carries no literal.
    """
    rows = [HEAD_CREDITS, "|---|---|"]
    with_authors = 0
    for j in data["games"]:
        authors = j.get("authors") or []
        if authors:
            with_authors += 1
            people = "; ".join(
                f"**{a['who']}** ({a.get('role_rom') or a['role']})" for a in authors
            )
        else:
            people = NO_AUTHORS
        page = PAGE.get(j["set"], j["set"])
        rows.append(f"| [{j['name']}]({page_link(page)}) | {people} |")
    if not with_authors:
        print("INVALID: not one game declares authors; this table would say nothing")
        sys.exit(3)
    note = (
        "\nRead from the ROMs themselves; the offset of each finding is in "
        "[docs/teams-and-signatures.md](docs/teams-and-signatures.md)."
    )
    return "\n".join(rows) + "\n" + note + "\n"


def preservation_table(data: dict) -> str:
    """Who preserved each game, credited per game."""
    if not data.get("preservation"):
        print("INVALID: there is nobody under `preservation`; the table would come out empty")
        sys.exit(3)
    rows = [HEAD_PRESERVED, "|---|---|"]
    for j in data["games"]:
        theirs = preservers_of(data, j["set"])
        page = PAGE.get(j["set"], j["set"])
        text = "; ".join(f"**{p['who']}** ({p['role']})" for p in theirs)
        rows.append(f"| [{j['name']}]({page_link(page)}) | {text} |")
    note = (
        "\nWithout them there would be nothing to emulate: without the boards dumped and "
        "the original drivers written, this repository does not exist."
    )
    return "\n".join(rows) + "\n" + note + "\n"


def preservers_of(data: dict, game: str) -> list[dict]:
    """A game's preservation entries in the file's order, which puts the original drivers' authors
    first; INVALID when there is none or an entry lacks its `who` or `role`."""
    theirs = [p for p in data.get("preservation") or [] if game in (p.get("games") or [])]
    if not theirs:
        print(f"INVALID: {game} has not one preserver credited")
        sys.exit(3)
    for p in theirs:
        if not p.get("who") or not p.get("role"):
            print(f"INVALID: a preservation entry of {game} lacks its `who` or its `role`: {p}")
            sys.exit(3)
    return theirs


def thanks_list(data: dict, game: str) -> str:
    """One game's preservers for its own page; the README's table carries the same entries."""
    return "\n".join(f"- **{p['who']}**: {p['role']}." for p in preservers_of(data, game)) + "\n"


def regions(romset: str) -> dict[str, tuple[int, int]]:
    """region -> (number of dumped ROMs, bytes), read from the driver's ROM_START.

    A `NO_DUMP` load is an empty socket, not a ROM, so it is not counted: a region holding only
    those reads (0, 0). The walk collects every file that defines the set and STOPS if two disagree,
    rather than publishing whichever sorts first.
    """
    seen: dict[str, dict[str, tuple[int, int]]] = {}
    for f in sorted(TCH.glob("*.cpp")) if TCH.exists() else []:
        text = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(rf"ROM_START\(\s*{re.escape(romset)}\s*\).*?ROM_END", text, re.S)
        if not m:
            continue
        by_region = {}
        for b in re.finditer(
            r'ROM_REGION\w*\([^,]+,\s*"([^"]+)".*?(?=ROM_REGION|ROM_END)', m.group(0), re.S
        ):
            loads = re.findall(
                r"ROM_LOAD\w*\([^,]+,\s*0x[0-9a-fA-F]+,\s*(0x[0-9a-fA-F]+)([^\n]*)", b.group(0)
            )
            if loads:
                dumped = [size for size, rest in loads if "NO_DUMP" not in rest]
                by_region[b.group(1)] = (len(dumped), sum(int(c, 16) for c in dumped))
        seen[f.name] = by_region
    if not seen:
        return {}
    distinct = {tuple(sorted(v.items())) for v in seen.values()}
    if len(distinct) > 1:
        print(
            f"INVALID: `{romset}` has different ROM_START blocks in {', '.join(sorted(seen))}. "
            "Publishing one of the two would be choosing by alphabetical order; say which holds."
        )
        sys.exit(3)
    return next(iter(seen.values()))


def size_of(octets: int) -> str:
    return f"{octets // 1024} KB" if octets % 1024 == 0 else f"{octets} B"


def resources_table(data: dict) -> str:
    """A ROM table by region, read from the drivers in `upstream/`; without them it fails rather
    than write a table with no rows."""
    rows = [HEAD_RESOURCES, "|---|---|---|---|---|"]
    no_data = []
    for j in data["games"]:
        r = regions(j["set"])
        if not r:
            no_data.append(j["set"])
            continue
        # The graphics region's name is not the same across the two drivers (`gfx` in rltennis,
        # `gfx1` in the others), so it is looked up by prefix and not by equality.
        gfx = [k for k in r if k.startswith("gfx")]
        main_regions = {"maincpu", "subcpu", *gfx}

        def cell(region_names: list[str], r: dict = r) -> str:
            present = [k for k in region_names if k in r]
            if not present:
                return "--"
            n = sum(r[k][0] for k in present)
            b = sum(r[k][1] for k in present)
            return f"{b // 1024} KB in {n}" if n else "not dumped (empty sockets)"

        others = ", ".join(
            f"{k} {size_of(v[1])}" for k, v in r.items() if k not in main_regions and v[1] > 0
        )
        rows.append(
            f"| {j['name']} | {cell(['maincpu'])} | {cell(['subcpu'])} | {cell(gfx)} | "
            f"{others or 'none'} |"
        )
    if no_data:
        print(
            f"INVALID: no ROM_START for {', '.join(no_data)}. The table would come out incomplete "
            "and nothing would say so. Complete `upstream/` with `make setup`."
        )
        sys.exit(3)
    if len(rows) == 2:
        print(
            f"INVALID: not one ROM_START read in {TCH}. Without `upstream/` this table would come "
            "out empty; run `make setup` instead of publishing a hole."
        )
        sys.exit(3)
    note = "\nRead from the `ROM_START` blocks of the MAME drivers."
    return "\n".join(rows) + "\n" + note + "\n"


def insert_block(text: str, label: str, content: str, where: str) -> str:
    return doc_blocks.replace(text, doc_blocks.opener("gen-games.py", label), content, where)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(GAMES.read_text(encoding="utf-8"))
    if not data.get("games"):
        print("INVALID: hardware/games.yaml declares not one game")
        sys.exit(3)

    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    new_text = insert_block(text, "games-table", games_table(data), "README.md")
    new_text = insert_block(new_text, "resources-table", resources_table(data), "README.md")
    new_text = insert_block(new_text, "credits-table", credits_table(data), "README.md")
    new_text = insert_block(new_text, "preservation-table", preservation_table(data), "README.md")
    pending = {path: (text, new_text)}
    for j in data["games"]:
        check_page(j)
        page_path = ROOT / page_link(PAGE[j["set"]])
        if not page_path.is_file():
            print(f"INVALID: {page_path.relative_to(ROOT)}, the page of {j['set']}, does not exist")
            sys.exit(3)
        page_text = page_path.read_text(encoding="utf-8")
        where = str(page_path.relative_to(ROOT))
        new_page = insert_block(page_text, "facts", facts_table(j), where)
        new_page = insert_block(new_page, "thanks", thanks_list(data, j["set"]), where)
        pending[page_path] = (page_text, new_page)
    stale = [p for p, (old, new) in pending.items() if old != new]
    if stale and args.check:
        for p in stale:
            print(f"out of sync: {p.relative_to(ROOT)}  (run: uv run scripts/gen-games.py)")
        return 1
    for p in stale:
        p.write_text(pending[p][1], encoding="utf-8", newline="\n")
        print(f"  blocks written into {p.relative_to(ROOT)}")
    if not stale:
        print("==> the game tables are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
