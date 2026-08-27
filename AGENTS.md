# nmg2-tools — agent instructions

Python tools for the Nord Modular G2 emulator project. This repository holds
analysis and build tools. It holds no emulator code and it uses no CMake.

Repository: `axiomantic/nmg2-tools`. Licence: MIT.

## Build and test

There is nothing to build. This repository uses no CMake and needs no install
step to test: `pyproject.toml` sets `testpaths = ["tests"]` and
`pythonpath = ["."]`, so pytest finds the tests and the tests import the package
from the repository root.

**The sibling repositories carry `CMakePresets.json` or `CMakeUserPresets.json`
so that the narrow check is shorter to type than the wide one. This one carries
no equivalent, deliberately.** There is no CMake here to hold a preset, and the
thing a preset would buy does not exist: the full run below is already the
shortest invocation in this file, and it costs seconds rather than the CPU-hours
that make a narrow path worth a mechanism in `gearmulator`. Adding a marker set
or a wrapper script to mirror the other repositories would be ceremony with
nothing behind it.

### Narrow

```bash
.venv/bin/python -m pytest tests/test_pch2.py    # one file
.venv/bin/python -m pytest tests/planlint        # the plan linter alone
.venv/bin/python -m pytest -k <expression>       # by name
```

**Narrowing here is by PATH or by `-k`, never by marker.** `pyproject.toml`
registers no markers and the suite defines none, so `pytest -m ...` selects
nothing. Do not write a `-m` invocation into a check line.

### Full

```bash
.venv/bin/python -m pytest
```

`.github/workflows` also runs the suite under `python -X dev -W error`, which
turns a warning into a failure. A change that touches deprecation surface —
`datetime`, `importlib`, `re` — passes the plain run and fails that one.

**The narrow run cannot see the consumer.** The firmware extractor here is the
test ORACLE for the C++ extractor in the `gearmulator` fork, and the two must
produce identical bytes. A change under `nmg2_tools/` that the oracle path
reaches — `container`, `lzo1x`, and what they call — is only checked by
`t0_extract_matches_python` in that repository, which nothing here runs.

### Environment

- **Use the interpreter in `.venv`.** The system `python3` on this host has no
  pytest installed, so a bare `pytest` works only from an activated environment.
  Requirements: Python 3.11 or later, pytest 7.0 or later.
- `NMG2_ARTIFACTS`, `NMG2_DESCRIPTORS` and `NMG2_INSTALLERS` name the private
  artifact trees, one variable per FAMILY of fixtures: the firmware images and
  patch corpus, the descriptor and panel tables, and the vendor installer
  images. They are separate because no one directory holds all three. Unset is
  the normal case: the tests that need a family skip with a stated reason and
  never fail for that reason. Set one only to exercise that family's gated half.
- A gated test declares its family by requesting that family's fixture
  (`artifacts_dir`, `descriptors_dir`, `installers_dir`) and declares the files
  its body opens with `@pytest.mark.artifacts(...)`, relative to that family's
  root. A family NEVER falls back to another family's root: a resolver that
  searched a second root on a miss would make a fixture's provenance
  unknowable.

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
tree; `NMG2_ARTIFACTS`, `NMG2_DESCRIPTORS` and `NMG2_INSTALLERS` give the paths,
one per family. When a family's variable is unset those tests **skip with a
stated reason**. They never fail for that reason.

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
- **An enumeration whose length is the claim.** A stale enumeration is a stale
  count with the number spelled out. Delete the word "four" from "any of those
  four values" and the list above it still says four. It goes wrong by the
  mechanism the word did.
- **A path that does not resolve.** A comment, a docstring, or a document that
  names a file, a script, a test, or a type must name one that exists.
- **A claim about the rest of the tree.** A comment or a docstring describes the
  code beside it. Do not write what else imports this module, what its only
  caller is, which task consumes it next, or what another file does not name.
  The import graph answers those and stays right; a sentence about them is
  derivable, goes stale the moment another task moves, and records no decision.

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

**`planlint/README.md` is also the live example of the path rule, and its wrong
paths are a separate defect from its wrong numbers.** It names the invocations
`./plan_lint.py`, `./payload_lint.py` and `./assert_section_7_6.py`, and not one
resolves as written: the loose wrappers were never migrated, and `payload_lint.py`
survives only as the package module the README's own third column names. Every
`tests/` path it cites has moved one directory down into `tests/planlint/`, so
each names a real file at a wrong location. Measured 2026-08-14 with `find` and a
file test, not with `git grep`.

**The path rule is the one a machine can decide, and that is why it is stated
apart from the others.** Each other rule here needs a reader's judgement about
what a sentence claims. "Every path-shaped token resolves" is a regular
expression and a file test. Write the check. Do not trust a sweep to hold.

**A path that MOVED is corrected. A path that never existed is deleted.** A moved
path has a correct target, so give it one. A named script that exists nowhere has
no target, so the sentence goes — unless the sentence records a known GAP, and
then the gap moves to a tracked item BEFORE the comment goes.

**A cross-reference that helps a reader NAVIGATE still stands.** "The section
offsets are also read in `nmg2_tools/pch2.py`" earns its place and stays,
provided it asserts no exclusivity and no sequence. What goes is ONLY, FIRST,
NEXT, and "does not name": those are the falsifiable forms, and that difference
is the whole of the rule.

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
