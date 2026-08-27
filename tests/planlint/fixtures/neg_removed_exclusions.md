# Negative fixture — the removed-mechanism lint's named exclusions

**WHAT THIS FILE IS.** Eleven task blocks the removed-mechanism lint MUST spare,
one for each REASON a flagged span cannot be a defect of this class. An empty
findings list over this fixture is the answer, and `examined` is non-zero, so
the emptiness is a measurement and not an absence of one.

**EVERY BLOCK HERE IS SYNTHETIC AND NONE IS A TRANSCRIPT.** The verbatim
calibration lives in `neg_removed_mechanism.md` and is untouched by this file,
because §24.6 row W3-408's TOOL-14 block states the contents of that pair by
name and a fixture the plan describes may not be grown from outside the plan.

**EACH BLOCK HAS A PAIRED BLOCK IN `pos_removed_exclusions.md` THAT DIFFERS AS
NARROWLY AS THE REASON ALLOWS AND MUST STILL BE REPORTED.** Without the paired
positive an exclusion is an untested `off` switch, and a zero proves nothing
unless the same command returns non-zero somewhere.

  * **KEP-1 — A `~~`-STRUCK PREDICATE.** The document's own convention is to
    strike and quote rather than delete, so struck text is HISTORY and not a
    live predicate. Its pair is the identical block with the `~~` markers
    removed.
  * **KEP-2 — A STATIC ASSERTION.** `NDEBUG` does not remove `static_assert`:
    it is a compile-time construct present in every build type, and the class
    this lint reads is *a mechanism the default build removes*. Its pair says
    `assert(` where this one says `static_assert(`, and nothing else.
  * **KEP-3 — A CITATION OF ONE OF THE PLAN'S OWN NUMBERED GRAPH ASSERTIONS.**
    §7.6's assertions are sentences in this document, checked by `planlint`
    itself; no build type deletes a sentence. Its pair drops the number and
    nothing else, which is the whole of the recognizer. The pair is driven
    through the SHAPE-keyed rule, because the noun alone convicts under
    neither rule.
  * **KEP-4 — A LIVE `debug build` SENTENCE.** §7.7's FORM 1 — *"it names
    `-DCMAKE_BUILD_TYPE=Debug` on a command inside the same block"* — in the
    ordinary case. Its pair is the identical block with that one sentence
    struck, so a withdrawn excuse stops excusing.
  * **KEP-7 — FORM 2, THE PROPERTY CONVERTED TO AN OBSERVABLE.** §7.7's second
    legal form: *"it converts the property to an OBSERVABLE the check reads in
    any build type — a returned value, a `g2::Status`, a counter, a file"*. The
    wording is BRD-7's own — nine bare `assert()`s replaced by a helper
    *"compiled in every build type"*. Its pair drops that one clause and
    nothing else.
  * **KEP-8 — FORM 2, IN THE OTHER WORDING THE DOCUMENT USES.** DSP-7's live
    clause reads back the registers *"through the peripheral set, which is an
    observable no build type deletes"*. The two wordings are separate
    alternatives of the same form and each is driven from both directions,
    because an alternative no fixture reaches is an alternative nothing proves.
    Its pair drops that one clause and nothing else.
  * **KEP-9 — FORM 3, THE PROPERTY DECLARED UNCHECKED IN THE DEFAULT BUILD.**
    §7.7's third legal form: *"the block says in words that the property is
    unchecked in the default build and names the task that checks it"*. BOTH
    halves are required — the form names the task, so a block that declares the
    gap and names no task states no form at all. Its pair drops the declaring
    clause and keeps the task identifier, so the pair proves the declaration is
    what spares and not the identifier beside it.
  * **KEP-10 — A VERDICT-SHAPE PREDICATE UNDER A LIVE FORM 1 SENTENCE.** The
    shape-keyed rule's sparing half. `without asserting` is the predicate SHAPE
    §7.7's boxed RULE names, and a block that states it under a legal form is
    spared exactly as the noun-keyed rule's blocks are. Its pair is the
    identical block with that one sentence removed.
  * **KEP-11 — FORM 1 IN THE SPELLING §7.7 ITSELF PRESCRIBES.** §7.7 writes
    form 1 down once and the spelling carries the flag prefix: *"it names
    `-DCMAKE_BUILD_TYPE=Debug` on a command inside the same block"*. KEP-4
    drives the PROSE wording of the same form; this block drives the COMMAND
    wording, which is the one the section wrote. Its pair says `Release` where
    this one says `Debug` and nothing else — the one word that turns a setting
    that KEEPS the mechanism into the setting that removes it.
  * **UNM-1 — A TRACK §7.1 PLACES IN AN UNMEASURED REPOSITORY.** §7.7 says the
    rule *"binds each repository from its own transcript"* and that `mcf5307`
    *"is a Nim-driven CMake project and its default build type is NOT
    measured"*. Its pair is the identical block under a track §7.1 places in
    the `gearmulator` fork.
  * **SPN-1 — A TRACK THAT SPANS A BOUND AND AN UNBOUND REPOSITORY.** A block
    whose track writes into `nmg2-tools` as well as the fork may be describing
    the work in the repository where `NDEBUG` has no meaning at all, and §7.7
    forbids applying a measured behaviour outside its own transcript. Its pair
    is the identical block under the single-repository track.

