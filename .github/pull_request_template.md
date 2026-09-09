## Summary

<!-- One or two sentences: what this PR adds or changes, in plain language. -->

## Scope

<!-- Which PR of docs/IMPLEMENTATION_PLAN.md is this? Name the number and the plan's
     title for it, and confirm nothing from an earlier or later PR leaked in. -->

PR __ of the plan — "\_\_\_\_":

## Gate output

<!-- Paste the tail of your last local `make check` run: the pass/fail summary for
     lint, typecheck, test + coverage, and hygiene. Not the full scrollback. -->

```
$ make check
```

## Decisions

<!-- Every judgment call made because the plan or docs/ARCHITECTURE.md didn't fully
     determine an implementation detail: what you chose, and why it was the simplest
     option consistent with docs/ARCHITECTURE.md. Write "None." if there were none. -->

## Self-review checklist

- [ ] `make check` passes locally (lint + typecheck + test + hygiene), with no step skipped or weakened.
- [ ] This PR implements exactly one plan item — no scope from an earlier or later PR leaked in.
- [ ] No `# noqa`, `# type: ignore`, or lowered coverage/size threshold was added without a same-line comment justifying it.
- [ ] No new dependency — runtime or development — was added; `pyproject.toml`'s dependency lists are unchanged.
- [ ] No file under `samples/*.expected.json` was edited.
- [ ] Every new or changed function is ≤ 40 lines; every module is ≤ 250 lines; the `src/` total is still inside budget.
- [ ] Every new public function and class is fully typed; no `Any` leaked in.
- [ ] No `TODO`, `FIXME`, or commented-out code in the diff.
- [ ] Commit message(s) follow Conventional Commits.
- [ ] The PR description's Decisions section records every judgment call made under uncertainty — or explicitly says there were none.
