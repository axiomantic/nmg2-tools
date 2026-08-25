# Negative fixture — a registration written outside every task block

Section 1.3 rule 9 says *some task* registers the name. A defect-register row is
not a task, so prose there must not satisfy the rule.

The two tasks differ in ONE thing: where the `add_test(NAME ...)` sentence is
written. BBB-1 writes it inside its own block and must be silent. BBB-2 writes
the identical sentence in the defect register below and must be reported.

## 24.6 Carried defects

| # | Finding |
|---|---|
| **W9-1** | The registration reads `add_test(NAME t0_outside COMMAND t0_outside)`. |

## 9. The tasks

**BBB-1 · The registration inside the task** — T0
Files: `test/t0_inside.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_inside`. The registration reads `add_test(NAME t0_inside COMMAND t0_inside)`.

**BBB-2 · The registration outside every task** — T0
Files: `test/t0_outside.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_outside`.
