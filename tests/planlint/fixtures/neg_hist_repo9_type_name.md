# Historical defect 2 — a check that reads a type another task creates

The pre-repair form of the SECOND of the three defects that blind-spot class 11
of the README records.

**The defect.** REPO-9's gate reads `Scheduler::Config` and
`Config::testOverride`. Both are SCH-18, which is Wave 3a. REPO-9 was Wave 2b,
and its closure held neither, so `t1_timebase_gate.cpp` did not compile and the
wave could not close.

**Why no other lint sees it.** A type that does not exist yet is a CODE
artifact. The `implicit` lint reads data suffixes and directories only. Both
graphs are acyclic. The `registrar` lint asserts that the test SOURCE and the
CMake registration are reachable, and both of those are reachable here — it is
the TYPE the source names that is not.

## 9. The tasks

**SCH-0 · The scheduler design note** — T0
Files: `docs/scheduler.md`
Design: 1
Depends: none
Check: The note states the frame budget.

**REPO-12 · The fork** — T0
Files: `README.md`
Design: 2
Depends: none
Check: The operator confirms the fork exists.

**BRD-0 · The `source/nord/g2/` skeleton** — T0
Files: `source/nord/g2/g2Lib/CMakeLists.txt`, `source/nord/g2/g2Lib/test/CMakeLists.txt`
Design: 3
Depends: REPO-12
Check: `cmake -S . -B build` configures from a clean clone of the fork.

**REPO-8 · The golden manifest** — T1
Files: `g2Lib/test/t1_manifest.cpp`
Design: 4
Depends: BRD-0
Check: `ctest --test-dir build --no-tests=error -R ^t1_manifest$`. Registered with `add_test(NAME t1_manifest ...)`.

**SCH-17 · The `Scheduler` surface** — T0
Files: `g2Lib/scheduler.h`, `g2Lib/test/t0_backend_rule.cpp`
Design: 5
Depends: SCH-0
Check: `ctest --test-dir build --no-tests=error -R ^t0_backend_rule$`. Registered with `add_test(NAME t0_backend_rule ...)`.

**SCH-18 · `g2::Status` and the eight rejections** — T0
Files: `g2Lib/status.h`, `g2Lib/scheduler.cpp`, `g2Lib/test/t0_construction_rejection.cpp`
Design: 6
Depends: SCH-17
Check: `ctest --test-dir build --no-tests=error -R ^t0_construction_rejection$`. Registered with `add_test(NAME t0_construction_rejection ...)`. `Scheduler::create` is the single rejection point, because every rejectable value arrives through `Scheduler::Config`.

**REPO-9 · The timebase gate** — T1
Files: `g2Lib/test/t1_timebase_gate.cpp`
Design: 7
Depends: REPO-8, SCH-0, BRD-0
Check: `ctest --test-dir build --no-tests=error -R ^t1_timebase_gate$`. Registered with `add_test(NAME t1_timebase_gate ...)`. The gate reads `Scheduler::Config` and `Config::testOverride`, and compares each recorded value against the value the run path will use.
