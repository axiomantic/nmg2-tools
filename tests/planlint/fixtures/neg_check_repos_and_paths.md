# Negative fixture — an unlisted repository and an unowned shared path

AAA-2 names `axiomantic/ghost` as a push target. Section 3.1's table does not
carry it, which is the shape of design defect D3.

AAA-1 and AAA-2 both claim `g2Lib/CMakeLists.txt` on their `Files:` lines, and
the section 7.4.2 owner table names an owner for a different path only.

## 3. The repositories

### 3.1 Layout B

| Repository | Visibility | Content |
|---|---|---|
| `axiomantic/core` | PUBLIC | The emulation code. |

## 7. The tracks

### 7.4.2 Every shared file has one owner

| Path | Owner | The mechanism for everybody else |
|---|---|---|
| `g2Lib/test/CMakeLists.txt` | **AAA-1** | The per-track test lists. |

## 9. The tasks

**AAA-1 · The owner** — T0
Files: `g2Lib/CMakeLists.txt`, `g2Lib/test/CMakeLists.txt`, `test/t0_alpha.cpp`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`. Registered with `add_test(NAME t0_alpha ...)`.

**AAA-2 · The second writer** — T0
Files: `g2Lib/CMakeLists.txt`, `g2Lib/test/CMakeLists.txt`, `test/t0_beta.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)`. The branch pushes to `axiomantic/ghost`.
