# planlint — executable lints for the NMG2 implementation plan

Python 3, standard library only. No dependencies and no network.

The plan states most of these rules about itself already. These tools make the
rules executable, so that an edit cannot break one in silence.

## How to run

```
cd tools/planlint

# every document lint
python3 -m planlint.cli --plan <plan.md>

# one lint
python3 -m planlint.cli --plan <plan.md> --only implicit

# the artifact boundary, against a repository tree
python3 -m planlint.cli --plan <plan.md> --repo <repository-path>
python3 -m planlint.cli --plan <plan.md> --repo <path> --private
```

Three wrapper scripts carry the names the plan gives them. Each migrates into a
repository as a move, not a rewrite: the wrapper and the `planlint/` package go
together and no code changes.

| Script | What it runs | Migrates to |
|---|---|---|
| `./plan_lint.py <plan.md>` | `checks` and `registrar` | `nmg2_tools/plan_lint.py` (REPO-14) |
| `./payload_lint.py <plan.md> <repo> [--private]` | `payload` | `nmg2_tools/payload_lint.py` (REPO-14, REPO-11) |
| `./assert_section_7_6.py <plan.md>` | `graph`, `waves`, `tiers`, `counts`, `implicit`, `closure` | the section 7.6 assertion script |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every selected lint ran and reported nothing. |
| 1 | A lint reported a finding, **or a lint found no input to examine**. |
| 2 | The invocation is wrong: an unknown lint, a missing plan, or `payload` with no `--repo`. |

**A lint that finds no input to examine exits non-zero.** `ctest -R` exits 0 when
its pattern matches no test, and that measured behaviour cost this project about
a hundred meaningless checks. Nothing to check is never a pass, so every lint
carries a `no-input` guard that reports the count it examined.

Severity orders the report. It never excuses a finding from the exit code.

## The lints

| # | Lint | What it checks | Plan section |
|---|---|---|---|
| 1 | `graph` | Every `Depends:` edge, ranges expanded. Strongly connected components of size above one (Tarjan), self-loops, unknown identifiers, and **prose on a `Depends:` line that a parser would read as an edge**. | 7.6 assertions 2, 3 |
| 2 | `waves` | Every task's wave order is at or after the order of everything it depends on. A task the wave table places nowhere, and a wave entry no task block defines. | 7.6 assertion 5 |
| 3 | `tiers` | Every task states a tier. A T0 check is not gated on `NMG2_ARTIFACTS` and reads no fixture the register marks PRIVATE. A T0 task waits on no T1 or T2 task outside the three named edges. A `Depends:` range swallows no higher tier and no conditional task. | 1.3 rule 8, 5.2, 7.6 assertions 1, 4, 6 |
| 4 | `checks` | Both directions: every `-R` name is created by some `Files:` line, and every test file a `Files:` line creates is invoked by some `-R` or `pytest`. Plus `ctest` with no `--no-tests=error`, `--` argument forwarding, a `--target` nothing creates, a repository outside section 3.1's table, and a path two tasks claim with no owner. | 1.3 rules 9, 10; 7.4.2; 7.7 |
| 5 | `payload` | No Clavia-authored content reaches a public repository by ANY route: a `.gitmodules` entry, a `*.pch2` outside the synthesized corpus, a committed fixture above the 65,536-byte ceiling with no allow-listed register row, **or a workflow step that uploads or caches a path intersecting a render, a dump, a capture or a corpus**. | 3.2, 7.8, 22.4 |
| 6 | `counts` | Every count the plan states about itself matches its own rows: the track rows, the total, the sum, the conditional-task count, and the number of cross-track edges inside one wave. | 7.3, 7.6 assertion 7, 24.1, 24.4 |
| 7 | `implicit` | A task that writes into or reads from an artifact another task creates, with no `Depends:` edge. The candidate whose missing edge would **close a cycle** is reported under its own rule. | — |
| 8 | `registrar` | A task whose check runs `ctest -R <name>` has the task that CREATES the test source and the task that REGISTERS the directory inside its transitive dependency closure. **The registrar is the OWNER section 7.4.2 names, not every task that declares the list.** That section obliges each registering task to declare the list it edits, so reading every declarer as a creator rejected the very form the document requires. | 7.4.2, 7.7 clause 2, 7.7.1 |
| 9 | `closure` | A **symbol, build target, header or gated build option** one task must produce for another task to compile or link is inside the consuming task's transitive dependency closure. Reported in two buckets: the violations the lint can assert, and the CANDIDATES a reader adjudicates. | — |
| 10 | `structure` | The markup the other nine lints parse. A task body carrying a backtick with no partner on its own line, and a fenced block opened and never closed. **A parse failure is a finding, never a quiet degradation.** | 7.7 |

