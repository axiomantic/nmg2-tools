# Negative fixture — the removed-mechanism lint

**WHAT THIS FILE IS.** Four task blocks the removed-mechanism lint MUST spare,
each carried FROM ITS `Check:` LINE THROUGH THE END OF ITS TASK BODY. An empty
findings list over this fixture is the answer, and `examined` is non-zero, so
the emptiness is a measurement and not an absence of one.

**THIS HALF IS VERBATIM, AND THAT IS THE DIRECTION A WRONG LINT FAILS IN.**

  * **SCH-8 — VERBATIM** from the plan at `40a9440`, lines 5968 to 5973. Its
    sparing phrase — *"A debug build asserts `dsp56k::g_useJIT`"* — sits FOUR
    LINES BELOW its `Check:` line, so a fixture carrying `Check:` LINES alone
    would lose it and this fixture would return a finding for a reason that has
    nothing to do with the lint being wrong.
  * **SCH-10 — VERBATIM** from the same revision, lines 5987 to 5988. Its
    sparing phrase sits on the `Check:` line itself.
  * **SCH-28 — VERBATIM** from `996c3dd`, lines 5326 to 5332, under its
    HISTORICAL identifier: SCH-28 was merged into SCH-21 on 2026-08-24, §24.6
    row W3-390, and this plan defines no SCH-28 block today. At `996c3dd` the
    block reads as a NEGATIVE — it names a release build beside a debug build —
    which is why the only revision that holds it puts it on this side.
  * **TOOL-14 — VERBATIM** from the plan at `40a9440`, line 4968: the lint's own
    task block. The empty-findings requirement therefore covers it, and
    TOOL-14's own `Check:` block is checked to be absent from the findings
    rather than merely intended to be.

## 9. The tasks

**SCH-8 · `g2::runDspCycles`** — T0
Files: `g2Lib/runDspCycles.h`, `g2Lib/test/t0_run_dsp_cycles_contract.cpp`
Design: 13.10.3
Depends: SCH-6
Check: `ctest --test-dir build --no-tests=error -R ^t0_run_dsp_cycles_contract$`. The registered test carries a `static_assert` on the declared signature — the argument list, the return type and `noexcept` — and it drives two cases against a synthetic `dsp56k::DSP`: **a `wantCycles` of 0 executes no `exec()` at all**, and a `wantCycles` of 1 against a scripted block that costs more than 1 executes exactly one `exec()`, which is what proves the test is BEFORE the call and not after. **A build of the target tests neither, and section 7.7.1 gives the class.** SCH-9 covers the bound over 1,000 quanta; this row covers the contract.
**`dsp56k::DSP::exec` is `void exec() noexcept` — no argument, no return value, one dispatch unit — so no cycle-bounded run call exists in the library at all. This is an adapter this project writes.**
The loop takes `start = dsp.getCycles()`, then `while (dsp.getCycles() - start < wantCycles) dsp.exec();`, and returns the difference narrowed to `uint32_t`. **The test is BEFORE each `exec()`, never after.** A test-after loop would return less than the budget, which is the case the cycle-debt rule assumes cannot happen.
`dsp.getCycles()` returns a `const uint64_t&`, which is a live counter. **Do not snapshot it.**
The counter is **just-in-time only**: the interpreter never writes `m_cycles`. A debug build asserts `dsp56k::g_useJIT`, and a debug build asserts the narrowing fits. **Both debug assertions are debug-only and neither is this check's predicate.** Measurement 7's rule applies to the statement and not to the verdict: a run that keeps them needs `-DCMAKE_BUILD_TYPE=Debug`, and the two driven cases pass in any build type.
A `wantCycles` of 0 runs nothing.

**SCH-10 · `transmitDspFrame` and `receiveDspFrame`** — T0
Files: `g2Lib/esaiFrame.h`, `g2Lib/test/t0_esai_frame.cpp`
Design: 13.10.3
Depends: SCH-4
Check: `ctest --test-dir build --no-tests=error -R ^t0_esai_frame$`. `transmitDspFrame` returns 0 when `hasEnabledTransmitters()` is false. Otherwise it loops `execTX()` while `getTxFrameCounter()` has not moved, counting slots, and returns the slot count. **One `execTX` is one slot. A frame costs `getTxWordCount() + 1` slots**, and a debug build asserts `slots <= getTxWordCount() + 1`, because a transmit-enable change can cost one slot fewer.
`receiveDspFrame` returns 0 when `hasEnabledReceivers()` is false. Otherwise it calls `execRX()` exactly `getRxWordCount() + 1` times and returns that count. **The fixed count is exact because the scheduler is the only `execRX` caller**: the mirror call at `esai.cpp:186` is commented out upstream.

