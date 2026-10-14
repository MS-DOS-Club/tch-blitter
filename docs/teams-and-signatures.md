# Who made these games: where each name is

An arcade game's credits are easily lost: there is no box art, the board changes hands and the team
disperses. But the code is still there.

**The names are in the README**, credited game by game beside whoever preserved them. This document
is the other half: **where each one comes from**, with the exact address, so that anyone can check
rather than take it on trust. Once `make disasm` has built the program images, it reproduces
whole:

```sh
uv run scripts/signatures.py
uv run scripts/signatures.py --image rltennis_maincpu
```

The sweep looks at **three views of each image**, and that is not a detail: the 68000 image is
interleaved byte by byte from two ROMs, so a text written into BOTH appears with every character
doubled and **only reads correctly de-interleaved**. Reality Tennis's signature is written that way,
which is why an ordinary `strings` over the combined image returns `EESSTTEE JJUUEEGGOO...` and gets
discarded as garbage.

Of the family's **nine** code images, **four carry a signature** and five do not. The ninth is
`rltennisa`, the second Reality Tennis dump, and its signature is IDENTICAL to the first's: the same
two names, nobody added and nobody removed. The revision is by its own authors.

---

## Reality Tennis: a hidden signature, in Spanish

At `0x001000` of `rltennis_maincpu`, readable in each half separately, repeated **four times** in a
row and surrounded by `0xFF` on both sides:

> **"ESTE JUEGO HA SIDO INTEGRAMENTE REALIZADO POR DAVID SANDOVAL Y ANTONIO A. CARRILLO."**

Quoted, and the quotation marks are load-bearing rather than decorative: this is what the ROM holds,
byte for byte, and translating it would falsify the evidence the page exists to record. A rough
rendering, for a reader who does not have the Spanish: *this game was made entirely by* the two
people it names.

It is not text the game paints: it is in Spanish inside a game with an English interface, it repeats
as filler, and its doubled encoding does not match that of any string appearing on screen. It is a
signature, put where it gets in nobody's way.

**And there is a fingerprint of the development environment.** At `0x013210`-`0x0132ff` there are
three near-identical blocks with the string `dos.library`, AmigaDOS `ReadArgs` templates (`FROM/M,T`,
where the `/M` multiple syntax is exclusive to AmigaDOS) and the AmigaOS calling convention
`jsr -414(a6)`, which is `CloseLibrary` from `exec.library`. It appears in the two Reality Tennis images, the
same program, and in none of the other seven. That the three blocks are nearly the same points to residual buffer content from
building the image: **a piece of an Amiga program that ended up inside the arcade ROM**.

---

## Wheels & Fire: the whole team, with job titles

At `0x0e3894` of `wheelfir_maincpu`, fourteen NUL-terminated strings, pairs of label and name, and
68000 code starting right behind them:

| role | who |
|------|-----|
| Executive producer | Francisco Chacon |
| Productive adviser | Jose Sanchez |
| **Hardware design** | **David Sandoval** |
| **Programming** | **Antonio Carrillo** |
| Auxiliar programming | Fernando Jimenez |
| Graphics | Javier Martinez, Francisco Bocanegra, **Joaquin Perez** |

**The two names in bold above are the same ones that sign Reality Tennis.** David Sandoval designs
the Wheels & Fire hardware and Antonio Carrillo programs it; on Reality Tennis the same two sign the
game together.

### And the silicon carries a name

The Reality Tennis board's two FPGAs are labelled **"JOAQUIN"** and **"JUANA"** (the header of
`tch/rltennis.cpp`), and Joaquin Perez is one of the three graphic artists credited here: a chip
named like a member of the team.

---

## Kong Ball (1997): credits, an email address and the initials in the high scores

Kong Ball is signed by **Digital Dreams Multimedia**, and its ROM says so in three ways.

**The credits**, at `0x03f4a7` of `kongball_maincpu`:

| role | who |
|------|-----|
| A game by | DDM (Digital Dreams Multimedia) |
| Programmer | Jesus R. Alvarez |
| Graphics | Julio Lopez and Oscar Cuesta |
| Colleague | Fernando Perez, Luis Fernando Fernandez |

**The club screen**, at `0x03f334`, inviting players to write in: `DIGITAL DREAMS` / `CLUB` /
`If you enyoyed playing` / `KONG BALL, please, send us` / **`ddm@servicom.es`** / `KONG BALL II`.
The `*1997 ALL RIGHTS RESERVED` at `0x048fc2` dates the game.

**And the team's initials, seeded into the default high-score table.** At `0x04afd4`, right behind an
`rts`, there are 28 four-byte entries:

```
QRY FTR CFS IGF ASD PLQ SOH CPD NQA PTA TOB TOD ACG TRP
DDM RJI TUT MCP OSC JUL JRA AAA BBB CCC AAA ASD LKJ LLL
```

Four match the credits: **"DDM"** (Digital Dreams), **"JRA"** (Jesus R. Alvarez), **"JUL"** (Julio Lopez)
and **OSC** (Oscar Cuesta). Others are obvious keyboard filler (`AAA`, `BBB`, `CCC`, `ASD`, `LKJ`,
`LLL`). The rest are unidentified initials.

It is the classic arcade signature vector: the team puts itself into the factory high-score table, so
that its name is there the day the machine is switched on in a bar.

---

## The ones that do not sign

**Radical Enduro holds not one readable text.** Neither in the combined image nor in either half,
neither in the main CPU nor in the sound one. It fits what it is: a prototype that never made it to
manufacture, with half-finished sections and no credits screen.

**Power Ball does not either**, in either of its two images.

And **the three sub-CPU images** (Radical Enduro, Wheels & Fire, Power Ball) are almost pure sound
sample data. Searching them for printable runs returns thousands, but they are an ACCIDENT of the
sample data, not text: none of them forms a word or a signature.

---

## How the sweep is built, and what it cannot find

`scripts/signatures.py` extracts the printable runs from the three views and filters them by MEANING
(the words a team credits itself with, a well-formed email address, a year with word boundaries). It
also discards **character ramps**: the ROMs are full of font test tables
(`!"#$%&'()*+,-./0123...`) that contain at signs, years and practically any substring you look for,
and without that filter they drown the result.

**What this method does NOT find**, and it is worth saying: compressed text, text stored as graphics
(a name drawn on the title screen is not a string), and signatures written in a private encoding. An
empty result here means "no readable strings", not "no signature".