`structure` runs FIRST. Every lint below it reads a parsed document, so a
broken fence is the cause and everything else is the consequence.

### How the backtick scanner reads a fence — defect L-5

A fenced block opens with THREE backticks. The scanner used one regex,
`` `([^`]+)` ``, over a whole task body, so a fence swallowed its own body as
one span and left two backticks over. **Every pairing after that point was
inverted:** prose read as a quoted span, and every quoted name read as prose.
Everything below the first fence in a task body was invisible.

It was measured, not theorised. Adding transcripts to five task bodies of the
real plan moved the warning count from **169 to 166** — DOWN, while three real
`symbol-closure-candidate` findings went silent. A count that falls as text is
added is the signature of a scanner going blind, and it reads as an improvement.
Two task bodies, `SCH-12` and `PLG-10`, each held a qualified name and reported
zero qualified spans.

Two rules replace the regex, and both **widen** what is seen:

1. **A fence is a REGION, not a run of inline spans.** It yields no backticked
   name, because a backtick inside a fence is a literal character and delimits
   nothing. The region is masked whole, so a verb printed inside a transcript is
   no more a consumer verb than one inside backticks. Section 7.7 already treats
   a fence as its own scope unit: `scoped_segments` hands the non-transcript
   ones to the check lint whole and holds the `$ ` transcripts back as records
   of a measurement. Reading a transcript's printed output as a run of symbol
   names would attribute a producer to whatever a tool happened to print.
2. **An inline span never crosses a LINE BREAK, and an unmatched backtick is
   literal text.** That is CommonMark's own reading. It is what stops one stray
   backtick from swallowing the remainder of a body — the same defect in a
   smaller shape. `sentences()` already refuses to cross a line for this reason.

An UNTERMINATED fence is deliberately NOT a region. Letting it run to the end of
the text would hide every task below it, which is the failure being repaired.
It stays visible, and `structure` reports it under `unclosed-fence`.

The scanner is `planlint.document.inline_code_spans`. `closure`, `checks` and
the `Files:` and table readers of `document` all read through it, so no consumer
carries a second, private notion of what a quoted span is.

### How the check lint reads the document

Section 7.7 states the scope, and the scope is part of the specification:

> `plan_lint.py` reads three things: every `Check:` BLOCK, every command in a
> milestone table row, and every fenced block whose first line does NOT begin
> with `$ `. It reads nothing else.

Both halves of the block rule are load-bearing and the parser implements both:

- A `Check:` BLOCK ends at the next task header, the next Markdown heading, or
  the end of the document. **A line-scoped parser misses CPU-4, TOOL-10,
  PROTO-11 and INT-2**, whose checks span several lines or a table, and then
  reports their tests as created and never invoked.
- **A fenced block opening with `$ ` is a transcript and is excluded even inside
  a `Check:` block, and that exclusion has precedence.** CPU-5 quotes a
  defective command on purpose. A lint without this rule fails on the
  counter-example the plan prints to teach the rule.

### What lint 4 does NOT assert

Section 7.7 condition 2 reads registered test names from `ctest -N` against a
real build tree. No build tree exists yet, so this tool reads the document
instead and reports `r-name-not-registered` as a **WARNING**: it says the plan
states no `add_test(NAME ...)` for the name, which is a fact about the plan and
not about a build. Lint 8 asserts the reachability half, which the document does
answer.

### How the closure lint reads "requires" and "produces"

Lint 9 is the only lint here whose INPUT is prose rather than a stated field, so
its two directions are written out. It prefers RECALL: a missed violation costs
a wave, and a false positive costs a reader a minute.

**A name is attributed to a producer** by the `targets` clause of a `Files:`
line; by a name after the word `library` or `target`; by a producer verb
(`exports`, `declares`, `defines`, `adds`, `creates`, `introduces`, `produces`)
with the name after it; by the phrase `` `X` … which CPU-1 exports `` anywhere
in the document; and by the file convention — `Scheduler::Config` is produced by
every task whose `Files:` line creates `scheduler.h` or `scheduler.cpp`.

**A name is read as consumed** by a consumer verb (`links`, `reads`, `calls`,
`uses`, `includes`, `compares`, `constructs`, `forwards to`, `takes the address
of`) with the names after it; by `#include "x.h"`; by a qualified name inside
the `Check:` BLOCK with no verb in front of it; and by the library prefix of a
C symbol, which is how `mcf5307_exec` reaches the task that exports `mcf5307`.

