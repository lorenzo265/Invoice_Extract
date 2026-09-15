"""Stage 6: every rule, over one document, in one loop.

The two families differ in what they ask — the arithmetic, and whether the values agree
with each other — and not in how they are run or recorded. What comes back is what the
document said (`Finding`s) and what was asked of it (`Check`s), because a rule that held
and a rule that was never applicable are different things and the findings alone cannot
tell them apart (ENGINE_SPEC §6).

A profile may excuse its vendor from a rule with a reason. The exemption is not silent:
it is recorded as a check that did not apply and an INFO finding that says why.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.validation.cross_field import CHECKS
from invoice_extractor.validation.facts import Facts, Verdict
from invoice_extractor.validation.invariants import INVARIANTS

Rule = Callable[[Facts], Verdict]
RULES: tuple[Rule, ...] = (*INVARIANTS, *CHECKS)
RULE_NAMES: tuple[str, ...] = tuple(rule.__name__ for rule in RULES)
EXEMPT = "invariant_exempt"


def validate(facts: Facts) -> tuple[tuple[Finding, ...], tuple[Check, ...]]:
    """Run every rule against one document: what it found, and what it looked at."""
    excused = _excused(facts)
    findings: list[Finding] = []
    checks: list[Check] = []
    for rule in RULES:
        finding, check = _applied(rule, facts, excused)
        checks.append(check)
        if finding is not None:
            findings.append(finding)
    return tuple(findings), tuple(checks)


def _applied(rule: Rule, facts: Facts, excused: Mapping[str, str]) -> tuple[Finding | None, Check]:
    code = rule.__name__
    reason = excused.get(code)
    if reason is not None:
        return _exemption(code, reason), Check(code, None, (), f"exempt: {reason}")
    return _recorded(code, rule(facts))


def _recorded(code: str, verdict: Verdict) -> tuple[Finding | None, Check]:
    """One verdict, as the two records it makes: always a check, sometimes a finding."""
    check = Check(code, verdict.passed, verdict.fields, verdict.detail)
    if verdict.passed is not False:
        return None, check
    about = verdict.fields[-1] if verdict.fields else None
    return Finding(verdict.severity, code, verdict.detail, about), check


def _exemption(code: str, reason: str) -> Finding:
    return Finding(Severity.INFO, EXEMPT, f"{code} does not apply: {reason}")


def _excused(facts: Facts) -> Mapping[str, str]:
    return {entry.code: entry.reason for entry in facts.profile.invariants.exempt}
