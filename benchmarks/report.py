"""`benchmarks/latest.json` rendered as markdown: the long report, and the README block.

Both are generated from the JSON and nothing else. Typing a number into the README by
hand is how a published figure outlives the run that produced it, so the block between
the two markers is written from `latest.json` every time `make bench` runs, and a test
fails when the file and the block disagree.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

BEGIN = "<!-- benchmark:begin -->"
END = "<!-- benchmark:end -->"
DASH = "--"


def render_readme_block(report: Mapping[str, object]) -> str:
    """The block the repository README carries between its two benchmark markers."""
    matrix = _mapping(report, "matrix")
    fields = _mapping(matrix, "fields")
    items = _mapping(matrix, "line_items")
    documents = matrix.get("documents", 0)
    lines = [
        BEGIN,
        f"Over the {documents}-document base corpus (`make corpus`), `make bench`",
        "measures this release at:",
        "",
        f"- **Profile detection:** {_detected(matrix)}; a document no profile matches is",
        "  reported and not read (ADR-0008).",
        f"- **Scalar fields:** {_overall(fields)} of the values the documents carry.",
        f"- **Line-item cells:** {_overall(_mapping(items, 'columns'))}, over",
        f"  {items.get('rows_agreed', 0)} of {documents} documents whose row count was read",
        "  exactly.",
        f"- **Party blocks:** {_overall(_mapping(matrix, 'parties'))} of the names and",
        "  addresses the documents print.",
        f"- **Totals block:** {_overall(_mapping(matrix, 'charges'))} of the charges the",
        "  documents carry, declared on the page or inferred from the arithmetic.",
        f"- **Confidence:** {_calibrated(matrix)}",
        f"- **Calibration:** the confidences are off by {_error(matrix)} on average, over the",
        "  weights and the curve `calibration/` was fitted with.",
        "- **Not covered:** the generator prints these and the extractor has no spec for",
        "  them, so they are never scored as wrong:",
        f"  {_not_covered(fields)}.",
        "",
        *_diagnosis(fields),
        "",
        "`benchmarks/README.md` is the field-by-field matrix, by profile, by family and by",
        "knob.",
        END,
    ]
    return "\n".join(lines)


def _detected(matrix: Mapping[str, object]) -> str:
    """How many documents were matched to the very profile that printed them."""
    documents = _count(matrix, "documents")
    detected = _count(matrix, "detected")
    share = _percent(detected / documents) if documents else "-"
    return f"{share} ({detected} of {documents})"


def _count(matrix: Mapping[str, object], key: str) -> int:
    value = matrix.get(key, 0)
    return value if isinstance(value, int) else 0


def _diagnosis(fields: Mapping[str, object]) -> list[str]:
    """What the misses were, split the one way that says where to go looking next."""
    miss = sum(_number(_mapping(fields, name), "miss") for name in fields)
    empty = sum(_number(_mapping(fields, name), "found_nothing") for name in fields)
    if not miss:
        return ["Nothing was missed."]
    how_many = "Every one of" if empty == miss else f"{empty} of"
    return [
        f"{how_many} those {miss} misses found no candidate at all, rather than reading",
        f"the wrong one ({miss - empty}). A field that found nothing was printed a way none",
        "of its strategies looks; `benchmarks/README.md` says which fields, on which",
        "profiles and in which families.",
    ]


def _calibrated(matrix: Mapping[str, object]) -> str:
    """Whether the confidence beside a value predicted whether the value was right."""
    bands = [band for band in _sequence(matrix, "calibration") if isinstance(band, dict)]
    scored = [band for band in bands if _number(band, "hit") + _number(band, "miss")]
    if not scored:
        return DASH
    parts = (f"{band.get('band', '')} at {_rate(band)}" for band in scored)
    return ", ".join(parts) + "."


def _error(matrix: Mapping[str, object]) -> str:
    found = matrix.get("expected_calibration_error")
    return DASH if not isinstance(found, float) else _percent(found)


def render_report(report: Mapping[str, object]) -> str:
    """The whole of `benchmarks/README.md`."""
    matrix = _mapping(report, "matrix")
    sections = [
        _heading(report, matrix),
        _fields_section(matrix),
        _misses_section(matrix),
        _columns_section(matrix),
        _vat_section(matrix),
        _parties_section(matrix),
        _totals_section(matrix),
        _by_section(matrix, "by_profile", "By profile", "Profile"),
        _by_section(matrix, "by_family", "By family", "Family"),
        _knob_section(matrix),
        _calibration_section(matrix),
    ]
    return "\n\n".join(sections) + "\n"


def _heading(report: Mapping[str, object], matrix: Mapping[str, object]) -> str:
    run = _mapping(report, "run")
    return "\n".join(
        [
            "# Benchmark",
            "",
            "Generated by `make bench`. Do not edit: `python -m benchmarks.run` rewrites",
            "this file from `benchmarks/latest.json`.",
            "",
            f"- Corpus: {matrix.get('documents', 0)} documents from `{run.get('corpus', '')}`",
            f"- Profile detected: {_detected(matrix)}",
            f"- Extractor: {run.get('extractor_version', '')}",
            f"- Generator: {run.get('generator_version', '')}",
            "",
            "A hit rate is `hit / (hit + miss)`. A field the document does not carry and the",
            "extractor does not claim is `absent` and is scored in neither. A field the",
            "extractor has no spec for is `not covered` and is never counted as wrong.",
        ]
    )


def _fields_section(matrix: Mapping[str, object]) -> str:
    rows = [
        (name, _cell(cell, "hit"), _cell(cell, "miss"), _cell(cell, "absent"), _rate(cell))
        for name, cell in _cells(_mapping(matrix, "fields"))
    ]
    return _section(
        "Scalar fields", ("Field", "Hit", "Miss", "Absent", "Hit rate"), rows, _RIGHT_FROM_ONE
    )


def _misses_section(matrix: Mapping[str, object]) -> str:
    """The two ways a field misses, counted apart: no candidate, or the wrong candidate."""
    rows = []
    for name, cell in _cells(_mapping(matrix, "fields")):
        miss, empty = _number(cell, "miss"), _number(cell, "found_nothing")
        if not miss:
            continue
        rows.append((name, str(miss), str(empty), str(miss - empty)))
    header = ("Field", "Miss", "Found nothing", "Read something else")
    table = _section("What the misses are", header, rows, _RIGHT_FROM_ONE)
    note = (
        "A field that found nothing is a field whose label the strategies never reached;"
        " a field that read something else reached a candidate and chose wrongly. The"
        " first is a strategy to add, the second a ranker to fix."
    )
    return f"{table}\n\n{note}"


def _number(cell: Mapping[str, object], key: str) -> int:
    value = cell.get(key)
    return value if isinstance(value, int) else 0


def _columns_section(matrix: Mapping[str, object]) -> str:
    items = _mapping(matrix, "line_items")
    rows = [
        (name, _cell(cell, "hit"), _cell(cell, "miss"), _cell(cell, "absent"), _rate(cell))
        for name, cell in _cells(_mapping(items, "columns"))
    ]
    header = ("Column", "Hit", "Miss", "Absent", "Hit rate")
    table = _section("Line-item columns", header, rows, _RIGHT_FROM_ONE)
    agreed, documents = items.get("rows_agreed", 0), matrix.get("documents", 0)
    note = (
        f"{agreed} of {documents} documents read the row count exactly. A cell is scored"
        " only where the truth records a box for it: a column a vendor does not print is"
        " `absent`, and the columns the corpus prints without recording — `pos`, `unit`,"
        " `discount_pct` and `vat_rate` — are read and published without being measured"
        " here."
    )
    return f"{table}\n\n{note}"


def _vat_section(matrix: Mapping[str, object]) -> str:
    summary = _mapping(matrix, "vat_summary")
    rows = [
        (name, _cell(cell, "hit"), _cell(cell, "miss"), _cell(cell, "absent"), _rate(cell))
        for name, cell in _cells(_mapping(summary, "columns"))
    ]
    header = ("Column", "Hit", "Miss", "Absent", "Hit rate")
    table = _section("VAT summary", header, rows, _RIGHT_FROM_ONE)
    agreed, documents = summary.get("rows_agreed", 0), matrix.get("documents", 0)
    carried = summary.get("documents", 0)
    note = (
        f"{carried} of {documents} documents print a VAT summary, and {agreed} of"
        f" {documents} read as many lines as were printed. The code beside a rate is read"
        " and not scored: the corpus records the numbers of a line, not its code."
    )
    return f"{table}\n\n{note}"


def _parties_section(matrix: Mapping[str, object]) -> str:
    rows = [
        (name, _cell(cell, "hit"), _cell(cell, "miss"), _cell(cell, "absent"), _rate(cell))
        for name, cell in _cells(_mapping(matrix, "parties"))
    ]
    header = ("Block", "Hit", "Miss", "Absent", "Hit rate")
    table = _section("Party blocks", header, rows, _RIGHT_FROM_ONE)
    note = (
        "A party a document knows but does not print is `absent`: the truth records a box"
        " per line it drew, and a block with none was never on the page. A block's VAT id"
        " is not scored here — a document need not print one inside the block, and the"
        " customer's is a field of its own."
    )
    return f"{table}\n\n{note}"


def _totals_section(matrix: Mapping[str, object]) -> str:
    """What the totals block carries beside its amounts: its charges and its echo."""
    rows = [
        (
            f"charge, {name}",
            _cell(cell, "hit"),
            _cell(cell, "miss"),
            _cell(cell, "absent"),
            _rate(cell),
        )
        for name, cell in _cells(_mapping(matrix, "charges"))
    ]
    rows += [
        (
            f"echo, {name}",
            _cell(cell, "hit"),
            _cell(cell, "miss"),
            _cell(cell, "absent"),
            _rate(cell),
        )
        for name, cell in _cells(_mapping(matrix, "secondary_amounts"))
    ]
    header = ("Reading", "Hit", "Miss", "Absent", "Hit rate")
    table = _section("Charges and second currency", header, rows, _RIGHT_FROM_ONE)
    note = (
        "A charge the block declares is scored on its type and its amount together. One"
        " no line declares is only a difference in the arithmetic — the page says neither"
        " what it is for nor how many of them there are — so what is scored is how much of"
        " the total nothing declared."
    )
    return f"{table}\n\n{note}"


def _by_section(matrix: Mapping[str, object], key: str, title: str, first: str) -> str:
    """One row per profile or family, one column per field the extractor has a spec for."""
    grouped = _mapping(matrix, key)
    fields = _scored_fields(grouped)
    rows = [
        (name, *(_rate(_mapping(_mapping(grouped, name), field)) for field in fields))
        for name in grouped
    ]
    return _section(title, (first, *fields), rows, _RIGHT_FROM_ONE)


def _scored_fields(grouped: Mapping[str, object]) -> list[str]:
    """A field nothing scores is a field the extractor does not read; it gets no column."""
    return [
        name
        for name in _names(grouped)
        if not any(_mapping(_mapping(grouped, group), name).get("not_covered") for group in grouped)
    ]


def _knob_section(matrix: Mapping[str, object]) -> str:
    rows = []
    for knob, sides in _cells(_mapping(matrix, "by_knob")):
        on, off = _mapping(sides, "on"), _mapping(sides, "off")
        rows.append((knob, _rate(on), _rate(off), _difference(on, off)))
    rows.sort(key=lambda row: row[3])
    table = _section("By knob", ("Knob", "On", "Off", "Difference"), rows, _RIGHT_FROM_ONE)
    note = (
        "A knob whose `on` rate sits below its `off` rate is a variation this release loses"
        " values to. Both rates are over every scalar field of every document on that side,"
        " so a knob that moves one field moves the column only a little. The base plan turns"
        " knobs on in themed bundles, so knobs that share a bundle share a row of documents"
        " and move together: what a column separates is a bundle, not always a single knob."
    )
    return f"{table}\n\n{note}"


def _calibration_section(matrix: Mapping[str, object]) -> str:
    rows = [
        (
            str(band.get("band", "")),
            _predicted(band),
            _cell(band, "hit"),
            _cell(band, "miss"),
            _rate(band),
        )
        for band in _sequence(matrix, "calibration")
        if isinstance(band, dict)
    ]
    header = ("Confidence", "Said", "Hit", "Miss", "Hit rate")
    table = _section("Calibration", header, rows, _RIGHT_FROM_ONE)
    error = matrix.get("expected_calibration_error")
    note = (
        "The confidence the extractor prints beside a value, against how often a value in"
        " that band turned out to be right. `Said` is what it claimed on average, and the"
        f" expected calibration error — the two, weighted by how many values each band"
        f" speaks for — is {_percent(float(error)) if isinstance(error, float) else DASH}."
        " The weights and the curve behind those numbers are in `calibration/`, fitted by"
        " `invoice-extractor calibrate` on this corpus."
    )
    return f"{table}\n\n{note}"


def _predicted(band: Mapping[str, object]) -> str:
    said = band.get("predicted")
    return DASH if not isinstance(said, float) else _percent(said)


_RIGHT_FROM_ONE = 1


def _section(
    title: str, header: Sequence[str], rows: Sequence[Sequence[str]], right_from: int
) -> str:
    alignment = ["---" if index < right_from else "---:" for index in range(len(header))]
    lines = [f"## {title}", "", _row(header), _row(alignment), *(_row(row) for row in rows)]
    return "\n".join(lines)


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _cells(data: Mapping[str, object]) -> Iterator[tuple[str, Mapping[str, object]]]:
    """Every entry of a JSON object whose values are themselves objects, narrowed as it is read."""
    for name, value in data.items():
        if isinstance(value, dict):
            yield name, value


def _names(grouped: Mapping[str, object]) -> list[str]:
    return sorted({name for _, row in _cells(grouped) for name in row})


def _overall(cells: Mapping[str, object]) -> str:
    hit = sum(_number(cell, "hit") for _, cell in _cells(cells))
    miss = sum(_number(cell, "miss") for _, cell in _cells(cells))
    return f"{_percent(hit / (hit + miss)) if hit + miss else DASH} ({hit} of {hit + miss})"


def _not_covered(fields: Mapping[str, object]) -> str:
    names = [name for name in fields if _mapping(fields, name).get("not_covered")]
    return ", ".join(f"`{name}`" for name in names) if names else "nothing"


def _difference(on: Mapping[str, object], off: Mapping[str, object]) -> str:
    left, right = on.get("hit_rate"), off.get("hit_rate")
    if not isinstance(left, float) or not isinstance(right, float):
        return DASH
    return f"{(left - right) * 100:+.1f} pp"


def _rate(cell: Mapping[str, object]) -> str:
    rate = cell.get("hit_rate")
    return _percent(rate) if isinstance(rate, float) else DASH


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _cell(cell: Mapping[str, object], key: str) -> str:
    return str(cell.get(key, 0))


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key) if key else None
    return value if isinstance(value, dict) else {}


def _sequence(data: Mapping[str, object], key: str) -> Sequence[object]:
    value = data.get(key)
    return value if isinstance(value, list) else ()
