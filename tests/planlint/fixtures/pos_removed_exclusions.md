# Positive fixture — the paired half of each named exclusion

**WHAT THIS FILE IS.** Six task blocks the removed-mechanism lint MUST report.
Each one is the PAIR of a block in `neg_removed_exclusions.md`, differing as
narrowly as its reason allows, so that every exclusion is falsifiable in both
directions rather than being an `off` switch nothing drives.

**EVERY BLOCK HERE IS SYNTHETIC AND NONE IS A TRANSCRIPT.**

  * **KEP-1** — `neg` KEP-1 with the `~~` markers removed. A live predicate.
  * **KEP-2** — `neg` KEP-2 with the word `static` removed. A runtime
    assertion, which `NDEBUG` does remove.
  * **KEP-3** — `neg` KEP-3 with the assertion NUMBER removed. Without a
    number the noun cites no §7.6 graph assertion and reads as the mechanism.
  * **KEP-4** — `neg` KEP-4 with its `debug build` sentence STRUCK. A
    withdrawn excuse stops excusing, which is the other direction of the
    strike rule and the reason the strike is applied to `kept_by` too.
  * **KEP-5** — `neg` UNM-1's text under a track §7.1 places in the
    `gearmulator` fork. The identifier is the pairing's, not a second defect.
  * **KEP-6** — `neg` SPN-1's text under that same single-repository track.

## 7.1 The tracks

| Track | Worktree name | Repository | Task prefix |
|---|---|---|---|
| 1 | `nmg2-kept` | `gearmulator` fork | `KEP` |

## 9. The tasks

**KEP-1 · A predicate not withdrawn** — T0
Files: `g2Lib/test/t0_kep_one.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_one$`. The registered test drives one case and the bound is held by an assertion in the helper.

**KEP-2 · A run-time bound** — T0
Files: `g2Lib/test/t0_kep_two.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_two$`. The registered test drives one case and the bound is held by an assertion in the helper.

**KEP-3 · A bound with no graph assertion behind it** — T0
Files: `g2Lib/test/t0_kep_three.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_three$`. The registered test drives the row and reports whether the assertion still holds.

**KEP-4 · A bound whose debug-build sentence is withdrawn** — T0
Files: `g2Lib/test/t0_kep_four.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_four$`. The registered test drives one case and the bound is held by an assertion in the helper. ~~A debug build keeps it.~~ **THE STRUCK SENTENCE IS WITHDRAWN AND IT IS QUOTED RATHER THAN OVERWRITTEN.**

**KEP-5 · A bound in the measured repository** — T0
Files: `g2Lib/test/t0_kep_five.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_unm_one$`. The registered test drives one case and the bound is held by an assertion in the helper.

**KEP-6 · A bound in a track that spans no second repository** — T0
Files: `g2Lib/test/t0_kep_six.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_spn_one$`. The registered test drives one case and the bound is held by an assertion in the helper.
