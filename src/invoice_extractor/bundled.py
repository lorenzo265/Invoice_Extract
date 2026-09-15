"""Where the vocabulary this package ships with lives, once it is installed.

A profile is data, not code (ADR-0006) — but an engine whose data is not in the wheel is
an engine that reads nothing. `pip install invoice-extractor` has to arrive with the
vendors it knows and the languages they speak, or every document comes back
`profile_not_detected` and the caller has no way of telling a missing vocabulary from an
unrecognised invoice.

So the profiles and the lexicons live *inside* the package, under `data/`, and are found
through `importlib.resources` rather than through a path relative to whatever directory
the caller happened to start in. A deployment that keeps its own vendors elsewhere passes
that directory instead; every entry point takes one.

The two sit side by side because the loader reads a lexicon from beside the profile that
names it: `profiles/de-DE.json` says `"lexicon": "de"` and the loader looks for
`../lexicon/de.json`. Keeping that rule means a caller's own directory works the same way
as this one.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def _root() -> Path:
    """The `data/` directory of this package, wherever pip put it."""
    return Path(str(files("invoice_extractor"))) / "data"


#: The vendors this package ships with. The default for `ProfileRegistry`.
PROFILES: Path = _root() / "profiles"

#: The languages those vendors speak, beside them, as the loader expects.
LEXICONS: Path = _root() / "lexicon"
