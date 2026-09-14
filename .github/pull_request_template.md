## Summary

<!-- One or two sentences: what this PR adds or changes, in plain language. -->

## Scope

<!-- Which PR of the plan in flight is this — docs/IMPLEMENTATION_PLAN.md,
     docs/FORGE_PLAN.md or docs/ENGINE_PLAN.md? Name the plan, the number and the
     plan's title for it, and confirm nothing from an earlier or later PR leaked in. -->

PR __ of \_\_\_\_ — "\_\_\_\_":

## Gate output

<!-- Paste the tail of your last local `make check` run: the pass/fail summary for
     lint, typecheck, test + coverage, and hygiene. Not the full scrollback. From
     series E on, paste the tail of `make bench` too. -->

```
$ make check
```

```
$ make bench
```

## Decisions

<!-- Every judgment call made because the plan or docs/ARCHITECTURE.md didn't fully
     determine an implementation detail: what you chose, and why it was the simplest
     option consistent with docs/ARCHITECTURE.md. Write "None." if there were none. -->

## Self-review checklist

- [ ] `make check` passes locally (lint + typecheck + test + hygiene), with no step skipped or weakened.
- [ ] `make bench` passes and no field's hit rate in `benchmarks/latest.json` is lower than on `main`.
- [ ] This PR implements exactly one plan item — no scope from an earlier or later PR leaked in.
- [ ] No `# noqa`, `# type: ignore`, or lowered coverage/size threshold was added without a same-line comment justifying it.
- [ ] No new dependency — runtime or development — was added; `pyproject.toml`'s dependency lists are unchanged.
- [ ] No truth file was edited to make a gate pass.
- [ ] Every new or changed function is ≤ 40 lines and every module is ≤ 250 lines, in every package under `src/`.
- [ ] Every new public function and class is fully typed; no `Any` leaked in.
- [ ] No `TODO`, `FIXME`, or commented-out code in the diff.
- [ ] Commit message(s) follow Conventional Commits.
- [ ] The PR description's Decisions section records every judgment call made under uncertainty — or explicitly says there were none.
