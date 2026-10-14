"""verify-games.py -- what hardware/games.yaml marks as verified really is.

A level says what can be trusted: `verified` (read from a binary or MAME's code), `external` (an
outside source, named in `sources`) or `unknown` (said, not filled in). This checks:

- verified states: `mame_status` against the set's `GAME(...)` flags in stock MAME at the pinned
  commit, `driver_status` against this repository's driver;
- verified years and manufacturers against the driver's `GAME(...)` macro, and an `unknown` one
  against what MAME does not know either (`199?`, `<unknown>`);
- authors and credits verified with ROM evidence: the text is at the offset the evidence names;
- an `external` fact names a source, an `unknown` one carries no value, a missing key is listed;
- a rejected attribution has not come back (the name a rejection quotes, as a whole name).

Whether an external source tells the truth is beyond it: such a fact is published cited and marked.

USAGE:
    uv run scripts/verify-games.py
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "hardware" / "games.yaml"
TCH = ROOT / "upstream" / "src" / "mame" / "tch"
IMGDIR = ROOT / "disasm" / "img"

MAME_SRC_LIB = ROOT / "scripts" / "lib" / "mame_src.sh"
_FLAG = re.compile(r"\bMACHINE_[A-Z_]+\b")
_OFFSET = re.compile(r"([a-z0-9_]+) (0x[0-9a-f]{4,6})", re.IGNORECASE)


def game_macro(machine: str) -> str | None:
    """That set's GAME(...) line, looked for across every tch driver."""
    if not TCH.exists():
        return None
    for f in sorted(TCH.glob("*.cpp")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("GAME(") and re.search(rf"\b{re.escape(machine)}\b", line):
                return line
    return None


@cache
def stock_macros() -> dict[str, str] | None:
    """Every tch `GAME(...)` line of stock MAME at the pinned commit, by set; None when the clone
    cannot answer. The pin is read from the one file that declares it, never repeated here."""
    pin = re.search(
        r'^MAME_PINNED_COMMIT="([0-9a-f]{40})"', MAME_SRC_LIB.read_text(encoding="utf-8"), re.M
    )
    clone = ROOT / "upstream"
    if pin is None or not (clone / ".git").exists():
        return None

    def git(*args: str) -> str | None:
        r = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, encoding="utf-8")
        return r.stdout if r.returncode == 0 else None

    names = git("ls-tree", "--name-only", pin.group(1), "src/mame/tch/")
    if not names:
        return None
    macros: dict[str, str] = {}
    for path in names.split():
        text = git("show", f"{pin.group(1)}:{path}") if path.endswith(".cpp") else None
        for line in (text or "").splitlines():
            m = re.match(r"GAME\(\s*[^,]+,\s*(\w+)", line)
            if m:
                macros[m.group(1)] = line
    return macros


def check_status(name: str, what: str, status: object, macro: str | None) -> tuple[int, list[str]]:
    """A `verified` state against the flags of the macro it describes."""
    level, failures = level_of(status, f"{name}'s {what}")
    if level != "verified" or macro is None:
        return 0, failures
    assert isinstance(status, dict)
    claimed = set(_FLAG.findall(str(status.get("evidence", ""))))
    actual = set(_FLAG.findall(macro))
    if claimed != actual:
        failures.append(
            f"{name}: {what} claims {' | '.join(sorted(claimed)) or 'no flag'}, "
            f"its GAME macro says {' | '.join(sorted(actual)) or 'no flag'}"
        )
    return 1, failures


