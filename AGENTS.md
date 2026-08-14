# nmg2-tools — agent instructions

Python tools for the Nord Modular G2 emulator project. This repository holds
analysis and build tools. It holds no emulator code and it uses no CMake.

Repository: `axiomantic/nmg2-tools`. Licence: MIT.

## Test

```bash
pytest                      # the whole suite
pytest tests/test_pch2.py   # one file
```

Requirements: Python 3.11 or later, pytest 7.0 or later.

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["."]`, so
pytest finds the tests and the tests import the package from the repository
root.

## Layout

The layout is fixed. Do not use a different one.

| Path | Content |
|---|---|
| `nmg2_tools/` | The tool package. All tool code lives here. |
| `planlint/` | The implementation-plan linter. Its own package with its own README. |
| `tests/` | All tests. They live in the repository root, not inside a package. |

The firmware extractor here is the test oracle for the C++ extractor in the
emulator. The two must produce identical bytes.

## Test data

This repository holds no data that Clavia wrote, and it never will.

The required tests read synthetic test data only. A contributor can run them
from a fork with no configuration. Some other tests read a private artifact
tree; `NMG2_ARTIFACTS` gives its path. When the variable is unset those tests
**skip with a stated reason**. They never fail for that reason.

A test that needs an external binary must skip or fail with a NAMED diagnostic
when the binary is absent. A bare `except Exception` around a subprocess makes
"the tool is missing" indistinguishable from "the tool found nothing", which is
this project's signature failure mode.

## The clean-room rule

This repository is MIT and is clean-room with respect to GPL and LGPL code. Do
not copy, port, translate or transliterate code from a GPL or LGPL source.
This covers the known GPL editors and tools in this problem space, among them
`msg/g2ools`, `BVerhue/nord_g2_editor` and `redpola/nomad2026`.

Facts stay usable. Protocol message formats, field offsets, bit layouts and
module type identifiers are facts, not expression, so a GPL tool is a
legitimate place to *check* a fact. Only copied expression is a problem.

## Comments and docstrings

Comments are sparse. Write one only where a reader must otherwise reconstruct a
DECISION. The code says what it does. The comment says why you chose it instead
of the alternative.

Never write these in a comment or a docstring:

- **A count** — rules, mutations, tests, cases, files, or lines. The next change
  makes it wrong, and nothing catches it.
- **A present-tense claim about what the tests cover**, or about what a wrong
  implementation would fail. If coverage matters, assert it in a test. A failing
  test is the only durable statement about coverage.
- **A note about history** ("this used to...", "an earlier version..."). Git
  holds that.

**One exception, and it is the only one.** A number that a mechanism reads and
checks at test time may stay. The check is then the source of truth, not the
comment, and it fails loudly when the number drifts. A number that no mechanism
reads is a liability.

**A date does not rescue a stale claim.** Within a day of churn a date
discriminates nothing.

This repository has already paid for the rule. A hand-maintained rule count in
`planlint/README.md` disagreed with the count asserted in the tests, and a
comment claiming a member count that "a grep for two property names finds"
was an unverifiable hand-count in the very file written to end hand-counts.
Where a count is genuinely needed, **compute it** — read it out of the source
with `ast`, or out of the tool itself — and assert the computed value.

### Scope: code we authored

This repository is original work, so the rule applies throughout. Do not delete
or rewrite comments as a sweep; repair a comment when you change the line it
describes.

## Gotchas

- `git grep` skips untracked files. Use `grep -r`, `rg`, or `git grep
  --untracked` before claiming something appears nowhere, and name the tool
  beside the claim.
- Measure against a fresh clone at a named commit when a claim is about what the
  committed tool does. An earlier pass on this project measured the wrong
  repository and reported a plausible result.
- A capability that is not committed is a capability no other clone or runner
  can use. The presence of a rule NAME in the tool is not evidence of the
  capability behind it.
