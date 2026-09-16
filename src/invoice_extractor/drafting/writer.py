"""Writing a draft where `--profiles` will find it, and never over a person's work.

A profile directory is three things (`profile/loader.py`): `_defaults.json`, one
`<id>.json` per vendor, and a `lexicon/` beside it with the language each vendor names.
A draft writes the second, and supplies the other two where the directory lacks them —
the defaults copied from the registry the draft was made against, the lexicon copied
from beside it, or written as a skeleton where no lexicon speaks the language yet.

The evidence goes in a `drafts/` directory beside `lexicon/`, not among the profiles: the
registry reads every `.json` under the profile directory as a vendor, and an evidence
file there would be refused by name on the next command.

Nothing here overwrites. A draft is the *start* of a person's work on a profile, and the
file they have been editing is that work; asking for a draft over it again is refused
with the name of the file, and `--id` names the draft something else.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from invoice_extractor.drafting.evidence import Evidence
from invoice_extractor.drafting.vocabulary import LISTS, MAPS, MONTH_LISTS, Vocabulary
from invoice_extractor.profile.loader import DEFAULTS_ID, lexicons_beside

INDENT = 2
DRAFTS = "drafts"


@dataclass(frozen=True, slots=True)
class Written:
    """What one draft put on disk. The optional two are absent where the directory had them."""

    profile: Path
    evidence: Path
    defaults: Path | None
    lexicon: Path | None


def write(
    profile: dict[str, object],
    evidence: Evidence,
    out: Path,
    source_root: Path,
    vocabulary: Vocabulary,
) -> Written:
    """The profile and its evidence under `out`, with the defaults and lexicon it needs.

    Raises `FileExistsError` where `<id>.json` is already there.
    """
    profile_id = str(profile["id"])
    language = str(profile["lexicon"])
    target = out / f"{profile_id}.json"
    if target.exists():
        raise FileExistsError(f"{target} already exists; pass --id to name the draft differently")
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(_dumped(profile), encoding="utf-8")
    beside = drafts_beside(out) / f"{profile_id}.json"
    beside.parent.mkdir(parents=True, exist_ok=True)
    beside.write_text(_dumped(evidence.to_dict()), encoding="utf-8")
    return Written(
        profile=target,
        evidence=beside,
        defaults=_defaults(out, source_root),
        lexicon=_lexicon(language, out, source_root, vocabulary),
    )


def drafts_beside(root: Path) -> Path:
    """Where a profile directory's evidence files go: `drafts/` beside its `lexicon/`."""
    return root.parent / DRAFTS


def _defaults(out: Path, source_root: Path) -> Path | None:
    target = out / f"{DEFAULTS_ID}.json"
    if target.exists():
        return None
    shutil.copyfile(source_root / f"{DEFAULTS_ID}.json", target)
    return target


def _lexicon(language: str, out: Path, source_root: Path, vocabulary: Vocabulary) -> Path | None:
    target = lexicons_beside(out) / f"{language}.json"
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    source = lexicons_beside(source_root) / f"{language}.json"
    if source.is_file():
        shutil.copyfile(source, target)
    else:
        target.write_text(_dumped(skeleton(language, vocabulary)), encoding="utf-8")
    return target


def skeleton(language: str, vocabulary: Vocabulary) -> dict[str, object]:
    """A lexicon with every entry the others have and a placeholder in each.

    The placeholder `?` folds to nothing, so the detector scores it as absent and no
    strategy reads a line as introduced by it: a skeleton matches nothing until a person
    puts the language's own words in it, which is what the draft's `unmapped` list is
    for.
    """
    keys: dict[str, list[str]] = {group: [] for group in MAPS}
    for terms in vocabulary.terms.values():
        for term in terms:
            if term.group in keys and term.key not in keys[term.group]:
                keys[term.group].append(term.key)
    drafted: dict[str, object] = {"language": language}
    for group in MAPS:
        drafted[group] = {key: ["?"] for key in sorted(keys[group])}
    for group in LISTS:
        drafted[group] = ["?"]
    for group in MONTH_LISTS:
        drafted[group] = []
    return drafted


def _dumped(data: dict[str, object]) -> str:
    return json.dumps(data, indent=INDENT, ensure_ascii=False) + "\n"
