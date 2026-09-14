"""Producing a document for a test to look at, rendered once and shared.

There is no `conftest.py` here on purpose. pytest puts every test directory on
`sys.path` and imports each `conftest.py` as the top-level module `conftest`, so a second
one would shadow the helpers `tests/conftest.py` already gives the extractor's tests.
A cache does what a session fixture would: render each profile once, keep it for the run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from make_forge_goldens import GOLDEN_SEED

from invoice_forge.corpus.plan import every_pair
from invoice_forge.families import Family
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.profiles.loader import profile_ids

# Every test that looks at a rendered document runs once per bundled profile.
for_each_profile = pytest.mark.parametrize("profile_id", profile_ids())
# And the golden images run once per profile and family the profile declares.
for_each_pair = pytest.mark.parametrize(
    ("profile_id", "family"), every_pair(), ids=[f"{p}-{f.value}" for p, f in every_pair()]
)


@dataclass(frozen=True, slots=True)
class Rendered:
    """One produced document: where it went, and what its truth says."""

    profile_id: str
    pdf: Path
    truth: dict[str, Any]
    pages: int


def render_document(
    profile_id: str,
    directory: Path,
    seed: int = GOLDEN_SEED,
    family: Family = Family.CLASSIC,
) -> Rendered:
    """Sample, render and read back one document, exactly as `forge render-one` does."""
    spec = DocumentSpec(profile_id, family, seed)
    produced = produce(spec, directory / f"{profile_id}_{family.value}.pdf")
    truth = json.loads(produced.truth.read_text(encoding="utf-8"))
    return Rendered(profile_id, produced.pdf, truth, produced.pages)


@cache
def rendered(profile_id: str, family: Family = Family.CLASSIC) -> Rendered:
    """This pair at the golden seed, rendered on first use and kept for the run."""
    return render_document(profile_id, Path(_scratch().name), family=family)


@cache
def _scratch() -> TemporaryDirectory[str]:
    """One directory for the whole run; it is removed when the process ends."""
    return TemporaryDirectory(prefix="forge-tests-")
