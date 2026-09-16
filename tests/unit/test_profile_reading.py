"""Every message the profile loader raises names the key that is wrong."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from invoice_extractor.document.model import Zone
from invoice_extractor.profile.loader import load_profile, parse
from invoice_extractor.profile.schema import Exemption, Placement, ProfileError, TableEdge

LEXICON: Mapping[str, Any] = {
    "header_labels": {"invoice_number": ["Rechnungsnummer", "Beleg-Nr."]},
    "totals_labels": {
        "subtotal": ["Nettosumme"],
        "vat_amount": ["Umsatzsteuer"],
        "total_amount": ["Rechnungsbetrag"],
    },
    "column_headers": {"description": ["Beschreibung"], "net_amount": ["Betrag"]},
    "document_titles": {"invoice": ["RECHNUNG"], "credit_note": ["GUTSCHRIFT"]},
    "address_placeholders": ["wie Rechnungsanschrift"],
}


def base() -> dict[str, Any]:
    """A merged profile that parses cleanly; every test breaks exactly one thing in it."""
    return {
        "id": "xx-XX",
        "language": "xx",
        "country": "XX",
        "lexicon": "xx",
        "number_format": {"decimal_separator": ",", "thousands_separators": ["."]},
        "date_formats": ["dd.mm.yyyy"],
        "currencies": ["EUR"],
        "vat": {"rates": {"standard": "19"}, "id_prefix": "XX", "id_pattern": "\\d{9}"},
        "supplier": {
            "name": "Beispiel Handel GmbH",
            "aliases": ["Beispiel"],
            "address_lines": ["Am Hafen 1"],
            "vat_id": "XX123456789",
        },
        "fields": {"invoice_number": {"labels": ["@header_labels.invoice_number"]}},
        "parties": {"bill_to": {"labels": ["Rechnungsempfänger"]}},
        "line_items": {
            "columns": {
                "description": ["@column_headers.description"],
                "net_amount": ["@column_headers.net_amount"],
            }
        },
        "totals": {
            "components": {
                "subtotal": {"labels": ["@totals_labels.subtotal"]},
                "vat_amount": {"labels": ["@totals_labels.vat_amount"]},
                "total_amount": {"labels": ["@totals_labels.total_amount"]},
            }
        },
        "document_types": {
            "invoice_titles": ["@document_titles.invoice"],
            "credit_note_titles": ["@document_titles.credit_note"],
        },
    }


def lexicon_root(root: Path) -> Path:
    """The language's words, written where a profile under `root/profiles` looks for them."""
    directory = root / "lexicon"
    directory.mkdir(exist_ok=True)
    (directory / "xx.json").write_text(json.dumps(LEXICON), encoding="utf-8")
    return directory


def written(tmp_path: Path, data: Mapping[str, object]) -> Path:
    """`base()` on disk, plus the lexicon it references, as a root a loader can read."""
    lexicon_root(tmp_path)
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    (profiles / "_defaults.json").write_text("{}", encoding="utf-8")
    (profiles / "xx-XX.json").write_text(json.dumps(data), encoding="utf-8")
    return profiles


def error(data: Mapping[str, object]) -> str:
    """What `parse` says about a profile that is wrong in exactly one place."""
    with TemporaryDirectory() as directory:
        with pytest.raises(ProfileError) as raised:
            parse(data, lexicon_root(Path(directory)))
        return str(raised.value)


def test_a_valid_profile_loads(tmp_path: Path) -> None:
    profile = load_profile("xx-XX", written(tmp_path, base()))
    assert profile.id == "xx-XX"
    assert profile.currencies == ("EUR",)
    assert profile.number_format.decimal_separator == ","
    assert profile.supplier.name == "Beispiel Handel GmbH"


def test_a_label_reference_expands_to_every_synonym_the_language_offers(tmp_path: Path) -> None:
    profile = load_profile("xx-XX", written(tmp_path, base()))
    assert profile.fields["invoice_number"].labels == ("Rechnungsnummer", "Beleg-Nr.")


