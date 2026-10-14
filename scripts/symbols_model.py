"""symbols_model.py -- the symbol table hardware/symbols.yaml: its rules and its two renders.

Carved out of gen-hw-docs.py, which projects the whole of hardware/ and was also the only place
that knew what a valid symbol row is. The rules (`validate_symbols`) and the files the tools read
(`symbols_file`, Ghidra's seed; `debugger_symbols_file`, one image for a debugger) live
here, and every pairing of a key with an image goes through image_keys.
"""

from __future__ import annotations

from pathlib import Path

from image_keys import COMMON, fragments, images_of, reaches, rows_for
from memory_map import in_code, in_ram

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "disasm" / "img"


def flatten(text):
    """Flattens a multi-line text so it fits on one line or in a table cell."""
    return " ".join(str(text).split()) if text else ""


def real_keys(symbols):
    """The image keys that are a PATH, that is all of them except the wildcard.

    `common` does not name an image: the emitter turns it into `@image *` and it is seeded into all
    of them. It is kept apart in ONE place so the two halves cannot drift, which is how a special
    case written twice ends up contradicting the emitter.
    """
    return [k for k in (symbols.get("images") or {}) if k != COMMON]


def validate_symbols(symbols):
    """A repeated symbol, two names for one address, or a confirmed one with no evidence.

    A name read off the disassembly by eye is a guess; a confirmed one needs its evidence.
    """
    failures = []
    # Every key must reach an image: SetupTCH.java applies a block to the images whose name
    # contains its fragment, so a mistyped key seeds nothing and says nothing.
    real_images = sorted(p.stem for p in IMAGES.glob("*.bin"))
    if not real_images:
        failures.append(
            "symbols: WARNING, there are no images in disasm/img, so neither the key routing nor "
            "the collisions between blocks have been checked (run 'make disasm')"
        )
    for image in real_keys(symbols):
        for piece in fragments(image):
            if real_images and not any(piece in r for r in real_images):
                failures.append(
                    f"symbols[{image}]: fragment '{piece}' reaches no image of "
                    f"disasm/img; its symbols would be seeded nowhere"
                )
    # Two blocks reaching one image with one address under two names: one of them is filed under
    # the wrong image (0x700000 is the blitter on the main 68000 and a DAC on the sound one). The
    # `common` block's own names are not collisions.
    by_image = {}
    for image in real_keys(symbols):
        entries = symbols["images"][image]
        for real in real_images:
            if not reaches(image, real):
                continue
            for e in entries or []:
                if "addr" not in e or "name" not in e:
                    continue
                seen_at_addr = by_image.setdefault(real, {})
                previous = seen_at_addr.setdefault(e["addr"], (image, e["name"]))
                if previous[1] != e["name"]:
                    failures.append(
                        f"symbols: in {real}, {e['addr']:#010x} is named by two blocks "
                        f"('{previous[0]}' calls it {previous[1]}, "
                        f"'{image}' calls it {e['name']}); "
                        f"one of the two is filed under the wrong image"
                    )

    for image, entries in (symbols.get("images") or {}).items():
        seen = {}
        names = {}
        for e in entries or []:
            if "addr" not in e or "name" not in e:
                failures.append(f"symbols[{image}]: entry with no addr or no name")
                continue
            if e["addr"] in seen and seen[e["addr"]] != e["name"]:
                failures.append(
                    f"symbols[{image}]: {e['addr']:#010x} with two names "
                    f"({seen[e['addr']]} and {e['name']})"
                )
            # THE SAME ADDRESS WITH THE SAME NAME, TWICE, which the other two checks miss because
            # they demand that something DIFFER. It is not harmless: `disasm/symbols.txt` is the
            # seed Ghidra eats, and a repeated address comes out as two lines with two different
            # descriptions, of which Ghidra applies whichever.
            if e["addr"] in seen and seen[e["addr"]] == e["name"]:
                failures.append(
                    f"symbols[{image}]: {e['name']} at {e['addr']:#010x} is DUPLICATED; "
                    f"merge the two entries, symbols.txt emits it twice"
                )
            seen[e["addr"]] = e["name"]
            # ONE NAME AT TWO ADDRESSES, the symmetric case: two routines describing different
            # things under one name. An address with two names shows up on reading; a name at two
            # addresses does not, because every site citing it looks self-consistent.
            if e["name"] in names and names[e["name"]] != e["addr"]:
                failures.append(
                    f"symbols[{image}]: {e['name']} at two addresses "
                    f"({names[e['name']]:#010x} and {e['addr']:#010x})"
                )
            names[e["name"]] = e["addr"]
            # `type` only accepts `data`: it is the mark that exempts a symbol from having to
            # decode as code (a pointer table, a descriptor). An invented value there exempts in
            # silence, which is precisely what the verifier exists to prevent.
            if e.get("type") not in (None, "data"):
                failures.append(f"symbols[{image}]: {e['name']} with unknown type '{e['type']}'")
            # `runs_from` is where a ROM routine executes once the game has copied it to RAM.
            # SetupTCH.java disassembles such a symbol (through symbols.txt's @code line) and the
            # audit expects code there, so a value outside the RAM, or on a symbol that is not in
            # ROM, would have them treat the wrong bytes as code in silence.
            runs_from = e.get("runs_from")
            if runs_from is not None and not (
                isinstance(runs_from, int) and in_ram(runs_from) and in_code(e["addr"])
            ):
                failures.append(
                    f"symbols[{image}]: {e['name']} runs_from must be a RAM address "
                    f"(0x200000..0x20ffff) on a ROM symbol"
                )
            state_ = e.get("state")
            if state_ == "confirmed" and not e.get("evidence"):
                failures.append(f"symbols[{image}]: {e['name']} marked confirmed, no evidence")
            if state_ not in (None, "confirmed", "open", "refuted"):
                failures.append(f"symbols[{image}]: {e['name']} with unknown state '{state_}'")
    return failures


