# Positive fixture — the removed-mechanism lint

**WHAT THIS FILE IS, AND THE PART THAT IS UNCOMFORTABLE IS STATED FIRST.** This
fixture carries five task blocks; the lint REPORTS three and SPARES two [R1]. Each
block is carried FROM ITS `Check:` LINE THROUGH THE END OF ITS TASK BODY, which
is the extent `planlint` parses as a `Check:` block.

**FOUR OF THE FIVE ARE RECONSTRUCTIONS AND ARE NOT TRANSCRIPTS.** `nmg2-artifacts`
carries the plan from ONE import commit, `996c3dd` "Take custody of the planning
documents and the G2 schematics", and at `996c3dd` BRD-17, SCH-7, SCH-20 and
SCH-28 ALREADY carry their repaired wording. The pre-repair text of those four
therefore exists in no revision this project holds. Block by block:

  * **BRD-17 — RECONSTRUCTION**, written to the defect shape §24.6 rows W3-4 and
    W3-18 describe. Not a transcript.
  * **SCH-7 — RECONSTRUCTION**, same ground. Not a transcript.
  * **SCH-20 — RECONSTRUCTION**, same ground. Not a transcript.
  * **SCH-28 — RECONSTRUCTION**, same ground, under a HISTORICAL identifier:
    SCH-28 was merged into SCH-21 on 2026-08-24, §24.6 row W3-390, and this plan
    defines no SCH-28 block today. The identifier is the FIXTURE's.
  * **DSP-7 — VERBATIM**, copied from the plan at `40a9440`, lines 6730 to 6754,
    its `Check:` line through the end of its body. Its defect is unrepaired, and
    it is the case the `kept_by` exclusion is falsifiable through: the block
    names `Release` and `NDEBUG` in the very sentence that DIAGNOSES its defect,
    and names no build type that keeps the mechanism.

**THE PROSE ABOVE AND BELOW EVERY TASK BLOCK IS PART OF THE FIXTURE'S PROOF.** It
names an assertion, and it names `assert()`, and it sits outside every `Check:`
block, so a lint that scanned raw file lines instead of parsed blocks would
report this commentary as an instance of the defect it describes.

## 9. The tasks

**BRD-17 · Blocking control on the HDI08** — T0
Files: `g2Lib/hdi08Adapter.cpp`, `g2Lib/test/t0_hdi08_nonblocking.cpp`
Design: 10.7
Depends: BRD-16
Check: `ctest --test-dir build --no-tests=error -R ^t0_hdi08_nonblocking$`. The shim bounds the words it moves in one quantum below the buffer capacity. The registered test drives more words than the capacity in one quantum and asserts that no assertion trips.

**SCH-7 · The `Executor` interface and the serial executor** — T0
Files: `g2Lib/executor.h`, `g2Lib/test/t0_executor.cpp`
Design: 13.3
Depends: SCH-6
Check: `ctest --test-dir build --no-tests=error -R ^t0_executor$`. `Executor::run` is not re-entrant, and the test drives a job that calls `run` again. The re-entry is caught by an `assert()` in the serial executor.

**SCH-20 · The context index** — T0
Files: `g2Lib/test/t0_context_index.cpp`
Design: 13.5
Depends: SCH-19
Check: `ctest --test-dir build --no-tests=error -R ^t0_context_index$`. The MCU has context index 0 and DSP position `p` has context index `p + 1`. The four accessors reject an index above `dspCount`, and the test drives that case and the rejection is an assertion in the accessor.

**SCH-28 · The thread map** — T0
Files: `g2Lib/scheduler.cpp`, `g2Lib/test/t0_thread_map.cpp`
Design: 13.10 rule 3
Depends: SCH-21
Check: `ctest --test-dir build --no-tests=error -R ^t0_thread_map$`. Ownership moves exactly once, and the registered test calls an audio-thread method from the boot thread and asserts the ownership assertion trips.

