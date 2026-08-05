# Historical defect 3 — a symbol behind a build option nobody turned on

The pre-repair form of the THIRD of the three defects that blind-spot class 11
of the README records. **The repair of defect 1 manufactured this one**, which
is why it is here: a lint that catches the first two and not the third would
have let the repair pass.

**The defect.** The repair put the `mcf5307::mcf5307` link behind
`option(G2_LINK_MCF5307 ... OFF)` in BRD-0, and gave BRD-23 the job of turning
it ON. BRD-21's `board.cpp` calls `mcf5307_exec`, so from BRD-21 onward every
link of `g2Lib` needs the option ON — and BRD-21 did not depend on BRD-23.

**Why the producer rule alone does not see it.** CPU-1 produces `mcf5307_exec`
and CPU-1 IS inside BRD-21's closure, through BRD-20. The task that is missing
is the one that turns the option ON, not the one that compiles the symbol.

## 9. The tasks

**CPU-0 · The Nim toolchain pin** — T0
Files: `.nim-version`
Design: 1
Depends: none
Check: The pinned version is read at configure time.

**CPU-1 · CMake drives Nim** — T0
Files: `cmake/Nim.cmake`, `src/mcf5307.nim`
Design: 2
Depends: CPU-0
Check: It adds a `STATIC` library `mcf5307`, and exports `mcf5307::mcf5307`.

**BRD-0 · The `source/nord/g2/` skeleton** — T0
Files: `source/nord/g2/g2Lib/CMakeLists.txt`
Design: 3
Depends: none
Check: `cmake -S . -B build` configures from a clean clone of the fork.
Edit 4 writes `source/nord/g2/g2Lib/CMakeLists.txt` and carries `option(G2_LINK_MCF5307 "Link the MCF5307 core" OFF)` with the `mcf5307::mcf5307` link behind it.

**BRD-20 · The transport hub** — T0
Files: `g2Lib/transport.cpp`
Design: 4
Depends: BRD-0, CPU-1
Check: The hub routes every chip select.

**BRD-21 · The `Board` class** — T0
Files: `g2Lib/board.h`, `.../board.cpp`, `g2Lib/test/t0_board_surface.cpp`
Design: 5
Depends: BRD-20
Check: `ctest --test-dir build --no-tests=error -R ^t0_board_surface$`. Registered with `add_test(NAME t0_board_surface ...)`. `runMcu` forwards to `mcf5307_exec` directly, because `mcf5307_exec` already takes a cycle budget.

**BRD-23 · Wire `mcf5307::mcf5307` into `g2Lib`** — T0
Files: `source/nord/g2/g2Lib/CMakeLists.txt`, `source/nord/g2/g2Lib/test/t0_mcf5307_link.cpp`
Design: 6
Depends: BRD-0, CPU-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_mcf5307_link$`. Registered with `add_test(NAME t0_mcf5307_link ...)`.
This task turns `G2_LINK_MCF5307` ON by default, in the one line of `g2Lib/CMakeLists.txt` that declares it.