def symbols_file(symbols):
    """The render of disasm/symbols.txt: Ghidra's analysis seed.

    It is generated so the seed and the documentation cannot come apart. SetupTCH.java fixes the
    format: "<hexaddr>  <label>  <description>", with "@image <fragment>" blocks, and an
    "@code <hexaddr>" line after a symbol with `runs_from`: code the game runs from a RAM copy,
    which Ghidra's flow would otherwise only ever see read as data by the copy loop.
    """
    lines = [
        "# symbols.txt -- GENERATED by scripts/gen-hw-docs.py from hardware/symbols.yaml.",
        "# Do not edit by hand: the source is hardware/symbols.yaml (make hw-docs).",
        "#",
        "# SetupTCH.java consumes it to seed the Ghidra analysis. An '@image <fragment>' block",
        "# applies only to the images whose name contains the fragment; '@image *' returns to what",
        "# is common (the hardware map and the vectors). '@code <addr>' marks code the game runs",
        "# from a RAM copy, which SetupTCH.java disassembles before the analysis.",
        "",
    ]
    order = [COMMON] + sorted(real_keys(symbols))
    for image in order:
        entries = symbols["images"].get(image) or []
        if not entries:
            continue
        lines.append(f"@image {'*' if image == COMMON else image}")
        lines.append("")
        for e in entries:
            desc = flatten(e.get("description") or "")
            lines.append(f"0x{e['addr']:08x}  {e['name']:<20s}  {desc}".rstrip())
            if e.get("runs_from") is not None:
                lines.append(f"@code 0x{e['addr']:08x}  runs from 0x{e['runs_from']:08x}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def debugger_symbols_file(symbols, image):
    """The symbols of ONE image, as addr:/name: pairs for a debugger.

    The `symbols.txt` above is for Ghidra and holds every image in a single file, separated by
    `@image` blocks. The debugger's reader does not understand those blocks: it picks up any
    `addr:`/`name:` pair it finds, so pointing it at the whole YAML would load the Wheels & Fire
    symbols onto Radical Enduro's addresses. A symbol from another game sitting on this one's
    address is exactly how a routine gets misnamed, and afterwards nobody questions it.
    """
    lines = [
        f"# GENERATED by scripts/gen-hw-docs.py: the symbols of {image} plus the common ones.",
        "# Format: addr:/name: pairs, for a debugger.",
        "symbols:",
    ]

    # An image picks up every block its key reaches, the shared ones included: they are the
    # hardware map the boards have in common, the symbols worth most.
    for _, e in rows_for(symbols["images"], image):
        lines.append(f"  - addr: 0x{e['addr']:08x}")
        lines.append(f"    name: {e['name']}")
    return "\n".join(lines) + "\n"


def debugger_images(symbols, extracted):
    """The images that get a debugger file: one per image the table's keys reach.

    A fragment naming part of a name (`wheelfir`) is expanded to the extracted images it reaches,
    so its rows land in those images' files; with no image extracted it can only stand for
    itself, which every key that names whole images does.
    """
    images = set()
    for f in (f for k in real_keys(symbols) for f in fragments(k)):
        images |= set(images_of(f, extracted)) or {f}
    return sorted(images)
