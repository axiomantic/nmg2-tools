# Negative fixture — the ownership marker of section 1.1.1 rule D

Section 7.4.2 states it verbatim: **"A marked entry never raises
`shared-path-without-owner`, because a marked entry is not a claim."** So a
marked entry is not a claimant at all. Stripping the marker and counting the
entry anyway would leave the rule firing wherever one marked writer meets one
bare one, which is the same defect one layer down.

Four paths, and the first of them is the control.

* `g2Lib/genuinely_unowned.cpp` — two BARE claimants and no owner row. The rule
  must fire, before the marker is understood and after. A repair that silences
  this path deleted the rule instead of repairing it.
* `g2Lib/owned_shared.cpp` — three BARE claimants and an owner row that resolves.
  Silent, before and after.
* `g2Lib/test/tests_marked.cmake` — one bare claimant, two MARKED entries and an
  owner row. This is the defect: the marked spelling is a key of its own today,
  two tasks carry it, and no owner row can ever name a path with a marker on the
  end of it.
* `g2Lib/unrowed_manifest.cpp` — one bare claimant, two MARKED entries and NO
  owner row. This path is what separates "a marked entry is never a claim" from
  "strip the marker and count the entry anyway": under the second reading it has
  three claimants and no owner, so it keeps firing. Section 7.4.2 gives the
  missing row to `second-write-no-owner-row`, which is a different rule and is
  not built.

## 3. The repositories

### 3.1 Layout B

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 7. The tracks

### 7.4.2 Every shared file has one owner

| Path | Owner | The mechanism for everybody else |
|---|---|---|
| `g2Lib/owned_shared.cpp` | **AAA-1** | Everybody else asks AAA-1. |
| `g2Lib/test/tests_marked.cmake` | **AAA-1** | Every other task of the track marks it `@AAA-1`. |

## 9. The tasks

**AAA-1 · The owner** — T0
Files: `g2Lib/owned_shared.cpp`, `g2Lib/test/tests_marked.cmake`, `g2Lib/unrowed_manifest.cpp`, `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The genuinely unowned collision** — T0
Files: `g2Lib/genuinely_unowned.cpp`, `g2Lib/owned_shared.cpp`, `g2Lib/test/tests_marked.cmake@AAA-1`, `g2Lib/unrowed_manifest.cpp@AAA-1`, `test/t0_beta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`.

**AAA-3 · The other side of the collision** — T0
Files: `g2Lib/genuinely_unowned.cpp`, `g2Lib/owned_shared.cpp`, `g2Lib/test/tests_marked.cmake@AAA-1`, `g2Lib/unrowed_manifest.cpp@AAA-1`, `test/t0_gamma.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`. Registered with `add_test(NAME t0_gamma ...)`.
