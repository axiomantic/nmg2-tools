# A plan with an empty `-R` argument

`ctest -R ^$` strips to the empty name. A `Files:` entry that names a DIRECTORY
has an empty basename, so the empty string was in the name pool, the ERROR gate
passed, and the registrar lint reported nothing at all.

This fixture carries that one defect. The task is otherwise clean: it creates
the registrar of its own directory, it invokes its own test, and the second
`-R` argument is the whole defect.

## 9. The tasks

**AAA-1 · The directory carrier** — T0
Files: `captures/`, `tests/CMakeLists.txt`, `tests/t0_alpha.cpp`
Design: 1
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$` and `ctest --test-dir build --no-tests=error -R ^$`. Registered with `add_test(NAME t0_alpha ...)`.
