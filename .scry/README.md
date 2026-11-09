# `.scry/`

How this repository's arcade boards start under SCRY. Each file in `start/` boots one board:

| file | board |
| --- | --- |
| `radendur.json` | Radical Enduro, the early prototype |
| `radendurh.json` | Radical Enduro, the clone whose ROM this repository fixes |
| `wheelfir.json` | Wheels & Fire |
| `pwball.json` | Power Ball |
| `kongball.json` | Kong Ball |
| `rltennis.json` | Reality Tennis |
| `rltennisa.json` | Reality Tennis, the second layout |

Build first: `make setup` and `make disasm`.
