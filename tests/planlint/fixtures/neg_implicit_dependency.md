# Negative fixture — the dependency nobody declared

BBB-1 writes into `corpus/data/`, which AAA-1 creates. No `Depends:` line states
the edge, so Tarjan cannot see it and the wave check cannot see it either.

DDD-1 writes into `axiomantic/store`, which CCC-1 creates, and CCC-1 declares
DDD-1 on its own `Depends:` line. The edge that is missing would close a cycle.
This is the shape that survived three rounds of careful reading.

EEE-1 reads the same directory and declares the edge. It must not be reported.

## 3. The repositories

### 3.1 Layout B

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/store` | **PRIVATE** | The recorded material. |

## 9. The tasks

**AAA-1 · The corpus writer** — T0
Files: `corpus/data/`, `corpus/data/MANIFEST.txt`
Depends: none
Check: `pytest tests/test_corpus.py`. The manifest records a count on its first line.

**BBB-1 · The undeclared consumer** — T0
Files: `src/reader.py`
Depends: none
Check: `pytest tests/test_reader.py` reads every file of `corpus/data/` and asserts the count against `corpus/data/MANIFEST.txt`.

**CCC-1 · `axiomantic/store`** — OPERATOR
Files: `README.md`
Depends: DDD-1
Check: The repository exists under `axiomantic` and is PRIVATE.

**DDD-1 · The extractor** — OPERATOR
Files: `src/extract.py`
Depends: none
Check: The extractor writes each file into `corpus/pch2/` in `axiomantic/store` unchanged.

**EEE-1 · The declared consumer** — T0
Files: `src/second_reader.py`
Depends: AAA-1
Check: `pytest tests/test_second_reader.py` reads `corpus/data/MANIFEST.txt`.