def text_in_image(image: str, offset: int, needle: str) -> bool:
    """Is that string in that image, in the combined one or in one of its halves?"""
    data = (IMGDIR / f"{image}.bin").read_bytes()
    # A generous window around the offset is searched: the evidence points at the start of the
    # credits block, not at the string itself.
    # without case: Wheels & Fire writes its credits in upper case, Kong Ball in mixed case
    needle_b = needle.lower().encode("latin1")
    for view, factor in ((data, 1), (data[0::2], 2), (data[1::2], 2)):
        start = max(0, offset // factor - 64)
        if needle_b in view[start : start + 512].lower():
            return True
    return False


def driver_phrase(who: str, ev: str) -> tuple[bool, list[str]]:
    """Evidence citing a driver file and a quoted phrase, the way MAME's original drivers are
    credited in their .cpp header: whether it could be checked, and the failure if it could."""
    src = re.search(r"([a-z0-9_]+\.cpp)", ev)
    phrase = re.search(r'"([^"]{8,})"', ev)
    if not (src and phrase and (TCH / src.group(1)).exists()):
        return False, []
    if phrase.group(1) in (TCH / src.group(1)).read_text(encoding="utf-8", errors="replace"):
        return True, []
    return True, [f"{who}: {phrase.group(1)!r} was not found in {src.group(1)}"]


LEVELS = ("verified", "external", "unknown")


def level_of(entry: object, label: str) -> tuple[str | None, list[str]]:
    """An entry's `level`, or None with why it has none usable; an `external` one needs a source."""
    level = entry.get("level") if isinstance(entry, dict) else None
    if not isinstance(entry, dict) or "level" not in entry:
        return None, [f"{label}: no `level`"]
    if level not in LEVELS:
        return None, [f"{label}: unknown level {level!r}"]
    if level == "external" and not entry.get("sources"):
        return level, [f"{label}: marked external and with no source"]
    return level, []


def year_in(macro: str, value: object) -> tuple[bool, bool]:
    """Whether MAME knows the year (not `199?`), and whether this value is it."""
    known = "199?" not in macro and bool(re.search(r"GAME\(\s*(19|20)\d\d", macro))
    return known, str(value) in macro


def maker_in(macro: str, value: object) -> tuple[bool, bool]:
    """Whether MAME knows the maker (not `<unknown>`), and whether this value is it. The macro's
    maker is quoted; its first word being there is enough, since compound ones such as
    "TCH / Sator Videogames" are written the same way on both sides."""
    quoted = re.findall(r'"([^"]*)"', macro)
    known = bool(quoted) and quoted[0] != "<unknown>"
    return known, bool(value) and str(value).split()[0] in macro


def check_fact(
    name: str, what: str, fact: object, macro: str | None, read: Callable[..., tuple[bool, bool]]
) -> tuple[int, list[str]]:
    """One `year` or `manufacturer` against its level: how many were checked, and the failures.
    `read` says how MAME's macro states that field; the rules per level are the same for both."""
    level, failures = level_of(fact, f"{name}'s {what}")
    if level is None or level == "external":
        return 0, failures
    assert isinstance(fact, dict)
    value = fact.get("value")
    # A value on an unknown fact is wrong with or without a macro to compare it against.
    if level == "unknown" and value is not None:
        failures.append(f"{name}: {what} marked unknown yet carrying {value!r}")
    if macro is None:
        return 0, failures
    known, matches = read(macro, value)
    if level == "verified":
        return 1, [] if matches else [f"{name}: {what} {value!r} does not appear in its GAME macro"]
    if known:
        failures.append(
            f"{name}: the {what} is unknown here and MAME DOES know it; read its GAME macro"
        )
    return 1, failures


def main() -> int:
    data = yaml.safe_load(GAMES.read_text(encoding="utf-8"))
    failures: list[str] = []
    checked = 0
    uncheckable: list[str] = []

    for j in data["games"]:
        name = j.get("name") or j.get("set") or "?"
        missing = [
            k
            for k in ("set", "name", "year", "manufacturer", "mame_status", "driver_status")
            if k not in j
        ]
        if missing:
            failures += [f"{name}: no `{k}`" for k in missing]
            continue
        macro = game_macro(j["set"])
        if macro is None:
            uncheckable.append(f"{name}: its GAME macro was not found (is the MAME clone missing?)")

        for what, read in (("year", year_in), ("manufacturer", maker_in)):
            n, found = check_fact(name, what, j[what], macro, read)
            checked += n
            failures += found

        stock = stock_macros()
        if stock is None:
            uncheckable.append(f"{name}: stock MAME at the pin could not be read (no clone?)")
        elif j["set"] not in stock:
            failures.append(f"{name}: stock MAME at the pin has no GAME macro for {j['set']}")
        for what, against in (
            ("mame_status", None if stock is None else stock.get(j["set"])),
            ("driver_status", macro),
        ):
            n, found = check_status(name, what, j[what], against)
            checked += n
            failures += found

        # --- authors and preservation
        for a in j.get("authors") or []:
            level, found = level_of(a, a.get("who", "?"))
            failures += found
            if level != "verified":
                continue
            ev = a.get("evidence", "")
            m = _OFFSET.search(ev)
            if not m:
                could, found = driver_phrase(a["who"], ev)
                checked += could
                failures += found
                if not could:
                    uncheckable.append(
                        f"{a['who']} ({a['role']}): evidence with no offset nor checkable file"
                    )
                continue
            image, offset = m.group(1), int(m.group(2), 16)
            # No image at all is a gate that could not look; images present and this one not
            # among them is evidence naming something that does not exist, which is a finding.
            if not any(IMGDIR.glob("*.bin")):
                uncheckable.append(f"{a['who']}: no image in {IMGDIR.name}/ (run make disasm)")
                continue
            checked += 1
            if not (IMGDIR / f"{image}.bin").exists():
                failures.append(f"{a['who']}: its evidence names {image}, which is not an image")
                continue
            # the first name, compared without case
            needle = a["who"].split(",")[0].strip().split()[0].upper()
            if not text_in_image(image, offset, needle):
                failures.append(f"{a['who']}: {needle!r} was not found near {image} {offset:#08x}")

    for a in data.get("preservation") or []:
        level, found = level_of(a, a.get("who", "?"))
        failures += found
        if level != "verified":
            continue
        could, found = driver_phrase(a["who"], a.get("evidence", ""))
        checked += could
        failures += found
        if not could:
            uncheckable.append(f"{a['who']}: evidence not automatically checkable")

    # every rejection carries its reason and its date, and none may come back as a field's value
    rejected = data.get("rejected") or []
    for r in rejected:
        if not r.get("reason"):
            failures.append(f"rejection {r.get('datum')!r} with no reason")
        if not r.get("date"):
            failures.append(f"rejection {r.get('datum')!r} with no date")
        # A rejected person, the name the rejection quotes, cannot appear as anybody's `who`.
        for person in re.findall(r'"([^"]+)"', r.get("datum", "")):
            whole = re.compile(rf"\b{re.escape(person)}\b")
            for j in data["games"]:
                for a in j.get("authors") or []:
                    if whole.search(a.get("who", "")):
                        failures.append(
                            f"{person!r} is rejected and appears as an author of {j.get('name')}"
                        )
    print(f"rejections watched: {len(rejected)}")

    print(f"data checked against its evidence: {checked}")
    if uncheckable:
        print(f"not checkable ({len(uncheckable)}):")
        for s in uncheckable:
            print(f"  {s}")
    # A failure that needs no evidence (an external fact with no URL, a rejection coming back) is
    # a finding whatever else could be checked, so it is reported before the INVALID and is never
    # masked as "could not look".
    if failures:
        print(f"\nFAILURES: {len(failures)}")
        for f in failures:
            print(f"  {f}")
        return 1
    if checked == 0:
        print("INVALID: not a single datum was checked. The MAME clone or the images are missing.")
        return 3
    print("\n==> everything marked as verified matches its evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
