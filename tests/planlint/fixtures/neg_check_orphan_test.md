# Negative fixture — the reverse direction

`t1_egress.cpp` is created by a `Files:` line and named by no `Check:` line at
all. A registered test that nothing runs is the same defect as an `-R` that
matches nothing, seen from the other side, and a forward-only lint is blind to it.

`tests/test_orphan.py` is the same defect in the Python half: created, never
driven by a `pytest` invocation.

The `-R t1_` prefix sweep does NOT count as an invocation of `t1_egress`. The
allow-list exempts the argument from the forward direction only.

## 9. The tasks

**AAA-1 · The egress assertion** — T1
Files: `test/t1_egress.cpp`, `test/t1_chain_health.cpp`, `tests/test_orphan.py`, `tests/test_driven.py`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t1_chain_health` and `pytest tests/test_driven.py`. Registered with `add_test(NAME t1_chain_health ...)` and `add_test(NAME t1_egress ...)`.

**AAA-2 · The standing sweep** — T1
Files: `.github/workflows/t1.yml`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t1_ --output-on-failure`.
