# Positive fixture — the two shapes a line-scoped lint gets wrong

This fixture must report NOTHING. It exists to prove the lint does not produce
the two false positives the plan names.

AAA-1 states its check across several lines and inside a table. A lint that read
the `Check:` LINE alone would report `t0_one` and `t1_two` as created and never
invoked.

AAA-2 prints a defective command on purpose, as a shell transcript, inside its
own `Check:` block. A lint that scanned the block without excluding transcripts
would fail on the counter-example the plan prints to teach the rule.

The prose after the next heading quotes a command that belongs to nobody. A lint
whose block had no heading boundary would pick it up.

## 9. The tasks

**AAA-1 · The split check** — T0
Files: `test/t0_one.cpp`, `test/t1_two.cpp`
Depends: none
Check: **The check is split by platform, and each half is registered.**

| Platform | What runs |
|---|---|
| Linux x86-64 | `ctest --test-dir build --no-tests=error -R t0_one` |
| macOS arm64 | `ctest --test-dir build --no-tests=error -R t1_two` |

Both are registered: `add_test(NAME t0_one ...)` and `add_test(NAME t1_two ...)`.

**AAA-2 · The counter-example carrier** — T0
Files: `test/t0_three.cpp`
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_three`, registered with `add_test(NAME t0_three ...)`.
The forwarding form is rejected, and this was measured rather than assumed:

```
$ ctest --test-dir build -R real_test -- --group move
CMake Error: Unknown argument: --
EXIT=1
```

An unflagged invocation on a name that matches nothing was measured too:

```
$ ctest --test-dir build -R t0_does_not_exist
No tests were found!!!
EXIT=0
```

## 10. Prose that quotes a command

Section 6.1 quotes `ctest --test-dir build -R t0_belongs_to_nobody` when it
describes what a defective check looks like. This is running prose and it is not
an instruction.