**The two sides are tuned in opposite directions, on purpose.** A producer verb
reaches at most two backticked names, because a WRONG producer sends a reader to
the wrong task. A consumer verb reaches every name after it until a span that is
not symbol-shaped, because a WRONG consumer resolves to no producer and is
dropped in silence.

**Three routes report CANDIDATES and never violations**, at WARNING and under
`symbol-closure-candidate`:

| The route | Why it is not an assertion |
|---|---|
| The sentence carries a hedge — `does not`, `cannot`, `never`, `rather than`, `behind an option`, `the previous revision`. | The sentence may describe what the task does NOT do. |
| The check names a qualified type with no verb in front of it. | A check that names a type must compile against it, but the lint is guessing about the relation. |
| The name is UNQUALIFIED and resolves through the producer map. | `stateSize` is a method of the `Board` and a method of the DSP state, and both tasks declare one. The bare spelling names neither. A name that is both a build target and a repository — `mcf5307` — is ambiguous the same way. |

Section 7.7.1 condition 8 — "a check that runs no test runner must name the
mechanism that lets it fail" — is not implemented. It needs a judgement about
whether prose names a mechanism, and a mechanical version of it would report the
whole spike, operator and repository classes as findings. It stays a human read.

## Tests

```
python3 -m unittest discover -s tests -t .
```

Every lint has a **negative fixture**: a small synthetic plan fragment carrying
the exact defect, committed beside the test, with a test asserting that the lint
reports it. A lint with no negative fixture is not done.

| Fixture | The defect it carries |
|---|---|
| `clean_plan.md` | None. The baseline every lint must report clean. It also carries, on purpose, the shapes a mutation needs: an abbreviated path and a canonical one that name one file, an anchored `-R` argument, a shell-quoted anchored argument, a directory owner row and a file owner row, an exported build target with a reachable consumer, a header with a reachable consumer, a qualified type name a check reads, and a build option one task declares OFF and another turns ON. |
| `neg_graph_cycle.md` | Two tasks waiting on each other. |
| `neg_graph_self_loop.md` | A task naming itself. |
| `neg_graph_unknown_dep.md` | An undefined identifier, and a range running past the last task. |
| `neg_graph_prose_depends.md` | "Scheduled before BBB-1" on a `Depends:` line, and an identifier inside a clause. |
| `neg_wave_order.md` | A task before its dependency, a task in no wave, a wave entry with no task. |
| `neg_tier_purity.md` | A T0 task on a T1 task, a gated T0 check, a T0 read of a PRIVATE fixture, a header with no tier, a range swallowing a higher tier and a conditional. |
| `neg_check_commands.md` | An `-R` nothing creates, a missing `--no-tests=error`, `--` forwarding, a `--target` nothing creates, an unstated registration. |
| `neg_check_orphan_test.md` | A test file created and never invoked, in C++ and in Python. |
| `neg_check_repos_and_paths.md` | A repository outside section 3.1, and a path two tasks claim with no owner. |
| `pos_check_multiline_transcript.md` | **No defect.** It proves the two false positives do not occur: a multi-line check block, and a deliberate transcript counter-example. |
| `neg_counts.md` | A wrong track count, a wrong total, a wrong sum, a wrong conditional count, a wrong cross-track count. |
| `neg_implicit_dependency.md` | An undeclared consumer of a created directory, and the undeclared edge that would close a cycle. |
| `neg_registrar_unreachable.md` | A registrar and a creator outside the depending task's closure. |
| `neg_path_abbreviation.md` | The two spellings of one file: an abbreviated `Files:` entry and a canonical one, colliding on a shared path and on a registrar directory. |
| `neg_check_marked_second_write.md` | The ownership marker of section 1.1.1 rule D: a bare collision with no owner row that must stay red, a bare collision with an owner row, a marked entry with an owner row, and a marked entry with none. |
| `neg_check_empty_r_argument.md` | `-R ^$`, which strips to the empty name. |
| `neg_closure_header_and_candidate.md` | An `#include` of a header outside the closure, a hedged consumption, and a control task that declares the producer and must not be reported. |
| `neg_hist_brd0_target_link.md` | **Historical defect 1, pre-repair.** BRD-0 links `mcf5307::mcf5307`, which CPU-1 exports, with a closure of `{BRD-0, REPO-3, REPO-12}`. |
| `neg_hist_repo9_type_name.md` | **Historical defect 2, pre-repair.** REPO-9's gate reads `Scheduler::Config`, and neither task that writes `scheduler.h` or `scheduler.cpp` is in its closure. |
| `neg_hist_brd21_gated_link.md` | **Historical defect 3, pre-repair.** BRD-21 calls `mcf5307_exec` behind an option BRD-23 turns ON, and does not declare BRD-23. Its producer CPU-1 IS reachable, so the producer rule stays silent and the option rule fires. |
| `neg_structure_unmatched_backtick.md` | A task body carrying a backtick with no partner on its own line. |
| `neg_structure_unclosed_fence.md` | A fenced block opened and never closed, outside every task body. |
| `repo_public_bad/`, `repo_public_good/` | A repository tree with each breach route, and one with none. |

