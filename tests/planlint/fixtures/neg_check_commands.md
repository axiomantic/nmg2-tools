# Negative fixture — four defective check-command forms

Each task carries exactly one defect.

AAA-1 passes `-R` a name that no `Files:` line creates. The pattern matches
nothing, and an unflagged run of it would exit 0.

AAA-2 omits `--no-tests=error`. Section 1.3 rule 10 says every invocation carries it.

AAA-3 forwards arguments with `--`. CTest rejects that form; it was measured.

AAA-4 builds a target that no `Files:` line creates.

AAA-5 passes `-R` a name that a `Files:` line creates and that no task registers
with `add_test(NAME ...)`.

## 9. The tasks

**AAA-1 · The name nothing creates** — T0
Files: `src/one.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_ghost`.

**AAA-2 · The unflagged invocation** — T0
Files: `test/t0_beta.cpp`
Depends: none
Check: `ctest --test-dir build -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**AAA-3 · The forwarded argument** — T0
Files: `test/t0_gamma.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_gamma -- --group move`. Registered with `add_test(NAME t0_gamma ...)`.

**AAA-4 · The target nothing creates** — T0
Files: `test/t0_delta.cpp`
Depends: none
Check: `cmake --build build --target ghost_target` and `ctest --test-dir build --no-tests=error -R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.

**AAA-5 · The unregistered name** — T0
Files: `test/t0_epsilon.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_epsilon`.
