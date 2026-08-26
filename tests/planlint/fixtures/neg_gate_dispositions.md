# A plan whose completion markers rest on every disposition a dependency can carry

One dependant per tier substitute of section 1.5, so that the two rules are
separated by the dependency's own declared disposition and never by a roster of
identifiers. The chain at the end is the transitive case: the finding sits on
the LAST marked task above the gap, because that is the edge a reader repairs.

## 3.1 The repositories

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 9. The tasks

**OPR-1 · The outward action** — OPERATOR
Files: `.github/workflows/momus.yml`
Design: 1
Depends: none
Check: The operator opens a scratch pull request and observes the review run.

**SPK-1 · The spike** — no tier (THROWAWAY)
Files: `spike/probe.cpp`
Design: 2
Depends: none
Check: The operator runs the probe against `extracted/` and records the value.

**DEF-1 · The unscheduled task** — deferred
Files: `tools/deferred.py`
Design: 3
Depends: none
Check: Nowhere. A deferred task has no check to run.

**UPS-1 · The upstream pull request** — upstream
Files: `upstream/patch.diff`
Design: 4
Depends: none
Check: The upstream maintainer's own continuous integration.

**BBB-1 · The dependant on the outward action** — T0
Files: `tests/t0_beta.cpp`
Design: 5
Depends: OPR-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.
**DONE on 2026-01-02, commit `2222222` → `tests/t0_beta.cpp`.**

**CCC-1 · The dependant on the spike** — T0
Files: `tests/t0_gamma.cpp`
Design: 6
Depends: SPK-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
**DONE on 2026-01-03, commit `3333333` → `tests/t0_gamma.cpp`.**

**DDD-1 · The dependant on the unscheduled task** — T0
Files: `tests/t0_delta.cpp`
Design: 7
Depends: DEF-1
Check: `ctest --test-dir build --no-tests=error -R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.
**DONE on 2026-01-04, commit `4444444` → `tests/t0_delta.cpp`.**

**EEE-1 · The dependant on the upstream pull request** — T0
Files: `tests/t0_epsilon.cpp`
Design: 8
Depends: UPS-1
Check: `ctest --test-dir build --no-tests=error -R t0_epsilon`. Registered with `add_test(NAME t0_epsilon ...)`.
**DONE on 2026-01-05, commit `5555555` → `tests/t0_epsilon.cpp`.**

**FFF-3 · The unstarted tail of the chain** — T0
Files: `tests/t0_zeta.cpp`
Design: 9
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_zeta`. Registered with `add_test(NAME t0_zeta ...)`.

**FFF-2 · The middle of the chain** — T0
Files: `tests/t0_eta.cpp`
Design: 10
Depends: FFF-3
Check: `ctest --test-dir build --no-tests=error -R t0_eta`. Registered with `add_test(NAME t0_eta ...)`.
**DONE on 2026-01-06, commit `6666666` → `tests/t0_eta.cpp`.**

**FFF-1 · The head of the chain** — T0
Files: `tests/t0_theta.cpp`
Design: 11
Depends: FFF-2
Check: `ctest --test-dir build --no-tests=error -R t0_theta`. Registered with `add_test(NAME t0_theta ...)`.
**DONE on 2026-01-07, commit `7777777` → `tests/t0_theta.cpp`.**
