# A plan whose completion markers do not cover what their tasks declare

## 3.1 The repositories

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 9. The tasks

**AAA-1 · The covered task** — T0
Files: `tests/CMakeLists.txt`, `tests/t0_alpha.cpp`, `conformance/corpus/*.json`, targets `core_tests`
Design: 1
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`. Registered with `add_test(NAME t0_alpha ...)`.
**DONE on 2026-01-01, 2 commits. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → `tests/CMakeLists.txt`; `axiomantic/core` `2222222` → `tests/t0_alpha.cpp`.

**AAA-2 · The short citation** — T0
Files: `tests/t0_beta.cpp`, `src/beta.cpp`, `src/beta.h`
Design: 2
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.
**DONE on 2026-01-02, 3 commits. CITED PER DECLARED PATH:** `axiomantic/core` `3333333` → `tests/t0_beta.cpp`, `src/beta.cpp`.

**AAA-3 · The older grammar** — T0
Files: `tests/t0_gamma.cpp`
Design: 3
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
**DONE on 2026-01-03, commit `4444444`.**

**AAA-4 · The task with no marker at all** — T0
Files: `tests/t0_delta.cpp`
Design: 4
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.
