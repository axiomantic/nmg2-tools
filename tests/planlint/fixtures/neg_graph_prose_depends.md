# Negative fixture — prose on a `Depends:` line

This is the defect the plan met for real. A scheduling note written on the
`Depends:` line is read as an edge by a parser, and the false edge closes a
cycle that no reader can see.

AAA-2 declares AAA-1 and then adds "Scheduled before BBB-1" as prose. BBB-1
depends on AAA-2 for real. A parser that harvests every identifier from the line
reports a cycle between AAA-2 and BBB-1 that does not exist.

AAA-3 carries the second shape: the identifier sits inside a clause rather than
in an item position, so it is prose in the edge region and not a declared edge.

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: AAA-1. Scheduled before BBB-1.
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**AAA-3 · The third** — T0
Files: `test/t0_delta.cpp`
Depends: AAA-1, and it is also scheduled after BBB-1 runs
Check: `ctest --test-dir build --no-tests=error -R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.

**BBB-1 · The joiner** — T0
Files: `test/t0_gamma.cpp`
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
