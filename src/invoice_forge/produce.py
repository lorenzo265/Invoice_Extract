"""One cell of a corpus: a profile, a family, a seed, and the two files they produce.

`produce` is the whole generator in one call — sample a document, render it, read the
result back, write the PDF and its truth beside it. A corpus is this function over a
plan, which is what PR F3 builds on top of it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.profiles.loader import load_profile
from invoice_forge.render.renderer import RenderRequest, render
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import SampleRequest, sample_document
from invoice_forge.truth.builder import build_truth

TRUTH_SUFFIX = ".truth.json"
JSON_INDENT = 2


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    """One cell of the corpus: everything that decides what is produced, and nothing else."""

    profile_id: str
    family: Family
    seed: int
    knobs: tuple[Knob, ...] = ()


@dataclass(frozen=True, slots=True)
class Produced:
    """What `produce` wrote, and what came out."""

    pdf: Path
    truth: Path
    pages: int


def produce(spec: DocumentSpec, pdf_path: Path) -> Produced:
    """Write `<stem>.pdf` and `<stem>.truth.json`. Same spec, same bytes, every time."""
    profile = load_profile(spec.profile_id)
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    sampled = SampleRequest(profile, lexicon, catalogue, spec.seed, spec.knobs)
    document = sample_document(sampled)
    request = RenderRequest(document, profile, lexicon, spec.family, spec.seed, spec.knobs)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    result = render(request, pdf_path)
    truth_path = truth_path_for(pdf_path)
    truth_path.write_text(_as_json(build_truth(request, result, pdf_path)), encoding="utf-8")
    return Produced(pdf=pdf_path, truth=truth_path, pages=result.pages)


def truth_path_for(pdf_path: Path) -> Path:
    """The truth file that belongs to a PDF: the same stem, in the same directory."""
    return pdf_path.with_suffix("").with_name(f"{pdf_path.stem}{TRUTH_SUFFIX}")


def _as_json(truth: dict[str, object]) -> str:
    return json.dumps(truth, ensure_ascii=False, indent=JSON_INDENT) + "\n"
