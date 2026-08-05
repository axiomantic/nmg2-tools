# Historical defect 1 — a link on a target another task exports

The pre-repair form of the FIRST of the three defects that blind-spot class 11
of the README records. It is reproduced here so that the ninth lint has evidence
it would have caught the defect, and not only evidence that the repaired plan is
clean.

**The defect.** BRD-0 is Wave 2 and its transitive dependency closure is
`{BRD-0, REPO-3, REPO-12}`. Its own text says `g2Lib` links `mcf5307::mcf5307`.
CPU-1 exports that target, and CPU-1 is Wave 3a. The link cannot resolve on the
day BRD-0 is declared complete.

**Why no other lint sees it.** Both graphs are acyclic, so the graph lint and
the wave lint report nothing. The `implicit` lint reads data suffixes and
directories only, so a CMake target is outside it. The `registrar` lint reads
`-R` arguments, and this defect carries none.

## 9. The tasks

**REPO-12 · The fork** — T0
Files: `README.md`
Design: 1
Depends: none
Check: The operator confirms the fork exists.

**REPO-3 · The build matrix** — T0
Files: `.github/workflows/build.yml`
Design: 2
Depends: REPO-12
Check: The workflow runs on three platforms.

**CPU-0 · The Nim toolchain pin** — T0
Files: `.nim-version`
Design: 3
Depends: none
Check: The pinned version is read at configure time.

**CPU-26 · The `mcf5307` CMake project** — T0
Files: `mcf5307/CMakeLists.txt`
Design: 4
Depends: CPU-0
Check: The project configures on three platforms.

**CPU-1 · CMake drives Nim** — T0
Files: `cmake/Nim.cmake`, `src/mcf5307.nim`
Design: 5
Depends: CPU-0, CPU-26
Check: It adds an `OBJECT` library `mcf5307_nim_objs`, adds a `STATIC` library `mcf5307`, and exports `mcf5307::mcf5307`.

**BRD-0 · The `source/nord/g2/` skeleton** — T0
Files: `source/nord/g2/g2Lib/CMakeLists.txt`
Design: 6
Depends: REPO-3
Check: `cmake -S . -B build --no-tests=error` configures from a clean clone of the fork.
`g2Lib` links `hardwareLib`, `dsp56kEmu`, `synthLib` and `mcf5307::mcf5307` unconditionally.