### Mutation check, per RULE

`tests/test_mutation.py` is the mutation check. It runs with the suite. It
breaks one thing in `clean_plan.md`, once for each rule, and asserts the exact
set of **rules** that go red.

The unit is the RULE and not the lint. An earlier revision asserted which LINT
went red. That revision was measured, and two whole `counts` rules could be dead
code with the suite fully green, because the same mutation tripped a third rule
in the same lint. The 14 mutations of that revision triggered 16 of the 31
rules. Fifteen rules had no mutation, and the fifteen included
`registrar-outside-closure` and `shared-path-without-owner`.

The nine document lints emit 38 rules and every one carries a mutation. A rule
that reached the inventory as a VARIABLE would hide from the meta-test, so
`closure.run` builds each breach as a `Finding` at the point where its rule is
known — the same reason `graph.build_edges` uses `dataclasses.replace`.

The suite now asserts three properties:

1. **Each mutation reddens exactly the rules named beside it.** Disable any one
   rule in any lint, and at least one subtest fails. The failure names the rule.
2. **Every rule has a mutation.** The rule inventory is read from the lint
   SOURCE with `ast`, and not from a list kept by hand. Add a rule to a lint,
   and this file fails until a mutation covers the rule.
3. **No mutation expects a rule no lint emits.** A renamed rule fails the same
   test.

The `payload` lint reads a repository tree and not the plan. Its equivalent is
the pair of fixture trees `repo_public_good/` and `repo_public_bad/`.

`tests/test_suite_integrity.py` asserts four properties of the suite itself. The
`if __name__ == "__main__"` guard is the LAST statement of every test module,
because a class below the guard is skipped when the file runs directly. Thirteen
tests were in that position, and they were the tests that pin the path
expansion. Every committed fixture also has a row in the table above.

The two other properties close a defect this file once carried itself.

4. **No collected test returns a value.** A test that returns in place of an
   assertion verifies nothing. `pytest` collects it, prints
   `PytestReturnNotNoneWarning`, and passes it. `unittest` does not collect a
   module-level one at all. Neither runner fails, so the AST is read instead.
5. **Both runners collect the same tests.** `pytest` collects a module-level
   `test*` function and `unittest` does not, thus a helper with a `test_`
   prefix makes the two counts differ. The scan is held against the set the
   `unittest` loader returns, so a test that only one runner runs is reported.

To run one module by itself, put the package root on the path:
`PYTHONPATH=. python3 tests/test_checks.py`. Without it the module cannot import
`tests.support`.

## What a green run does not prove

Every class below was demonstrated. A real defect went into a copy of
`clean_plan.md`, the full command line stayed green, and a control copy with the
same defect in canonical form went red.

**Read this list before you use a clean run as evidence.** A clean run is a good
signal. It is not a gate.

