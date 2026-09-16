"""PR E7: one test per way a label-based extractor is known to be wrong.

`docs/ENGINE_PLAN.md` §3 lists twelve. Each is proved here against the thing that would
break — a real corpus document where the corpus can print one, a document built line by
line where the failure is about geometry or about a vocabulary no vendor in this
repository speaks. Where an earlier PR already proved a mode, it is proved again here,
because the value of a list of failure modes is that one file answers for all of it.

The documents are the committed fixture corpus, so `make check` proves all of this on a
clone that has never run `make corpus` — the base corpus is generated and is not in git.
The same modes are measured again over all 270 documents by `make bench`, whose hardening
cells sit at the end of `corpus/plan.json`, appended rather than inserted: a cell is drawn
from its profile, family, seed and knobs alone, so adding one at the end leaves every
document before it byte for byte the same.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from conftest import make_document, make_field_profile, make_profile
from invoice_extractor import ProfileRegistry, bundled, extract
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import InvoiceResult
from invoice_extractor.extraction.engine import FIELD_MISSING, run
from invoice_extractor.extraction.spec import DerivedSpec, LabelSpec
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_extractor.extraction.units.dates import parse_date
from invoice_extractor.extraction.units.normalizers import parse_number
from invoice_extractor.pipeline import NOT_DETECTED
from invoice_extractor.profile.loader import DATE_PATTERNS, load_profile
from invoice_extractor.profile.schema import Profile

FIXTURES = Path("tests/forge/fixtures/corpus")
REGISTRY = ProfileRegistry()
BY_LABEL = ("valid_first", "zone_priority", "closest_to_label", "top_most")


def cells(**wanted: object) -> list[Path]:
    """Every fixture whose truth says it was drawn the way this test needs.

    Raises where nothing matches, rather than handing `parametrize` an empty list: a
    hardening test that quietly stops running is worse than one that fails.
    """
    found = []
    for truth_path in sorted(FIXTURES.glob("*.truth.json")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        made = truth["generator"]
        knobs = set(made["knobs"])
        if all(_holds(made, knobs, key, value) for key, value in wanted.items()):
            found.append(truth_path.with_name(truth_path.name.replace(".truth.json", ".pdf")))
    if not found:
        raise ValueError(f"no fixture document is drawn with {wanted}")
    return found


def _holds(made: dict[str, object], knobs: set[str], key: str, value: object) -> bool:
    if key == "knobs":
        return set(value) <= knobs if isinstance(value, tuple | list) else False
    return made.get(key) == value


def read(pdf: Path) -> tuple[InvoiceResult, dict[str, object]]:
    truth = json.loads(pdf.with_suffix("").with_suffix(".truth.json").read_text(encoding="utf-8"))
    return extract(pdf, REGISTRY), truth


def codes(result: InvoiceResult, code: str) -> list[Finding]:
    return [finding for finding in result.findings if finding.code == code]


# 1. A currency outside the profile's list.


def test_a_currency_the_profile_does_not_list_is_a_finding_and_not_a_silence() -> None:
    """Counting only the codes a vendor trades in is what stops the echo winning; a
    document in a third currency therefore resolves nothing, and has to say so."""
    profile = dataclasses.replace(make_profile(), currencies=("GBP",))
    document = make_document([(1, "Total 1,234.56 SGD", 400.0, 60.0, 540.0, 74.0)])
    found = run(DerivedSpec(name="currency", derive="currency"), document, profile, {})
    assert found.field.value is None
    assert [finding.code for finding in found.findings] == [FIELD_MISSING]
    assert found.findings[0].severity is Severity.WARNING
    assert found.findings[0].field == "currency"


# 2. A document no profile matches.


def test_a_document_no_profile_matches_is_reported_and_not_read(tmp_path: Path) -> None:
    empty = ProfileRegistry(_only_the_defaults(tmp_path))
    result = extract(cells(profile="de-DE")[0], empty)
    assert result.profile_id is None
    assert result.fields == {}
    assert result.line_items == ()
    assert [finding.code for finding in result.findings] == [NOT_DETECTED]
    assert result.findings[0].severity is Severity.ERROR


def _only_the_defaults(tmp_path: Path) -> Path:
    """A profiles root with the shared defaults and the lexicons, and no vendor at all.

    The lexicons come too because a profile without its language cannot be loaded: the
    loader reads them from beside the profiles, and a registry has to be given both.
    """
    root = tmp_path / "profiles"
    root.mkdir()
    (root / "_defaults.json").write_text(
        (bundled.PROFILES / "_defaults.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    lexicons = tmp_path / "lexicon"
    lexicons.mkdir()
    for source in bundled.LEXICONS.glob("*.json"):
        (lexicons / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return root


# 3. Something that looks like a table, printed after the totals.


@pytest.mark.parametrize("pdf", cells(knobs=("noise_footer", "stamp_copy")))
def test_what_is_printed_after_the_totals_is_not_read_as_rows(pdf: Path) -> None:
    """A legal footer, a total spelled out in words and a copy stamp all sit below the
    table and all carry numbers; the row count is what says none of them was read."""
    result, truth = read(pdf)
    assert len(result.line_items) == len(truth["line_items"])


# 4. A text stream whose order is not the page's order.


def test_a_value_under_its_label_is_found_however_the_stream_is_ordered() -> None:
    """`label_below` is geometric: it asks which line overlaps this one and sits under
    it, never which line came next in the file (ENGINE_SPEC §3, geometry over order)."""
    below = [
        (1, "INV-2024-0001", 400.0, 80.0, 500.0, 94.0),
        (1, "Invoice Number", 400.0, 60.0, 500.0, 74.0),
    ]
    profile = dataclasses.replace(
        make_profile(), fields={"invoice_number": make_field_profile(labels=("Invoice Number",))}
    )
    spec = LabelSpec(
        name="invoice_number",
        normalizer="strip_label",
        validator="is_identifier",
        rankers=BY_LABEL,
    )
    found = run(spec, make_document(below), profile, {})
    assert found.field.value == "INV-2024-0001"


# 5. A trap label beside the one a date field wants.


@pytest.mark.parametrize("pdf", cells(knobs=("trap_labels",)))
def test_a_trap_label_never_becomes_the_date_it_sits_beside(pdf: Path) -> None:
    """The order date, the print date and the dispatch date are drawn next to the real
    ones. A field the page does not carry must come back empty, not carrying a trap."""
    result, truth = read(pdf)
    for name in ("invoice_date", "due_date", "supply_date"):
        printed = truth["fields"][name]
        found = result.fields[name]
        expected = None if printed["value"] is None else date.fromisoformat(printed["value"])
        assert found.value == expected, f"{pdf.name}: {name}"


# 6. A field the catalog does not name, declared by a vendor.


@pytest.mark.parametrize("pdf", cells(knobs=("extra_references",)))
def test_a_field_a_vendor_declares_is_read_under_its_own_name(pdf: Path) -> None:
    """A name the catalog does not fix is still a name: declared in the profile under
    `custom_fields`, published in `fields` under it, and scored beside every other."""
    result, truth = read(pdf)
    declared = ("contract_number", "our_reference", "your_reference")
    carried = [name for name in declared if truth["fields"][name]["value"] is not None]
    assert carried, f"{pdf.name} was meant to print at least one vendor reference"
    for name in carried:
        assert result.fields[name].value == truth["fields"][name]["value"], name
        assert name in FIELD_ORDER, f"{name} is read and the benchmark would not score it"


# 7. A profile added while the process is running.


def test_a_profile_added_after_the_registry_was_built_is_found(tmp_path: Path) -> None:
    root = _only_the_defaults(tmp_path)
    held = ProfileRegistry(root)
    assert held.ids() == ()
    (root / "de-DE.json").write_text(
        (bundled.PROFILES / "de-DE.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert held.ids() == ("de-DE",)
    assert held.get("de-DE").id == "de-DE"


# 8. Numbers written with every thousands separator a vendor may use.


@pytest.mark.parametrize(
    ("thousands", "decimal", "printed"),
    [
        (".", ",", "1.234.567,89"),
        (",", ".", "1,234,567.89"),
        (" ", ",", "1 234 567,89"),
        ("'", ".", "1'234'567.89"),
        ("", ".", "1234567.89"),
    ],
)
def test_every_thousands_separator_a_profile_may_declare_reads_the_same_number(
    thousands: str, decimal: str, printed: str
) -> None:
    """All five a shipped profile declares: the dot, the comma, the space, the Swiss
    apostrophe, and none at all. Which one a vendor uses is profile data with no code
    fallback, so the same seven digits read the same number under every one of them."""
    profile = make_profile(decimal_separator=decimal, thousands_separators=(thousands,))
    assert parse_number(printed, profile) == Decimal("1234567.89")


@pytest.mark.parametrize("pdf", cells(knobs=("thousands_variant",)))
def test_a_document_written_with_the_other_separator_still_adds_up(pdf: Path) -> None:
    result, truth = read(pdf)
    for name in ("subtotal", "vat_amount", "total_amount"):
        assert result.fields[name].value == Decimal(truth["fields"][name]["value"]), name


# 9. A vendor that writes the month before the day.


def test_the_same_slashed_date_reads_two_ways_under_the_two_profiles_that_declare_them() -> None:
    """`03/04/2024` is a valid date under both, and they are different days. Which one a
    vendor means is a profile key, because nothing on the page can be asked instead."""
    day_first = (DATE_PATTERNS["dd/mm/yyyy"],)
    month_first = (DATE_PATTERNS["mm/dd/yyyy"],)
    calendar = make_profile().calendar
    assert parse_date("03/04/2024", day_first, calendar) == date(2024, 4, 3)
    assert parse_date("03/04/2024", month_first, calendar) == date(2024, 3, 4)


def test_a_profile_may_declare_the_month_first_and_is_read_that_way(tmp_path: Path) -> None:
    profile = _declaring_dates(tmp_path, "mm/dd/yyyy")
    spec = LabelSpec(
        name="invoice_date", normalizer="parse_date", validator="is_date", rankers=BY_LABEL
    )
    document = make_document([(1, "Invoice Date: 03/04/2024", 400.0, 60.0, 540.0, 74.0)])
    found = run(spec, document, profile, {})
    assert found.field.value == date(2024, 3, 4)


def _declaring_dates(tmp_path: Path, *names: str) -> Profile:
    """A profile read through the real loader, so the format names are validated."""
    root = _only_the_defaults(tmp_path)
    declared = json.loads((bundled.PROFILES / "en-GB.json").read_text(encoding="utf-8"))
    declared["date_formats"] = list(names)
    (root / "us-US.json").write_text(
        json.dumps({**declared, "id": "us-US"}, ensure_ascii=False), encoding="utf-8"
    )
    loaded = load_profile("us-US", root)
    return dataclasses.replace(
        loaded, fields={**loaded.fields, "invoice_date": make_field_profile(("Invoice Date",))}
    )


# 10. A credit note, and the invoice it reverses.


@pytest.mark.parametrize("pdf", cells(profile="en-GB", knobs=("credit_note",)))
def test_a_credit_note_is_told_apart_and_cites_the_invoice_it_reverses(pdf: Path) -> None:
    """Stage 2 makes the reference required on a credit note and only on one: the same
    vendor's ordinary invoices have nothing to cite (`profiles/en-GB.json`)."""
    result, truth = read(pdf)
    assert result.document_type == "credit_note" == truth["document"]["type"]
    assert result.fields["credit_reference"].value == truth["fields"]["credit_reference"]["value"]
    assert codes(result, "credit_note_references_invoice") == []


