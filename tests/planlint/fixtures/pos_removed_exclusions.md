# Positive fixture — the paired half of each named exclusion

**WHAT THIS FILE IS.** Ten task blocks the removed-mechanism lint MUST report.
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
  * **KEP-7** — `neg` KEP-7 with the *"compiled in every build type"* clause
    dropped. The helper is still named; what is gone is the statement that it
    survives the default build, which is the whole of §7.7's form 2.
  * **KEP-8** — `neg` KEP-8 with the *"which is an observable no build type
    deletes"* clause dropped, and nothing else.
  * **KEP-9** — `neg` KEP-9 with the *"unchecked in the default build"*
    declaration dropped and the TASK IDENTIFIER KEPT. §7.7's form 3 needs both
    halves; this pair proves the declaration is the half that spares.
  * **KEP-10** — `neg` KEP-10 with its `debug build` sentence dropped. It
    carries the predicate SHAPE and no assertion NOUN, so it is reported under
    the shape-keyed rule and under no other.

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

**KEP-7 · A bound whose observable clause is dropped** — T0
Files: `g2Lib/test/t0_kep_seven.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_seven$`. The registered test drives one case and the bound is held by an assertion in the helper. Nine bare `assert()`s are replaced by `checkEqual`.

**KEP-8 · A read-back with no observable clause** — T0
Files: `g2Lib/test/t0_kep_eight.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_eight$`. The registered test drives one case and the bound is held by an assertion in the helper. The test asserts the arming by reading back that channel's own registers through the peripheral set.

**KEP-9 · A bound that names a task and declares no gap** — T0
Files: `g2Lib/test/t0_kep_nine.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_nine$`. The registered test drives one case and the bound is held by an assertion in the helper. KEP-4 is the task that checks it.

**KEP-10 · A verdict-shape predicate no build type keeps** — T0
Files: `g2Lib/test/t0_kep_ten.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_ten$`. The registered test drives one case and verifies it completes without asserting.