| # | The lints cannot see this | Why |
|---|---|---|
| 1 | **A registrar that does not exist at all, where section 7.4.2 names no owner for the list.** | `registrars_of()` returns an empty list when the document states no owner for the directory's `CMakeLists.txt` AND no task declares it. An empty list gives no finding. Delete the one task that creates such a test directory's `CMakeLists.txt`, and the lint reports clean. **Where section 7.4.2 DOES name an owner the class is closed**: the owner row states the registrar, so the lint keeps asking for it even when no `Files:` line carries the path. |
| 2 | **Coverage is counted, never asserted.** | Every lint guards only `examined == 0`. Forty of 209 task blocks give zero commands, and the report still says how many commands it examined. A task with no command is invisible, not reported. |
| 3 | **A two-space indent on a task's fields.** | The indent erases `Files:`, `Design:`, `Depends:` and `Check:` together. The header still parses and the task still counts. Four real defects in one task became invisible. |
| 4 | **A dual-tier header turns off every T0 purity rule.** | Three rules read `task.tiers == {"T0"}`. A header that reads `— T0 and T1` is not that set, so the rules do not run. Section 5.2 rule 8 says the task is classified by its T0 half; the lint reads neither half. |
| 5 | **A check written as a `$ `-prefixed shell session.** | A transcript fence is excluded, and the exclusion has precedence over the `Check:` block that holds it. Two characters exempt a command from every command rule. |
| 6 | **A non-transcript fence between `Design:` and `Depends:`.** | Neither path reads it. `scoped_segments` excludes it as in-body, and the block text starts at `Check:`. |
| 7 | **Nothing outside the plan file is read.** | Every upstream citation, every hardware fact, every design reference and every tier justification is unasserted. |
| 8 | **The `-R` anchoring rule of section 7.7 is implemented nowhere.** | The anchors are stripped. No rule reports an argument that carries none. An unanchored argument that is also a prefix of a longer test sweeps tests outside its own closure. |
| 9 | **A marker word on a `Depends:` line makes a real edge vanish.** | A sentence that opens with one of six markers is skipped, and no finding is reported — not even `depends-prose`. |
| 10 | **The command vocabulary is seven program names.** | `g2TestConsole`, `nim`, `make` and `sh` are not commands. No rule applies to them, and they add nothing to the examined count. |
| 11 | **The `implicit` lint is deliberately blind to CODE artifacts, and lint 9 reads code artifacts out of PROSE.** | `implicit` reads nine data suffixes and directories, single-claimant only, literal substring only. Lint 9 covers the code half — a symbol, a build target, a header or a gated build option one task must produce for another to compile — but only where the plan's OWN WORDS name it. The three defects this class produced were measured back into the real plan and all three redden. **What stays uncovered is stated below, and it is not small.** |
| 12 | **An unbounded dependency chain inside one wave.** | The wave rule compares `here < there`, so two tasks of equal order always pass. |
| 13 | **The `Design:` field is parsed and read by no lint.** | A dangling design reference is invisible. |
| 14 | **Table recognition is by exact header text and exact cell shape.** | Remove the bold from a milestone cell, and the row and its defects leave the scope in silence. The fixture register and the total row fail the same way. |
| 15 | **Shared-path detection is exact-string only.** | A glob and a file that name one artifact never collide. Any owner row that ends in `/` silences every finding beneath it. |
| 16 | **Test-file recognition is a naming convention over five suffixes.** | A test file named otherwise is exempt from the reverse direction. |

### What the closure heuristic cannot see

Class 11 above is now half-covered. This is the other half, and a clean lint 9
run is evidence about the plan's WORDS and never about its code.

| # | The closure lint cannot see this | Why |
|---|---|---|
| 11a | **A requirement the plan never writes down.** | `requires` is read from prose. A task that needs `Scheduler::Config` and never names it carries no signal at all, and the lint has nothing to fail on. This is the largest remaining hole and no wording change closes it. |
| 11b | **A producer the plan never names either.** | A name with no producer is DROPPED in silence — it is how `hardwareLib` and every other upstream name stay quiet. So a name both sides leave unattributed is invisible twice. |
| 11c | **An unqualified name.** | `stateSize` resolves to a candidate and never to a violation, because two tasks can each declare one. A real defect on a bare name arrives at WARNING, in the bucket a reader may skim. |
| 11d | **Anything outside a backticked span.** | A symbol written in plain prose is not a span, and no rule reads it. |
| 11e | **A verb the list does not carry.** | Nine consumer verbs and seven producer verbs. `wraps`, `feeds`, `drives` and `owns` are not among them. |
| 11f | **A qualified name whose head matches no file.** | `Config::testOverride` has no `config.h`, so it resolves to nothing. The file convention is the only route for a type, and a type declared in a differently-named header is outside it. |
| 11g | **A build option that no task turns ON.** | The option rule fires only when an enabler EXISTS and is unreachable. An option declared OFF and never turned on is a different defect, and this lint reports it nowhere. |
| 11h | **Ordering INSIDE one task.** | The unit is the task. A file this task writes late and reads early is not a closure question. |
| 11i | **Whether a producer really produces the thing.** | `declares` in front of a name is taken at its word. A sentence that says a task declares something it does not is believed. |

**What no lint can detect at all.** A check that passes by construction. A check
that asserts nothing falsifiable. A test whose name suggests a behaviour it does
not test. A task whose body contradicts its own check. A definition of done that
nobody can measure. These classes need a human reader.

## Constraints this tool obeys

- Nothing under `extracted/` is read or written.
- `reference/{dsp56300,gearmulator}` are read-only clones; this tool does not
  touch them.
- No network, no git, no GitHub. The tools read files and report.