## 7.1 The tracks

| Track | Worktree name | Repository | Task prefix |
|---|---|---|---|
| 1 | `nmg2-kept` | `gearmulator` fork | `KEP` |
| 2 | `nmg2-unmeasured` | `mcf5307` | `UNM` |
| 3 | `nmg2-spanning` | `gearmulator` fork, `nmg2-tools` | `SPN` |

## 9. The tasks

**KEP-1 · A predicate withdrawn by a strike** — T0
Files: `g2Lib/test/t0_kep_one.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_one$`. ~~The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper.~~ **THE STRUCK CLAUSE IS REPLACED AND IT IS QUOTED RATHER THAN OVERWRITTEN.** The registered test drives one case and reads the bound back out of the helper's own counter.

**KEP-2 · A compile-time bound** — T0
Files: `g2Lib/test/t0_kep_two.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_two$`. The registered test drives one case and the bound is held by a `static_assert(lo <= hi)` in the helper.

**KEP-3 · A graph invariant this document states** — T0
Files: `g2Lib/test/t0_kep_three.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_three$`. The registered test drives the row and reports that no assertion 5 trips.

**KEP-4 · A bound the debug build keeps** — T0
Files: `g2Lib/test/t0_kep_four.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_four$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper. A debug build keeps it.

**UNM-1 · A bound in the unmeasured repository** — T0
Files: `tests/t_unm_one.nim`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_unm_one$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper.

**SPN-1 · A bound in a track that spans two repositories** — T0
Files: `g2Lib/test/t0_spn_one.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_spn_one$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper.

**KEP-7 · A bound converted to an observable, in BRD-7's wording** — T0
Files: `g2Lib/test/t0_kep_seven.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_seven$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper. Nine bare `assert()`s are replaced by `checkEqual`, which is compiled in every build type.

**KEP-8 · A bound converted to an observable, in DSP-7's wording** — T0
Files: `g2Lib/test/t0_kep_eight.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_eight$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper. The test asserts the arming by reading back that channel's own registers through the peripheral set, which is an observable no build type deletes.

**KEP-9 · A bound declared unchecked in the default build** — T0
Files: `g2Lib/test/t0_kep_nine.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_nine$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper. The property is unchecked in the default build and KEP-4 is the task that checks it.

**KEP-10 · A verdict-shape predicate the debug build keeps** — T0
Files: `g2Lib/test/t0_kep_ten.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_kep_ten$`. The registered test drives one case and verifies it completes without asserting. A debug build keeps it.

**KEP-11 · A bound the debug build keeps, named on the check command** — T0
Files: `g2Lib/test/t0_kep_eleven.cpp`
Depends: none
Check: `cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug` then `ctest --test-dir build-debug --no-tests=error -R ^t0_kep_eleven$`. The registered test drives one case and the bound is held by an `assert(lo <= hi)` in the helper.
