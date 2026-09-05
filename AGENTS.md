# nmg2-tools — agent instructions

Python tools for the Nord Modular G2 emulator project. This repository holds
analysis and build tools. It holds no emulator code and it uses no CMake.

Repository: `axiomantic/nmg2-tools`. Licence: MIT.

This repository is part of the Nord Modular G2 emulator project. The work and
the execution ceremony live in the project roadmap, in the `nmg2-artifacts`
repository. Read it before you start a task. This file states the rules that
apply while you write code here.

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
.venv/bin/python -m pytest -k <expression>       # by name
```

**Narrow by PATH or by `-k`.** `pyproject.toml` registers exactly one marker,
`artifacts(*paths)`, and `pytest -m artifacts` selects the tests that declare a
firmware file. That marker is a DECLARATION consumed by the `<family>_dir`
fixtures in `tests/conftest.py`, not a selector meant for a check line: the set
it names is "tests that open an artifact", which is not the set any narrow run
wants. Use a path or `-k`.

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

## Tests

**Always pass `--no-tests=error` to ctest.** Without it, ctest exits 0 when the
filter matches no test. A pass and an empty run then look the same. This project
has a repository where that exact false green is live today.

Write the failing test first. Confirm that it fails for the intended reason.

A test must consume real values. A test that checks only exit status,
non-emptiness, or truthiness proves nothing. Before you call a test done, plant
a fault and confirm that the test goes red.

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

Never write these in a comment, a docstring, or a test name:

- **A plan-task identifier or a design-section or plan-section pointer.**
  `TOOL-18`, `REPO-7`, `W3-114`, "design section 15.7", "plan section 5.2",
  "logbook section 3.1", "trap 7.10". This is the most-violated rule in this
  repository. A comment states the FACT or the DECISION; the pointer to where
  the fact was first written down is a foreign ledger that this tree cannot
  keep right. **There is no exception for the project's own specification.**
  "These sections are this project's own design, so the pointer is a citation"
  is the argument this rule exists to refuse. Write what the specification
  says, not where it says it.
- **A count** — rules, mutations, tests, cases, files, or lines. The next change
  makes it wrong, and nothing catches it.
- **A present-tense claim about what the tests cover**, or about what a wrong
  implementation would fail. If coverage matters, assert it in a test. A failing
  test is the only durable statement about coverage.
- **A note about history** ("this used to...", "an earlier version..."). Git
  holds that.
- **A list of unfinished work.**
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

**What the rules above do NOT reach.** A datasheet or hardware-manual citation
(Motorola, Freescale, Clavia, ISP1181) names an external, immutable document and
stays. So does a hazard banner, and so does a comment inherited from upstream or
vendored code. A design-section pointer is not a datasheet citation, and reading
it as one is the mistake that let the pointers accumulate.

**One exception, and it is the only one.** A number that a mechanism reads and
checks at test time may stay. The check is then the source of truth, not the
comment, and it fails loudly when the number drifts. A number that no mechanism
reads is a liability.

**A date does not rescue a stale claim.** Within a day of churn a date
discriminates nothing.

This repository has already paid for the rule. A comment claiming a member
count that "a grep for two property names finds" was an unverifiable hand-count
in the very file written to end hand-counts. Where a count is genuinely needed,
**compute it** — read it out of the source with `ast`, or out of the tool
itself — and assert the computed value.

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

This repository is original work, so the rule applies throughout. A sweep is a
legitimate way to apply it: `scripts/check-comment-rubric.sh` measures the tree,
every hit is read in context before anything is cut, and a sweep that touches
only comments and docstrings must prove it changed no behaviour — parse each
modified `.py` file before and after, strip docstrings, and compare `ast.dump`.
Repairing a comment when you change the line it describes is the other way in,
not the only one.

## Verify the artifact, not the signal

A step that can do nothing reports success in the same way as a step that
worked. When a step writes a file, regenerates code, or targets a path you did
not name, look at what it produced. Do not read the exit code and stop.

Count with a command. Never estimate a number, and never recall one.

State what you ran next to the result. A rule stated more broadly than what you
tested is false in a way the test will not show you.

## Git

Never push to a default branch without permission. Never force push without
stating what it discards first.

Never run a tree-wide git operation in a checkout you share with anyone:
`git stash`, `git checkout .`, `git restore .`, `git clean -fd`,
`git reset --hard`. To compare against a commit, read it with `git show`.

Never put an issue number in a commit message, a pull request title, or a pull
request body. It notifies every subscriber.

Work in a clone you created yourself. Never delete a path you did not create.

## Gotchas

- `git grep` skips untracked files. Use `grep -r`, `rg`, or `git grep
  --untracked` before claiming something appears nowhere, and name the tool
  beside the claim.
- Quote every argument that contains a glob character. An unquoted `?` or `*` is
  eaten by the shell, the command never runs, and the empty output reads exactly
  like a measured absence.
- A path that is missing from a default branch is not missing from the
  repository. Two repositories here hold their product work on stacked branches.
  Check the branch before you report a file as absent.
- Measure against a fresh clone at a named commit when a claim is about what the
  committed tool does. An earlier pass on this project measured the wrong
  repository and reported a plausible result.
- **"ruff clean" in a commit message means nothing without a version.** Two
  commits (`fbbff97`, `8adb54d`) assert it, and when they were written nothing
  read the claim. The same unmodified tree reports 1 finding under ruff 0.6.9
  and 0.12.0 and 275 under 0.16.5, because 0.16 turned on a far wider default
  rule set: the claim was close to true against the tool of its day and is
  false against today's. Do not repeat it in a commit message. The rules now
  live in `[tool.ruff.lint]` in `pyproject.toml`, the tool version in
  `.ruff-version`, and the gate in the `lint` job of `.github/workflows/ci.yml`,
  which diffs `scripts/ruff-baseline.sh` output against `.ruff-baseline.txt`.
  Cite a run of that gate instead.
- **The lint gate is a ratchet, and it fails in both directions.** A NEW finding
  makes the diff non-empty; so does FIXING one without running
  `scripts/ruff-baseline.sh > .ruff-baseline.txt`. Fixing findings is welcome and
  is not a precondition for anything — the baseline is not an approval of them.
- A capability that is not committed is a capability no other clone or runner
  can use. The presence of a rule NAME in the tool is not evidence of the
  capability behind it.

## This repository

**Licence: MIT. This repository is clean room.** Facts yes, expression no. The
full rule is `The clean-room rule` above.

Language: Python.

Test:

    python -m pytest tests -q
