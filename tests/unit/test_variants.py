"""Stage 2: which profile a document is read with, when a vendor describes more than one.

`docs/ENGINE_SPEC.md` §2 gives the stage two fingerprints — the kind of document, and a
string the page carries — and `docs/PROFILE_FORMAT.md` says the overlay is a partial
profile merged like any other layer. Both are checked here on profiles written into a
temporary root, so what is proved is the stage rather than the vendor that ships one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from conftest import make_document
from invoice_extractor.document.model import Document
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import Profile, ProfileError
from invoice_extractor.profile.variants import select_variant

VENDOR = "en-GB"
CREDIT_NOTE = "CREDIT NOTE"


def root_with(variants: Sequence[Mapping[str, object]], tmp_path: Path) -> Path:
    """A profiles root holding the shared defaults, the lexicons, and one vendor."""
    root = tmp_path / "profiles"
    root.mkdir()
    (root / "_defaults.json").write_text(
        Path("profiles/_defaults.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    lexicons = tmp_path / "lexicon"
    lexicons.mkdir()
    for source in Path("lexicon").glob("*.json"):
        (lexicons / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    declared = json.loads(Path(f"profiles/{VENDOR}.json").read_text(encoding="utf-8"))
    declared["variants"] = list(variants)
    (root / f"{VENDOR}.json").write_text(json.dumps(declared, ensure_ascii=False), encoding="utf-8")
    return root


def page(*texts: str) -> Document:
    return make_document(
        [
            (1, text, 50.0, 60.0 + index * 20, 300.0, 74.0 + index * 20)
            for index, text in enumerate(texts)
        ]
    )


def required(profile: Profile) -> bool:
    """Whether this vendor says every one of these documents carries a credit reference."""
    declared = {custom.name: custom.field for custom in profile.custom_fields}
    return declared["credit_reference"].required


CREDIT_NOTE_VARIANT: Mapping[str, object] = {
    "id": "credit-note",
    "when": {"document_type": "credit_note"},
    "overlay": {
        "custom_fields": [
            {
                "name": "credit_reference",
                "labels": ["@header_labels.credit_reference"],
                "zones": ["r1c3"],
                "required": True,
            }
        ]
    },
}


def test_a_document_matching_no_variant_is_read_with_the_profile_as_it_stands(
    tmp_path: Path,
) -> None:
    registry = ProfileRegistry(root_with([CREDIT_NOTE_VARIANT], tmp_path))
    profile = registry.get(VENDOR)
    chosen = select_variant(page("INVOICE", "Invoice Number: INV-1"), profile, registry.root)
    assert chosen is profile
    assert required(chosen) is False


def test_a_document_type_fingerprint_selects_its_variant(tmp_path: Path) -> None:
    registry = ProfileRegistry(root_with([CREDIT_NOTE_VARIANT], tmp_path))
    profile = registry.get(VENDOR)
    chosen = select_variant(page(CREDIT_NOTE, "Original Invoice: INV-1"), profile, registry.root)
    assert chosen is not profile
    assert required(chosen) is True


def test_a_text_fingerprint_selects_its_variant(tmp_path: Path) -> None:
    """The other of the two `when` keys: a string the page carries, matched case-blind."""
    variant = {
        "id": "reverse-charge",
        "when": {"any_text": "reverse charge"},
        "overlay": {
            "invariants": {
                "exempt": [
                    {
                        "code": "vat_equals_subtotal_times_rate",
                        "reason": "the customer accounts for the tax, so the invoice states none",
                    }
                ]
            }
        },
    }
    registry = ProfileRegistry(root_with([variant], tmp_path))
    profile = registry.get(VENDOR)
    assert profile.invariants.exempt == ()
    chosen = select_variant(
        page("INVOICE", "Reverse charge: customer to account for VAT."), profile, registry.root
    )
    assert [entry.code for entry in chosen.invariants.exempt] == ["vat_equals_subtotal_times_rate"]


def test_a_text_fingerprint_no_page_carries_selects_nothing(tmp_path: Path) -> None:
    variant = {
        "id": "reverse-charge",
        "when": {"any_text": "reverse charge"},
        "overlay": {"currencies": ["GBP"]},
    }
    registry = ProfileRegistry(root_with([variant], tmp_path))
    profile = registry.get(VENDOR)
    assert select_variant(page("INVOICE", "Total Due"), profile, registry.root) is profile


def test_every_condition_a_fingerprint_names_has_to_hold(tmp_path: Path) -> None:
    """A fingerprint narrows: two conditions mean both, not either."""
    variant = {
        "id": "narrow",
        "when": {"document_type": "credit_note", "any_text": "Duplicate"},
        "overlay": {"currencies": ["USD"]},
    }
    registry = ProfileRegistry(root_with([variant], tmp_path))
    profile = registry.get(VENDOR)
    half = select_variant(page(CREDIT_NOTE, "Original Invoice: INV-1"), profile, registry.root)
    assert half is profile
    both = select_variant(page(CREDIT_NOTE, "DUPLICATE"), profile, registry.root)
    assert both.currencies == ("USD",)


def test_the_first_matching_variant_wins(tmp_path: Path) -> None:
    variants = [
        {"id": "first", "when": {"any_text": "INVOICE"}, "overlay": {"currencies": ["USD"]}},
        {"id": "second", "when": {"any_text": "INVOICE"}, "overlay": {"currencies": ["CHF"]}},
    ]
    registry = ProfileRegistry(root_with(variants, tmp_path))
    chosen = select_variant(page("INVOICE"), registry.get(VENDOR), registry.root)
    assert chosen.currencies == ("USD",)


def test_an_overlay_is_validated_as_strictly_as_the_profile_under_it(tmp_path: Path) -> None:
    """The overlay goes through the one loader, so a key no profile has is refused."""
    variant = {"id": "bad", "when": {"any_text": "INVOICE"}, "overlay": {"no_such_key": 1}}
    registry = ProfileRegistry(root_with([variant], tmp_path))
    profile = registry.get(VENDOR)
    with pytest.raises(ProfileError) as raised:
        select_variant(page("INVOICE"), profile, registry.root)
    assert "no_such_key is not a recognized key" in str(raised.value)
