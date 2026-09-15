"""Synthetic invoice corpus generation: realistic PDFs with exact ground truth.

`invoice_forge` is the proving ground for `invoice_extractor` — a corpus in which every
value, label and position is known, so accuracy can be measured per axis of variation
instead of guessed at. `docs/FORGE_SPEC.md` is the design.
"""

from invoice_forge.knobs import Knob

__version__ = "0.3.0"

__all__ = ["Knob", "__version__"]