**DSP-7 · Attach eight DSPs** — T0
Files: `g2Lib/dspSet.h`, `g2Lib/test/t0_dsp_attach.cpp`
Design: 11.1
Depends: DSP-6
Check: `ctest --test-dir build --no-tests=error -R ^t0_dsp_attach$`. Eight `DSP` instances construct with a `Peripherals56311` each, attached as `DSP(memory, &periph, &periph.ySpace())` — the X-space face in `_pX` and the Y-space face in `_pY`, per design section 11.1. The test arms one DMA channel on each and asserts no assertion trips. ~~It also writes and reads back ESAI_1's `M_RX0_1` at `$FFFF88` and `M_TX2_1` at `$FFFF82` through the Y space, which a `PeripheralsNop` in that slot would silently swallow.~~ **THE STRUCK CLAUSE IS REPLACED 2026-08-18 BY OPERATOR DECISION AND IT IS QUOTED RATHER THAN OVERWRITTEN; §24.6 row W3-242 carries the measurement.** It also writes and reads back ESAI_1's `M_TSMA_1` at `$FFFF99` and `M_TSMB_1` at `$FFFF9A` through the Y space, reading each back **both** through the Y face and through the X face's second-ESAI accessor, which a `PeripheralsNop` in that slot would silently swallow. **THE CLAUSE `asserts no assertion trips` IS UNFALSIFIABLE IN THIS REPOSITORY'S DEFAULT BUILD, AND IT IS STRUCK 2026-08-25 — §24.6 row W3-404 — RATHER THAN LEFT TO CERTIFY NOTHING.** **THE DOCUMENT REFUTES THIS AGAINST ITSELF, WHICH IS WHY THE FINDING IS CONFIRMED RATHER THAN SUSPECTED: DSP-4, THREE BLOCKS EARLIER, REFUSES THE IDENTICAL WORDING IN ITS OWN TEXT** on the ground that **a Release build defines `NDEBUG`, which removes every `assert()`** — so the predicate names a mechanism the default build deletes. **§24.6 ROW W3-4 ALREADY NAMES THE CLASS AND LISTS SIX TASKS, AND DSP-7 IS NOT ON THAT ROSTER.** **THAT ABSENCE IS THE MORE INTERESTING HALF AND IT IS RECORDED AS SUCH: A ROSTER AMENDED ONCE PER CASE IS A MISSING PREDICATE.** W3-4 enumerated the instances it had found instead of stating the rule that generates them, **so every later block that reached for the same wording was admitted by default** — and a neighbouring clause of THIS VERY `Check:` had already been struck once as an inert discriminator (§24.6 row W3-242) **while this clause survived that same pass.** **WHAT REPLACES IT: the arming of one DMA channel on each of the eight is asserted by READING BACK the channel's own registers through the peripheral set, which is an observable the build cannot delete.** **NO CODE CHANGES BY THIS AMENDMENT** — `t0_dsp_attach` passes today and the machine is not in question; **what changes is that this line stops claiming an observation it does not make.**
**One further case, because the two spaces carry the same numbers.** The test writes `$FFFF88` in the **Y** space and asserts that **no `Timers` register moved**, then writes `$FFFF88` in the **X** space and asserts that the matching `Timers` register **did** move and that ESAI_1 did not. DSP-1's advisory gives the overlap: `Timers` spans X:`$FFFF82` to X:`$FFFF8F` and ESAI_1's Y face carries `$FFFF82` and `$FFFF88`. **Without the second half of the case the first half would pass against a handler that answers nothing at all.**

**THE READ-BACK CLAUSE STRUCK IN THE `Check:` LINE WAS INERT: IT RETURNED 0 WHETHER THE PERIPHERAL WORKED OR NOT, SO THE STATED DISCRIMINATOR DID NOT DISCRIMINATE. OPERATOR DECISION 2026-08-18; §24.6 row W3-242.** **MEASURED 2026-08-18, READ-ONLY IN THE WORKING `gearmulator` CLONE at commit `dd109e30`, under `source/dsp56300/source/dsp56kEmu/`, and the tool is NAMED beside each result because an unsearched tree and an empty one print the same thing.**

- **`M_RX0_1` at `$FFFF88`.** The Y-space write switch carries **no case** for it (`peripherals56311.cpp:72-91`), so the write falls through to the backing array at `:99`. The read switch **does** carry a case (`:44-47`) returning the receive-data read, and that read opens `if(!inputEnabled(_index)) return 0;` (`esai.cpp:265-266`) over a receive-control-register bit the ESAI reset **clears** (`esai.cpp:29`). **Write, then read, returns 0.**
- **`M_TX2_1` at `$FFFF82`.** The write **does** reach the transmit-data limb (`peripherals56311.cpp:82-87`), but the read switch carries **no transmit case at all**, so the read falls to the backing array the write never touched. **Returns 0.** There is no public transmit read accessor to reach instead — the slot array is private (`esai.h:460`) and `rg -n "readTX" source/dsp56300/source/dsp56kEmu/esai.h` returns nothing.
- **The comparison the clause claimed to make.** `PeripheralsNop::read` returns 0 for **every** address (`peripherals.h:142`). **So both halves returned 0 from the real handler and 0 from the null one, and no implementation of either could ever have failed the assertion.**