def test_a_label_beside_a_reference_is_kept_as_it_is_written(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["labels"] = ["Unser Zeichen", "@header_labels.invoice_number"]
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.fields["invoice_number"].labels[0] == "Unser Zeichen"


def test_the_defaults_are_the_layer_a_profile_is_laid_over(tmp_path: Path) -> None:
    profiles = written(tmp_path, base())
    (profiles / "_defaults.json").write_text(
        json.dumps({"fields": {"invoice_number": {"labels": ["Belegnummer"], "zones": ["r1c3"]}}}),
        encoding="utf-8",
    )
    profile = load_profile("xx-XX", profiles)
    assert profile.fields["invoice_number"].labels[0] == "Belegnummer"
    assert profile.fields["invoice_number"].zones == (Zone(1, 3),)


def test_an_unknown_key_names_itself() -> None:
    data = base()
    data["numbers"] = {}
    assert error(data) == "numbers is not a recognized key"


def test_a_missing_required_key_names_itself() -> None:
    data = base()
    del data["country"]
    assert error(data) == "country is required"


def test_a_wrong_type_says_what_it_should_be() -> None:
    data = base()
    data["currencies"] = "EUR"
    assert error(data) == "currencies must be a list of strings"


def test_a_profile_must_name_a_currency() -> None:
    data = base()
    data["currencies"] = []
    assert error(data) == "currencies must name at least one currency"


def test_an_unknown_date_format_lists_the_known_ones() -> None:
    data = base()
    data["date_formats"] = ["yyyy/dd/mm"]
    assert error(data).startswith("date_formats[0] must be one of: ")


def test_a_date_format_that_spells_a_month_is_tried_after_one_that_reads_digits(
    tmp_path: Path,
) -> None:
    data = base()
    data["date_formats"] = ["d Month yyyy", "dd.mm.yyyy"]
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.date_formats == ("%d.%m.%Y", "%d %B %Y")


def test_a_field_must_name_a_label() -> None:
    data = base()
    data["fields"]["invoice_number"]["labels"] = []
    assert error(data) == "fields.invoice_number.labels must name at least one label"


def test_a_reference_no_lexicon_entry_names_is_refused() -> None:
    data = base()
    data["fields"]["invoice_number"]["labels"] = ["@header_labels.lucky_number"]
    assert "@header_labels.lucky_number" in error(data)


def test_a_placement_of_pattern_needs_a_pattern() -> None:
    data = base()
    data["fields"]["invoice_number"]["placement"] = "pattern"
    assert error(data) == "fields.invoice_number.pattern is required when placement is pattern"


def test_a_placement_defaults_to_the_value_beside_the_label(tmp_path: Path) -> None:
    profile = load_profile("xx-XX", written(tmp_path, base()))
    assert profile.fields["invoice_number"].placement is Placement.RIGHT


def test_a_broken_pattern_says_so() -> None:
    data = base()
    data["fields"]["invoice_number"]["pattern"] = "([0-9"
    assert error(data).startswith("fields.invoice_number.pattern must be a valid")


def test_a_zone_name_may_be_a_grid_reference_or_one_of_the_nine_names(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["zones"] = ["r1c3", "bottom_left"]
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.fields["invoice_number"].zones == (Zone(1, 3), Zone(3, 1))


def test_a_zone_name_that_is_neither_says_what_one_looks_like() -> None:
    data = base()
    data["fields"]["invoice_number"]["zones"] = ["north"]
    assert error(data) == (
        "fields.invoice_number.zones[0] must be a zone name such as r1c3 or top_right"
    )


def test_a_zone_outside_the_grid_is_refused() -> None:
    data = base()
    data["fields"]["invoice_number"]["zones"] = ["r4c1"]
    assert error(data) == "fields.invoice_number.zones[0] must name a zone inside a 3 by 3 grid"


def test_only_the_three_party_blocks_are_recognized() -> None:
    data = base()
    data["parties"]["pay_to"] = {"labels": ["Zahlungsempfänger"]}
    assert error(data) == "parties.pay_to is not a recognized key"


def test_a_line_item_table_needs_a_description_and_an_amount() -> None:
    data = base()
    del data["line_items"]["columns"]["net_amount"]
    assert error(data) == "line_items.columns.net_amount is required"


def test_a_vat_summary_needs_a_rate_and_the_tax_charged_at_it() -> None:
    data = base()
    data["vat_summary"] = {"columns": {"base": ["Netto"]}}
    assert error(data) == "vat_summary.columns.rate is required"


def test_the_totals_block_must_name_the_three_components_every_invoice_has() -> None:
    data = base()
    del data["totals"]["components"]["vat_amount"]
    assert error(data) == "totals.components.vat_amount is required"


def test_a_charge_component_must_say_what_kind_of_charge_it_is() -> None:
    data = base()
    data["totals"]["components"]["shipping"] = {"labels": ["Versand"], "kind": "charge"}
    assert error(data) == "totals.components.shipping.charge_type is required when kind is charge"


def test_a_tolerance_defaults_to_a_cent_and_half_a_percent(tmp_path: Path) -> None:
    profile = load_profile("xx-XX", written(tmp_path, base()))
    assert str(profile.totals.tolerance.absolute) == "0.01"
    assert str(profile.totals.tolerance.relative) == "0.005"


def test_a_grid_other_than_thirds_is_refused() -> None:
    data = base()
    data["zones"] = {"grid": [4, 4]}
    assert error(data) == "zones.grid must be [3, 3]: the grid a page is classified on"


def test_a_custom_field_is_a_declared_label_field(tmp_path: Path) -> None:
    data = base()
    data["custom_fields"] = [{"name": "contract_number", "labels": ["Vertragsnummer"]}]
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.custom_fields[0].name == "contract_number"
    assert profile.custom_fields[0].field.labels == ("Vertragsnummer",)


def test_a_variant_says_when_it_applies_and_what_it_changes(tmp_path: Path) -> None:
    data = base()
    data["variants"] = [
        {"id": "credit", "when": {"document_type": "credit_note"}, "overlay": {"country": "AT"}}
    ]
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.variants[0].id == "credit"
    assert profile.variants[0].when == {"document_type": "credit_note"}
    assert profile.variants[0].overlay == {"country": "AT"}


def test_a_variant_fingerprint_is_one_of_the_two_the_format_knows() -> None:
    data = base()
    data["variants"] = [{"id": "x", "when": {"phase_of_the_moon": "full"}, "overlay": {}}]
    assert error(data) == "variants[0].when.phase_of_the_moon is not a recognized key"


def test_a_missing_profile_names_the_path_it_looked_for(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="no profile at"):
        load_profile("no_such_vendor", written(tmp_path, base()))


def test_invalid_json_names_the_file(tmp_path: Path) -> None:
    profiles = written(tmp_path, base())
    (profiles / "broken.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(ProfileError, match=r"broken\.json is not valid JSON"):
        load_profile("broken", profiles)


def test_a_profile_may_be_loaded_by_path(tmp_path: Path) -> None:
    profiles = written(tmp_path, base())
    assert load_profile(str(profiles / "xx-XX.json"), profiles).id == "xx-XX"


def test_a_missing_lexicon_names_the_language() -> None:
    with pytest.raises(ProfileError, match="lexicon xx is not readable"):
        parse(base(), Path("nowhere"))


def test_a_decimal_separator_is_one_character() -> None:
    data = base()
    data["number_format"]["decimal_separator"] = ",,"
    assert error(data) == "number_format.decimal_separator must be a single character"


def test_a_profile_must_name_a_vat_rate() -> None:
    data = base()
    data["vat"]["rates"] = {}
    assert error(data) == "vat.rates must name at least one rate"


def test_a_totals_block_may_echo_its_total_in_a_second_currency(tmp_path: Path) -> None:
    data = base()
    data["totals"]["secondary_echo"] = {"labels": ["Gegenwert"], "rate_labels": ["Kurs"]}
    echo = load_profile("xx-XX", written(tmp_path, data)).totals.secondary_echo
    assert echo is not None
    assert echo.labels == ("Gegenwert",)
    assert echo.rate_labels == ("Kurs",)


def test_a_table_may_say_where_it_ends_on_a_page(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["page_bounds"] = {"start": "header", "end": "stop_label"}
    bounds = load_profile("xx-XX", written(tmp_path, data)).line_items.page_bounds
    assert bounds.end is TableEdge.STOP_LABEL


def test_a_vendor_may_be_excused_an_invariant_with_a_reason(tmp_path: Path) -> None:
    """A reverse-charge invoice states no tax and is right not to (ENGINE_SPEC §6)."""
    data = base()
    data["invariants"] = {
        "exempt": [{"code": "vat_equals_subtotal_times_rate", "reason": "reverse charge"}]
    }
    profile = load_profile("xx-XX", written(tmp_path, data))
    assert profile.invariants.exempt == (
        Exemption(code="vat_equals_subtotal_times_rate", reason="reverse charge"),
    )


def test_a_vendor_that_excuses_nothing_is_excused_nothing(tmp_path: Path) -> None:
    assert load_profile("xx-XX", written(tmp_path, base())).invariants.exempt == ()


def test_an_exemption_that_gives_no_reason_is_refused() -> None:
    data = base()
    data["invariants"] = {"exempt": [{"code": "dates_in_order"}]}
    assert "invariants.exempt[0].reason is required" in error(data)


def test_an_exemption_key_nobody_reads_is_refused() -> None:
    data = base()
    data["invariants"] = {"exempt": [{"code": "x", "reason": "y", "severity": "info"}]}
    assert "invariants.exempt[0].severity" in error(data)


def test_an_invariants_key_nobody_reads_is_refused() -> None:
    data = base()
    data["invariants"] = {"exempt": [], "relax": True}
    assert "invariants.relax" in error(data)