**SCH-28 · The thread map** — T0
Files: `g2Lib/scheduler.cpp` debug ownership check, `docs/threading.md`, `g2Lib/test/t0_thread_map.cpp`, `.../tests_sched.cmake@BRD-0`
Design: 13.10 rule 3
Depends: SCH-21
Check: `ctest --test-dir build --no-tests=error -R ^t0_thread_map$`. The boot thread owns `create`, `reset`, `stateLoad`, the boot `runFrames` calls and `beginPlayPhase`. The audio thread owns `push`, `runFrames`, `pull`, `queueMidi` and the accessors. **Ownership moves exactly once.** **The scheduler records the owning thread identity and exposes it**, and the registered test asserts the recorded identity against the caller for each of the two phases, **in a release build as well as a debug build**. A debug build additionally asserts on a call from another thread; the assertion is not the check's predicate. **The thread map is the property that stops a data race in the shipped build, so a check that only runs in Debug checks the wrong build.** `docs/threading.md` carries the full map: 14 `Scheduler` rows covering 24 methods, and 2 `TransportHub` rows covering 3.
**A console harness that wants an observability accessor from another thread reads a copy the audio thread published, never the accessor.**

**TOOL-14 · The removed-mechanism lint, for a `Check:` predicate that names a mechanism the default build deletes** — T0
Files: `planlint/removed.py`, `tests/planlint/test_removed.py`
Design: none
Depends: REPO-14
Check: `pytest tests/planlint/test_removed.py` in `axiomantic/nmg2-tools`, and `pytest tests/planlint` for the registry. **Every case drives committed fixtures or a synthetic table, so none needs this document, a build tree or an artifact, and the task is therefore genuinely T0.** **THE DISCRIMINATOR CASE, BOTH DIRECTIONS IN ONE CHECK AND NEITHER DIRECTION ALONE:** run against `fixtures/pos_removed_mechanism.md`, the returned findings list holds **exactly five** entries and the set of their `task` fields equals `{BRD-17, SCH-7, SCH-20, SCH-28, DSP-7}` — **THESE IDENTIFIERS ARE THE FIXTURE'S AND NOT THIS PLAN'S, AND `SCH-28` IN PARTICULAR NAMES THE FIXTURE'S HISTORICAL BLOCK AND NOT A BLOCK OF THIS DOCUMENT, WHICH DEFINES NONE**; run against `fixtures/neg_removed_mechanism.md`, the findings list is **EMPTY** and `examined` is **non-zero**, so the empty list is an answer and not an absence of one. **THE LIVE-EXPECTATION CASE, WHICH IS THE FIFTH POSITIVE AND IS THE ONE THE `kept_by` EXCLUSION IS FALSIFIABLE THROUGH:** that fifth block is DSP-7's `Check:` block copied VERBATIM from this document at the revision the fixture header names — defect unrepaired, no build type named in it that keeps the mechanism — and the run must report it BY NAME. **THE SELF-CONSISTENCY CASE, WHICH CONVERTS A PROMISE INTO A CHECKED FACT:** the negative fixture carries a further block, **THIS TASK'S OWN `Check:` BLOCK**, copied verbatim at that same revision, so the EMPTY-findings requirement above covers it and **TOOL-14's own block is NOT among the findings** rather than merely intended not to be. **THE EVIDENCE CASE:** each of the four findings carries `severity` ERROR, a `line` that resolves to the fixture line the clause is on, and an `evidence` string that is a SUBSTRING of that line — a message that merely names the task passes none of these. **THE DATA-TABLE CASE, WHICH IS WHAT SEPARATES THIS LINT FROM A REGEX:** `run()` is driven against a one-row table whose `mechanism` is a token that appears nowhere in this project, over a fixture written to that token, and it reports that row's finding; the same call over the real table reports nothing for that fixture. **THE EMPTY-POPULATION CASE:** run against a fixture holding no task block at all, the result carries a `no-input` finding at ERROR and `examined` 0, so nothing-to-check is never a pass. **THE REGISTRY CASE:** `validate_lint_registry` is called with an `all_lints` mapping that holds `removed` and an `always_run` mapping that does not, and it raises `LintRegistryError`; called with the shipped mappings it returns. **REQUIRED-RED, AND EACH NAMES THE EXACT CASE IT TURNS:** deleting the `kept_by` test spares nothing and turns the negative-fixture case red, because SCH-8 and SCH-10 are then reported; **WIDENING `kept_by` TO BUILD-TYPE NAMES GENERALLY — WHICH IS THE SHAPE AN IMPLEMENTER READING THE ENGLISH REACHES FOR FIRST — TURNS THE LIVE-EXPECTATION CASE RED, BECAUSE A `kept_by` THAT MATCHES `Release` OR `NDEBUG` SPARES DSP-7:** the block names both in the very sentence that DIAGNOSES its own defect, so the text that makes the finding true would be read as the text that excuses it, the lint's first live run would be CLEAN, and this block's warning that a clean first run proves nothing would be satisfied backwards; replacing the table iteration with a literal `assert` regex turns the synthetic-table case red, because the invented mechanism is then invisible; scanning raw file lines instead of parsed `Check:` blocks turns the finding-count case on the positive fixture red, because the fixtures' own prose commentary is then counted; returning `LintResult` directly instead of through `guard_no_input` turns the empty-population case red; dropping the `evidence` field turns the evidence case red; and removing the `DOCUMENT_LINTS` row turns the registry case red at import.
