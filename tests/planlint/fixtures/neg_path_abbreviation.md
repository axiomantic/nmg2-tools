# Negative fixture — the abbreviations of section 1.1.1 rules B and C

This fixture carries defects that are INVISIBLE to a lint comparing the strings
as written, and visible the moment rules B and C are expanded.

AAA-1 owns the registrar `source/nord/g2/g2Lib/test/CMakeLists.txt`, spelled in
full. BBB-1 writes `g2Lib/test/t0_short.cpp`, spelled with the abbreviation, and
declares no path to AAA-1. **The two spellings name one directory**, so BBB-1's
check cannot pass — and a lint that compares the written strings sees two
unrelated directories and reports nothing.

CCC-1 and CCC-2 collide on one file that each spells differently: CCC-1 writes
`g2Lib/shared.cpp` and CCC-2 writes `source/nord/g2/g2Lib/shared.cpp`. Section
7.4.2 names no owner, and the collision is only visible after expansion.

DDD-1 uses the rule C ellipsis. `.../ellipsed.cpp` repeats the DIRECTORY of the
item before it, so it is `source/nord/g2/g2Lib/ellipsed.cpp` and it collides
with DDD-2, which spells the same file in full.

## 7.4.2 Every shared file has one owner

| Path | Owner | Repository | The mechanism for everybody else |
|---|---|---|---|
| `g2JucePlugin/` | **plugin track** | `gearmulator` fork | A DIRECTORY row owns every path beneath it. |

## 9. The tasks

**AAA-1 · The registrar** — T0
Files: `source/nord/g2/g2Lib/test/CMakeLists.txt`, `source/nord/g2/g2Lib/test/t0_root.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_root$`.

**BBB-1 · The abbreviated writer** — T0
Files: `g2Lib/test/t0_short.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R ^t0_short$`.

**CCC-1 · The abbreviated claim** — T0
Files: `g2Lib/shared.cpp`, `g2Lib/test/t0_ccc_one.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_ccc_one$`.

**CCC-2 · The full-spelling claim** — T0
Files: `source/nord/g2/g2Lib/shared.cpp`, `source/nord/g2/g2Lib/test/t0_ccc_two.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_ccc_two$`.

**DDD-1 · The ellipsis claim** — T0
Files: `g2Lib/ellipsis_anchor.h`, `.../ellipsed.cpp`, `g2Lib/test/t0_ddd_one.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_ddd_one$`.

**DDD-2 · The full-spelling ellipsis collision** — T0
Files: `source/nord/g2/g2Lib/ellipsed.cpp`, `source/nord/g2/g2Lib/test/t0_ddd_two.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_ddd_two$`.

**EEE-1 · The directory row covers this** — T0
Files: `g2JucePlugin/covered.cpp`, `g2Lib/test/t0_eee_one.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_eee_one$`.

**EEE-2 · The other claimant under the directory row** — T0
Files: `source/nord/g2/g2JucePlugin/covered.cpp`, `g2Lib/test/t0_eee_two.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R ^t0_eee_two$`.
