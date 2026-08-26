# A plan whose section 1.5 names a substitute the gate lint has no disposition for

Section 1.5's table is the one home of the substitute SET. The gate lint owns
the VERDICT — whether the act that closes a dependency is an engineering one —
and section 1.5 states no verdict, so the two cannot be the same list. This
fixture is the case where the set outruns the verdicts: `SANDBOX` has a row in
section 1.5 and no disposition in the lint, and a marked task waits on a task
that declares it.

## 1.5 The tier substitutes

| Substitute | Count | What it means | Where its check runs |
|---|---|---|---|
| **THROWAWAY** | 1 | A spike task. The code does not become production code. | The operator's own machine, against `extracted/`. |
| **OPERATOR** | 1 | The task needs an outward action only the operator may take. | Nowhere automatic. The operator performs it and records the result. |
| **deferred** | 1 | Listed, not scheduled. | Nowhere. A deferred task has no check to run. |
| **upstream** | 1 | The check is a pull request against a repository this project does not own. | The upstream maintainer's own continuous integration. |
| **SANDBOX** | 1 | The task runs inside a vendor sandbox this plan does not drive. | The vendor's own harness. |

## 3.1 The repositories

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 9. The tasks

**SND-1 · The sandboxed task** — SANDBOX
Files: `sandbox/probe.cpp`
Design: 1
Depends: none
Check: The vendor's own harness reports the result.

**GGG-1 · The dependant on the sandboxed task** — T0
Files: `tests/t0_gamma.cpp`
Design: 2
Depends: SND-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
**DONE on 2026-01-03, commit `3333333` → `tests/t0_gamma.cpp`.**
