# ADR-0008: No default profile

Status: Accepted

## Context
An extractor that cannot tell which vendor printed a document can either guess a
default configuration and extract anyway, or stop. Guessing produces plausible-looking
results with the wrong vocabulary and no signal that anything went wrong — the most
expensive failure an extractor can have, because it is silent.

## Decision
`detect_profile` scores every registered profile and returns the best one **above a
threshold**, or `None`. `None` yields `Finding(ERROR, "profile_not_detected")`,
`valid=False` and no field extraction. A file-path hint may add score; it never decides.

## Consequences
An unknown vendor is a visible event, routed to a human, not a wrong result. Onboarding
a vendor means writing a profile (and rendering it with the generator to prove it),
never tuning a default. The registry re-reads changed profile files, so a profile added
while the process runs is detected on the next document.
