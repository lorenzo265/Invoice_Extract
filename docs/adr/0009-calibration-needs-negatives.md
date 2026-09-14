# ADR-0009: Calibration needs negatives; the synthetic corpus provides them

Status: Accepted

## Context
A confidence score is only meaningful if it is calibrated: among fields reported at
0.9, about nine in ten should be right. Fitting weights and reliability floors on a
sample that contains only correct extractions inflates confidence — every score above a
gate becomes "almost certain" because the fit never saw a wrong value.

## Decision
Weights and calibration maps are fitted **offline** by `invoice-extractor calibrate` on
the synthetic corpus, which contains negatives by construction (difficulty knobs and
mutated documents produce misses and wrong values with known truth). The run is
deterministic; it writes `weights.json`, `calibration_maps.json` and
`reliability_report.json` (predicted vs observed hit rate per field, ten bins).
Promotion into the repository is a reviewed pull request. There is no automatic
trigger, no watermark and no background thread.

## Consequences
Published confidence has a published reliability curve. A field without fitted weights
uses the uniform mean and says so (`confidence_source = "uniform"`). Calibration on
real, private data remains possible with the same command and stays private.
