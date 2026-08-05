# Negative fixture — the registrar is outside the closure

AAA-1 is a contract task. Its check runs `ctest -R t0_abi_header`, and the test
source is on its own `Files:` line — but the task that creates
`tests/CMakeLists.txt`, which is what registers anything in that directory, is
AAA-3, and AAA-3 waits on AAA-1. The check cannot pass when the task is declared
complete. This is the mirror of a check that cannot fail.

AAA-4 runs `-R t0_late`, whose test source AAA-5 creates. AAA-5 is downstream of
AAA-4, so the creator is outside the closure too.

BBB-1 is the clean shape: it depends on AAA-3, which registers the directory,
and it creates its own test source.

## 9. The tasks

**AAA-1 · The contract** — T0
Files: `include/one.h`, `tests/t0_abi_header.c`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_abi_header`.

**AAA-2 · CMake drives the build** — T0
Files: `CMakeLists.txt`
Depends: AAA-1
Check: `cmake -S . -B build` configures. A negative case drives it to fail.

**AAA-3 · The test aggregate** — T0
Files: `tests/CMakeLists.txt`, `tests/t0_smoke.cpp`
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_smoke`.

**AAA-4 · The early caller** — T0
Files: `src/four.cpp`
Depends: AAA-3
Check: `ctest --test-dir build --no-tests=error -R t0_late`.

**AAA-5 · The late creator** — T0
Files: `tests/t0_late.cpp`
Depends: AAA-4
Check: `ctest --test-dir build --no-tests=error -R t0_late`.

**BBB-1 · The clean shape** — T0
Files: `tests/t0_clean.cpp`
Depends: AAA-3
Check: `ctest --test-dir build --no-tests=error -R t0_clean`.