**WHAT REPLACES IT, AND IT IS A SHAPE THAT IS ALREADY GREEN RATHER THAN A NEW INVENTION.** `M_TSMA_1` at `$FFFF99` and `M_TSMB_1` at `$FFFF9A` are the transmit slot-mask registers: **plain stores with a real limb on BOTH sides of the Y window** — written at `peripherals56311.cpp:88-89` into `esai.cpp:399-407`, read at `peripherals56311.cpp:48-49` out of `esai.h:343-351` — so a written value comes back and a `PeripheralsNop` in that slot returns 0 for both. **DSP-1's own landed test drives exactly this round trip and passes**: `dsp56k_peripherals56311_surface.cpp:145-153` writes `M_TSMA_1` through the Y face and reads it back through the Y face **and** through the X face's second-ESAI accessor (`peripherals56311.h:77`). **They are also outside the `Timers` span, deliberately**, so this clause and the overlap case above cannot be satisfied by one another.

**THE TWO ASSERTIONS ANSWER DIFFERENT DEFECTS AND NEITHER SUBSTITUTES FOR THE OTHER, WHICH IS WHY THE PARAGRAPH ABOVE IS NOT WIDENED TO COVER THIS.** The round trip discriminates **a null peripheral in the Y slot**. The X-against-Y overlap case discriminates **one object answering both address spaces**. **DSP-1's `dsp56k_peripherals56311_surface.cpp:186-189` is the precedent for the second and it DECLINES the read-back the struck clause demanded** — it writes Y:`$FFFF88` and asserts only that the X-space `Timers` register did not move, which is the one assertion at that address that can fail.

**ONE CONSEQUENCE FOR THE `Note:` LINE IS RECORDED AND NOT REPAIRED, BECAUSE REPAIRING IT EDITS A `Depends:` JUSTIFICATION.** That line names `M_RX0_1` and `M_TX2_1` as writes this check makes, and it rests the ONE declared edge `DSP-3` — and, through it, DSP-4's dispatch branch, which is reached rather than declared — on them. **The DMA-ARMING clause beside them is untouched by this repair and it is what carries that justification.** After this repair `M_RX0_1` is still written — by the overlap case at `$FFFF88` — and **`M_TX2_1` is named by no clause of this check.** **The second half of that sentence is ALSO measured as overstated independently of this repair**: a Y-space write of `M_RX0_1` has no limb and reaches no `Dma` at all, so it never exercised the Y-space `Dma` wiring the sentence credits it with. **NO EDGE IS ADDED OR REMOVED HERE and no `Depends:` line is touched**; §1.3 rule 4 leaves a change of that size with the operator, and §24.6 row **W3-242** is the record.

**TWO SURFACES THIS BLOCK LEFT UNDEFINED ARE SPECIFIED HERE, BECAUSE AN IMPLEMENTER CANNOT PROCEED WITHOUT EITHER AND AMBIGUITY COSTS MORE THAN VOLUME.**

**SURFACE ONE — WHAT ELSE `DspSet` EXPOSES.** The paragraph below names only the three state members, and **four** consumers need per-slot reach: **this task's own check** arms a DMA channel and writes a Y-space register on each of eight sets; **DSP-8** ~~asserts both callbacks on every ESAI of every DSP~~ **installs the Rx/Tx callback pair on every ESAI of every DSP and asserts that a frame CROSSES from one slot to the next — struck and restated 2026-08-18 with that task's re-scope, and the surface it needs is UNCHANGED by the restatement**, because reaching an ESAI to install on it and reaching one to read from it are the same per-slot reference; **DSP-12** sets three `JitConfig` fields per DSP; **DSP-16** installs the host-port bridge against the port each slot owns. **So the surface is a count and two per-slot references, and it is stated rather than left to be re-derived four times:** the number of attached sets; a per-slot reference to the `DSP`; and a per-slot reference to the `Peripherals56311`, from which the Y-space face is already reachable through the accessor DSP-1 ships (`peripherals56311.h:81`). **Both references carry a `const` overload beside the mutable one.** **THE SPELLINGS ARE THE IMPLEMENTER'S AND THAT IS RECORDED AS THE DECISION**; what is fixed here is what must be REACHABLE, and **no other member is added by this task.**

