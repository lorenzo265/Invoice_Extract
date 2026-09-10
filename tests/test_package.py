"""What `import invoice_extractor` guarantees to a caller."""

from __future__ import annotations

import re

import invoice_extractor
import invoice_forge

SEMVER = re.compile(r"\d+\.\d+\.\d+")


def test_version_is_semver() -> None:
    assert SEMVER.fullmatch(invoice_extractor.__version__)


def test_both_packages_report_the_distribution_version() -> None:
    # They ship as one distribution; two version constants that disagree would be a lie
    # in every truth file the generator writes.
    assert invoice_forge.__version__ == invoice_extractor.__version__
