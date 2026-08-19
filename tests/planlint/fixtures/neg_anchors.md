# A plan whose anchored figures have gone stale

The `Depends:` graph below holds exactly two edges that cross a track inside one
wave: BBB-1 → AAA-2 and CCC-1 → BBB-1. Every anchored restatement here disagrees
with that derivation, each in a different way.

### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-1 |
| 2 | 2 | AAA-2, BBB-1, CCC-1 |

### 7.6 The dependency and wave check

**<!-- derived: cross-track-edge-count -->Fifteen cross-track edges sit inside
one wave**, and the recut leaves each one where it was.

The count is not restated as a word everywhere. Where the sentence reads
<!-- derived: cross-track-edge-count -->several edges, no figure is stated at
all and the anchor marks a word this tool does not read.

The third one names a figure the tool does not compute: it says
<!-- derived: cross-track-edge-kount -->two, under a key with no derivation
behind it.

## 9. The tasks

**AAA-1 · The build and the surface** — T0
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`.

**AAA-2 · The synthesized corpus** — T0
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`.

**BBB-1 · The gated read** — T0
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`.

**CCC-1 · The late gate** — T0
Depends: BBB-1
Check: `ctest --test-dir build --no-tests=error -R t0_delta`.
