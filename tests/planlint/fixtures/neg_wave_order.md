# Negative fixture — a task that starts before what it waits on

AAA-2 sits in wave 1 and depends on AAA-1, which sits in wave 3. The work cannot
start in the wave the table puts it in.

BBB-1 is a task the wave table names nowhere, and CCC-9 is a wave-table entry
that this document defines in no task block.

## 7. The tracks

### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-2 |
| 3a | 3 | AAA-1; CCC-9 |

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**BBB-1 · The unplaced** — T0
Files: `test/t0_gamma.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