def test_a_credit_note_without_its_reference_says_so(tmp_path: Path) -> None:
    """What the variant is for: the same missing field is a finding here and not on an
    invoice, because only one of the two kinds of document is required to carry it."""
    pdf = cells(profile="en-GB", knobs=("credit_note",))[0]
    blinded = _without_the_reference_labels(tmp_path)
    result = extract(pdf, blinded)
    assert result.document_type == "credit_note"
    assert [finding.field for finding in codes(result, FIELD_MISSING)] == ["credit_reference"]


def _without_the_reference_labels(tmp_path: Path) -> ProfileRegistry:
    """The same vendor, blinded to the words a credit reference is printed under.

    The blinding is done in the language rather than in the profile, because every layer
    names the same lexicon entry: the defaults, the vendor and the variant all say
    `@header_labels.credit_reference`, so changing one of them changes nothing.
    """
    root = _only_the_defaults(tmp_path)
    lexicon = json.loads((root.parent / "lexicon" / "en.json").read_text(encoding="utf-8"))
    lexicon["header_labels"]["credit_reference"] = ["No Such Label"]
    (root.parent / "lexicon" / "en.json").write_text(
        json.dumps(lexicon, ensure_ascii=False), encoding="utf-8"
    )
    (root / "en-GB.json").write_text(
        (bundled.PROFILES / "en-GB.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return ProfileRegistry(root)


# 11. A charge no line of the page declares.


@pytest.mark.parametrize("pdf", cells(knobs=("undeclared_charge",)))
def test_a_charge_folded_into_the_total_is_found_in_the_arithmetic(pdf: Path) -> None:
    result, truth = read(pdf)
    hidden = [charge for charge in truth["charges"] if not charge["declared"]]
    assert hidden, f"{pdf.name} was meant to hide a charge"
    inferred = [charge for charge in result.charges if not charge.declared]
    assert [charge.amount for charge in inferred] == [Decimal(one["amount"]) for one in hidden]
    assert codes(result, "undeclared_charge_inferred")


# 12. Findings and checks survive being written down and read back.


@pytest.mark.parametrize("pdf", cells(knobs=("undeclared_charge",)))
def test_every_finding_and_check_survives_the_round_trip(pdf: Path) -> None:
    result, _ = read(pdf)
    mirrored = InvoiceResult.from_dict(json.loads(json.dumps(result.to_dict())))
    assert mirrored.findings == result.findings
    assert mirrored.checks == result.checks
    assert mirrored.line_items == result.line_items
    assert mirrored.charges == result.charges


# The field the bank footer carries, and the documents that print no footer at all.


@pytest.mark.parametrize("pdf", sorted(FIXTURES.glob("*.pdf")))
def test_the_account_number_is_read_where_a_page_prints_one_and_nowhere_else(
    pdf: Path,
) -> None:
    """The one field found by its shape rather than by a label, both ways round.

    A vendor knows its own account number whether or not it prints it, so the truth
    carries a value for every document; only a document that drew the bank block carries
    a box for it. Read it where there is a box, and read nothing where there is none —
    an IBAN invented from a VAT id would pass a shape check and fail the checksum.
    """
    result, truth = read(pdf)
    entry = truth["fields"]["iban"]
    found = result.fields["iban"]
    if entry["evidence"]:
        assert found.value == entry["value"]
        assert found.evidence is not None
    else:
        assert found.value is None
