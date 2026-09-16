"""What `profile draft` prints: where it wrote, what it read, and what is left to a person.

The evidence file has every detail; this is the page of it that decides what the person
does next. Each line is one thing the draft settled or could not, and the last lines are
the commands that turn the draft into a profile.
"""

from __future__ import annotations

from invoice_extractor.drafting.evidence import Evidence
from invoice_extractor.drafting.writer import Written

RULE = "=" * 80
VOTES_SHOWN = 3


def render(evidence: Evidence, written: Written) -> str:
    """The summary, from the evidence the draft wrote and the paths it wrote to."""
    return "\n".join(
        [
            f"Drafted {evidence.profile_id} from {evidence.source_path}",
            RULE,
            f"  profile    {written.profile}",
            f"  evidence   {written.evidence}",
            *_supplied(written),
            "",
            _language(evidence),
            *_settings(evidence),
            "",
            *_fields(evidence),
            "",
            *_next(evidence, written),
        ]
    )


def _supplied(written: Written) -> list[str]:
    supplied = []
    if written.defaults is not None:
        supplied.append(f"  defaults   {written.defaults}  (copied: the directory had none)")
    if written.lexicon is not None:
        supplied.append(f"  lexicon    {written.lexicon}")
    return supplied


def _language(evidence: Evidence) -> str:
    votes = ", ".join(f"{name} {count}" for name, count in evidence.votes[:VOTES_SHOWN])
    return f"  language   {evidence.language}  (lexicon entries matched: {votes or 'none'})"


def _settings(evidence: Evidence) -> list[str]:
    return [
        f"  {trace.key:<32} {trace.value or '-':<24} {trace.reason}" for trace in evidence.settings
    ]


def _fields(evidence: Evidence) -> list[str]:
    placed = ", ".join(dict.fromkeys(one.field for one in evidence.placed))
    return [
        f"  fields     {len(evidence.placed)} labels placed: {placed or 'none'}",
        f"  missing    {', '.join(evidence.missing) or 'none'}",
        f"  unmapped   {len(evidence.unmapped)} labelled values no lexicon names"
        " (listed in the evidence file)",
    ]


def _next(evidence: Evidence, written: Written) -> list[str]:
    steps = []
    if evidence.placeholders:
        steps.append(
            f"Fill in: {', '.join(evidence.placeholders)}"
            " — the loader refuses the profile until you do."
        )
    where = written.profile.parent
    steps.append(
        f"Then: profile lint {evidence.profile_id} --profiles {where}, "
        f"and extract <pdf> --profiles {where}."
    )
    return steps
