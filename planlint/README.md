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

# the citation form, against the clones its entries name
python3 -m planlint.cli --plan <plan.md> \
    --clone axiomantic/mcf5307=<path> --clone axiomantic/gearmulator=<path>
```

**`--clone` takes the repository name a citation WRITES**, so
`axiomantic/mcf5307=/path/to/mcf5307`. The `citations` lint reads the one clone
an entry names and never hunts a sha across several, which is how the two ways
a cross-clone scan passes for the wrong reason — a sha that resolves in NONE,
and a short sha that resolves in TWO — are removed rather than guarded against.
A repository no `--clone` names is reported UNDECIDED, per entry, and never
passed.

**The full-coverage invocation is `--plan <plan.md> --repo <repo> --private`.**
Omitting `--repo` does not trim the report by a line — it drops the `payload`
lint, which reads every committed file in the tree, thousands of them on a real
repository. An error count from a run with no `--repo` is therefore not
comparable with one from a run that had it. That is why the report enumerates a
lint it did not run, as `payload: SKIPPED — no --repo given`, and why the
verdict then reads `SELECTED LINTS CLEAN` and never `ALL LINTS CLEAN`.
`--private` is the right flag for a private repository: the boundary `payload`
guards is the PUBLIC one, so its findings do not apply and it reports clean over
the same file count.

**The notice covers the DEFAULT run only.** `--only` reports just the lints it
names and says nothing about the rest, because the caller's own command line is
the record of what they asked for. The silent narrowing this guards against is
the one a missing flag performs.

Each wrapper script migrates into a repository as a move, not a rewrite: the
wrapper and the `planlint/` package go together and no code changes.

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
| 2 | The invocation is wrong: an unknown lint, a missing plan, `payload` with no `--repo`, or `citations` with no `--clone`. |

**A lint that finds no input to examine exits non-zero.** `ctest -R` exits 0 when
its pattern matches no test. Nothing to check is never a pass, so every lint
carries a `no-input` guard that reports the count it examined.

Severity orders the report. It never excuses a finding from the exit code.

## The lints

| # | Lint | What it checks | Plan section |
|---|---|---|---|
| 1 | `graph` | Every `Depends:` edge, ranges expanded. Strongly connected components of size above one (Tarjan), self-loops, unknown identifiers, and **prose on a `Depends:` line that a parser would read as an edge**. | 7.6 assertions 2, 3 |
| 2 | `waves` | Every task's wave order is at or after the order of everything it depends on. A task the wave table places nowhere, and a wave entry no task block defines. | 7.6 assertion 5 |
| 3 | `tiers` | Every task states a tier. A T0 check is not gated on `NMG2_ARTIFACTS` and reads no fixture the register marks PRIVATE. A T0 task holding a higher-tier task in its dependency CLOSURE satisfies section 5.2 rule 7's admissibility predicate, which the lint DECIDES rather than reading from a roster. A `Depends:` range swallows no higher tier and no conditional task. | 1.3 rule 8, 5.2, 7.6 assertions 1, 4, 6 |
| 4 | `checks` | Both directions: every `-R` name is created by some `Files:` line, and every test file a `Files:` line creates is invoked by some `-R` or `pytest`. Plus `ctest` with no `--no-tests=error`, `--` argument forwarding, a `--target` nothing creates, a repository outside section 3.1's table, and a path two tasks claim with no owner. | 1.3 rules 9, 10; 7.4.2; 7.7 |
| 5 | `payload` | No Clavia-authored content reaches a public repository by ANY route: a `.gitmodules` entry, a `*.pch2` outside the synthesized corpus, a committed fixture above the 65,536-byte ceiling with no allow-listed register row, **or a workflow step that uploads or caches a path intersecting a render, a dump, a capture or a corpus**. | 3.2, 7.8, 22.4 |
| 6 | `counts` | Every claim the plan states about itself matches what the plan holds: the track rows, the total, the sum, the conditional-task count, and the cross-track edges inside one wave. **The cross-track set is DERIVED from the `Depends:` graph** and held against section 7.3's column AND section 7.4's table, each in both directions, and assertion 7's number is held against that derived set — a table is an operand and never the source. **Section 7.4.1's table is read as part of section 7.4's**, because the plan states in its own words that the edge it carries is one assertion 7 counts. **An arrow either site STATES is held against the graph in ANY wave**, because an arrow is a claim about a `Depends:` line and no wave excuses it; the reverse direction stays inside one wave, because section 7.3 lists a track's contract inputs once for the track and omits them per task in bulk. | 7.3, 7.4, 7.4.1, 7.6 assertions 7 and 13, 24.1, 24.4 |
| 7 | `implicit` | A task that writes into or reads from an artifact another task creates, with no `Depends:` edge. The candidate whose missing edge would **close a cycle** is reported under its own rule. | — |
| 8 | `registrar` | A task whose check runs `ctest -R <name>` has the task that CREATES the test source and the task that REGISTERS the directory inside its transitive dependency closure. **The registrar is the OWNER section 7.4.2 names, not every task that declares the list.** That section obliges each registering task to declare the list it edits, so reading every declarer as a creator rejected the very form the document requires. **A MARKED `Files:` entry creates nothing**, for the same reason one layer down: section 1.1.1 rule D says `<path>@<OWNER-ID>` is not a claim of ownership, so a second writer that marks its entry — the form section 7.6 assertion 8 requires — is not the task that creates the source, and reporting the owner for not reaching it punished the compliant spelling. **An UNMARKED second write is still a creation** and still has to be reachable. | 1.1.1 rule D, 7.4.2, 7.6 assertion 8, 7.7 clause 2, 7.7.1 |
| 9 | `closure` | A **symbol, build target, header or gated build option** one task must produce for another task to compile or link is inside the consuming task's transitive dependency closure. Reported in separate buckets: the violations the lint can assert, and the CANDIDATES a reader adjudicates. | — |
| 10 | `structure` | The markup the other lints parse. A task body carrying a backtick with no partner on its own line, a fenced block opened and never closed, **a completion marker written behind a lead-in**, which a census anchored at the start of the line reads as an absent marker rather than as an error, and **a table row whose unescaped `\|` count is not the one its own delimiter row declares**, which renders with the wrong number of cells so that a reader and a lint read the wrong text in the wrong column. That last rule decides a run of table rows that CONTAINS a delimiter row, against that row; **a run carrying none states no column count and is reported UNDECIDED under its own rule rather than skipped**, because a run the rule passed over and a run it found correct print the same result. **A parse failure is a finding, never a quiet degradation, and neither is a lint's own silence.** | 7.7, 24.6 |
| 11 | `anchors` | Every ANCHORED prose restatement of a figure the tool derives equals the derived value. The anchor is an HTML comment beside the written number, so the check reads the restatements a plan MARKS and never scans prose for numbers. It also reports the anchor count, a key it cannot compute, a token it cannot read, and a derived figure no anchor names at all. | 7.6 assertion 7 |
| 12 | `markers` | The UNION half of section 24.6's citation form: every path a task's `Files:` line declares is NAMED by some cited entry of that task's completion marker. Rules B, C and D of section 1.1.1 are expanded on both operands out of one expander. A marker that carries no entry at all is reported as UNDECIDED under its own rule rather than passed, because a silence there reads exactly like coverage. | 24.6 |
| 13 | `citations` | The REPOSITORY half of the same form, and section 24.6 states that the two are not one finding: every cited entry's sha actually touched the path that entry claims. One command per cited commit — `git show --format= --name-only <sha>` in the repository the entry NAMES — so it needs no build tree and no network. Needs `--clone`, and a run without one announces the lint as SKIPPED. Three states are not a verdict and each is reported: no clone for the named repository, a sha the clone does not resolve, and a MERGE commit, for which `--name-only` prints nothing. | 24.6 |
| 14 | `secondwrite` | Condition 10, tests 1 and 4, of section 7.4.2's second-writer rule. A marked `Files:` entry whose canonical path carries NO owner row is a marker whose own premise the document refutes (`second-write-no-owner-row`). A second writer whose owner row states no class sentence is refused (`second-write-outside-class`), as is one every track limb of the class excludes; where admission turns on the edit-kind half of the class — prose — the finding is `second-write-class-undecided`, never a pass. Tests 2, 3 and 5 of condition 10 are not implemented here and are reported by nothing. | 7.4.2, 7.6 assertion 8 |
| 15 | `removed` | A `Check:` predicate that names a mechanism the DEFAULT BUILD REMOVES. Release defines `NDEBUG` and `NDEBUG` removes every `assert()`, so a check whose verdict rests on an assertion firing passes against a tree in which the property was never written. The mechanism list is a **data table** — `mechanism`, `predicates`, `removed_by`, `kept_by`, `authority`, `not_the_mechanism`, `repositories` — that `run()` iterates and never a pattern in the rule body, because a roster amended once per case is a missing predicate. **`predicates` holds the TWO QUESTIONS the lint asks, each with its own rule id, its own severity and its own message fragment, and `run()` names none of the three.** The NOUN question, `check-predicate-removed-by-default-build`, reads every SPELLING a block reaches for, the call and the English nouns beside it, and **it is not narrowed**: row W3-405 refused that and row W3-408 restates the refusal, and the count against the live plan is **40**, which resembles no roster. The SHAPE question, `check-verdict-rests-on-an-assertion-not-firing`, reads the shape of the VERDICT — *"no assertion trips"*, *"without asserting"*, *"asserts no assertion"* — which is what §7.7's boxed RULE actually states, and against the live plan it returns **one** block, DSP-20, which is the block that rule names. It is an ADDITION beside the noun question and not a narrowing of it; a block that answers both badly is reported twice, which is two true statements about one block. What is excluded instead is named and reasoned: `not_the_mechanism` holds spans that carry the spelling and provably are NOT the mechanism — **a static assertion**, because `NDEBUG` does not remove `static_assert`, and **a numbered graph assertion**, because §7.6's assertions are sentences this tool checks and no build type deletes a sentence. `repositories` is the scope §7.7 gives the rule — *"binds each repository from its own transcript"* — resolved through §7.1's own track table, so a block is convicted only when EVERY repository its track writes into is one the row binds. A `~~`-struck span is masked before any pattern is applied, in both directions: a struck clause stops convicting and a struck sparing phrase stops excusing. `authority` states that measurement 8 is **OWED AND NOT TAKEN** rather than citing it as taken. **`kept_by` is THREE ROWS, one per legal form §7.7 gives a block, each with its own name and its own reason** — it names the build type that keeps the mechanism; or it converts the property to an OBSERVABLE the check reads in any build type; or it says in words that the property is unchecked in the default build and names the task that checks it. §7.7 adds that *"silence is not a fourth form"*. The lint shipped **form 1 alone** while citing the whole section as its authority, so it convicted the two blocks that took form 2 — **BRD-7**, which records nine bare `assert()`s replaced by a helper *"compiled in every build type"*, and **DSP-7**, whose live clause reads the registers back through *"an observable no build type deletes"*. A rule that convicts the blocks that did the right thing trains a reader to ignore it, and sparing is the direction a wrong lint fails in. **No form may reach `Release` or `NDEBUG`**, which are the settings that REMOVE the mechanism and whose appearance in a block is the DIAGNOSIS of the defect, and **form 2 requires a SURVIVAL word beside its phrase** because *"deleted in every build type that defines NDEBUG"* carries the same five words and states the opposite. Form 3 requires BOTH halves, and it names the task through the document's own identifier GRAMMAR rather than through a list of track prefixes. One unit is one task block's `Check:` BLOCK — the `Check:` line through the end of the task body. | 7.7 measurements 7 and 8; 7.7.1 condition 8; 24.6 rows W3-4, W3-18, W3-404, W3-405 |
| 16 | `rule9` | Section 1.3 rule 9 in BOTH of its clauses, which the `checks` lint answers only as far as the plan STATES a registration. **Half A is plan-internal**: no `Files:` line creates the `-R` name (`rule9a-name-not-created`), and neither the checking task nor any task that creates the named source declares the registration list it edits (`rule9a-no-registration-list`), which is what section 7.4.2's boxed RULE makes declarable. A registration list is recognised by the CLASS that section states — `tests_<track>.cmake`, `conformance_<track>.cmake`, and the `CMakeLists.txt` of a `test/`, `tests/` or `conformance/` directory — and never by a roster; the `@<OWNER-ID>` marker of section 1.1.1 rule D is split off before the path is read. **Half B reads the repository** and is the half that catches BRD-21, whose source shipped and whose `t0_board_surface` was registered nowhere: the name is registered by no `add_test(NAME <name> ...)` reachable in the tree (`rule9b-not-registered`). COMPLETE is read from the REPOSITORY and never from the plan, by two independent signals — the named test source is present, or `docs/check-targets.txt` declares the name. Scoping to complete tasks is not a softening: a half that reported every unwritten test would be red before any work began, and a lint red on day one is a lint an engineer turns off. A registration is resolved STATICALLY and the literal form is not the only one — a wrapper function or macro that registers its own first argument is RESOLVED rather than special-cased, because a grep for the literal form reports every wrapped name as unregistered, a false alarm the size of the real finding. **Half B runs only when `--source-repo` gives it a tree**, and the lint is not conditional, so a run without one reports half A and announces nothing — this is the one place in the report where a narrowing is not named, and the flag belongs in any invocation whose result is meant to cover rule 9. It reads the CMake files as written and needs no build directory. | 1.3 rule 9; 7.4.2 |
| 17 | `gate` | **The completion gate §7.6 never had.** Assertion 5 compares wave ORDER and never COMPLETION, so a Wave-3a task whose dependency sits in Wave 0 satisfies it whether or not the Wave-0 task was ever started, and enforcement and its absence produced the identical green. This lint reports a task carrying a live `DONE` marker while a task on its `Depends:` line carries none. **The predicate is the DEPENDENCY GRAPH and not the wave**, which is what §24.6 row W3-422's own acceptance clause asks for — *"a task in its transitive dependency closure"* — and what the pairs it names as proof are. **The closure is read at its EDGES, and that reports the same documents**: walk any path from a marked task into its closure and stop at the first unmarked node; the node before it is marked, so the direct edge into it is reported. What the edge form drops is the redundant restatement of a gap two hops down. A `**~~DONE` strike is not a marker: `document._scan_done_markers` reads the `**DONE` spelling, so a withdrawn marker arrives here as an absence and no second scanner states the rule twice. **TWO RULES, separated by what the DEPENDENCY declares about itself.** `done-marker-over-incomplete-dependency` is unfinished engineering work. `done-marker-over-a-dependency-this-plan-does-not-schedule` is a dependency §1.5 gives a tier SUBSTITUTE whose act is not this plan's to take — `OPERATOR`, `deferred`, `upstream` — each carrying §1.5's own reason; it is a WARNING and it is still REPORTED, because the statement is true and a silence here reads exactly like coverage. The discriminator is the substitute on the dependency's own header and never a roster of identifiers. **`THROWAWAY` is deliberately not in that table**: §1.5 gives a spike a check the operator runs against `extracted/`, so it is work this plan schedules — and the pairs W3-422 offers as its proof depend on spikes, so a table that excused `THROWAWAY` would silence its own evidence. A header carrying a §5.1 tier is scheduled work whatever else it says. | 7.6 assertion 5; 1.5; 24.6 row W3-422 |
| 18 | `provenance` | **The licence ruling, as far as a lint can reach it — which is not as far as the ruling goes.** `nmg2-tools` is MIT and some of what it implements was implemented first by somebody else under a copyleft licence. THREE RULES. `imported-copyleft-artifact` reports a copyleft SPDX identifier or a copyleft licence GRANT sitting in a file of this repository; a prose mention of a licence NAME is not a grant, which is why every provenance record this repository already carries names `GPL` and none of them trips it. `missing-provenance-record` reports a shipped module the record obligation reaches whose module docstring carries no record, and `incomplete-provenance-record` reports a record that carries the house heading and then omits an element of the form, so the heading alone cannot satisfy the check. **The obligation is a PREDICATE and not a roster**, because a roster amended once per case is a missing predicate: it is the UNION of two triggers read off the module itself — a function signature annotated `bytes`, `bytearray` or `memoryview`, and a named copyleft licence. A union is the right shape because each trigger only widens the population, so one can be added without any module losing an obligation it already had; and both are needed because `nmg2_tools/dsp56k_dis.py` decodes an instruction set out of `int` words and the first trigger never reaches it. **The house form is READ off the records that exist** — `lzo1x`, `container`, `dsp56k_dis`, `flashimage`, `pch2`, `pe`, `rsrc` — and held against them in the test file, so it is a checked fact and not a recalled one: a heading line reading `..., because the licence makes it matter`, a statement of this repository's own licence, and a statement that no line of another implementation is copied, transliterated or paraphrased. **Test code is examined by the artifact scan and exempt from the record obligation**; it is not a shipped implementation. This lint states the grant phrases it hunts, so it matches itself: a file carrying the sentinel `planlint-provenance-detector` is excluded from the text scan and the COUNT of such files is printed beside the examined count, because a silent exclusion and a clean scan read the same. **What it cannot do is row 30 below, and that row is the more important half of this one.** | the licence ruling; rows 30 and 31 below |

`structure` runs FIRST. Every lint below it reads a parsed document, so a
broken fence is the cause and everything else is the consequence.

### How the backtick scanner reads a fence — defect L-5

A fenced block opens with THREE backticks. The scanner used one regex,
`` `([^`]+)` ``, over a whole task body, so a fence swallowed its own body as
one span and left two backticks over. **Every pairing after that point was
inverted:** prose read as a quoted span, and every quoted name read as prose.
Everything below the first fence in a task body was invisible.

It was measured, not theorised. A warning count that falls as text is added is
the signature of a scanner going blind, and it reads as an improvement.

The rules that replace the regex both **widen** what is seen:

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

### What the anchor deliberately does not reach — lint 11

A figure the tool DERIVES may also be written out in prose, and until this lint
the prose was invisible: the derivation was right, the derived value was pinned
at both of its sites, and two separate sentences still restated a number the
graph had stopped holding — one said eleven and one said ten while the graph
held sixteen. A stale claim read exactly like a current one. Both were corrected
and both now carry an anchor.

The prose is reached through an ANCHOR:

```
... it is one of the <!-- derived: cross-track-edge-count -->sixteen edges
section 7.6 assertion 7 counts.
```

That is section 14.3's sentence, one of the two. It is a restatement because its
SUBJECT is the edge set assertion 7 counts, and not merely because it holds a
number.

The anchor is an HTML comment. Measured against `markdown-it-py` 4.2.0 in
CommonMark mode: with raw HTML enabled the anchor reaches the output as a
comment and the paragraph reads exactly as it would without it, and with raw
HTML disabled it is escaped and the reader sees it. The plan's renderer passes
raw HTML through. The checked token is the run of letters and digits
IMMEDIATELY after the closing `-->`, so one anchor marks exactly one figure and
the marking is decidable. English number words are read as well as digits, from
the bounded list `counts.WORDS`; a token outside it is REPORTED and never
skipped.

**The alternative was a scan for numbers, and it is rejected because it cannot
decide what it is looking at.** `W3` holds a digit and states no figure, and a
pattern cannot tell the two apart without reading the sentence. The same class
has been paid for in this project by an alternation that named four log levels
and excluded a fifth spelling, and by a `^### ` locator run against blocks whose
headings are bold lines. What such a scanner buys is COMPLETENESS, and
completeness is not what makes a check trustworthy — a confident wrong answer
is worse than a narrow right one.

**So the trade is completeness for decidability, and it is DECLARED rather than
hidden.** Three mechanisms declare it:

  * the lint reports how many anchors it examined, on a clean run as well as a
    red one, so an anchor set that silently shrinks is visible in the report;
  * an empty anchor set is a hard error through the `no-input` guard, so a lint
    that found nothing to check never reads as "all clear";
  * a derived key that NO anchor names is its own finding, so registering a new
    derived figure without anchoring its prose is loud.

**What it does not reach: an unanchored sentence.** A number typed into prose
with no anchor beside it is outside this lint entirely, and no rule reports it.
That is the residual, and it is the price of never reporting a false one.

**The counter-example: what an anchor must NOT be attached to.** A third
sentence was considered at the same pass and deliberately left alone. Section
7.4 opens with *"Fifteen cross-track edges exist inside or around what was one
wave, and five of them are header reads"*, and it is not a restatement of the
derived figure. Its subject is section 7.4's OWN table — 27 rows, 12 of which
name a header — and its predicate reads "inside **or around**" one wave, which
keeps the wave-crossing rows assertion 7's "crosses a track inside one wave"
excludes. **Anchoring it would have obliged the writer to type "Sixteen" there
to get a green run, and the lint would then hold a claim about a 27-row table
VERIFIED at the derived 16.** A false claim wearing a verified costume is worse
than the stale claim it replaces, and it is the harder one to find later. So the
sentence stays unanchored and its 15/5 stays stale, until it is deleted or a
second derived key measures the table itself. **Deciding which sentences are
restatements is the half of this lint no mechanism performs**, and getting it
wrong in this direction is worse than leaving a sentence outside the lint: an
unanchored stale sentence is only unchecked, while a wrongly anchored one is
reported clean.

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

**The routes below report CANDIDATES and never violations**, at WARNING and under
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
| `clean_plan.md` | None. The baseline every lint must report clean. It also carries, on purpose, the shapes a mutation needs: an abbreviated path and a canonical one that name one file, an anchored `-R` argument, a shell-quoted anchored argument, a directory owner row and a file owner row, an exported build target with a reachable consumer, a header with a reachable consumer, a qualified type name a check reads, a build option one task declares OFF and another turns ON, and an anchored restatement of the derived cross-track edge count. |
| `neg_graph_cycle.md` | Two tasks waiting on each other. |
| `neg_graph_self_loop.md` | A task naming itself. |
| `neg_graph_unknown_dep.md` | An undefined identifier, and a range running past the last task. |
| `neg_graph_prose_depends.md` | "Scheduled before BBB-1" on a `Depends:` line, and an identifier inside a clause. |
| `neg_wave_order.md` | A task before its dependency, a task in no wave, a wave entry with no task. |
| `neg_tier_purity.md` | A T0-to-T1 edge failing conjunct (b) of section 5.2 rule 7, a gated T0 check, a T0 read of a PRIVATE fixture, a header with no tier, a range swallowing a higher tier and a conditional. |
| `neg_check_commands.md` | An `-R` nothing creates, a missing `--no-tests=error`, `--` forwarding, a `--target` nothing creates, an unstated registration. |
| `neg_check_registration_outside_task.md` | The calibrated pair for section 1.3 rule 9's registration clause: the identical `add_test(NAME ...)` sentence written inside a task block (silent) and written only in a §24.6 defect-register row (reported). |
| `neg_check_orphan_test.md` | A test file created and never invoked, in C++ and in Python. |
| `neg_check_repos_and_paths.md` | A repository outside section 3.1, and a path two tasks claim with no owner. |
| `pos_check_multiline_transcript.md` | **No defect.** It proves the false positives do not occur: a multi-line check block, and a deliberate transcript counter-example. |
| `neg_anchors.md` | An anchored figure the graph no longer holds, an anchor marking a word that is no number, and an anchor naming a key the tool does not compute. The fourth rule — a derived key NO anchor names — cannot co-occur with these in one document, so it is asserted against documents built in the test. |
| `neg_counts.md` | A wrong track count, a wrong total, a wrong sum, a wrong conditional count, a wrong cross-track count, an in-wave cross-track edge section 7.3 omits, a section 7.3 row no `Depends:` line declares, and NO section 7.4 table at all. |
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
| `neg_structure_table_row_column_count.md` | A table row carrying a raw `\|` inside a cell, beside the escaped spelling that must stay silent, and a one-row table that states no column count at all. |
| `neg_marker_path_uncited.md` | A completion marker whose citation leaves one declared path out, beside a marker that covers every one of its own, a marker in the grammar that predates the citation form, and a task with no marker at all. |
| `pos_removed_mechanism.md` | **The blocks the removed-mechanism lint must report.** BRD-17, SCH-7, SCH-20 and SCH-28 are **RECONSTRUCTIONS and not transcripts** — the pre-repair wording exists in no revision this project holds, because the plan arrives from one import commit, `996c3dd`, which already carries the repaired text. DSP-7 is **VERBATIM** and is the case the `kept_by` exclusion is falsifiable through: it names `Release` and `NDEBUG` in the sentence that diagnoses its own defect. |
| `neg_removed_mechanism.md` | **The blocks the same lint must spare, and this half is VERBATIM**, because sparing is the direction a wrong lint fails in. SCH-8, whose sparing phrase sits BELOW its `Check:` line; SCH-10, whose sits on the line itself; SCH-28 at `996c3dd`, under its historical identifier; and TOOL-14's own `Check:` block, so the lint's self-consistency is a checked fact. |
| `pos_removed_exclusions.md` | **The paired half of every named exclusion the removed-mechanism lint carries, and every block here is SYNTHETIC.** Each one differs from its `neg_removed_exclusions.md` partner as narrowly as the reason allows — the strike markers removed, the word `static` removed, the assertion NUMBER removed, the `debug build` sentence struck, the track changed to one §7.1 places in the fork, the observable clause dropped, the unchecked-in-the-default-build declaration dropped with the task identifier KEPT — so that no exclusion is an `off` switch nothing drives. KEP-10 carries the predicate SHAPE and no assertion NOUN, so it is reported under the shape-keyed rule alone. |
| `neg_removed_exclusions.md` | **The blocks the same lint must spare, one per REASON a flagged span cannot be a defect of this class**: a `~~`-struck predicate, a static assertion, a citation of one of §7.6's numbered graph assertions, §7.7's form 1 as a live `debug build` sentence, a track §7.1 places in an unmeasured repository, a track that spans a bound and an unbound one, §7.7's **form 2** in BOTH wordings the live plan uses — BRD-7's *"compiled in every build type"* and DSP-7's *"an observable no build type deletes"* — §7.7's **form 3**, and a verdict-shape predicate under a live form 1 sentence. It carries a §7.1 track table of its own, which is where the repository scope is read from. |
| `neg_removed_empty_population.md` | No task block at all. `examined` is 0 and the result carries the `no-input` finding: nothing to check is never a pass. |
| `pos_gate_complete.md` | **No defect.** The SILENT half of the completion gate's calibrated pair: a marked task whose dependency carries a live marker. |
| `neg_gate_incomplete.md` | The REPORTED half. It is `pos_gate_complete.md` with two `~~` pairs added to the dependency's marker line and nothing else changed, so the strike alone separates a report from a silence. |
| `neg_gate_dispositions.md` | One marked dependant per §1.5 tier substitute a dependency can carry — `OPERATOR`, `deferred`, `upstream` and `THROWAWAY` — and a three-task chain whose tail is unmarked, so the edge above the gap is the one reported. |
| `neg_gate_unknown_substitute.md` | A §1.5 table naming a substitute the completion-gate lint states no disposition for. The document is the authority for the substitute SET and the lint for the VERDICT, so the set outrunning the verdicts is reported rather than resolved by falling through to the engineering-work rule. |
| `repo_public_bad/`, `repo_public_good/` | A repository tree with each breach route, and one with none. |
| `repo_provenance_bad/`, `repo_provenance_good/` | A repository tree carrying one of each provenance breach — an imported grant, an imported SPDX identifier beside a COMPLETE record, a module the binary trigger reaches with no record, a module the copyleft-name trigger reaches with no record, and a record that stops after the heading — and one with none. The good tree also carries the two SILENCES that keep the predicate from being universal: a module no trigger reaches, and test code annotated `bytes`. |

### Mutation check, per RULE

`tests/test_mutation.py` is the mutation check. It runs with the suite. It
breaks one thing in `clean_plan.md`, once for each rule, and asserts the exact
set of **rules** that go red.

The unit is the RULE and not the lint. An earlier revision asserted which LINT
went red, and a rule can be dead code with the suite fully green when the same
mutation trips another rule inside the same lint.

A rule that reached the inventory as a VARIABLE would hide from the meta-test, so
`closure.run` builds each breach as a `Finding` at the point where its rule is
known — the same reason `graph.build_edges` uses `dataclasses.replace`.

The suite now asserts:

1. **Each mutation reddens exactly the rules named beside it.** Disable any one
   rule in any lint, and at least one subtest fails. The failure names the rule.
2. **Every rule has a mutation.** The rule inventory is read from the lint
   SOURCE with `ast`, and not from a list kept by hand. Add a rule to a lint,
   and this file fails until a mutation covers the rule.
3. **No mutation expects a rule no lint emits.** A renamed rule fails the same
   test.

The `payload` lint reads a repository tree and not the plan. Its equivalent is
the pair of fixture trees `repo_public_good/` and `repo_public_bad/`.

`tests/test_suite_integrity.py` asserts properties of the suite itself. The
`if __name__ == "__main__"` guard is the LAST statement of every test module,
because a class below the guard is skipped when the file runs directly. Every
committed fixture also has a row in the table above.

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
| 2 | **Coverage is counted, never asserted.** | Every lint guards only `examined == 0`. A task with no command is invisible, not reported. |
| 3 | **A two-space indent on a task's fields.** | The indent erases `Files:`, `Design:`, `Depends:` and `Check:` together. The header still parses and the task still counts, and the defects inside it become invisible. |
| 4 | **A dual-tier header turns off every T0 purity rule.** | The purity rules read `task.tiers == {"T0"}`. A header that reads `— T0 and T1` is not that set, so the rules do not run. Section 5.2 rule 8 says the task is classified by its T0 half; the lint reads neither half. |
| 5 | **A check written as a `$ `-prefixed shell session.** | A transcript fence is excluded, and the exclusion has precedence over the `Check:` block that holds it. Two characters exempt a command from every command rule. |
| 6 | **A non-transcript fence between `Design:` and `Depends:`.** | Neither path reads it. `scoped_segments` excludes it as in-body, and the block text starts at `Check:`. |
| 7 | **Nothing outside the plan file is read.** | Every upstream citation, every hardware fact, every design reference and every tier justification is unasserted. |
| 8 | **The `-R` anchoring rule of section 7.7 is implemented nowhere.** | The anchors are stripped. No rule reports an argument that carries none. An unanchored argument that is also a prefix of a longer test sweeps tests outside its own closure. |
| 9 | **A marker word on a `Depends:` line makes a real edge vanish.** | A sentence that opens with a marker is skipped, and no finding is reported — not even `depends-prose`. |
| 10 | **The command vocabulary is a fixed list of program names.** | `g2TestConsole`, `nim`, `make` and `sh` are not commands. No rule applies to them, and they add nothing to the examined count. |
| 11 | **The `implicit` lint is deliberately blind to CODE artifacts, and lint 9 reads code artifacts out of PROSE.** | `implicit` reads data suffixes and directories, single-claimant only, literal substring only. Lint 9 covers the code half — a symbol, a build target, a header or a gated build option one task must produce for another to compile — but only where the plan's OWN WORDS name it. **What stays uncovered is stated below, and it is not small.** |
| 12 | **An unbounded dependency chain inside one wave.** | The wave rule compares `here < there`, so two tasks of equal order always pass. |
| 13 | **The `Design:` field is parsed and read by no lint.** | A dangling design reference is invisible. |
| 14 | **Table recognition is by exact header text and exact cell shape.** | Remove the bold from a milestone cell, and the row and its defects leave the scope in silence. The fixture register and the total row fail the same way. |
| 15 | **Shared-path detection is exact-string only.** | A glob and a file that name one artifact never collide. Any owner row that ends in `/` silences every finding beneath it. |
| 16 | **Test-file recognition is a naming convention over a fixed suffix list.** | A test file named otherwise is exempt from the reverse direction. |
| 17 | **A restatement of a derived figure that carries no anchor.** | Lint 11 reads anchored restatements only. An unanchored number in prose is outside it, deliberately: the scan that would reach it cannot tell the `3` of `W3` from a figure. The anchor count in the report is what keeps the residual visible. **The lint also cannot tell whether a sentence a human anchored is a restatement at all**; the counter-example under "What the anchor deliberately does not reach" is the near-miss where an anchor on the wrong sentence would have stamped a false claim VERIFIED. |
| 18 | **A cross-track graph edge that NEITHER section 7.3's column nor section 7.4's table states, where the two ends sit in different waves.** | Section 7.3 lists a track's contract inputs once for the TRACK and does not repeat them per task, so the column omits such edges in bulk and by design. A rule widened in that direction would report every one of them against a document obeying its own stated convention, and a rule that fires on correct input trains a reader to ignore it. **The other direction IS asserted in every wave**: an arrow either site STATES is a claim about a `Depends:` line, and it is held against the graph whatever wave its ends sit in. So the tool now says "what these tables state is true" and still does not say "these tables are complete". |
| 19 | **Conjunct (c) of section 5.2 rule 7 is decided by nothing, and conjunct (b) only for the paths a `Check:` line NAMES.** | Nothing in the plan marks, per path, which of a T1 task's outputs its gated half produces, so (c) is not decided at all. (b) is decided by joining a named path to section 7.8's register and section 3.1's table, so a path the check reads without naming, and a path the register omits, are both read as UNDECIDED and neither is reported. An admitted edge has been shown to satisfy (a), and (b) for the paths it names. Only an execution with `NMG2_ARTIFACTS` unset settles the rest. |
| 20 | **A `Files:` entry whose only claimant is MARKED.** | Rule D says a marked entry creates nothing, so a file no unmarked entry names has no creator at all. `registrar-unknown` is what reports that, and it reports it as a missing creator rather than as an unreachable one. Where a name resolves through a marked entry only, read the finding as "nobody declares that they create this", not as a closure failure. |
| 21 | **Whether a completion marker's task actually PASSES its `Check:`.** | Section 24.6 states this in its own words and the citation lints do not weaken it. A marker answers "was this built?" and leaves "does it work?" to the task's own check. No pass that wrote one of these citations ran a `Check:` command, configured a build tree or compiled anything. A clean `markers` and `citations` run is evidence about coverage and never about correctness. |
| 22 | **Whether a cited commit CREATED a path, or was written FOR the task.** | `git show --format= --name-only` says the commit touched the path. A one-character edit satisfies it exactly as a creation does. A commit subject naming the task is a separate and stronger claim that neither rule requires, which is the Tier-B class section 24.6 row W3-39 carries. |
| 23 | **Whether a citation's entries are the WHOLE of a task's work.** | The union rule reads one direction: every declared path is named by some entry. A commit that touched no declared path is invisible to it, which is why the commit COUNT stays on the marker beside the entries. |
| 24 | **The coverage of a marker written before the citation form.** | Such a marker assigns no path to any commit, so the naming question has no operand. This is REPORTED as `done-marker-citation-not-in-form` rather than passed — most of the plan's markers are in that state — but the rule decides nothing about whether their coverage holds. |
| 25 | **A `Files:` entry that is a GLOB, a build target, or a repository name.** | `markers.is_comparable_path` excludes all three from the union compare, and states why at the branch: a glob names a SET that no entry names literally, and `nmg2-tools` or `dsp56300` names a repository that no commit can touch. Section 24.6 asks for such an entry to be named in a `NOT PATHS:` clause, which is PROSE; reading the entry is what keeps the exclusion out of a sentence. On the `citations` side a glob IS decided, by matching any file the commit touched. |
| 26 | **A cited sha the named clone does not resolve, a MERGE commit, and a machine that could not run `git` at all.** | All three are reported as `done-marker-citation-undecided` and none is a verdict. A clone may be behind or on another remote, so an unresolvable sha is a fact about this machine. `--name-only` prints nothing for a merge, so "touched nothing" and "is a merge" are the same output and the parents are asked for separately. A missing `git`, or a clone that does not answer inside the timeout, arrives as a finding rather than as a traceback, because a traceback out of one lint takes the whole report's verdict line with it. |
| 27 | **A table with no delimiter row.** | `structure.column_norm` takes the norm from the delimiter row, because that is the row Markdown itself fixes the column count at. A table carrying none — a one-row continuation is the plan's case — states no column count and is not decided. **It is REPORTED as `table-column-count-undecided` rather than skipped**, so the class stays visible; what stays uncovered is the cell count of the rows inside such a run, which nothing here supplies. |
| 28 | **A table drawn inside a fenced block, and ASCII art that resembles one.** | `structure.table_blocks` excludes every fenced line, so a fenced run is neither decided by `table-row-column-count` nor reported by `table-column-count-undecided` — it is outside the rule in both directions, deliberately, because a fence is a quotation and its contents are never rendered as a table. Section 7.2's wave diagram is the case that matters: a row of pipes drawn as tree connectors has the exact shape of a delimiter row, and the lines below it have the shape of short rows. A scan that read fenced lines reported three such lines of that diagram as broken table rows; they are not table rows at all. |
| 29 | **Whether a class limb ADMITS a writer whose track it names.** The lint decides only the track conjunct and the absence of a class. "Adds a CONDITION to step 2" is prose about an edit, so a writer inside the class's track but outside the reader's judgement arrives as `second-write-class-undecided`, at WARNING, and stays there until an operator rules. A row that names no owner id this tool can resolve is treated as naming no owner for test-4 purposes while `owner_of` answers `None`. |
| 30 | **That anybody READ a copyleft source.** | This is the residual that matters most, because lint 18 is named for provenance and a reader may take a clean run for a clean-room guarantee. It is not one. Contamination leaves no trace in the output: a transliterated decoder and an independently derived one produce the same bytes, the same tests and the same diff, so no scan over this repository can separate them. That is precisely why the written RECORD is the control and not a formality — the result cannot distinguish the two histories and only the account of how it was obtained can. What the lint checks is that the control EXISTS, never that it worked. |
| 31 | **Whether a record is TRUE, and whether the obligation reached every module it should.** | The record rules read FORM. A complete, well-formed and false record passes, and a reviewer is the only thing that catches it. And the obligation reaches a module only through the two triggers: a module that restates an outside party's format while touching no `bytes` and naming no copyleft licence is asked for nothing. That gap is real, and the union shape is what lets a third trigger close part of it later without any module losing an obligation it already had. |

### What the closure heuristic cannot see

Class 11 above is now half-covered. This is the other half, and a clean lint 9
run is evidence about the plan's WORDS and never about its code.

| # | The closure lint cannot see this | Why |
|---|---|---|
| 11a | **A requirement the plan never writes down.** | `requires` is read from prose. A task that needs `Scheduler::Config` and never names it carries no signal at all, and the lint has nothing to fail on. This is the largest remaining hole and no wording change closes it. |
| 11b | **A producer the plan never names either.** | A name with no producer is DROPPED in silence — it is how `hardwareLib` and every other upstream name stay quiet. So a name both sides leave unattributed is invisible twice. |
| 11c | **An unqualified name.** | `stateSize` resolves to a candidate and never to a violation, because two tasks can each declare one. A real defect on a bare name arrives at WARNING, in the bucket a reader may skim. |
| 11d | **Anything outside a backticked span.** | A symbol written in plain prose is not a span, and no rule reads it. |
| 11e | **A verb the list does not carry.** | `wraps`, `feeds`, `drives` and `owns` are not among the consumer or producer verbs. |
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
- No network and no GitHub. Every lint but one reads files and reports.
- **`citations` is the one exception, and it is stated here rather than left to
  be discovered.** It runs `git rev-list` and `git show` — both read-only, both
  under `git -C`, so neither writes and neither touches a working tree — and it
  runs them only for the clones a `--clone` argument supplies. Section 24.6's
  citation form is a claim about a repository's history, and no reading of the
  document alone can decide it. Every OTHER lint still runs no program at all,
  which is why the exception belongs to one module and not to the package.
