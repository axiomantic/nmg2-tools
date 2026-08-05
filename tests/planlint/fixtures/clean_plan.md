# A Clean Test Plan

This fixture is the baseline. Every lint must report zero findings against it.
Each negative fixture is this document with exactly one defect added, and
`tests/test_mutation.py` mutates this document once for every rule the document
lints can emit.

The document therefore carries, on purpose, the shapes a mutation needs: an
ABBREVIATED path and a CANONICAL one that name one file, an ANCHORED `-R`
argument, a SHELL-QUOTED anchored argument, a directory owner row and a file
owner row, a conditional-task count, and a cross-track edge count. It also
carries an EXPORTED build target with a reachable consumer, a header with a
reachable consumer, a qualified type name a check reads, and a build option
declared OFF by one task and turned ON by another.

## 3. The repositories

### 3.1 Layout B

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/artifacts` | **PRIVATE** | The firmware and the private corpus. |
| `axiomantic/core` | PUBLIC | The emulation code. |

## 6. The milestone ladder

| # | Milestone | Tier | How it is checked |
|---|---|---|---|
| **M1** | The core builds and the surface answers. | T0 | `cmake --build build --target core_tests && ctest --test-dir build --no-tests=error -R ^t0_alpha$` → PASS. |

## 7. The tracks and the dependency graph

### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-1 |
| 2 | 2 | AAA-2, BBB-1, DDD-1, DDD-2 |
| 3 | 3 | CCC-1, CCC-2 |
| 4 | 4 | EEE-1 |

### 7.3 The cross-track edges

Assertion 7. There are two edges in the column below whose source and whose target sit in one wave, and each of the two crosses a track inside one wave.

| Source | Target | Cross-track edges |
|---|---|---|
| Alpha | Beta | AAA-2 → BBB-1 |
| Alpha | Delta | AAA-2 → DDD-1 |
| Alpha | Gamma | AAA-2 → CCC-1, CCC-2 |
| Gamma | Epsilon | CCC-1 → EEE-1; CCC-2 → EEE-1 |

### 7.4.2 Every shared file has one owner

A row whose path ends in `/` is a DIRECTORY row and owns every path beneath it.
A file row owns exactly the path it names. Both forms are here, so that
disabling either one reddens this document.

| Path | Owner |
|---|---|
| `g2Lib/test/` | AAA-1 |
| `testdata/shared.json` | AAA-2 |

### 7.8 The recorded-fixture register

| Fixture | Path | Named by | Repository | Visibility |
|---|---|---|---|---|
| The synthesized corpus | `testdata/synth/` | AAA-2 | `core` | PUBLIC |
| The big generated corpus | `conformance/corpus/*.json` | AAA-1 | `core` | PUBLIC — **allow-listed** above the byte ceiling. |
| The private session log | `dumps/session.log` | BBB-1 | `artifacts` | **PRIVATE** |

## 9. The tasks

**AAA-1 · The build and the surface** — T0
Files: `tests/CMakeLists.txt`, `tests/t0_alpha.cpp`, `source/nord/g2/g2Lib/test/CMakeLists.txt`, `conformance/corpus/*.json`, targets `core_tests`
Design: 1
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`. The test is registered with `add_test(NAME t0_alpha ...)` and carries one negative case that drives it to fail. The work lands in the `axiomantic/core` repository.

**AAA-2 · The synthesized corpus** — T0
Files: `testdata/synth/`, `testdata/shared.json`, `tests/t0_beta.cpp`
Design: 2
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)` through the track test list.

**BBB-1 · The gated read** — T1
Files: `g2Lib/test/CMakeLists.txt`, `g2Lib/test/t1_gamma.cpp`, `testdata/beta/`
Design: 3
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t1_gamma` with `NMG2_ARTIFACTS` set. Registered with `add_test(NAME t1_gamma ...)`.

**CCC-1 · The conditional extra** — T0
Files: `tests/t0_delta.cpp`, `g2Lib/delta.cpp`
Design: 4
Depends: CCC-2, AAA-2. **CONDITIONAL: this task exists only if the probe reports a result.**
Check: `ctest --test-dir build --no-tests=error -R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.

**CCC-2 · The second conditional** — T0
Files: `tests/t0_epsilon.cpp`, `g2Lib/gamma.h`, targets `gamma_lib`
Design: 5
Depends: AAA-2. **CONDITIONAL: this task exists only if the probe reports a second result.**
Check: `ctest --test-dir build --no-tests=error -R t0_epsilon`. Registered with `add_test(NAME t0_epsilon ...)`.
It exports `gamma::gamma_lib` and declares `option(G2_LINK_GAMMA "Link gamma" OFF)` in `g2Lib/CMakeLists.txt` with the `gamma::gamma_lib` link behind it.

**DDD-1 · The Python half** — T0
Files: `tools/test_delta.py`, `testdata/shared.json`
Design: 6
Depends: AAA-2
Check: `pytest tools/test_delta.py`. The suite carries a failing case of its own.

**DDD-2 · The oracle comparison** — T2
Files: `tests/t2_zeta.cpp`
Design: 7
Depends: DDD-1
Check: `ctest --test-dir build --no-tests=error -R '^t2_zeta$'`. Registered with `add_test(NAME t2_zeta ...)`.

**EEE-1 · The late gate** — T0
Files: `tests/t0_eta.cpp`
Design: 8
Depends: CCC-1, CCC-2
Check: `ctest --test-dir build --no-tests=error -R t0_eta`. Registered with `add_test(NAME t0_eta ...)`.
This task turns `G2_LINK_GAMMA` ON. The gate carries `#include "gamma.h"`, links `gamma::gamma_lib` and reads `Gamma::Config`.

## 24. Task index

### 24.1 Counts

| Track | Tasks |
|---|---|
| Alpha (AAA) | 2 |
| Beta (BBB) | 1 |
| Gamma (CCC) | 2 |
| Delta (DDD) | 2 |
| Epsilon (EEE) | 1 |
| **Total task blocks** | **8** |

### 24.4 The conditional tasks

Of the two conditional tasks, neither one blocks a milestone.

| Task | Condition |
|---|---|
| CCC-1 | Exists only if the probe reports a result. |
| CCC-2 | Exists only if the probe reports a second result. |
