"""Imports a script of scripts/ by path, for the tests: most carry a hyphen in their name, which
the import statement cannot spell."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str, file: str) -> ModuleType:
    """`scripts/<file>` as the module `name`, registered so dataclasses can find it."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod
