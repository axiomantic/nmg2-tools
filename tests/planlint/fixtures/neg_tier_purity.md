# Negative fixture — the tier rules broken four ways

AAA-2 is T0 and depends on BBB-1, which is T1. A required check that needs an
artifact cannot run in a public repository.

AAA-3 is T0 and its own check is gated on `NMG2_ARTIFACTS`, so the required tier
cannot run with the variable unset.

AAA-4 is T0 and reads a fixture the section 7.8 register marks PRIVATE.

AAA-5 carries no tier on its header line at all.

BBB-2's range swallows a task of a higher tier and a conditional task, which is
section 1.3 rule 8.

## 7. The tracks

### 7.8 The recorded-fixture register

| Fixture | Path | Named by | Repository | Visibility |
|---|---|---|---|---|
| The recorded trace | `fixtures/protocol/` | BBB-1 | `artifacts` | **PRIVATE** |

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The artifact reader** — T0
Files: `test/t0_beta.cpp`
Depends: BBB-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**AAA-3 · The gated required check** — T0
Files: `test/t0_gamma.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma` with `NMG2_ARTIFACTS` set. Registered with `add_test(NAME t0_gamma ...)`.

**AAA-4 · The private reader** — T0
Files: `test/t0_delta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_delta` reads `fixtures/protocol/`. Registered with `add_test(NAME t0_delta ...)`.

**AAA-5 · The untiered**
Files: `test/t0_epsilon.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_epsilon`. Registered with `add_test(NAME t0_epsilon ...)`.

**BBB-1 · The gated producer** — T1
Files: `test/t1_zeta.cpp`, `fixtures/protocol/`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t1_zeta` with `NMG2_ARTIFACTS` set. Registered with `add_test(NAME t1_zeta ...)`.

**BBB-2 · The range swallower** — T0
Files: `test/t0_eta.cpp`
Depends: BBB-1 to BBB-3
Check: `ctest --test-dir build --no-tests=error -R t0_eta`. Registered with `add_test(NAME t0_eta ...)`.

**BBB-3 · The conditional** — T0
Files: `test/t0_theta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_theta`. Registered with `add_test(NAME t0_theta ...)`.

## 24. Task index

### 24.4 The conditional tasks

| Task | Condition |
|---|---|
| BBB-3 | Exists only if the probe reports a result. |