**SURFACE TWO — WHAT "RESTORES IDENTICAL PER-DSP STATE" MEANS. IT IS NARROWED, AND THE NARROWING IS STATED RATHER THAN LEFT TO BE DISCOVERED AT THE WALL.** **MEASURED 2026-08-18: the DSP library carries NO state-serialisation API of any kind.** `rg -ln -i "savestate|loadstate|serializ" source/dsp56300/source/dsp56kEmu/` returns **zero files**, and `rg` is NAMED here because it reads untracked files where `git grep` does not. What exists is a non-`const` register-block accessor (`dsp.h:302-303`) and a memory-area pointer with its size (`memory.h:127-135` and `memory.h:116`). **So the clause means the register block copied as a struct, plus P, X and Y memory copied over those two accessors — AND IT DOES NOT INCLUDE THE PERIPHERALS.** The peripheral set, its two ESAIs, its `Dma`, its `Timers` and its host port carry **no save or load member at all**, by the same measurement. **Restoring them needs NEW API in the `dsp56300` fork, which is a DIFFERENT REPOSITORY and is on no `Files:` line of this task**, so it is not this task's work — and it is not silently dropped either: §24.6 row **W3-243** carries it, and **SCH-24's composition of the three snapshots is read against the NARROWED clause and not against the wider one.** **A round trip that claims to restore the peripherals and restores only registers and memory is exactly the silent-success shape §92 names as worse than no mechanism at all.**

**Each DSP free-runs.** Every `DSP` object has its own instruction counter and its own cycle counter, and nothing links two instances. Peripherals advance against the counter of the DSP that owns them. **The scheduler is what links them.**
**`DspSet` declares `stateSize`, `stateSave` and `stateLoad`, in the shape BRD-21's `Board` and CHN-14's `ChainAdapter` already use, and `stateLoad` returns `g2::Status`.** The registered test asserts the three exist and that a save-and-load round trip over eight attached sets restores identical per-DSP state. **Without them SCH-24's round trip has no DSP-set half at all**: `stateSize`, `stateSave` and `stateLoad` existed on the `Board` and on the `ChainAdapter` and on nothing for the DSP set, while SCH-24 runs "100 quanta, save, run 100 more, load, run the same 100 again" through a `Scheduler` that owns all three. SCH-19 constructs and owns the set and SCH-24 composes the three snapshots.
**THE THING THAT ACTUALLY BLOCKS THIS TASK IS `g2::Status`, NOT BRD-0, AND IT IS UNDECLARED. RECORDED 2026-08-18; §24.6 row W3-236 holds it and NO `Depends:` EDGE IS ADDED HERE.** The paragraph above puts `g2::Status` on this task's state-load declaration. **SCH-18 owns that type** — its `Files:` line names `g2Lib/status.h` — **and SCH-18 does not appear on this task's `Depends:` line, which reads `DSP-6, DSP-3, BRD-0`.** ~~**The file does not exist**: `find source/nord -name 'status*'` in the working clone returns nothing at all, and the tool is NAMED beside the absence because an unsearched tree and an empty one print the same result.~~ **THE STRUCK PREMISE IS FALSE FROM 2026-08-18 AND IT IS QUOTED RATHER THAN OVERWRITTEN, BECAUSE IT WAS TRUE ON THE DAY IT WAS MEASURED.** **SCH-32 LANDED**: `find source/nord -name 'status*'` in the working clone now returns `source/nord/g2/g2Lib/status.h`, at `gearmulator` commit `dd109e30`, together with `g2Lib/test/t0_status_contract.cpp` and its registration in `tests_sched.cmake`. **THE OWNER IS SCH-32 AND NOT SCH-18, AND NOTHING ELSE IN THIS PARAGRAPH CHANGES: NO `Depends:` EDGE IS ADDED BY THIS PASS EITHER, and the §7.3, §7.4 and §7.6 assertion 7 bookkeeping the last sentence names is still owed.** §24.6 row **W3-236** carries the same correction. **THIS IS THE THIRD TASK TO MEET THE COLLISION, AND THE FIRST TWO WROTE IT INTO THE SOURCE RATHER THAN INTO THIS DOCUMENT**, which is why no lint and no reader ever met it here: `board.h:160-174` records it for BRD-21's `Board`, `chainAdapter.h:233-242` records it for CHN-5's `ChainAdapter`, and **both declare the same method returning `void` on the stated ground that defining `g2::Status` would be implementing SCH-18's owned file.** **THE METHOD NAME IS DELIBERATELY NOT WRITTEN IN BACKTICKS IN THIS PARAGRAPH**, because §15.2's own precedent three blocks up records the closure lint reading a task that DESCRIBES a declaration as a task that CONSUMES it, and the name is already backticked once in the paragraph above where it belongs. **THE BRD-0 HALF IS BOOKKEEPING BY COMPARISON** — BRD-0 landed 2026-08-05 at `859f6327`, now carries its own marker, and what this task takes from it is one appended line in `tests_dsp.cmake`, which exists and holds no line that is not blank and not a comment. **WHICH REPAIR TO TAKE IS NOT DECIDED HERE**, because either one moves §7.3's `dsp` row, §7.4's symbol-availability table and §7.6 assertion 7's cross-track edge count, and §1.3 rule 4 leaves a scope decision of that size with the operator.
