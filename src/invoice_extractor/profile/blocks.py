"""The two-dimensional halves of a profile: the tables, and the totals block.

A table is described by what its header says per canonical column and by what stops it;
the totals block by what each of its lines is called and by how close an identity has to
come before it counts as closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from invoice_extractor.profile.lexicon import expand
from invoice_extractor.profile.parts import as_label_map
from invoice_extractor.profile.reading import (
    optional_count,
    optional_decimal,
    optional_flag,
    optional_fraction,
    optional_mapping,
    optional_strings,
    optional_text,
    reject_unknown,
    require_choice,
    require_mapping,
    require_text,
)
from invoice_extractor.profile.schema import (
    COMPONENT_KIND_NAMES,
    REQUIRED_COMPONENTS,
    TABLE_EDGE_NAMES,
    BlockProfile,
    ComponentKind,
    ComponentProfile,
    PageBounds,
    ProfileError,
    SecondaryEcho,
    TableEdge,
    TableProfile,
    Tolerance,
)

TABLE_KEYS = (
    "columns",
    "min_header_matches",
    "stop_labels",
    "page_bounds",
    "carry_forward_labels",
    "sub_item_indent",
    "number_columns",
)
PAGE_BOUNDS_KEYS = ("start", "end")
BLOCK_KEYS = ("components", "cluster_gap", "secondary_echo", "tolerance")
COMPONENT_KEYS = ("labels", "kind", "charge_type", "accumulate")
ECHO_KEYS = ("labels", "rate_labels")
TOLERANCE_KEYS = ("absolute", "relative")

DEFAULT_HEADER_MATCHES = 3
DEFAULT_SUB_ITEM_INDENT = 8.0
DEFAULT_CLUSTER_GAP = 0.08
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("0.01")
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.005")
# A line-item table is not a table without something to name and something to price; a
# VAT summary is not one without a rate and the tax charged at it.
ITEM_COLUMNS: tuple[str, ...] = ("description", "net_amount")
SUMMARY_COLUMNS: tuple[str, ...] = ("rate", "vat")


def table_profile(
    data: Mapping[str, object],
    path: str,
    lexicon: Mapping[str, object],
    required_columns: Sequence[str],
) -> TableProfile:
    reject_unknown(data, TABLE_KEYS, f"{path}.")
    columns = as_label_map(
        require_mapping(data, "columns", f"{path}.columns"), f"{path}.columns", lexicon
    )
    for required in required_columns:
        if required not in columns:
            raise ProfileError(f"{path}.columns.{required} is required")
    return TableProfile(
        columns=columns,
        min_header_matches=optional_count(
            data, "min_header_matches", f"{path}.min_header_matches", DEFAULT_HEADER_MATCHES
        ),
        stop_labels=expand(
            optional_strings(data, "stop_labels", f"{path}.stop_labels"),
            lexicon,
            f"{path}.stop_labels",
        ),
        page_bounds=_page_bounds(data, path),
        carry_forward_labels=expand(
            optional_strings(data, "carry_forward_labels", f"{path}.carry_forward_labels"),
            lexicon,
            f"{path}.carry_forward_labels",
        ),
        sub_item_indent=optional_fraction(
            data, "sub_item_indent", f"{path}.sub_item_indent", DEFAULT_SUB_ITEM_INDENT
        ),
        number_columns=optional_strings(data, "number_columns", f"{path}.number_columns"),
    )


def block_profile(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> BlockProfile:
    reject_unknown(data, BLOCK_KEYS, f"{path}.")
    declared = require_mapping(data, "components", f"{path}.components")
    components = {
        name: _component(
            require_mapping(declared, name, f"{path}.components.{name}"),
            f"{path}.components.{name}",
            lexicon,
        )
        for name in declared
    }
    for required in REQUIRED_COMPONENTS:
        if required not in components:
            raise ProfileError(f"{path}.components.{required} is required")
    return BlockProfile(
        components=components,
        cluster_gap=optional_fraction(
            data, "cluster_gap", f"{path}.cluster_gap", DEFAULT_CLUSTER_GAP
        ),
        secondary_echo=_secondary_echo(data, path, lexicon),
        tolerance=_tolerance(data, path),
    )


def _page_bounds(data: Mapping[str, object], path: str) -> PageBounds:
    bounds = optional_mapping(data, "page_bounds", f"{path}.page_bounds")
    if not bounds:
        return PageBounds(start="header", end=TableEdge.TOTALS_ANCHOR)
    reject_unknown(bounds, PAGE_BOUNDS_KEYS, f"{path}.page_bounds.")
    edge = require_choice(bounds, "end", f"{path}.page_bounds.end", TABLE_EDGE_NAMES)
    return PageBounds(
        start=require_text(bounds, "start", f"{path}.page_bounds.start"),
        end=TableEdge(edge),
    )


def _component(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> ComponentProfile:
    reject_unknown(data, COMPONENT_KEYS, f"{path}.")
    kind = ComponentKind(
        require_choice(data, "kind", f"{path}.kind", COMPONENT_KIND_NAMES)
        if "kind" in data
        else ComponentKind.AMOUNT.value
    )
    charge_type = optional_text(data, "charge_type", f"{path}.charge_type", "") or None
    if kind is ComponentKind.CHARGE and charge_type is None:
        raise ProfileError(f"{path}.charge_type is required when kind is charge")
    return ComponentProfile(
        labels=expand(
            optional_strings(data, "labels", f"{path}.labels"), lexicon, f"{path}.labels"
        ),
        kind=kind,
        charge_type=charge_type,
        accumulate=optional_flag(data, "accumulate", f"{path}.accumulate", False),
    )


def _secondary_echo(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> SecondaryEcho | None:
    echo = optional_mapping(data, "secondary_echo", f"{path}.secondary_echo")
    if not echo:
        return None
    reject_unknown(echo, ECHO_KEYS, f"{path}.secondary_echo.")
    return SecondaryEcho(
        labels=expand(
            optional_strings(echo, "labels", f"{path}.secondary_echo.labels"),
            lexicon,
            f"{path}.secondary_echo.labels",
        ),
        rate_labels=expand(
            optional_strings(echo, "rate_labels", f"{path}.secondary_echo.rate_labels"),
            lexicon,
            f"{path}.secondary_echo.rate_labels",
        ),
    )


def _tolerance(data: Mapping[str, object], path: str) -> Tolerance:
    declared = optional_mapping(data, "tolerance", f"{path}.tolerance")
    reject_unknown(declared, TOLERANCE_KEYS, f"{path}.tolerance.")
    return Tolerance(
        absolute=optional_decimal(
            declared, "absolute", f"{path}.tolerance.absolute", DEFAULT_ABSOLUTE_TOLERANCE
        ),
        relative=optional_decimal(
            declared, "relative", f"{path}.tolerance.relative", DEFAULT_RELATIVE_TOLERANCE
        ),
    )
