"""What `import invoice_extractor` guarantees to a caller."""

from __future__ import annotations

import re

import invoice_extractor

SEMVER = re.compile(r"\d+\.\d+\.\d+")


def test_version_is_semver() -> None:
    assert SEMVER.fullmatch(invoice_extractor.__version__)
