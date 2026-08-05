# Negative fixture — a self-loop

AAA-2 names itself. A component of size one that carries its own edge.

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: AAA-1, AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.
