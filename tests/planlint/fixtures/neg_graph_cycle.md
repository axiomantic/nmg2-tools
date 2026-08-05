# Negative fixture — a dependency cycle

AAA-1 and AAA-2 wait on each other. Tarjan reports one component of size two.

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.
