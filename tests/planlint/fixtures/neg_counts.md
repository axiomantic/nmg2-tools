# Negative fixture — the plan miscounts itself

The track row says Alpha has 3 tasks and the document holds 2. The total row
says 9 and the document holds 4. The track rows sum to 5, not to 9.

The conditional sentence says four and the table holds one row.

The cross-track sentence says there are three; the section 7.3 table holds one
edge whose two ends share a wave.

## 7. The tracks

### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-1 |
| 2 | 2 | AAA-2, BBB-1, CCC-1 |

### 7.3 Track dependencies

| Track | Depends on | Cross-track task edges |
|---|---|---|
| alpha | nothing | AAA-2 → AAA-1 |
| beta | alpha | BBB-1 → CCC-1 |

### 7.6 The dependency and wave check

| # | Assertion |
|---|---|
| 7 | Every edge that crosses a track inside one wave appears in section 7.3's column. **There are three.** |

## 9. The tasks

**AAA-1 · The first** — T0
Files: `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`.

**AAA-2 · The second** — T0
Files: `test/t0_beta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`.

**BBB-1 · The third** — T0
Files: `test/t0_gamma.cpp`
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`.

**CCC-1 · The fourth** — T0
Files: `test/t0_delta.cpp`
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_delta`.

## 24. Task index

### 24.1 Counts

| Track | Tasks |
|---|---|
| Alpha (AAA) | 3 |
| Beta (BBB) | 1 |
| Gamma (CCC) | 1 |
| **Total task blocks** | **9** |

### 24.4 The conditional tasks

| Task | Condition |
|---|---|
| CCC-1 | Exists only if the probe reports a result. |

**Of the four conditional tasks, exactly one is depended on at all.**
