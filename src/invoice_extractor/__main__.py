"""Makes the package runnable as `python -m invoice_extractor`."""

from __future__ import annotations

from invoice_extractor.cli import main

raise SystemExit(main())
