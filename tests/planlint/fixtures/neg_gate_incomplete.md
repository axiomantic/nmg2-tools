# A plan whose completion marker rests on a withdrawn one

This is the REPORTED half of the calibrated pair. It is `pos_gate_complete.md`
with two `~~` pairs added to AAA-1's marker line and nothing else changed, so
what separates a report from a silence here is the strike and only the strike.

## 3.1 The repositories

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 9. The tasks

**AAA-1 · The dependency** — T0
Files: `tests/t0_alpha.cpp`
Design: 1
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`. Registered with `add_test(NAME t0_alpha ...)`.
**~~DONE on 2026-01-01, commit `1111111` → `tests/t0_alpha.cpp`.~~**

**AAA-2 · The dependant** — T0
Files: `tests/t0_beta.cpp`
Design: 2
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.
**DONE on 2026-01-02, commit `2222222` → `tests/t0_beta.cpp`.**
