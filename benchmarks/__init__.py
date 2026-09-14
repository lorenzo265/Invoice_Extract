"""Measuring `invoice_extractor` against the corpus `invoice_forge` generates.

The two packages know nothing about each other, and this one knows both: it builds a
layout from each vendor profile, runs the extractor over every document in `corpus/`,
and compares what came back against the truth beside it, by the rules in
`docs/GROUND_TRUTH_SCHEMA.md`. `make bench` is `python -m benchmarks.run`.

Nothing here is imported by either package, and neither package is changed to suit it.
A number this produces is a number about the extractor as it is.
"""
