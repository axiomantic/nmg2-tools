# Negative fixture — an unknown task identifier

AAA-2 names ZZZ-9, which this document defines nowhere. The range AAA-1 to AAA-4
runs past the last task the document defines, so AAA-3 and AAA-4 are unknown too.

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: ZZZ-9
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**BBB-1 · The joiner** — T0
Files: `test/t0_gamma.cpp`
Depends: AAA-1 to AAA-4
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
